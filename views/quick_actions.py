"""Quick Actions page — state transitions with confirmation."""

from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st

from config.constants import ISSUE_CATEGORIES, STATUS_DISPLAY_NAMES
from config.permissions import check_page_access, render_access_denied
from services.asset_service import (
    update_asset_status, create_assignment_record,
    create_repair_record, create_issue_record,
)
from services.audit_service import log_activity_event
from components.confirmation import (
    init_action_confirmation, request_action_confirmation,
    clear_action_confirmation, render_confirmation_dialog,
)
from components.empty_states import render_empty_state, render_success_state
from components.feedback import render_error_state
from core.data import safe_rerun, clear_cache, get_table
from views.context import AppContext

try:
    from database.db import update_asset as mysql_update_asset
except ImportError:
    mysql_update_asset = None

def render(ctx: AppContext) -> None:
    """Render this page."""
    # Route-level access control (defense in depth)
    if not check_page_access("Quick Actions", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "operations"])
        st.stop()

    st.markdown('<p class="main-header">Quick Actions</p>', unsafe_allow_html=True)

    # Initialize confirmation system
    init_action_confirmation()
    current_role = st.session_state.user_role

    if not ctx.api:
        st.warning("Please configure your Airtable API key in Settings first.")
    elif st.session_state.get('data_load_error'):
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load data for Quick Actions. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    else:
        # Action options (clean labels without emojis)
        action_options = ["Assign to Client", "Receive Return", "Send to Vendor", "Complete Repair"]

        # Check if redirected from dashboard with specific tab
        quick_action_tab = st.session_state.get("quick_action_tab", None)
        default_index = 0
        if quick_action_tab:
            tab_mapping = {"ship": 0, "return": 1, "repair": 2, "repaired": 3}
            default_index = tab_mapping.get(quick_action_tab, 0)
            del st.session_state.quick_action_tab

        # Use radio for tab-like selection (supports default value)
        selected_action = st.radio(
            "Select Action",
            action_options,
            index=default_index,
            horizontal=True,
            label_visibility="collapsed"
        )

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        # SECTION 1: Assign to Client
        if selected_action == "Assign to Client":
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
                <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Assign Asset to Client</span>
            </div>
            """, unsafe_allow_html=True)

            # Get available assets (IN_STOCK_WORKING)
            available_assets = ctx.assets_df[ctx.assets_df["Current Status"] == "IN_STOCK_WORKING"] if "Current Status" in ctx.assets_df.columns else pd.DataFrame()

            if available_assets.empty:
                render_empty_state("no_stock_available", show_action=False)
            else:
                # Check if there's a pending confirmation for this action
                pending = st.session_state.get('pending_action')
                if pending and pending.get('action_type') == 'assign':
                    # Show confirmation dialog
                    confirmed, cancelled = render_confirmation_dialog(current_role)

                    if confirmed:
                        # Execute the action
                        record_id = pending['record_id']
                        extra = pending.get('extra_data', {})

                        success, error_msg = update_asset_status(record_id, "WITH_CLIENT", extra.get('client'))
                        if success:
                            assignment_data = {
                                "Assignment Name": f"{pending['asset_serial']} → {extra.get('client')}",
                                "Assignment Type": "Rental",
                                "Shipment Date": extra.get('shipment_date', date.today().isoformat()),
                                "Status": "ACTIVE"
                            }
                            if extra.get('tracking'):
                                assignment_data["Tracking Number"] = extra['tracking']

                            create_assignment_record(assignment_data, user_role=st.session_state.get('user_role', 'admin'))

                            # Enhanced audit logging for asset assignment (critical action)
                            log_activity_event(
                                action_type="ASSET_ASSIGNED",
                                category="assignment",
                                user_role=st.session_state.get('user_role', 'admin'),
                                description=f"Asset assigned to client: {pending['asset_serial']} → {extra.get('client')}",
                                serial_number=pending['asset_serial'],
                                client_name=extra.get('client'),
                                old_value="IN_STOCK_WORKING",
                                new_value="WITH_CLIENT",
                                success=True,
                                metadata={
                                    "shipment_date": extra.get('shipment_date'),
                                    "tracking_number": extra.get('tracking'),
                                    "assignment_type": "Rental"
                                }
                            )

                            clear_action_confirmation()
                            st.success(f"{pending['asset_serial']} assigned to {extra.get('client')}.")
                            st.balloons()
                            safe_rerun()
                        else:
                            # Log failed assignment attempt
                            log_activity_event(
                                action_type="ASSET_ASSIGNED",
                                category="assignment",
                                user_role=st.session_state.get('user_role', 'admin'),
                                description=f"Failed to assign asset: {pending['asset_serial']}",
                                serial_number=pending['asset_serial'],
                                client_name=extra.get('client'),
                                success=False,
                                error_message=error_msg
                            )
                            clear_action_confirmation()
                            st.error(f"Cannot assign asset: {error_msg}")

                    if cancelled:
                        safe_rerun()
                else:
                    # Show the form
                    col1, col2 = st.columns(2)

                    with col1:
                        asset_options = available_assets["Serial Number"].tolist() if "Serial Number" in available_assets.columns else []
                        selected_asset = st.selectbox("Select Asset to Ship", asset_options, key="ship_asset")

                        # Show asset details
                        if selected_asset:
                            asset_row = available_assets[available_assets["Serial Number"] == selected_asset].iloc[0]
                            st.info(f"**{asset_row.get('Brand', 'N/A')} {asset_row.get('Model', 'N/A')}** | RAM: {asset_row.get('RAM (GB)', 'N/A')}GB")

                    with col2:
                        client_options = sorted(ctx.clients_df["Client Name"].dropna().unique().tolist()) if not ctx.clients_df.empty and "Client Name" in ctx.clients_df.columns else []
                        selected_client = st.selectbox("Select Client", client_options, key="ship_client")

                    shipment_date = st.date_input("Shipment Date", value=date.today(), key="ship_date")
                    tracking = st.text_input("Tracking Number (Optional)", key="ship_tracking")

                    if st.button("Assign to Client", type="primary"):
                        if selected_asset and selected_client:
                            record_id = available_assets[available_assets["Serial Number"] == selected_asset]["_id"].iloc[0]
                            asset_row = available_assets[available_assets["Serial Number"] == selected_asset].iloc[0]

                            # Request confirmation
                            request_action_confirmation(
                                action_type="assign",
                                asset_serial=selected_asset,
                                record_id=record_id,
                                current_status="IN_STOCK_WORKING",
                                new_status="WITH_CLIENT",
                                extra_data={
                                    "client": selected_client,
                                    "shipment_date": shipment_date.isoformat(),
                                    "tracking": tracking
                                },
                                asset_info={
                                    "brand": asset_row.get('Brand', 'N/A'),
                                    "model": asset_row.get('Model', 'N/A')
                                }
                            )
                            safe_rerun()
                        else:
                            st.error("Please select both asset and client")

        # SECTION 2: Receive Return
        elif selected_action == "Receive Return":
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Receive Asset Return from Client</span>
            </div>
            """, unsafe_allow_html=True)

            # Get assets with clients
            with_client_assets = ctx.assets_df[ctx.assets_df["Current Status"] == "WITH_CLIENT"] if "Current Status" in ctx.assets_df.columns else pd.DataFrame()

            if with_client_assets.empty:
                render_success_state(
                    "No Assets With Clients",
                    "All assets are either in stock, under repair, or returned. Deploy assets to clients first."
                )
            else:
                # Check if there's a pending confirmation for this action
                pending = st.session_state.get('pending_action')
                if pending and pending.get('action_type') == 'return':
                    # Show confirmation dialog
                    confirmed, cancelled = render_confirmation_dialog(current_role)

                    if confirmed:
                        record_id = pending['record_id']
                        extra = pending.get('extra_data', {})

                        success, error_msg = update_asset_status(record_id, "RETURNED_FROM_CLIENT", "Office")
                        if success:
                            # Enhanced audit logging for asset return (critical action)
                            log_activity_event(
                                action_type="ASSET_RETURNED",
                                category="assignment",
                                user_role=st.session_state.get('user_role', 'admin'),
                                description=f"Asset returned from client: {pending['asset_serial']} ← {extra.get('client', 'Unknown')}",
                                serial_number=pending['asset_serial'],
                                client_name=extra.get('client'),
                                old_value="WITH_CLIENT",
                                new_value="RETURNED_FROM_CLIENT",
                                success=True,
                                metadata={
                                    "return_reason": extra.get('return_reason'),
                                    "has_issue": extra.get('has_issue', False),
                                    "return_date": date.today().isoformat()
                                }
                            )

                            st.success(f"{pending['asset_serial']} return received.")

                            # Create issue if reported
                            if extra.get('has_issue'):
                                issue_table = get_table("issues")
                                if issue_table:
                                    issue_table.create({
                                        "Issue Title": f"{extra.get('issue_category', 'Issue')} - {pending['asset_serial']}",
                                        "Issue Type": extra.get('issue_type', 'Software'),
                                        "Issue Category": extra.get('issue_category', 'Other'),
                                        "Description": extra.get('issue_desc', ''),
                                        "Reported Date": date.today().isoformat(),
                                        "Severity": "Medium",
                                        "Status": "Open"
                                    })
                                    st.info("Issue logged successfully")
                            clear_action_confirmation()
                            safe_rerun()
                        else:
                            # Log failed return attempt
                            log_activity_event(
                                action_type="ASSET_RETURNED",
                                category="assignment",
                                user_role=st.session_state.get('user_role', 'admin'),
                                description=f"Failed to return asset: {pending['asset_serial']}",
                                serial_number=pending['asset_serial'],
                                client_name=extra.get('client'),
                                success=False,
                                error_message=error_msg
                            )
                            clear_action_confirmation()
                            st.error(f"Cannot process return: {error_msg}")

                    if cancelled:
                        safe_rerun()
                else:
                    # Build dropdown options with client info: "SerialNumber - AssetType (ClientName)"
                    return_options_map = {}
                    for _, row in with_client_assets.iterrows():
                        serial = row.get("Serial Number", "Unknown")
                        asset_type = row.get("Asset Type", "Asset")
                        client = row.get("Current Location", "Unknown Client")
                        display_text = f"{serial} - {asset_type} ({client})"
                        return_options_map[display_text] = serial

                    return_display_options = list(return_options_map.keys())

                    # Show the form
                    col1, col2 = st.columns(2)

                    with col1:
                        selected_return_display = st.selectbox("Select Asset Being Returned", return_display_options, key="return_asset")
                        selected_return = return_options_map.get(selected_return_display) if selected_return_display else None

                    with col2:
                        return_reason = st.selectbox("Return Reason", ["End of Rental", "Issue Reported", "Client Request", "Other"], key="return_reason")

                    # Show asset details card when selected
                    if selected_return:
                        asset_row = with_client_assets[with_client_assets["Serial Number"] == selected_return].iloc[0]
                        client_name = asset_row.get('Current Location', 'Unknown')
                        asset_type = asset_row.get('Asset Type', 'N/A')
                        brand = asset_row.get('Brand', 'N/A')
                        model = asset_row.get('Model', 'N/A')

                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border: 1px solid #10b981; border-radius: 8px; padding: 16px; margin: 12px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
                                <div>
                                    <div style="font-size: 11px; color: #059669; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Currently With</div>
                                    <div style="font-size: 18px; font-weight: 600; color: #065f46;">{client_name}</div>
                                </div>
                                <div style="display: flex; gap: 24px;">
                                    <div>
                                        <div style="font-size: 11px; color: #6b7280;">Asset Type</div>
                                        <div style="font-size: 14px; font-weight: 500; color: #1f2937;">{asset_type}</div>
                                    </div>
                                    <div>
                                        <div style="font-size: 11px; color: #6b7280;">Brand / Model</div>
                                        <div style="font-size: 14px; font-weight: 500; color: #1f2937;">{brand} {model}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    has_issue = st.checkbox("Asset has an issue?", key="return_has_issue")

                    issue_type = None
                    issue_category = None
                    issue_desc = None
                    if has_issue:
                        issue_type = st.selectbox("Issue Type", ["Software", "Hardware"], key="return_issue_type")
                        issue_category = st.selectbox("Issue Category", ISSUE_CATEGORIES, key="return_issue_cat")
                        issue_desc = st.text_area("Issue Description", key="return_issue_desc")

                    if st.button("Receive Return", type="primary"):
                        if selected_return:
                            record_id = with_client_assets[with_client_assets["Serial Number"] == selected_return]["_id"].iloc[0]
                            asset_row = with_client_assets[with_client_assets["Serial Number"] == selected_return].iloc[0]

                            # Request confirmation
                            request_action_confirmation(
                                action_type="return",
                                asset_serial=selected_return,
                                record_id=record_id,
                                current_status="WITH_CLIENT",
                                new_status="RETURNED_FROM_CLIENT",
                                extra_data={
                                    "return_reason": return_reason,
                                    "has_issue": has_issue,
                                    "issue_type": issue_type,
                                    "issue_category": issue_category,
                                    "issue_desc": issue_desc,
                                    "client": asset_row.get('Current Location', 'Unknown')
                                },
                                asset_info={
                                    "brand": asset_row.get('Brand', 'N/A'),
                                    "model": asset_row.get('Model', 'N/A')
                                }
                            )
                            safe_rerun()

        # SECTION 3: Send to Vendor
        elif selected_action == "Send to Vendor":
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #f59e0b;">
                <div style="width: 4px; height: 20px; background: #f59e0b; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Send to Vendor</span>
            </div>
            """, unsafe_allow_html=True)

            # Get returned assets
            returned_assets = ctx.assets_df[ctx.assets_df["Current Status"].isin(["RETURNED_FROM_CLIENT", "IN_OFFICE_TESTING"])] if "Current Status" in ctx.assets_df.columns else pd.DataFrame()

            if returned_assets.empty:
                render_success_state(
                    "No Assets Need Repair",
                    "No returned or testing assets available to send for repair."
                )
            else:
                # Check if there's a pending confirmation for this action
                pending = st.session_state.get('pending_action')
                if pending and pending.get('action_type') == 'repair':
                    # Show confirmation dialog
                    confirmed, cancelled = render_confirmation_dialog(current_role)

                    if confirmed:
                        record_id = pending['record_id']
                        extra = pending.get('extra_data', {})

                        success, error_msg = update_asset_status(record_id, "WITH_VENDOR_REPAIR", "Vendor")
                        if success:
                            repair_ref = f"RPR-{datetime.now().strftime('%Y%m%d')}-{pending['asset_serial']}"
                            repair_data = {
                                "Repair Reference": repair_ref,
                                "Sent Date": date.today().isoformat(),
                                "Expected Return": (date.today() + timedelta(days=extra.get('expected_days', 14))).isoformat(),
                                "Repair Description": f"{extra.get('repair_issue', 'Issue')}: {extra.get('repair_desc', '')}",
                                "Status": "WITH_VENDOR"
                            }
                            create_repair_record(repair_data, user_role=st.session_state.get('user_role', 'admin'))

                            # Enhanced audit logging for repair action
                            log_activity_event(
                                action_type="REPAIR_CREATED",
                                category="asset",
                                user_role=st.session_state.get('user_role', 'admin'),
                                description=f"Asset sent for repair: {pending['asset_serial']} - {extra.get('repair_issue', 'Issue')}",
                                serial_number=pending['asset_serial'],
                                old_value=pending.get('current_status', 'RETURNED_FROM_CLIENT'),
                                new_value="WITH_VENDOR_REPAIR",
                                success=True,
                                metadata={
                                    "repair_reference": repair_ref,
                                    "repair_issue": extra.get('repair_issue'),
                                    "repair_description": extra.get('repair_desc'),
                                    "expected_days": extra.get('expected_days', 14),
                                    "sent_date": date.today().isoformat()
                                }
                            )

                            clear_action_confirmation()
                            st.success(f"{pending['asset_serial']} sent for repair.")
                            safe_rerun()
                        else:
                            # Log failed repair attempt
                            log_activity_event(
                                action_type="REPAIR_CREATED",
                                category="asset",
                                user_role=st.session_state.get('user_role', 'admin'),
                                description=f"Failed to send asset for repair: {pending['asset_serial']}",
                                serial_number=pending['asset_serial'],
                                success=False,
                                error_message=error_msg
                            )
                            clear_action_confirmation()
                            st.error(f"Cannot send for repair: {error_msg}")

                    if cancelled:
                        safe_rerun()
                else:
                    # Show the form
                    col1, col2 = st.columns(2)

                    with col1:
                        repair_options = returned_assets["Serial Number"].tolist()
                        selected_repair = st.selectbox("Select Asset", repair_options, key="repair_asset")

                    with col2:
                        repair_issue = st.selectbox("Issue Type", ISSUE_CATEGORIES, key="repair_issue")

                    repair_desc = st.text_area("Repair Description", key="repair_desc")
                    expected_days = st.number_input("Expected Repair Days", min_value=1, max_value=90, value=14)

                    if st.button("Send to Vendor", type="primary"):
                        if selected_repair:
                            record_id = returned_assets[returned_assets["Serial Number"] == selected_repair]["_id"].iloc[0]
                            asset_row = returned_assets[returned_assets["Serial Number"] == selected_repair].iloc[0]
                            current_status = asset_row.get("Current Status", "RETURNED_FROM_CLIENT")

                            # Request confirmation
                            request_action_confirmation(
                                action_type="repair",
                                asset_serial=selected_repair,
                                record_id=record_id,
                                current_status=current_status,
                                new_status="WITH_VENDOR_REPAIR",
                                extra_data={
                                    "repair_issue": repair_issue,
                                    "repair_desc": repair_desc,
                                    "expected_days": expected_days
                                },
                                asset_info={
                                    "brand": asset_row.get('Brand', 'N/A'),
                                    "model": asset_row.get('Model', 'N/A')
                                }
                            )
                            safe_rerun()

        # SECTION 4: Complete Repair
        elif selected_action == "Complete Repair":
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #8b5cf6;">
                <div style="width: 4px; height: 20px; background: #8b5cf6; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Complete Repair</span>
            </div>
            """, unsafe_allow_html=True)

            # Get assets under repair
            repair_assets = ctx.assets_df[ctx.assets_df["Current Status"] == "WITH_VENDOR_REPAIR"] if "Current Status" in ctx.assets_df.columns else pd.DataFrame()

            if repair_assets.empty:
                render_empty_state("no_repairs", show_action=False)
            else:
                # Check if there's a pending confirmation for this action
                pending = st.session_state.get('pending_action')
                if pending and pending.get('action_type') in ['fix', 'dispose']:
                    # Show confirmation dialog
                    confirmed, cancelled = render_confirmation_dialog(current_role)

                    if confirmed:
                        record_id = pending['record_id']
                        extra = pending.get('extra_data', {})
                        new_status = pending['new_status']

                        success, error_msg = update_asset_status(record_id, new_status, "Office")
                        if success:
                            outcome = extra.get('repair_outcome', 'Fixed')
                            st.success(f"{pending['asset_serial']} marked as {outcome}!")

                            # Update reuse count if fixed
                            if new_status == "IN_STOCK_WORKING":
                                current_reuse = extra.get('current_reuse', 0)
                                mysql_update_asset(int(record_id), {"Reuse Count": int(current_reuse) + 1})

                            clear_action_confirmation()
                            safe_rerun()
                        else:
                            clear_action_confirmation()
                            st.error(f"Cannot complete repair: {error_msg}")

                    if cancelled:
                        safe_rerun()
                else:
                    # Show the form
                    col1, col2 = st.columns(2)

                    with col1:
                        repaired_options = repair_assets["Serial Number"].tolist()
                        selected_repaired = st.selectbox("Select Repaired Asset", repaired_options, key="repaired_asset")

                    with col2:
                        repair_outcome = st.selectbox("Repair Outcome", ["Fixed", "Replaced", "Unrepairable"], key="repair_outcome")

                    repair_notes = st.text_area("Repair Notes", placeholder="What was fixed/replaced...", key="repair_notes")
                    repair_cost = st.number_input("Repair Cost (₹)", min_value=0, value=0, key="repair_cost")

                    if st.button("Complete Repair", type="primary"):
                        if selected_repaired:
                            record_id = repair_assets[repair_assets["Serial Number"] == selected_repaired]["_id"].iloc[0]
                            asset_row = repair_assets[repair_assets["Serial Number"] == selected_repaired].iloc[0]

                            new_status = "IN_STOCK_WORKING" if repair_outcome == "Fixed" else "DISPOSED"
                            action_type = "fix" if repair_outcome == "Fixed" else "dispose"

                            current_reuse = asset_row.get("Reuse Count", 0)
                            current_reuse = current_reuse if pd.notna(current_reuse) else 0

                            # Request confirmation
                            request_action_confirmation(
                                action_type=action_type,
                                asset_serial=selected_repaired,
                                record_id=record_id,
                                current_status="WITH_VENDOR_REPAIR",
                                new_status=new_status,
                                extra_data={
                                    "repair_outcome": repair_outcome,
                                    "repair_notes": repair_notes,
                                    "repair_cost": repair_cost,
                                    "current_reuse": current_reuse
                                },
                                asset_info={
                                    "brand": asset_row.get('Brand', 'N/A'),
                                    "model": asset_row.get('Model', 'N/A')
                                }
                            )
                            safe_rerun()

    # ADD ASSET PAGE

