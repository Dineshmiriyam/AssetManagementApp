"""Assets page — inventory list, filters, bulk operations."""

from datetime import datetime, date

import pandas as pd
import streamlit as st

from config.constants import (
    ASSET_STATUSES, SLA_CONFIG, STATUS_COLORS, STATUS_DISPLAY_NAMES,
    ALLOWED_TRANSITIONS, BILLING_CONFIG,
)
from config.permissions import (
    check_page_access, render_access_denied, validate_action,
    can_perform_lifecycle_action,
)
from services.sla_service import calculate_sla_status
from services.billing_service import get_asset_billing_status
from services.asset_service import update_asset_status, validate_state_transition, create_assignment_record
from services.audit_service import log_activity_event
from components.empty_states import render_empty_state
from components.feedback import (
    render_error_state, render_billing_status_badge,
    render_inline_error, render_inline_warning,
)
from core.data import (
    safe_rerun, clear_cache, get_table,
    paginate_dataframe, render_page_navigation,
)
from core.errors import log_error
from database.db import get_activity_log
from views.context import AppContext


def _build_timeline_events(serial, asset_id, assignments_df, issues_df, repairs_df, limit=50):
    """Merge 4 data sources into unified timeline events sorted by date DESC."""
    events = []

    # 1. Assignments
    if not assignments_df.empty and "Serial Number" in assignments_df.columns:
        for _, row in assignments_df[assignments_df["Serial Number"] == serial].iterrows():
            dt = pd.to_datetime(row.get("Shipment Date"), errors="coerce")
            if pd.notna(dt):
                events.append({"type": "assignment", "date": dt, "data": row.to_dict()})

    # 2. Issues (column name varies)
    if not issues_df.empty:
        serial_col = next(
            (c for c in ["Serial Number", "Asset Serial", "Asset_Serial"] if c in issues_df.columns),
            None,
        )
        if serial_col:
            for _, row in issues_df[issues_df[serial_col] == serial].iterrows():
                dt = pd.to_datetime(row.get("Reported Date"), errors="coerce")
                if pd.notna(dt):
                    events.append({"type": "issue", "date": dt, "data": row.to_dict()})

    # 3. Repairs
    if not repairs_df.empty and "Serial Number" in repairs_df.columns:
        for _, row in repairs_df[repairs_df["Serial Number"] == serial].iterrows():
            dt = pd.to_datetime(row.get("Sent Date"), errors="coerce")
            if pd.notna(dt):
                events.append({"type": "repair", "date": dt, "data": row.to_dict()})

    # 4. Activity log (server-side query)
    if asset_id is not None:
        try:
            activity_df = get_activity_log(asset_id=int(asset_id), limit=limit)
            if not activity_df.empty:
                for _, row in activity_df.iterrows():
                    dt = pd.to_datetime(row.get("Timestamp"), errors="coerce")
                    if pd.notna(dt):
                        events.append({"type": "activity", "date": dt, "data": row.to_dict()})
        except Exception:
            pass  # Skip activity log on error

    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:limit]


def _render_timeline_card(event):
    """Render a single timeline event card with color-coded HTML."""
    etype = event["type"]
    d = event["data"]
    dt = event["date"]
    date_str = dt.strftime("%b %d, %Y %I:%M %p") if pd.notna(dt) else "N/A"

    colors = {
        "assignment": ("#3b82f6", "#3b82f608"),
        "issue":      ("#ef4444", "#ef444408"),
        "repair":     ("#f97316", "#f9731608"),
        "activity":   ("#64748b", "#64748b08"),
    }
    main_c, bg_c = colors.get(etype, colors["activity"])

    if etype == "assignment":
        icon = "📦"
        title = f"Assignment: {d.get('Client Name', 'Unknown Client')}"
        parts = [
            f"<div><strong>Type:</strong> {d.get('Assignment Type', 'N/A')}</div>",
            f"<div><strong>Status:</strong> {d.get('Status', 'N/A')}</div>",
            f"<div><strong>Shipment:</strong> {d.get('Shipment Date', 'N/A')}</div>",
        ]
        if d.get("Return Date"):
            parts.append(f"<div><strong>Return:</strong> {d['Return Date']}</div>")
        details = "".join(parts)

    elif etype == "issue":
        icon = "⚠"
        title = f"Issue: {d.get('Issue Title', 'Untitled')}"
        sev = str(d.get("Severity", ""))
        sev_colors = {"Low": "#10b981", "Medium": "#f59e0b", "High": "#ef4444", "Critical": "#dc2626"}
        sev_c = sev_colors.get(sev, "#64748b")
        parts = [
            f'<div><span style="background:{sev_c}15;color:{sev_c};padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600;">{sev}</span></div>' if sev else "",
            f"<div style='margin-top:4px;'><strong>Type:</strong> {d.get('Issue Type', 'N/A')}</div>",
            f"<div><strong>Status:</strong> {d.get('Status', 'N/A')}</div>",
        ]
        if d.get("Resolved Date"):
            parts.append(f"<div><strong>Resolved:</strong> {d['Resolved Date']}</div>")
        details = "".join(parts)

    elif etype == "repair":
        icon = "🔧"
        title = f"Repair: {d.get('Vendor Name', 'Unknown Vendor')}"
        desc = str(d.get("Repair Description", "") or "")
        desc_short = (desc[:80] + "...") if len(desc) > 80 else desc
        cost = d.get("Repair Cost", "")
        cost_str = f"₹{cost}" if cost else "N/A"
        parts = [
            f"<div><strong>Description:</strong> {desc_short or 'N/A'}</div>",
            f"<div><strong>Cost:</strong> {cost_str}</div>",
            f"<div><strong>Status:</strong> {d.get('Status', 'N/A')}</div>",
        ]
        if d.get("Return Date"):
            parts.append(f"<div><strong>Returned:</strong> {d['Return Date']}</div>")
        details = "".join(parts)

    else:  # activity
        icon = "📋"
        title = str(d.get("Action", "Activity"))
        desc = str(d.get("Description", "") or "")
        from_v = str(d.get("From", "") or "")
        to_v = str(d.get("To", "") or "")
        parts = []
        if desc:
            parts.append(f"<div>{desc}</div>")
        if from_v and to_v:
            parts.append(f"<div><strong>Changed:</strong> {from_v} → {to_v}</div>")
        user = d.get("User", "System")
        role = d.get("Role", "")
        parts.append(f"<div><strong>By:</strong> {user}" + (f" ({role})" if role else "") + "</div>")
        details = "".join(parts)

    st.markdown(
        '<div style="'
        f"background:{bg_c};"
        f"border-left:3px solid {main_c};"
        "border-radius:8px;"
        "padding:16px 16px 16px 20px;"
        'margin-bottom:12px;">'
        '<div style="display:flex;gap:12px;">'
        f'<div style="font-size:1.5rem;line-height:1;">{icon}</div>'
        '<div style="flex:1;">'
        f'<div style="font-weight:600;color:#1e293b;">{title}</div>'
        f'<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:8px;">{date_str}</div>'
        f'<div style="font-size:0.875rem;color:#475569;">{details}</div>'
        "</div></div></div>",
        unsafe_allow_html=True,
    )


def render(ctx: AppContext) -> None:
    """Render this page."""
    st.markdown('<p class="main-header">All Assets</p>', unsafe_allow_html=True)

    # Summary badges (quick status overview at the top)
    if not ctx.assets_df.empty and "Current Status" in ctx.assets_df.columns:
        total_count = len(ctx.assets_df)
        deployed_count = len(ctx.assets_df[ctx.assets_df["Current Status"] == "WITH_CLIENT"])
        available_count = len(ctx.assets_df[ctx.assets_df["Current Status"] == "IN_STOCK_WORKING"])
        returned_count = len(ctx.assets_df[ctx.assets_df["Current Status"] == "RETURNED_FROM_CLIENT"])
        repair_count = len(ctx.assets_df[ctx.assets_df["Current Status"] == "WITH_VENDOR_REPAIR"])
        testing_count = len(ctx.assets_df[ctx.assets_df["Current Status"] == "IN_OFFICE_TESTING"])

        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 8px 0 16px 0;">
            <span style="font-size: 14px; color: #6b7280;">Total: <strong style="color: #111827; font-size: 16px;">{total_count}</strong></span>
            <span style="color: #e5e7eb;">|</span>
            <span style="font-size: 12px; font-weight: 600; color: #FF6B35; padding: 3px 10px; background: #FF6B3515; border-radius: 12px;">{deployed_count} Deployed</span>
            <span style="font-size: 12px; font-weight: 600; color: #4CAF50; padding: 3px 10px; background: #4CAF5015; border-radius: 12px;">{available_count} Available</span>
            <span style="font-size: 12px; font-weight: 600; color: #2196F3; padding: 3px 10px; background: #2196F315; border-radius: 12px;">{returned_count} Returned</span>
            <span style="font-size: 12px; font-weight: 600; color: #FF9800; padding: 3px 10px; background: #FF980015; border-radius: 12px;">{repair_count} In Repair</span>
            <span style="font-size: 12px; font-weight: 600; color: #9C27B0; padding: 3px 10px; background: #9C27B015; border-radius: 12px;">{testing_count} Testing</span>
        </div>
        """, unsafe_allow_html=True)

    if not ctx.api:
        st.warning("Please configure your Airtable API key in Settings first.")
    elif st.session_state.get('data_load_error'):
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load assets data. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    elif ctx.assets_df.empty:
        render_empty_state("no_assets")
    else:
        # Get filters from session state (set by KPI card or chart clicks)
        default_status_filter = st.session_state.get("asset_filter", "All")
        default_brand_filter = st.session_state.get("brand_filter", "All")
        sla_filter_value = st.session_state.get("sla_filter", None)
        billing_paused_filter = st.session_state.get("billing_paused_filter", False)
        client_location_filter = st.session_state.get("client_location_filter", None)

        # Clear the filters after using them
        if "asset_filter" in st.session_state:
            del st.session_state.asset_filter
        if "brand_filter" in st.session_state:
            del st.session_state.brand_filter
        if "sla_filter" in st.session_state:
            del st.session_state.sla_filter
        if "billing_paused_filter" in st.session_state:
            del st.session_state.billing_paused_filter
        if "client_location_filter" in st.session_state:
            del st.session_state.client_location_filter

        # Show active filter banner if SLA or billing paused filter is applied
        if sla_filter_value:
            sla_labels = {"critical": "SLA Critical", "warning": "SLA Warning", "ok": "SLA OK"}
            sla_colors = {"critical": "#dc2626", "warning": "#f59e0b", "ok": "#16a34a"}
            st.info(f"🔍 Showing assets with **{sla_labels.get(sla_filter_value, sla_filter_value)}** status. Clear filters to see all assets.")
        elif billing_paused_filter:
            st.info("🔍 Showing assets with **Billing Paused** (Returned/Under Repair). Clear filters to see all assets.")
        elif client_location_filter:
            st.info(f"🔗 Showing assets at **{client_location_filter}**. Clear filters to see all assets.")

        # Handle linked record navigation - pre-fill search with serial number
        linked_serial = st.session_state.get("asset_search_serial", None)
        if linked_serial:
            st.session_state.assets_search = linked_serial
            del st.session_state.asset_search_serial
            st.info(f"🔗 Navigated from linked record. Showing asset: **{linked_serial}**")

        # Clear filters flag check BEFORE form (callback + flag pattern)
        if st.session_state.get('clear_asset_filters_flag', False):
            for key in ["assets_search", "asset_filter", "brand_filter"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.clear_asset_filters_flag = False

        # Search and Filters (wrapped in form to prevent rerun on every keystroke)
        with st.form(key="assets_search_form"):
            search = st.text_input("🔍 Search (Serial Number, Brand, Model)", key="assets_search", placeholder="Type to search...")

            # Filters row
            col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

            with col1:
                filter_options = ["All"] + ASSET_STATUSES
                default_index = filter_options.index(default_status_filter) if default_status_filter in filter_options else 0
                status_filter = st.selectbox("Status", filter_options, index=default_index)

            with col2:
                brand_list = sorted(list(ctx.assets_df["Brand"].dropna().unique())) if "Brand" in ctx.assets_df.columns else []
                brand_options = ["All"] + brand_list
                default_brand_index = brand_options.index(default_brand_filter) if default_brand_filter in brand_options else 0
                brand_filter = st.selectbox("Brand", brand_options, index=default_brand_index)

            with col3:
                type_list = sorted(list(ctx.assets_df["Asset Type"].dropna().unique())) if "Asset Type" in ctx.assets_df.columns else []
                type_filter = st.selectbox("Type", ["All"] + type_list)

            with col4:
                location_list = sorted(list(ctx.assets_df["Current Location"].dropna().unique())) if "Current Location" in ctx.assets_df.columns else []
                location_filter = st.selectbox("Location", ["All"] + location_list)

            # Search and Clear buttons side by side inside form
            btn_col1, btn_col2 = st.columns([3, 1])
            with btn_col1:
                search_submitted = st.form_submit_button("🔍 Search", use_container_width=True, type="primary")
            with btn_col2:
                clear_submitted = st.form_submit_button("Clear Filters", use_container_width=True)

        # Handle clear - set flag and rerun so flag check above clears state
        if clear_submitted:
            st.session_state.clear_asset_filters_flag = True
            safe_rerun()

        # Active filter indicator pills
        active_filters = []
        if status_filter != "All":
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Status:</span> {status_filter}</span>')
        if brand_filter != "All":
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Brand:</span> {brand_filter}</span>')
        if type_filter != "All":
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Type:</span> {type_filter}</span>')
        if location_filter != "All":
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Location:</span> {location_filter}</span>')
        if search:
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Search:</span> {search}</span>')

        if active_filters:
            pills_html = ''.join(active_filters)
            st.markdown(f"""
            <div class="filter-pills-container">
                <span class="filter-pills-title">Active filters:</span>
                {pills_html}
            </div>
            """, unsafe_allow_html=True)

        # Apply filters
        filtered_df = ctx.assets_df.copy()

        if status_filter != "All" and "Current Status" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Current Status"] == status_filter]

        if brand_filter != "All" and "Brand" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Brand"] == brand_filter]

        if type_filter != "All" and "Asset Type" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Asset Type"] == type_filter]

        if location_filter != "All" and "Current Location" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Current Location"] == location_filter]

        # Apply SLA filter if set from dashboard click
        if sla_filter_value and "Current Status" in filtered_df.columns:
            # SLA only applies to certain statuses
            sla_statuses = ["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR", "IN_OFFICE_TESTING"]
            filtered_df = filtered_df[filtered_df["Current Status"].isin(sla_statuses)]

            if "Days in Status" in filtered_df.columns:
                def get_sla_level(row):
                    status = row.get("Current Status", "")
                    days = row.get("Days in Status", 0)
                    if pd.isna(days):
                        days = 0
                    days = int(days)

                    # Get SLA thresholds for this status
                    if status in SLA_CONFIG:
                        warning_threshold = SLA_CONFIG[status].get("warning", 999)
                        critical_threshold = SLA_CONFIG[status].get("critical", 999)

                        if days >= critical_threshold:
                            return "critical"
                        elif days >= warning_threshold:
                            return "warning"
                        else:
                            return "ok"
                    return "ok"

                # Add SLA level column and filter
                filtered_df = filtered_df.copy()
                filtered_df["_sla_level"] = filtered_df.apply(get_sla_level, axis=1)
                filtered_df = filtered_df[filtered_df["_sla_level"] == sla_filter_value]
                filtered_df = filtered_df.drop(columns=["_sla_level"])

        # Apply billing paused filter if set from dashboard click
        if billing_paused_filter and "Current Status" in filtered_df.columns:
            paused_statuses = ["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR"]
            filtered_df = filtered_df[filtered_df["Current Status"].isin(paused_statuses)]

        # Apply client location filter if set from Billing page navigation
        if client_location_filter and "Current Location" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Current Location"] == client_location_filter]

        # Enhanced search - searches multiple columns
        if search:
            search_mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
            if "Serial Number" in filtered_df.columns:
                search_mask |= filtered_df["Serial Number"].str.contains(search, case=False, na=False)
            if "Brand" in filtered_df.columns:
                search_mask |= filtered_df["Brand"].str.contains(search, case=False, na=False)
            if "Model" in filtered_df.columns:
                search_mask |= filtered_df["Model"].str.contains(search, case=False, na=False)
            filtered_df = filtered_df[search_mask]

        # Results count bar with export button
        results_col1, results_col2 = st.columns([3, 1])
        with results_col1:
            is_filtered = len(filtered_df) != len(ctx.assets_df)
            count_style = "font-size: 18px; color: #f97316; font-weight: 700;" if is_filtered else "font-size: 16px; color: #3b82f6; font-weight: 700;"
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; padding: 12px 0;">
                <span style="font-size: 14px; color: #374151; font-weight: 500;">Showing</span>
                <span style="{count_style}">{len(filtered_df)}</span>
                <span style="font-size: 14px; color: #6b7280;">of {len(ctx.assets_df)} assets</span>
                <span style="margin-left: 12px; display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="font-size: 11px; color: #4CAF50; font-weight: 600; padding: 2px 8px; background: #4CAF5020; border-radius: 4px;">In Stock</span>
                    <span style="font-size: 11px; color: #FF6B35; font-weight: 600; padding: 2px 8px; background: #FF6B3520; border-radius: 4px;">With Client</span>
                    <span style="font-size: 11px; color: #2196F3; font-weight: 600; padding: 2px 8px; background: #2196F320; border-radius: 4px;">Returned</span>
                    <span style="font-size: 11px; color: #9C27B0; font-weight: 600; padding: 2px 8px; background: #9C27B020; border-radius: 4px;">Testing</span>
                    <span style="font-size: 11px; color: #FF9800; font-weight: 600; padding: 2px 8px; background: #FF980020; border-radius: 4px;">Repair</span>
                </span>
            </div>
            """, unsafe_allow_html=True)
        with results_col2:
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Export CSV",
                data=csv,
                file_name=f"assets_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        # ========== BULK OPERATIONS SECTION ==========
        # Initialize session state for bulk selection
        if 'bulk_selected_assets' not in st.session_state:
            st.session_state.bulk_selected_assets = []

        # Display columns for table (prioritized order - most important first)
        display_cols = ["Serial Number", "Brand", "Model", "Current Status", "Current Location",
                       "Asset Type", "RAM (GB)", "Storage (GB)", "Office License Key", "Reuse Count"]
        available_cols = [c for c in display_cols if c in filtered_df.columns]

        if available_cols and len(filtered_df) > 0:
            # Create asset options for multiselect
            asset_options = []
            asset_map = {}  # Map display label to asset data
            for _, row in filtered_df.iterrows():
                serial = row.get('Serial Number', '')
                asset_type = row.get('Asset Type', '')
                brand = row.get('Brand', '')
                status = row.get('Current Status', '')
                asset_id = row.get('_id', '')
                label = f"{serial} | {asset_type} | {brand} | {status}"
                asset_options.append(label)
                asset_map[label] = {'_id': asset_id, 'serial': serial, 'status': status, 'row': row}

            # Bulk selection multiselect
            st.markdown("""
            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                Bulk Operations
            </div>
            """, unsafe_allow_html=True)

            # Check if we need to clear the selection (flag set by callback/previous action)
            if st.session_state.get('clear_bulk_selection_flag', False):
                st.session_state.bulk_asset_select = []
                st.session_state.clear_bulk_selection_flag = False

            selected_assets = st.multiselect(
                "Select Assets for Bulk Action",
                options=asset_options,
                default=[],
                key="bulk_asset_select",
                help="Select multiple assets to perform bulk actions"
            )

            # Show bulk operations panel if assets selected
            if selected_assets:
                selected_count = len(selected_assets)

                st.markdown(f"""
                <div style="background: #eff6ff; border: 1px solid #3b82f6; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                    <strong style="color: #1e40af;">📦 {selected_count} asset(s) selected</strong>
                </div>
                """, unsafe_allow_html=True)

                # Action selection
                bulk_col1, bulk_col2 = st.columns(2)

                with bulk_col1:
                    bulk_action = st.selectbox(
                        "Bulk Action",
                        ["Select Action...", "Change Status", "Assign to Client"],
                        key="bulk_action_select"
                    )

                # Action-specific options
                if bulk_action == "Change Status":
                    with bulk_col2:
                        new_status = st.selectbox("New Status", ASSET_STATUSES, key="bulk_new_status")

                    # Show current statuses of selected assets
                    current_statuses = set()
                    for label in selected_assets:
                        current_statuses.add(asset_map[label]['status'])
                    st.caption(f"Current statuses: {', '.join(current_statuses)}")

                    if st.button(f"🔄 Change Status for {selected_count} Assets", type="primary", use_container_width=True):
                        with st.spinner(f"Updating {selected_count} assets..."):
                            success_count = 0
                            fail_count = 0
                            errors = []

                            for label in selected_assets:
                                asset_data = asset_map[label]
                                asset_id = asset_data['_id']
                                serial = asset_data['serial']

                                try:
                                    success, error_msg = update_asset_status(asset_id, new_status)
                                    if success:
                                        success_count += 1
                                    else:
                                        fail_count += 1
                                        errors.append(f"{serial}: {error_msg}")
                                except Exception as e:
                                    fail_count += 1
                                    errors.append(f"{serial}: {str(e)}")

                            # Log bulk action
                            log_activity_event(
                                action_type="BULK_STATUS_CHANGE",
                                category="bulk_operation",
                                user_role=st.session_state.user_role,
                                description=f"Bulk status change to {new_status} for {success_count} assets",
                                success=success_count > 0,
                                metadata={"total": selected_count, "success": success_count, "failed": fail_count}
                            )

                            if success_count > 0:
                                st.success(f"✅ Successfully updated {success_count} assets to {new_status}")
                            if fail_count > 0:
                                st.warning(f"⚠️ {fail_count} assets failed to update")
                                with st.expander("View errors"):
                                    for err in errors[:10]:
                                        st.write(f"• {err}")

                            # Clear selection and refresh (use flag to avoid widget state error)
                            st.session_state.clear_bulk_selection_flag = True
                            safe_rerun()

                elif bulk_action == "Assign to Client":
                    # Get client list
                    if not ctx.clients_df.empty and "Client Name" in ctx.clients_df.columns:
                        client_list = sorted(ctx.clients_df["Client Name"].dropna().unique().tolist())
                    else:
                        client_list = []

                    with bulk_col2:
                        if client_list:
                            selected_client = st.selectbox("Select Client", client_list, key="bulk_client_select")
                        else:
                            st.warning("No clients available")
                            selected_client = None

                    # Check if selected assets are assignable (IN_STOCK_WORKING)
                    assignable_count = 0
                    non_assignable = []
                    for label in selected_assets:
                        if asset_map[label]['status'] == "IN_STOCK_WORKING":
                            assignable_count += 1
                        else:
                            non_assignable.append(asset_map[label]['serial'])

                    if non_assignable:
                        st.warning(f"⚠️ {len(non_assignable)} asset(s) not in IN_STOCK_WORKING status will be skipped")

                    if selected_client and assignable_count > 0:
                        # Optional shipment details
                        ship_col1, ship_col2 = st.columns(2)
                        with ship_col1:
                            shipment_date = st.date_input("Shipment Date", value=date.today(), key="bulk_ship_date")
                        with ship_col2:
                            tracking_number = st.text_input("Tracking Number (optional)", key="bulk_tracking")

                        if st.button(f"📦 Assign {assignable_count} Assets to {selected_client}", type="primary", use_container_width=True):
                            with st.spinner(f"Assigning {assignable_count} assets..."):
                                success_count = 0
                                fail_count = 0
                                errors = []

                                for label in selected_assets:
                                    asset_data = asset_map[label]
                                    if asset_data['status'] != "IN_STOCK_WORKING":
                                        continue

                                    asset_id = asset_data['_id']
                                    serial = asset_data['serial']

                                    try:
                                        # Update status to WITH_CLIENT
                                        success, error_msg = update_asset_status(asset_id, "WITH_CLIENT", selected_client)
                                        if success:
                                            # Create assignment record
                                            assignment_data = {
                                                "Serial Number": serial,
                                                "Client Name": selected_client,
                                                "Assignment Name": f"{serial} → {selected_client}",
                                                "Assignment Type": "Rental",
                                                "Shipment Date": shipment_date.isoformat() if shipment_date else None,
                                                "Tracking Number": tracking_number if tracking_number else None,
                                                "Status": "Active"
                                            }
                                            create_assignment_record(assignment_data, user_role=st.session_state.user_role)
                                            success_count += 1
                                        else:
                                            fail_count += 1
                                            errors.append(f"{serial}: {error_msg}")
                                    except Exception as e:
                                        fail_count += 1
                                        errors.append(f"{serial}: {str(e)}")

                                # Log bulk action
                                log_activity_event(
                                    action_type="BULK_ASSIGNMENT",
                                    category="bulk_operation",
                                    user_role=st.session_state.user_role,
                                    client_name=selected_client,
                                    description=f"Bulk assignment of {success_count} assets to {selected_client}",
                                    success=success_count > 0,
                                    metadata={"total": assignable_count, "success": success_count, "failed": fail_count, "client": selected_client}
                                )

                                if success_count > 0:
                                    st.success(f"✅ Successfully assigned {success_count} assets to {selected_client}")
                                if fail_count > 0:
                                    st.warning(f"⚠️ {fail_count} assets failed to assign")
                                    with st.expander("View errors"):
                                        for err in errors[:10]:
                                            st.write(f"• {err}")

                                # Clear selection and refresh (use flag to avoid widget state error)
                                st.session_state.clear_bulk_selection_flag = True
                                safe_rerun()

                # Clear selection button - uses callback to avoid widget state modification error
                def clear_bulk_selection_callback():
                    st.session_state.clear_bulk_selection_flag = True

                st.button("🗑️ Clear Selection", key="clear_bulk_selection", on_click=clear_bulk_selection_callback)

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

            # Apply pagination to filtered data
            paginated_df = paginate_dataframe(filtered_df, "assets_table", show_controls=True)

            # Enhanced color coding for status with better visibility
            def highlight_status(row):
                status = row.get("Current Status", "")
                color = STATUS_COLORS.get(status, "#6b7280")
                # Stronger background for status column, subtle tint for entire row
                styles = []
                for col in row.index:
                    if col == "Current Status":
                        styles.append(f'background-color: {color}40; color: {color}; font-weight: 600;')
                    else:
                        styles.append(f'background-color: {color}10;')
                return styles

            styled_df = paginated_df[available_cols].style.apply(highlight_status, axis=1)
            st.dataframe(styled_df, hide_index=True)
            render_page_navigation("assets_table")

        # ========== ASSET QUICK ACTIONS PANEL ==========
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        with st.expander("⚡ Asset Quick Actions", expanded=False):
            if "Serial Number" in filtered_df.columns and len(filtered_df) > 0:
                qa_serial_options = filtered_df["Serial Number"].dropna().unique().tolist()
                if qa_serial_options:
                    selected_qa_serial = st.selectbox(
                        "Select an asset",
                        options=qa_serial_options,
                        key="qa_asset_serial"
                    )

                    if selected_qa_serial:
                        qa_asset_info = filtered_df[filtered_df["Serial Number"] == selected_qa_serial]
                        if not qa_asset_info.empty:
                            qa_row = qa_asset_info.iloc[0]
                            qa_status = qa_row.get('Current Status', 'N/A')
                            qa_status_color = STATUS_COLORS.get(qa_status, '#6b7280')

                            # Asset detail card
                            st.markdown(f"""
                            <div class="asset-detail-card">
                                <div class="asset-detail-header">
                                    <span class="asset-detail-serial">{selected_qa_serial}</span>
                                    <span class="asset-detail-status" style="background: {qa_status_color}20; color: {qa_status_color};">{qa_status}</span>
                                </div>
                                <div class="asset-detail-grid">
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Brand / Model</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Brand', 'N/A')} {qa_row.get('Model', '')}</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Asset Type</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Asset Type', 'N/A')}</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Location</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Current Location', 'N/A')}</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">RAM / Storage</div>
                                        <div class="asset-detail-item-value">{qa_row.get('RAM (GB)', 'N/A')} GB / {qa_row.get('Storage (GB)', 'N/A')} GB</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Reuse Count</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Reuse Count', 0)}</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Notes</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Notes', '-') or '-'}</div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Quick action buttons
                            qa_action_col1, qa_action_col2, qa_action_col3 = st.columns(3)

                            with qa_action_col1:
                                qa_new_status = st.selectbox(
                                    "Change Status To",
                                    options=[s for s in ASSET_STATUSES if s != qa_status],
                                    key="qa_new_status"
                                )

                            with qa_action_col2:
                                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("🔄 Update Status", key="qa_update_status", type="primary", use_container_width=True):
                                    asset_id = qa_row.get('_id', '')
                                    if asset_id:
                                        success, error_msg = update_asset_status(asset_id, qa_new_status)
                                        if success:
                                            log_activity_event(
                                                action_type="STATUS_CHANGE",
                                                category="asset",
                                                user_role=st.session_state.user_role,
                                                description=f"Changed {selected_qa_serial} from {qa_status} to {qa_new_status}",
                                                success=True,
                                                metadata={"serial": selected_qa_serial, "old_status": qa_status, "new_status": qa_new_status}
                                            )
                                            st.success(f"Updated {selected_qa_serial} to {qa_new_status}")
                                            safe_rerun()
                                        else:
                                            st.error(f"Failed: {error_msg}")

                            with qa_action_col3:
                                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("📋 View Full History", key="qa_view_history", use_container_width=True):
                                    st.session_state.asset_search_serial = selected_qa_serial
                                    safe_rerun()
            else:
                st.info("No assets available.")

        # ========== ASSET HISTORY TIMELINE ==========
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        with st.expander("📅 Asset History Timeline", expanded=False):
            if "Serial Number" in filtered_df.columns and len(filtered_df) > 0:
                serial_options = filtered_df["Serial Number"].dropna().unique().tolist()
                if serial_options:
                    hist_col1, hist_col2 = st.columns([3, 1])
                    with hist_col1:
                        selected_history_serial = st.selectbox(
                            "Select Asset to View Timeline",
                            options=serial_options,
                            key="asset_history_serial"
                        )
                    with hist_col2:
                        timeline_limit = st.selectbox(
                            "Show Events",
                            options=[50, 100, 200],
                            key="timeline_limit"
                        )

                    if selected_history_serial:
                        asset_info = filtered_df[filtered_df["Serial Number"] == selected_history_serial]
                        if not asset_info.empty:
                            asset_row = asset_info.iloc[0]
                            asset_id = asset_row.get("_id") if "_id" in asset_info.columns else None

                            # Asset details header
                            st.markdown("---")
                            st.markdown("**📦 Asset Details:**")
                            d_col1, d_col2, d_col3, d_col4 = st.columns(4)
                            with d_col1:
                                st.markdown(f"**Serial:** {asset_row.get('Serial Number', 'N/A')}")
                            with d_col2:
                                st.markdown(f"**Type:** {asset_row.get('Asset Type', 'N/A')}")
                            with d_col3:
                                st.markdown(f"**Brand:** {asset_row.get('Brand', 'N/A')} {asset_row.get('Model', '')}")
                            with d_col4:
                                st.markdown(f"**Status:** {asset_row.get('Current Status', 'N/A')}")

                            st.markdown("---")

                            # Build timeline
                            timeline_events = _build_timeline_events(
                                serial=selected_history_serial,
                                asset_id=asset_id,
                                assignments_df=ctx.assignments_df,
                                issues_df=ctx.issues_df,
                                repairs_df=ctx.repairs_df,
                                limit=timeline_limit,
                            )

                            if timeline_events:
                                # Summary counts
                                type_counts = {}
                                for ev in timeline_events:
                                    type_counts[ev["type"]] = type_counts.get(ev["type"], 0) + 1
                                summary_parts = []
                                if type_counts.get("assignment"):
                                    summary_parts.append(f"{type_counts['assignment']} Assignments")
                                if type_counts.get("issue"):
                                    summary_parts.append(f"{type_counts['issue']} Issues")
                                if type_counts.get("repair"):
                                    summary_parts.append(f"{type_counts['repair']} Repairs")
                                if type_counts.get("activity"):
                                    summary_parts.append(f"{type_counts['activity']} Activities")

                                st.markdown(
                                    '<div style="'
                                    "background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"
                                    'padding:12px 16px;margin-bottom:16px;font-size:0.875rem;color:#475569;">'
                                    f"<strong>{len(timeline_events)} events:</strong> "
                                    + " &bull; ".join(summary_parts)
                                    + "</div>",
                                    unsafe_allow_html=True,
                                )

                                for ev in timeline_events:
                                    _render_timeline_card(ev)
                            else:
                                render_empty_state(
                                    "no_activity",
                                    custom_message="No history found for this asset. Activity will appear here as assignments, issues, repairs, or status changes occur.",
                                    show_action=False,
                                )
            else:
                st.info("No assets available to view history.")

    # QUICK ACTIONS PAGE

