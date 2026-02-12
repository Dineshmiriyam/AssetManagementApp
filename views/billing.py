"""Billing page — billing period management and metrics."""

from datetime import datetime, date

import pandas as pd
import streamlit as st

from config.constants import BILLING_CONFIG, STATUS_DISPLAY_NAMES
from config.permissions import (
    check_page_access, render_access_denied,
    can_override_billing, can_view_billing, validate_action,
)
from services.billing_service import (
    get_asset_billing_status, calculate_billing_metrics,
    get_billable_assets, get_paused_billing_assets,
    validate_billing_override,
)
from services.audit_service import log_activity_event
from components.empty_states import render_empty_state
from components.feedback import render_error_state, render_inline_error
from core.data import safe_rerun, clear_cache, paginate_dataframe, render_page_navigation
from views.context import AppContext

try:
    from database.db import (
        get_current_billing_period, get_billing_period_status,
        is_billing_period_closed, get_all_billing_periods,
        close_billing_period, reopen_billing_period,
        can_modify_billing_data, get_billing_period,
        ACTION_TYPES, BILLING_ACTIONS, BILLING_STATES,
    )
except ImportError:
    get_current_billing_period = None

def render(ctx: AppContext) -> None:
    """Render this page."""
    # Route-level access control (defense in depth)
    if not check_page_access("Billing", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "finance"])
        st.stop()

    st.markdown('<p class="main-header">Billing & Revenue</p>', unsafe_allow_html=True)

    current_role = st.session_state.user_role

    if not ctx.api:
        st.warning("Please configure your Airtable API key in Settings first.")
    elif st.session_state.get('data_load_error'):
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load billing data. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    else:
        # Use centralized billing calculations
        billing_metrics = calculate_billing_metrics(ctx.assets_df)

        # Billing Rules Notice
        st.markdown(f"""
        <div style="background: #eff6ff; border: 1px solid #3b82f6; border-radius: 8px; padding: 12px; margin-bottom: 20px;">
            <strong style="color: #1e40af;">Billing Rules (Enforced)</strong><br>
            <span style="color: #1e3a5a; font-size: 0.9rem;">
                <span style="color: {BILLING_CONFIG['status_colors']['active']};">{BILLING_CONFIG['status_icons']['active']}</span> Active: Asset WITH_CLIENT |
                <span style="color: {BILLING_CONFIG['status_colors']['paused']};">{BILLING_CONFIG['status_icons']['paused']}</span> Paused: RETURNED_FROM_CLIENT, WITH_VENDOR_REPAIR |
                <span style="color: {BILLING_CONFIG['status_colors']['not_applicable']};">{BILLING_CONFIG['status_icons']['not_applicable']}</span> Not Billable: All other states
            </span>
        </div>
        """, unsafe_allow_html=True)

        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Billable Assets", billing_metrics['billable_count'], help="Assets currently with clients (WITH_CLIENT)")
        with col2:
            st.metric("Monthly Rate", f"₹{billing_metrics['monthly_rate']:,}", help="Per asset per month")
        with col3:
            st.metric("Est. Monthly Revenue", f"₹{billing_metrics['monthly_revenue']:,}")
        with col4:
            st.metric("Est. Annual Revenue", f"₹{billing_metrics['annual_revenue']:,}")

        # Paused billing indicator
        if billing_metrics['paused_count'] > 0:
            st.markdown(f"""
            <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 10px 15px; margin: 10px 0; border-radius: 4px;">
                <strong style="color: #92400e;">{BILLING_CONFIG['status_icons']['paused']} {billing_metrics['paused_count']} asset(s) with paused billing</strong>
                <span style="color: #78350f; font-size: 0.9rem;"> - Returned or in repair. Billing resumes when redeployed.</span>
            </div>
            """, unsafe_allow_html=True)

        # ========== BILLING PERIOD STATUS INDICATOR ==========
        if ctx.data_source == "mysql" and ctx.mysql_available:
            current_period = get_current_billing_period()
            month_names = ["", "January", "February", "March", "April", "May", "June",
                           "July", "August", "September", "October", "November", "December"]
            period_name = f"{month_names[current_period['month']]} {current_period['year']}"

            if current_period['status'] == 'CLOSED':
                st.markdown(f"""
                <div style="background: #fef2f2; border: 2px solid #ef4444; border-radius: 8px; padding: 15px; margin: 10px 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <strong style="color: #991b1b; font-size: 1.1rem;">Billing Period Closed</strong><br>
                            <span style="color: #7f1d1d; font-size: 0.9rem;">
                                {period_name} is closed. Invoices are read-only.
                                {f"Closed by {current_period['closed_by']}" if current_period['closed_by'] else ""}
                            </span>
                        </div>
                        <div style="background: #ef4444; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;">
                            CLOSED
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 12px; margin: 10px 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <strong style="color: #065f46;">Current Billing Period: {period_name}</strong>
                            <span style="color: #047857; font-size: 0.9rem;"> - Open for modifications</span>
                        </div>
                        <div style="background: #10b981; color: white; padding: 4px 10px; border-radius: 4px; font-size: 0.85rem;">
                            OPEN
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # Create tabs for different views
        if ctx.data_source == "mysql" and ctx.mysql_available:
            billing_tabs = st.tabs(["Revenue by Client", "Asset Billing Status", "Paused Billing", "Billing Periods"])
        else:
            billing_tabs = st.tabs(["Revenue by Client", "Asset Billing Status", "Paused Billing"])

        with billing_tabs[0]:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Revenue by Client</span>
            </div>
            """, unsafe_allow_html=True)

            if billing_metrics['client_breakdown']:
                # Build summary from centralized calculation
                client_data = []
                for client, data in billing_metrics['client_breakdown'].items():
                    client_data.append({
                        "Client": client,
                        "Asset Count": data['asset_count'],
                        "Monthly Rate (₹)": data['monthly_rate'],
                        "Monthly Revenue (₹)": data['monthly_revenue'],
                        "Annual Revenue (₹)": data['annual_revenue']
                    })

                billing_summary = pd.DataFrame(client_data)

                # Quick View Client Assets - Linked Records Navigation
                with st.expander("🔗 View Client's Assets", expanded=False):
                    client_options = billing_summary["Client"].tolist()
                    if client_options:
                        cqv_col1, cqv_col2 = st.columns([3, 1])
                        with cqv_col1:
                            selected_billing_client = st.selectbox(
                                "Select Client",
                                options=client_options,
                                key="billing_quick_view_client"
                            )
                        with cqv_col2:
                            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                            if st.button("🔍 View Client Assets", key="billing_view_client_btn", width="stretch"):
                                st.session_state.current_page = "Assets"
                                st.session_state.asset_filter = "WITH_CLIENT"
                                st.session_state.client_location_filter = selected_billing_client
                                safe_rerun()

                        # Show client's assets
                        if selected_billing_client and not ctx.assets_df.empty:
                            client_assets_df = ctx.assets_df[
                                (ctx.assets_df["Current Status"] == "WITH_CLIENT") &
                                (ctx.assets_df["Current Location"] == selected_billing_client)
                            ]
                            if not client_assets_df.empty:
                                st.markdown("---")
                                st.markdown(f"**Assets with {selected_billing_client}:**")
                                display_cols = ["Serial Number", "Brand", "Model", "Asset Type"]
                                available_cols = [c for c in display_cols if c in client_assets_df.columns]
                                st.dataframe(client_assets_df[available_cols].head(10), hide_index=True)
                                if len(client_assets_df) > 10:
                                    st.caption(f"Showing 10 of {len(client_assets_df)} assets. Click 'View Client Assets' to see all.")

                st.dataframe(
                    billing_summary,
                                        hide_index=True,
                    column_config={
                        "Client": st.column_config.TextColumn("Client"),
                        "Asset Count": st.column_config.NumberColumn("Assets"),
                        "Monthly Rate (₹)": st.column_config.NumberColumn("Rate/Asset", format="₹%d"),
                        "Monthly Revenue (₹)": st.column_config.NumberColumn("Monthly", format="₹%d"),
                        "Annual Revenue (₹)": st.column_config.NumberColumn("Annual", format="₹%d"),
                    }
                )

                # Summary totals
                st.markdown("---")
                total_col1, total_col2, total_col3 = st.columns(3)
                with total_col1:
                    st.metric("Total Monthly Revenue", f"₹{billing_metrics['monthly_revenue']:,}")
                with total_col2:
                    st.metric("Total Annual Revenue", f"₹{billing_metrics['annual_revenue']:,}")
                with total_col3:
                    st.metric("Fleet Utilization", f"{billing_metrics['utilization_rate']:.1f}%",
                              help="Percentage of fleet currently generating revenue")

                # Export option
                csv = billing_summary.to_csv(index=False)
                st.download_button(
                    label="Export Billing Report",
                    data=csv,
                    file_name="billing_report.csv",
                    mime="text/csv"
                )
            else:
                render_empty_state("no_billable_assets", show_action=True)

        with billing_tabs[1]:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
                <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Asset Billing Status</span>
            </div>
            """, unsafe_allow_html=True)

            if not ctx.assets_df.empty and "Current Status" in ctx.assets_df.columns:
                # Create billing status view
                billing_view = ctx.assets_df[["Serial Number", "Brand", "Model", "Current Status", "Current Location"]].copy()

                # Add billing status column using centralized function
                billing_view["Billing Status"] = billing_view["Current Status"].apply(
                    lambda x: get_asset_billing_status(x)["label"]
                )
                billing_view["Billing Reason"] = billing_view["Current Status"].apply(
                    lambda x: get_asset_billing_status(x)["reason"]
                )

                # Search bar
                billing_search = st.text_input("🔍 Search (Serial Number, Location)", key="billing_search", placeholder="Type to search...")

                # Filter options
                bcol1, bcol2, bcol3 = st.columns([1, 1, 0.5])
                with bcol1:
                    status_filter = st.selectbox(
                        "Billing Status",
                        ["All", "Billing Active", "Billing Paused", "Not Billable"],
                        key="billing_status_filter"
                    )
                with bcol2:
                    location_list = sorted(list(billing_view["Current Location"].dropna().unique()))
                    billing_location_filter = st.selectbox("Location", ["All"] + location_list, key="billing_location_filter")
                with bcol3:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Clear", key="clear_billing_filters", width="stretch"):
                        for key in ["billing_search", "billing_status_filter", "billing_location_filter"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        safe_rerun()

                if status_filter != "All":
                    billing_view = billing_view[billing_view["Billing Status"] == status_filter]

                if billing_location_filter != "All":
                    billing_view = billing_view[billing_view["Current Location"] == billing_location_filter]

                # Search
                if billing_search:
                    search_mask = (
                        billing_view["Serial Number"].str.contains(billing_search, case=False, na=False) |
                        billing_view["Current Location"].str.contains(billing_search, case=False, na=False)
                    )
                    billing_view = billing_view[search_mask]

                # Display with color coding
                def highlight_billing_status(row):
                    status = row["Billing Status"]
                    if status == "Billing Active":
                        return [f'background-color: {BILLING_CONFIG["status_colors"]["active"]}20'] * len(row)
                    elif status == "Billing Paused":
                        return [f'background-color: {BILLING_CONFIG["status_colors"]["paused"]}20'] * len(row)
                    return [''] * len(row)

                # Quick View Asset Panel - Linked Records Navigation
                with st.expander("🔗 Quick View Asset Details", expanded=False):
                    if "Serial Number" in billing_view.columns and len(billing_view) > 0:
                        serial_options = billing_view["Serial Number"].dropna().unique().tolist()
                        if serial_options:
                            bqv_col1, bqv_col2 = st.columns([3, 1])
                            with bqv_col1:
                                selected_billing_serial = st.selectbox(
                                    "Select Asset Serial",
                                    options=serial_options,
                                    key="billing_quick_view_serial"
                                )
                            with bqv_col2:
                                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("🔍 View in Assets", key="billing_view_asset_btn", width="stretch"):
                                    st.session_state.current_page = "Assets"
                                    st.session_state.asset_search_serial = selected_billing_serial
                                    safe_rerun()

                            # Show asset details
                            if selected_billing_serial:
                                asset_info = billing_view[billing_view["Serial Number"] == selected_billing_serial]
                                if not asset_info.empty:
                                    asset_row = asset_info.iloc[0]
                                    st.markdown("---")
                                    detail_col1, detail_col2, detail_col3 = st.columns(3)
                                    with detail_col1:
                                        st.markdown(f"**Brand:** {asset_row.get('Brand', 'N/A')}")
                                        st.markdown(f"**Model:** {asset_row.get('Model', 'N/A')}")
                                    with detail_col2:
                                        st.markdown(f"**Status:** {asset_row.get('Current Status', 'N/A')}")
                                        st.markdown(f"**Location:** {asset_row.get('Current Location', 'N/A')}")
                                    with detail_col3:
                                        st.markdown(f"**Billing:** {asset_row.get('Billing Status', 'N/A')}")
                                        st.markdown(f"**Reason:** {asset_row.get('Billing Reason', 'N/A')}")
                        else:
                            st.info("No assets in current view")
                    else:
                        st.info("No assets available")

                st.dataframe(
                    billing_view,
                                        hide_index=True,
                    column_config={
                        "Serial Number": st.column_config.TextColumn("Serial"),
                        "Current Status": st.column_config.TextColumn("State"),
                        "Current Location": st.column_config.TextColumn("Location"),
                        "Billing Status": st.column_config.TextColumn("Billing"),
                        "Billing Reason": st.column_config.TextColumn("Reason"),
                    }
                )

                # Summary counts
                status_counts = billing_view["Billing Status"].value_counts()
                count_cols = st.columns(3)
                with count_cols[0]:
                    active = status_counts.get("Billing Active", 0)
                    st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background: {BILLING_CONFIG['status_colors']['active']}20; border-radius: 8px;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: {BILLING_CONFIG['status_colors']['active']};">{active}</div>
                        <div style="font-size: 0.8rem; color: #64748b;">Billing Active</div>
                    </div>
                    """, unsafe_allow_html=True)
                with count_cols[1]:
                    paused = status_counts.get("Billing Paused", 0)
                    st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background: {BILLING_CONFIG['status_colors']['paused']}20; border-radius: 8px;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: {BILLING_CONFIG['status_colors']['paused']};">{paused}</div>
                        <div style="font-size: 0.8rem; color: #64748b;">Billing Paused</div>
                    </div>
                    """, unsafe_allow_html=True)
                with count_cols[2]:
                    not_billable = status_counts.get("Not Billable", 0)
                    st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background: {BILLING_CONFIG['status_colors']['not_applicable']}20; border-radius: 8px;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: {BILLING_CONFIG['status_colors']['not_applicable']};">{not_billable}</div>
                        <div style="font-size: 0.8rem; color: #64748b;">Not Billable</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No asset data available.")

        with billing_tabs[2]:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #f59e0b;">
                <div style="width: 4px; height: 20px; background: #f59e0b; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Paused Billing Assets</span>
            </div>
            """, unsafe_allow_html=True)
            st.caption("Assets that were previously billing but are now paused. Billing resumes when redeployed to WITH_CLIENT.")

            paused_assets = get_paused_billing_assets(ctx.assets_df)

            if not paused_assets.empty:
                paused_view = paused_assets[["Serial Number", "Brand", "Model", "Current Status", "Current Location"]].copy()
                paused_view["Pause Reason"] = paused_view["Current Status"].apply(
                    lambda x: get_asset_billing_status(x)["reason"]
                )

                st.dataframe(
                    paused_view,
                                        hide_index=True,
                    column_config={
                        "Serial Number": st.column_config.TextColumn("Serial"),
                        "Current Status": st.column_config.TextColumn("State"),
                        "Current Location": st.column_config.TextColumn("Last Location"),
                        "Pause Reason": st.column_config.TextColumn("Reason"),
                    }
                )

                # Potential revenue loss calculation
                potential_monthly_loss = len(paused_assets) * billing_metrics['monthly_rate']
                st.markdown(f"""
                <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 15px; margin-top: 15px; border-radius: 4px;">
                    <strong style="color: #991b1b;">Potential Revenue Impact</strong><br>
                    <span style="color: #7f1d1d;">
                        {len(paused_assets)} paused assets = ₹{potential_monthly_loss:,}/month potential revenue
                        if redeployed
                    </span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.success("No assets with paused billing. All previously billed assets are either active or returned to stock.")

        # ========== BILLING PERIODS TAB ==========
        if ctx.data_source == "mysql" and ctx.mysql_available and len(billing_tabs) > 3:
            with billing_tabs[3]:
                # Section header
                st.markdown("""
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #8b5cf6;">
                    <div style="width: 4px; height: 20px; background: #8b5cf6; border-radius: 2px;"></div>
                    <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Billing Period Management</span>
                </div>
                """, unsafe_allow_html=True)

                month_names = ["", "January", "February", "March", "April", "May", "June",
                               "July", "August", "September", "October", "November", "December"]

                # Current period info
                current_period = get_current_billing_period()
                current_period_name = f"{month_names[current_period['month']]} {current_period['year']}"

                st.markdown(f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                    <strong>Current Period:</strong> {current_period_name}<br>
                    <strong>Status:</strong>
                    <span style="color: {'#ef4444' if current_period['status'] == 'CLOSED' else '#10b981'}; font-weight: bold;">
                        {'CLOSED' if current_period['status'] == 'CLOSED' else 'OPEN'}
                    </span>
                </div>
                """, unsafe_allow_html=True)

                # Period selection for close/reopen
                period_col1, period_col2 = st.columns(2)

                with period_col1:
                    selected_year = st.selectbox(
                        "Year",
                        options=list(range(datetime.now().year - 2, datetime.now().year + 1)),
                        index=2,
                        key="period_year"
                    )

                with period_col2:
                    selected_month = st.selectbox(
                        "Month",
                        options=list(range(1, 13)),
                        format_func=lambda x: month_names[x],
                        index=datetime.now().month - 1,
                        key="period_month"
                    )

                # Check selected period status
                selected_period_status = get_billing_period_status(selected_year, selected_month)
                selected_period_name = f"{month_names[selected_month]} {selected_year}"

                st.markdown("---")

                # Show selected period status and actions
                if selected_period_status == 'CLOSED':
                    st.markdown(f"""
                    <div style="background: #fef2f2; border: 2px solid #ef4444; border-radius: 8px; padding: 15px;">
                        <strong style="color: #991b1b; font-size: 1.1rem;">{selected_period_name} - CLOSED</strong><br>
                        <span style="color: #7f1d1d;">
                            This billing period is closed. Invoices and billing data are read-only.
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                    # Only admin can reopen
                    if current_role == "admin":
                        st.markdown("##### Admin: Reopen Period")
                        st.warning("Reopening a closed period allows modifications. This should only be done for corrections.")

                        reopen_reason = st.text_input(
                            "Reason for reopening",
                            placeholder="e.g., Correction needed for invoice #123",
                            key="reopen_reason"
                        )

                        if st.button("Reopen Period", key="reopen_period", type="secondary"):
                            if not reopen_reason:
                                st.error("Please provide a reason for reopening.")
                            else:
                                success, error = reopen_billing_period(
                                    selected_year, selected_month,
                                    reopened_by=current_role,
                                    notes=reopen_reason
                                )
                                if success:
                                    # Log the action
                                    log_activity_event(
                                        action_type="BILLING_PERIOD_REOPENED",
                                        category="billing",
                                        user_role=current_role,
                                        description=f"Billing period reopened: {selected_period_name}. Reason: {reopen_reason}",
                                        old_value="CLOSED",
                                        new_value="OPEN",
                                        success=True
                                    )
                                    st.success(f"{selected_period_name} has been reopened.")
                                    safe_rerun()
                                else:
                                    st.error(f"Failed to reopen: {error}")
                    else:
                        st.info("Contact an administrator to reopen a closed billing period.")

                else:
                    st.markdown(f"""
                    <div style="background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 15px;">
                        <strong style="color: #065f46; font-size: 1.1rem;">{selected_period_name} - OPEN</strong><br>
                        <span style="color: #047857;">
                            This billing period is open. Invoices and billing data can be modified.
                        </span>
                    </div>
                    """, unsafe_allow_html=True)

                    # Only admin can close
                    if current_role == "admin":
                        st.markdown("##### Close Billing Period")
                        st.info("Closing a period finalizes all billing data. Once closed, no modifications are allowed without admin override.")

                        # Show what will be locked
                        st.markdown(f"""
                        **Closing {selected_period_name} will:**
                        - Lock all invoices for this period
                        - Prevent retroactive billing changes
                        - Record current revenue: ₹{billing_metrics['monthly_revenue']:,}
                        - Record billable assets: {billing_metrics['billable_count']}
                        """)

                        close_notes = st.text_input(
                            "Closing notes (optional)",
                            placeholder="e.g., All invoices verified and sent",
                            key="close_notes"
                        )

                        close_col1, close_col2 = st.columns(2)
                        with close_col1:
                            confirm_close = st.checkbox(
                                f"I confirm I want to close {selected_period_name}",
                                key="confirm_close"
                            )

                        with close_col2:
                            if st.button("Close Period", key="close_period", type="primary", disabled=not confirm_close):
                                success, error = close_billing_period(
                                    selected_year, selected_month,
                                    closed_by=current_role,
                                    total_revenue=billing_metrics['monthly_revenue'],
                                    total_assets=billing_metrics['billable_count'],
                                    notes=close_notes
                                )
                                if success:
                                    # Log the action
                                    log_activity_event(
                                        action_type="BILLING_PERIOD_CLOSED",
                                        category="billing",
                                        user_role=current_role,
                                        description=f"Billing period closed: {selected_period_name}. Revenue: ₹{billing_metrics['monthly_revenue']:,}",
                                        old_value="OPEN",
                                        new_value="CLOSED",
                                        success=True,
                                        metadata={
                                            "revenue": billing_metrics['monthly_revenue'],
                                            "assets": billing_metrics['billable_count']
                                        }
                                    )
                                    st.success(f"{selected_period_name} has been closed.")
                                    st.balloons()
                                    safe_rerun()
                                else:
                                    st.error(f"Failed to close: {error}")
                    else:
                        st.info("Only administrators can close billing periods.")

                # Period History
                st.markdown("---")
                st.markdown("##### Billing Period History")

                period_history = get_all_billing_periods(limit=12)
                if not period_history.empty:
                    # Format the dataframe for display
                    period_history["Period"] = period_history.apply(
                        lambda row: f"{month_names[int(row['Month'])]} {int(row['Year'])}", axis=1
                    )
                    period_history["Revenue"] = period_history["Revenue"].apply(
                        lambda x: f"₹{x:,.0f}" if pd.notna(x) and x > 0 else "-"
                    )

                    display_cols = ["Period", "Status", "Revenue", "Assets", "Closed By", "Closed At"]
                    available_cols = [c for c in display_cols if c in period_history.columns]

                    st.dataframe(
                        period_history[available_cols],
                                                hide_index=True,
                        column_config={
                            "Status": st.column_config.TextColumn("Status"),
                            "Closed At": st.column_config.DatetimeColumn("Closed", format="YYYY-MM-DD HH:mm"),
                        }
                    )
                else:
                    st.info("No billing periods have been closed yet.")

        # Admin Override Section
        if can_override_billing(current_role):
            st.markdown("---")
            with st.expander("Admin: Billing Override Options", expanded=False):
                # Section header
                st.markdown("""
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #ef4444;">
                    <div style="width: 4px; height: 20px; background: #ef4444; border-radius: 2px;"></div>
                    <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Custom Rate Override</span>
                </div>
                """, unsafe_allow_html=True)

                # Warning message with better styling
                st.markdown("""
                <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; border-radius: 4px; margin-bottom: 16px;">
                    <span style="color: #991b1b; font-weight: 500;">Manual overrides bypass automated billing rules. Use with caution.</span>
                </div>
                """, unsafe_allow_html=True)

                override_col1, override_col2 = st.columns([2, 1])
                with override_col1:
                    custom_rate = st.number_input(
                        "Custom Monthly Rate (₹)",
                        min_value=0,
                        value=BILLING_CONFIG["default_monthly_rate"],
                        step=500,
                        key="custom_billing_rate"
                    )

                with override_col2:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Recalculate", key="recalc_billing", type="primary"):
                        # Server-side RBAC validation (don't rely on UI hiding)
                        validation_result = validate_action("billing_override", current_role)
                        if not validation_result.success:
                            st.error(validation_result.message)
                            log_activity_event(
                                action_type="ACCESS_DENIED",
                                category="security",
                                user_role=current_role,
                                description="Unauthorized billing override attempt",
                                success=False
                            )
                        else:
                            custom_metrics = calculate_billing_metrics(ctx.assets_df, monthly_rate=custom_rate)
                            st.info(f"With ₹{custom_rate}/month: Monthly Revenue = ₹{custom_metrics['monthly_revenue']:,}")
                            # Log the override attempt
                            log_activity_event(
                                action_type="BILLING_OVERRIDE",
                                category="billing",
                                user_role=current_role,
                                description=f"Billing rate override: ₹{BILLING_CONFIG['default_monthly_rate']} -> ₹{custom_rate}",
                                old_value=str(BILLING_CONFIG['default_monthly_rate']),
                                new_value=str(custom_rate),
                                success=True
                            )

    # ACTIVITY LOG PAGE (Audit Trail)

