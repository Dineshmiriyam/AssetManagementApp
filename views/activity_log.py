"""Activity Log page — audit trail and event history."""

from datetime import datetime, date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from config.constants import CRITICAL_ACTIONS, STATUS_DISPLAY_NAMES
from services.audit_service import get_audit_summary, log_activity_event
from components.empty_states import render_empty_state
from components.feedback import render_error_state
from core.data import safe_rerun, paginate_dataframe, render_page_navigation
from core.errors import log_error
from views.context import AppContext

try:
    from database.db import (
        get_activity_log as db_get_activity_log,
        get_activity_stats as db_get_activity_stats,
        ACTION_TYPES,
    )
except ImportError:
    db_get_activity_log = None
    db_get_activity_stats = None
    ACTION_TYPES = {}

def render(ctx: AppContext) -> None:
    """Render this page."""
    st.markdown('<p class="main-header">Activity Log</p>', unsafe_allow_html=True)

    current_role = st.session_state.user_role

    # Role-based description
    role_descriptions = {
        "admin": "Full activity feed - all actions across the system",
        "operations": "Your operations activities - state changes, repairs, issues",
        "finance": "Billing-related activities - assignments, returns, payments"
    }
    st.caption(role_descriptions.get(current_role, "Activity history"))

    # Activity Log is IMMUTABLE - show notice
    st.markdown("""
    <div style="background: #f0fdf4; border: 1px solid #22c55e; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            <strong style="color: #166534;">Immutable Audit Trail</strong>
        </div>
        <span style="color: #15803d; font-size: 0.85rem; margin-left: 28px;">
            Append-only log. All actions are permanently recorded with unique audit IDs for compliance.
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Audit Summary Statistics (from session log)
    audit_summary = get_audit_summary()
    session_logs = st.session_state.get('activity_log', [])

    if session_logs:
        # Count by severity
        critical_count = len([e for e in session_logs if e.get('severity') == 'critical'])
        high_count = len([e for e in session_logs if e.get('severity') == 'high'])
        failed_count = len([e for e in session_logs if not e.get('success', True)])
        billing_count = len([e for e in session_logs if e.get('billing_impact', False)])

        summary_cols = st.columns(5)
        with summary_cols[0]:
            st.markdown(f"""
            <div style="text-align: center; padding: 8px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div style="font-size: 1.5rem; font-weight: 700; color: #1e293b;">{len(session_logs)}</div>
                <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase;">Total</div>
            </div>
            """, unsafe_allow_html=True)
        with summary_cols[1]:
            critical_bg = "#fef2f2" if critical_count > 0 else "#f8fafc"
            critical_color = "#dc2626" if critical_count > 0 else "#64748b"
            st.markdown(f"""
            <div style="text-align: center; padding: 8px; background: {critical_bg}; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div style="font-size: 1.5rem; font-weight: 700; color: {critical_color};">{critical_count}</div>
                <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase;">Critical</div>
            </div>
            """, unsafe_allow_html=True)
        with summary_cols[2]:
            high_bg = "#fff7ed" if high_count > 0 else "#f8fafc"
            high_color = "#ea580c" if high_count > 0 else "#64748b"
            st.markdown(f"""
            <div style="text-align: center; padding: 8px; background: {high_bg}; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div style="font-size: 1.5rem; font-weight: 700; color: {high_color};">{high_count}</div>
                <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase;">High</div>
            </div>
            """, unsafe_allow_html=True)
        with summary_cols[3]:
            failed_bg = "#fef2f2" if failed_count > 0 else "#f8fafc"
            failed_color = "#ef4444" if failed_count > 0 else "#64748b"
            st.markdown(f"""
            <div style="text-align: center; padding: 8px; background: {failed_bg}; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div style="font-size: 1.5rem; font-weight: 700; color: {failed_color};">{failed_count}</div>
                <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase;">Failed</div>
            </div>
            """, unsafe_allow_html=True)
        with summary_cols[4]:
            billing_bg = "#fef3c7" if billing_count > 0 else "#f8fafc"
            billing_color = "#d97706" if billing_count > 0 else "#64748b"
            st.markdown(f"""
            <div style="text-align: center; padding: 8px; background: {billing_bg}; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div style="font-size: 1.5rem; font-weight: 700; color: {billing_color};">{billing_count}</div>
                <div style="font-size: 0.75rem; color: #64748b; text-transform: uppercase;">Billing</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Check data source
    if ctx.data_source == "mysql" and ctx.mysql_available:
        # ========== MySQL-based Activity Log ==========

        # Filters
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

        with filter_col1:
            days_filter = st.selectbox(
                "Time Period",
                options=[1, 7, 14, 30, 90],
                index=1,
                format_func=lambda x: f"Last {x} day{'s' if x > 1 else ''}",
                key="activity_days"
            )

        with filter_col2:
            category_options = ["All", "asset", "assignment", "client", "billing", "system"]
            category_filter = st.selectbox(
                "Category",
                options=category_options,
                key="activity_category"
            )

        with filter_col3:
            # Role-based success filter
            if current_role == "admin":
                success_options = ["All", "Successful", "Failed"]
                success_filter = st.selectbox("Status", options=success_options, key="activity_success")
            else:
                success_filter = "All"
                st.text_input("Status", value="All", disabled=True, key="activity_success_ro")

        with filter_col4:
            limit_options = [20, 50, 100, 200]
            limit = st.selectbox("Show", options=limit_options, index=1, format_func=lambda x: f"{x} entries", key="activity_limit")

        # Statistics (Admin sees full stats, others see limited)
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Activity Summary</span>
        </div>
        """, unsafe_allow_html=True)

        try:
            stats = db_get_activity_stats(days_back=days_filter)

            if stats:
                stat_cols = st.columns(4 if current_role == "admin" else 3)

                with stat_cols[0]:
                    st.metric("Total Activities", stats.get('total_activities', 0))

                if current_role == "admin":
                    with stat_cols[1]:
                        st.metric("Failed Actions", stats.get('failed', 0),
                                  delta=None if stats.get('failed', 0) == 0 else f"{stats.get('failed', 0)} blocked")

                    with stat_cols[2]:
                        st.metric("Billing Events", stats.get('billing_related', 0))

                    with stat_cols[3]:
                        # Most active role
                        by_role = stats.get('by_role', {})
                        if by_role:
                            top_role = max(by_role, key=by_role.get)
                            st.metric("Most Active Role", top_role.title(), delta=f"{by_role[top_role]} actions")
                        else:
                            st.metric("Most Active Role", "N/A")

                elif current_role == "finance":
                    with stat_cols[1]:
                        st.metric("Billing Events", stats.get('billing_related', 0))

                    with stat_cols[2]:
                        by_type = stats.get('by_type', {})
                        assignment_count = by_type.get('ASSIGNMENT_CREATED', 0) + by_type.get('ASSIGNMENT_COMPLETED', 0)
                        st.metric("Assignment Changes", assignment_count)

                else:  # operations
                    with stat_cols[1]:
                        by_type = stats.get('by_type', {})
                        state_changes = by_type.get('STATE_CHANGE', 0)
                        st.metric("State Changes", state_changes)

                    with stat_cols[2]:
                        repair_count = by_type.get('REPAIR_CREATED', 0) + by_type.get('REPAIR_COMPLETED', 0)
                        st.metric("Repair Activities", repair_count)

        except Exception as e:
            st.warning(f"Could not load statistics: {e}")

        st.markdown("---")

        # Fetch activity log with role-based filters
        try:
            # Apply role-based filtering
            role_filter = None
            billing_only = False

            if current_role == "operations":
                # Operations sees only their own actions
                role_filter = "operations"
            elif current_role == "finance":
                # Finance sees only billing-related events
                billing_only = True

            # Apply UI filters
            cat_param = None if category_filter == "All" else category_filter
            success_param = None
            if success_filter == "Successful":
                success_param = True
            elif success_filter == "Failed":
                success_param = False

            activity_df = db_get_activity_log(
                limit=limit,
                role_filter=role_filter,
                category_filter=cat_param,
                billing_only=billing_only,
                success_only=success_param,
                days_back=days_filter
            )

            if not activity_df.empty:
                # Format for display
                st.markdown("""
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                    <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                    <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Audit Trail</span>
                </div>
                """, unsafe_allow_html=True)

                # Severity color mapping
                severity_colors = {
                    "critical": {"bg": "#fef2f2", "text": "#dc2626", "border": "#ef4444"},
                    "high": {"bg": "#fff7ed", "text": "#c2410c", "border": "#f97316"},
                    "medium": {"bg": "#fefce8", "text": "#a16207", "border": "#eab308"},
                    "low": {"bg": "#f0fdf4", "text": "#15803d", "border": "#22c55e"}
                }

                # Display as cards for better readability
                for idx, row in activity_df.iterrows():
                    timestamp = row['Timestamp']
                    if hasattr(timestamp, 'strftime'):
                        time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        time_str = str(timestamp)[:19]

                    success = row['Success']
                    status_color = "#22c55e" if success else "#ef4444"
                    status_text = "Success" if success else "Failed"
                    status_bg = "#dcfce7" if success else "#fee2e2"

                    action = row['Action'] or "Unknown"
                    category = row['Category'] or ""
                    asset = row['Asset'] or ""
                    client = row['Client'] or ""
                    from_val = row['From'] or ""
                    to_val = row['To'] or ""
                    role = row['Role'] or ""
                    description = row['Description'] or ""
                    error = row['Error'] or ""
                    billing_impact = row['Billing Impact']

                    # Get severity from action type
                    action_config = CRITICAL_ACTIONS.get(action, {"severity": "low", "billing_impact": False})
                    severity = action_config["severity"]
                    severity_style = severity_colors.get(severity, severity_colors["low"])
                    is_critical = severity in ["critical", "high"]

                    # Build detail string
                    details = []
                    if asset:
                        details.append(f"Asset: {asset}")
                    if client:
                        details.append(f"Client: {client}")
                    if from_val and to_val:
                        from_display = STATUS_DISPLAY_NAMES.get(from_val, from_val)
                        to_display = STATUS_DISPLAY_NAMES.get(to_val, to_val)
                        details.append(f"{from_display} → {to_display}")

                    detail_str = " | ".join(details) if details else description

                    # Badge HTML
                    badges_html = ""

                    # Severity badge
                    severity_badge = f'<span style="background:{severity_style["bg"]};color:{severity_style["text"]};padding:2px 6px;border-radius:4px;font-size:0.7rem;font-weight:500;text-transform:uppercase;margin-left:4px;">{severity}</span>'
                    badges_html += severity_badge

                    # Billing impact badge
                    if billing_impact:
                        badges_html += '<span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-left:4px;">Billing</span>'

                    # Error section
                    error_html = f'<div style="background:#fef2f2;color:#ef4444;font-size:0.85rem;margin-top:8px;padding:8px;border-radius:4px;">Error: {error}</div>' if error else ""

                    # Audit metadata section (for critical actions)
                    audit_metadata_html = ""
                    if is_critical or not success:
                        # Generate audit reference for display
                        audit_ref = f"AUD-{timestamp.strftime('%Y%m%d%H%M%S') if hasattr(timestamp, 'strftime') else 'UNKNOWN'}"
                        audit_metadata_html = (
                            f'<div style="background:#f8fafc;border-top:1px solid #e2e8f0;margin-top:10px;padding:10px;border-radius:0 0 4px 4px;">'
                            f'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">'
                            f'<div style="font-size:0.75rem;color:#64748b;"><span style="font-weight:600;">Audit Ref:</span> {audit_ref}</div>'
                            f'<div style="font-size:0.75rem;color:#64748b;"><span style="font-weight:600;">Performed By:</span> {role}</div>'
                            f'<div style="font-size:0.75rem;color:#64748b;"><span style="font-weight:600;">Affected Asset:</span> {asset or "N/A"}</div>'
                            f'</div></div>'
                        )

                    # Critical action highlight
                    card_border = severity_style["border"] if is_critical else status_color
                    card_bg = "#fffbeb" if is_critical and not success else "#ffffff"

                    card_html = (
                        f'<div style="background:{card_bg};border:1px solid #e2e8f0;border-left:4px solid {card_border};border-radius:6px;padding:12px;margin-bottom:8px;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">'
                        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
                        f'<span style="font-weight:600;color:#1e293b;">{action}</span>'
                        f'<span style="background:{status_bg};color:{status_color};padding:2px 8px;border-radius:4px;font-size:0.7rem;font-weight:500;">{status_text}</span>'
                        f'{badges_html}'
                        f'</div>'
                        f'<span style="font-size:0.75rem;color:#64748b;font-family:monospace;">{time_str}</span>'
                        f'</div>'
                        f'<div style="color:#475569;font-size:0.9rem;margin-top:8px;">{detail_str}</div>'
                        f'<div style="color:#94a3b8;font-size:0.8rem;margin-top:6px;">Category: {category}</div>'
                        f'{error_html}'
                        f'{audit_metadata_html}'
                        f'</div>'
                    )

                    st.markdown(card_html, unsafe_allow_html=True)

                # Export option (Admin only)
                if current_role == "admin":
                    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                    csv = activity_df.to_csv(index=False)
                    st.download_button(
                        label="Export Activity Log",
                        data=csv,
                        file_name=f"activity_log_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            else:
                render_empty_state("no_activity", show_action=False)

        except Exception as e:
            error_id = log_error(e, "load_activity_log", st.session_state.get('user_role'))
            st.error(f"Unable to load activity log. Please try again. (Ref: {error_id})")

    else:
        # ========== Session-based Activity Log (Airtable mode) ==========
        st.warning("Full activity log requires MySQL. Showing session-based log only.")

        # Show session state log
        if 'state_change_log' in st.session_state and st.session_state.state_change_log:
            log_data = st.session_state.state_change_log

            # Apply role-based filtering for session log too
            if current_role == "operations":
                log_data = [l for l in log_data if l['user_role'] == 'operations']
            elif current_role == "finance":
                # Finance sees state changes that affect billing
                billing_states = ["WITH_CLIENT", "RETURNED_FROM_CLIENT", "SOLD"]
                log_data = [l for l in log_data if l['old_status'] in billing_states or l['new_status'] in billing_states]

            if log_data:
                # Summary
                total = len(log_data)
                successful = len([l for l in log_data if l['success']])
                failed = len([l for l in log_data if not l['success']])

                col1, col2, col3 = st.columns(3)
                col1.metric("Total", total)
                col2.metric("Successful", successful)
                col3.metric("Blocked", failed)

                st.markdown("---")

                # Display entries
                for entry in reversed(log_data[-20:]):
                    timestamp = entry['timestamp'][:16].replace('T', ' ')
                    icon = "✅" if entry['success'] else "❌"
                    old_display = STATUS_DISPLAY_NAMES.get(entry['old_status'], entry['old_status'])
                    new_display = STATUS_DISPLAY_NAMES.get(entry['new_status'], entry['new_status'])

                    if entry['success']:
                        st.markdown(f"**{icon} {timestamp}** | `{entry['serial_number']}` | {old_display} → {new_display} | Role: {entry['user_role']}")
                    else:
                        st.markdown(f"**{icon} {timestamp}** | `{entry['serial_number']}` | {old_display} → {new_display} | **BLOCKED**: {entry['error_message']}")
            else:
                render_empty_state("no_activity", show_action=False)
        else:
            render_empty_state("no_activity", show_action=False)

    # USER MANAGEMENT PAGE

