"""Settings page — system configuration and credentials."""

import os

import pandas as pd
import streamlit as st

from config.constants import (
    USER_ROLES, ALLOWED_TRANSITIONS, STATUS_DISPLAY_NAMES, BILLING_CONFIG,
)
from config.permissions import check_page_access, render_access_denied, get_permitted_actions, ACTION_DISPLAY_NAMES
from services.audit_service import log_activity_event
from core.data import safe_rerun, clear_cache, get_table
from core.errors import log_error
from views.context import AppContext

try:
    from database.db import (
        DatabaseConnection, setup_database, check_tables_exist,
        get_table_stats, create_asset as mysql_create_asset,
    )
    from database.config import DB_CONFIG
except ImportError:
    DatabaseConnection = None
    DB_CONFIG = {}

try:
    from core.data import get_airtable_api
except ImportError:
    get_airtable_api = None

def render(ctx: AppContext) -> None:
    """Render this page."""
    # Route-level access control (defense in depth)
    if not check_page_access("Settings", st.session_state.user_role):
        render_access_denied(required_roles=["admin"])
        st.stop()

    st.markdown('<p class="main-header">Settings</p>', unsafe_allow_html=True)

    # Data Source Configuration
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
        <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Data Source Configuration</span>
    </div>
    """, unsafe_allow_html=True)

    source_col1, source_col2 = st.columns(2)
    with source_col1:
        current_source = "MySQL" if ctx.data_source == "mysql" else "Airtable"
        source_badge_color = "#10b981" if ctx.data_source == "mysql" else "#f59e0b"
        st.markdown(f"""
        <div style="background: {source_badge_color}; color: white; padding: 10px 20px;
                    border-radius: 8px; text-align: center; font-weight: bold;">
            Active Data Source: {current_source}
        </div>
        """, unsafe_allow_html=True)

    with source_col2:
        mysql_status = "Available" if ctx.mysql_available else "Not configured"
        mysql_status_color = "#10b981" if ctx.mysql_available else "#ef4444"
        st.markdown(f"""
        <div style="background: #1e293b; color: white; padding: 10px 20px;
                    border-radius: 8px; text-align: center;">
            MySQL Module: <span style="color: {mysql_status_color}; font-weight: 600;">{mysql_status}</span>
        </div>
        """, unsafe_allow_html=True)

    st.caption("To switch data source, set the `ctx.data_source` environment variable to 'mysql' or 'airtable'")

    st.markdown("---")

    # MySQL Connection (if available)
    if ctx.mysql_available:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
            <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">MySQL Connection</span>
        </div>
        """, unsafe_allow_html=True)

        mysql_col1, mysql_col2 = st.columns(2)
        with mysql_col1:
            st.text_input("Host", value=DB_CONFIG.get('host', 'localhost'), disabled=True, key="mysql_host")
            st.text_input("Database", value=DB_CONFIG.get('database', 'assetmgmt_db'), disabled=True, key="mysql_db")

        with mysql_col2:
            st.text_input("Port", value=str(DB_CONFIG.get('port', 3306)), disabled=True, key="mysql_port")
            st.text_input("User", value=DB_CONFIG.get('user', ''), disabled=True, key="mysql_user")

        if st.button("Test MySQL Connection", key="test_mysql"):
            success, message = DatabaseConnection.test_connection()
            if success:
                st.success(f"MySQL: {message}")
            else:
                st.error(f"MySQL: {message}")

        st.markdown("---")

        # Database Tables Status
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #8b5cf6;">
            <div style="width: 4px; height: 20px; background: #8b5cf6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Database Tables Status</span>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Check Tables", key="check_tables"):
            table_stats = get_table_stats()
            if table_stats:
                st.success("Database tables found!")
                for table, count in table_stats.items():
                    if count >= 0:
                        st.write(f"✅ **{table}**: {count} rows")
                    else:
                        st.write(f"❌ **{table}**: Not found")
            else:
                st.error("Could not connect to database")

        col_setup, col_migrate = st.columns(2)
        with col_setup:
            if st.button("Setup/Create Tables", key="setup_tables"):
                success, message = setup_database()
                if success:
                    st.success(message)
                else:
                    st.error(message)

        with col_migrate:
            if st.button("Migrate from Airtable", key="migrate_data"):
                st.session_state.show_migration = True

        # Migration Dialog
        if st.session_state.get('show_migration', False):
            st.warning("⚠️ This will copy all data from Airtable to MySQL. Existing MySQL data will NOT be deleted.")
            if st.button("Confirm Migration", key="confirm_migrate", type="primary"):
                with st.spinner("Migrating data from Airtable to MySQL..."):
                    try:
                        # Get Airtable data
                        airtable_api = get_airtable_api()
                        if not airtable_api:
                            st.error("Airtable API not configured")
                        else:
                            base = airtable_api.base(ctx.airtable_base_id)

                            # Migrate Assets
                            st.write("Migrating assets...")
                            assets_table = base.table("Assets")
                            assets = assets_table.all()
                            migrated_assets = 0
                            for record in assets:
                                fields = record.get('fields', {})
                                try:
                                    mysql_create_asset({
                                        'Serial Number': fields.get('Serial Number', ''),
                                        'Asset Type': fields.get('Asset Type', 'Laptop'),
                                        'Brand': fields.get('Brand', ''),
                                        'Model': fields.get('Model', ''),
                                        'Current Status': fields.get('Current Status', 'IN_STOCK_WORKING'),
                                        'Current Location': fields.get('Current Location', ''),
                                        'Specs': fields.get('Specs', ''),
                                        'RAM (GB)': fields.get('RAM (GB)', 0),
                                        'Storage (GB)': fields.get('Storage (GB)', 0),
                                        'Storage Type': fields.get('Storage Type', ''),
                                        'Processor': fields.get('Processor', ''),
                                        'Touch Screen': fields.get('Touch Screen', False),
                                        'OS Installed': fields.get('OS Installed', ''),
                                        'Notes': fields.get('Notes', '')
                                    })
                                    migrated_assets += 1
                                except Exception as e:
                                    st.write(f"Skipped asset: {fields.get('Serial Number', 'Unknown')} - {str(e)[:50]}")

                            # Migrate Clients
                            st.write("Migrating clients...")
                            clients_table = base.table("Clients")
                            clients = clients_table.all()
                            migrated_clients = 0
                            for record in clients:
                                fields = record.get('fields', {})
                                try:
                                    from database.db import create_client
                                    create_client({
                                        'Client Name': fields.get('Client Name', ''),
                                        'Contact Person': fields.get('Contact Person', ''),
                                        'Email': fields.get('Email', ''),
                                        'Phone': fields.get('Phone', ''),
                                        'Address': fields.get('Address', ''),
                                        'City': fields.get('City', ''),
                                        'State': fields.get('State', ''),
                                        'Status': fields.get('Status', 'ACTIVE')
                                    })
                                    migrated_clients += 1
                                except Exception as e:
                                    st.write(f"Skipped client: {fields.get('Client Name', 'Unknown')} - {str(e)[:50]}")

                            st.success(f"Migration complete! Migrated {migrated_assets} assets and {migrated_clients} clients.")
                            st.session_state.show_migration = False
                            # Mark data as stale to force refresh
                            st.session_state.data_stale = True
                            st.info("Please refresh the page or go to Dashboard to see the migrated data.")
                    except Exception as e:
                        st.error(f"Migration error: {str(e)}")

            if st.button("Cancel", key="cancel_migrate"):
                st.session_state.show_migration = False
                st.rerun()

        st.markdown("---")

    # Airtable Connection
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #f59e0b;">
        <div style="width: 4px; height: 20px; background: #f59e0b; border-radius: 2px;"></div>
        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Airtable Connection</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Base ID", value=ctx.airtable_base_id, disabled=True)

    with col2:
        api_status = "Connected" if ctx.api else "Not configured"
        st.text_input("API Status", value=api_status, disabled=True)

    if st.button("Test Airtable Connection", key="test_airtable"):
        if ctx.api:
            try:
                table = get_table("assets")
                records = table.all()
                st.success(f"Connection successful! Found {len(records)} assets.")
            except Exception as e:
                error_id = log_error(e, "test_airtable_connection", st.session_state.get('user_role'))
                st.error(f"Connection failed. Please check your API credentials. (Ref: {error_id})")
        else:
            st.error("API key not configured")

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #8b5cf6;">
        <div style="width: 4px; height: 20px; background: #8b5cf6; border-radius: 2px;"></div>
        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Data Summary</span>
    </div>
    """, unsafe_allow_html=True)

    if ctx.api:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Assets", len(ctx.assets_df))
        col2.metric("Clients", len(ctx.clients_df))
        col3.metric("Issues", len(ctx.issues_df))
        col4.metric("Repairs", len(ctx.repairs_df))

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #6b7280;">
        <div style="width: 4px; height: 20px; background: #6b7280; border-radius: 2px;"></div>
        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Quick Links</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    - [Open Airtable Base](https://airtable.com/{ctx.airtable_base_id})
    - [Airtable API Tokens](https://airtable.com/create/tokens)
    """)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Role Permissions Display
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #8b5cf6;">
        <div style="width: 4px; height: 20px; background: #8b5cf6; border-radius: 2px;"></div>
        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Role-Based Access Control (RBAC)</span>
    </div>
    """, unsafe_allow_html=True)

    st.caption("Server-side permission enforcement is active. Actions are validated regardless of UI state.")

    # Show all roles and their permissions
    for role_key, role_info in USER_ROLES.items():
        is_current = role_key == st.session_state.user_role
        badge_style = "background: #10b981; color: white;" if is_current else "background: #e2e8f0; color: #475569;"

        with st.expander(f"{role_info['name']} {'(Current)' if is_current else ''}", expanded=is_current):
            st.markdown(f"<p style='color: #64748b; margin-bottom: 12px;'>{role_info['description']}</p>", unsafe_allow_html=True)

            # Get permitted actions for this role
            permitted_actions = get_permitted_actions(role_key)

            # Categorize permissions
            action_categories = {
                "Asset Management": ["create_asset", "edit_asset", "delete_asset"],
                "Lifecycle Actions": ["assign_to_client", "receive_return", "send_for_repair", "mark_repaired", "change_status"],
                "Issues & Repairs": ["log_issue", "create_repair"],
                "Billing": ["billing_override", "view_billing", "view_revenue"]
            }

            for category, actions in action_categories.items():
                st.markdown(f"**{category}**")
                cols = st.columns(len(actions))
                for i, action in enumerate(actions):
                    action_name = ACTION_DISPLAY_NAMES.get(action, action.replace("_", " ").title())
                    if action in permitted_actions:
                        cols[i].markdown(f"<span style='color: #10b981;'>Allowed</span> {action_name}", unsafe_allow_html=True)
                    else:
                        cols[i].markdown(f"<span style='color: #ef4444;'>Denied</span> {action_name}", unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # State Change Audit Log
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #ef4444;">
        <div style="width: 4px; height: 20px; background: #ef4444; border-radius: 2px;"></div>
        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Lifecycle State Change Log</span>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Audit trail of all asset status transitions (session-based)")

    if 'state_change_log' in st.session_state and st.session_state.state_change_log:
        log_data = st.session_state.state_change_log

        # Summary metrics
        total_changes = len(log_data)
        successful = len([l for l in log_data if l['success']])
        failed = len([l for l in log_data if not l['success']])

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Attempts", total_changes)
        col2.metric("Successful", successful, delta=None)
        col3.metric("Blocked", failed, delta=None if failed == 0 else f"{failed} invalid")

        # Show log entries (most recent first)
        with st.expander("View Log Entries", expanded=False):
            for entry in reversed(log_data[-20:]):  # Show last 20 entries
                timestamp = entry['timestamp'][:19].replace('T', ' ')
                old_display = STATUS_DISPLAY_NAMES.get(entry['old_status'], entry['old_status'])
                new_display = STATUS_DISPLAY_NAMES.get(entry['new_status'], entry['new_status'])

                if entry['success']:
                    st.markdown(f"""
                    <div style="background:#ecfdf5;border-left:3px solid #10b981;padding:8px 12px;margin-bottom:6px;border-radius:4px;">
                        <span style="font-weight:600;color:#065f46;">{timestamp}</span> |
                        <code style="background:#d1fae5;padding:2px 6px;border-radius:3px;">{entry['serial_number']}</code> |
                        {old_display} → {new_display} | Role: {entry['user_role']}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background:#fef2f2;border-left:3px solid #ef4444;padding:8px 12px;margin-bottom:6px;border-radius:4px;">
                        <span style="font-weight:600;color:#991b1b;">{timestamp}</span> |
                        <code style="background:#fee2e2;padding:2px 6px;border-radius:3px;">{entry['serial_number']}</code> |
                        {old_display} → {new_display} | <strong style="color:#ef4444;">BLOCKED</strong>: {entry['error_message']}
                    </div>
                    """, unsafe_allow_html=True)

        # Clear log button
        if st.button("Clear Log", key="clear_log_btn"):
            st.session_state.state_change_log = []
            safe_rerun()
    else:
        st.info("No state changes recorded in this session")

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Allowed Transitions Reference
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #06b6d4;">
        <div style="width: 4px; height: 20px; background: #06b6d4; border-radius: 2px;"></div>
        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Lifecycle Transition Rules</span>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Reference: Allowed state transitions for assets")

    with st.expander("View Allowed Transitions", expanded=False):
        for from_status, to_statuses in ALLOWED_TRANSITIONS.items():
            from_display = STATUS_DISPLAY_NAMES.get(from_status, from_status)
            if to_statuses:
                to_display = [STATUS_DISPLAY_NAMES.get(s, s) for s in to_statuses]
                st.markdown(f"**{from_display}** → {', '.join(to_display)}")
            else:
                st.markdown(f"**{from_display}** → _(terminal state)_")

