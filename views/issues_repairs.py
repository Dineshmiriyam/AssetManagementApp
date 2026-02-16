"""Issues & Repairs page — issue/repair management."""

from datetime import datetime, date

import pandas as pd
import streamlit as st

from config.constants import ISSUE_CATEGORIES
from config.permissions import check_page_access, render_access_denied
from components.empty_states import render_empty_state
from core.data import safe_rerun, clear_cache, get_table, paginate_dataframe, render_page_navigation
from core.errors import log_error
from views.context import AppContext

def render(ctx: AppContext) -> None:
    """Render this page."""
    # Route-level access control (defense in depth)
    if not check_page_access("Issues & Repairs", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "operations"])
        st.stop()

    st.markdown('<p class="main-header">Issues & Repairs</p>', unsafe_allow_html=True)

    if not ctx.api:
        st.warning("Please configure your Airtable API key in Settings first.")
    else:
        tab1, tab2, tab3 = st.tabs(["Issues", "Repairs", "Log New Issue"])

        with tab1:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #ef4444;">
                <div style="width: 4px; height: 20px; background: #ef4444; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Issue Tracker</span>
            </div>
            """, unsafe_allow_html=True)

            if not ctx.issues_df.empty:
                # Search bar
                issue_search = st.text_input("🔍 Search (Issue Title, Category)", key="issue_search", placeholder="Type to search...")

                # Filter options
                icol1, icol2, icol3, icol4 = st.columns([1, 1, 1, 0.5])
                with icol1:
                    issue_status_filter = st.selectbox("Status", ["All", "Open", "In Progress", "Resolved", "Closed"], key="issue_status_filter")
                with icol2:
                    issue_type_filter = st.selectbox("Type", ["All", "Software", "Hardware"], key="issue_type_filter")
                with icol3:
                    severity_list = sorted(list(ctx.issues_df["Severity"].dropna().unique())) if "Severity" in ctx.issues_df.columns else []
                    issue_severity_filter = st.selectbox("Severity", ["All"] + severity_list, key="issue_severity_filter")
                with icol4:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Clear", key="clear_issue_filters", use_container_width=True):
                        for key in ["issue_search", "issue_status_filter", "issue_type_filter", "issue_severity_filter"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        safe_rerun()

                filtered_issues = ctx.issues_df.copy()
                if issue_status_filter != "All" and "Status" in filtered_issues.columns:
                    filtered_issues = filtered_issues[filtered_issues["Status"] == issue_status_filter]
                if issue_type_filter != "All" and "Issue Type" in filtered_issues.columns:
                    filtered_issues = filtered_issues[filtered_issues["Issue Type"] == issue_type_filter]
                if issue_severity_filter != "All" and "Severity" in filtered_issues.columns:
                    filtered_issues = filtered_issues[filtered_issues["Severity"] == issue_severity_filter]

                # Search
                if issue_search:
                    search_mask = pd.Series([False] * len(filtered_issues), index=filtered_issues.index)
                    if "Issue Title" in filtered_issues.columns:
                        search_mask |= filtered_issues["Issue Title"].str.contains(issue_search, case=False, na=False)
                    if "Issue Category" in filtered_issues.columns:
                        search_mask |= filtered_issues["Issue Category"].str.contains(issue_search, case=False, na=False)
                    filtered_issues = filtered_issues[search_mask]

                display_cols = ["Issue Title", "Issue Type", "Issue Category", "Severity", "Status", "Reported Date"]
                available_cols = [c for c in display_cols if c in filtered_issues.columns]

                # Results count
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                    <span style="font-size: 14px; color: #374151; font-weight: 500;">Showing</span>
                    <span style="font-size: 16px; color: #ef4444; font-weight: 700;">{len(filtered_issues)}</span>
                    <span style="font-size: 14px; color: #6b7280;">of {len(ctx.issues_df)} issues</span>
                </div>
                """, unsafe_allow_html=True)

                # Quick View Asset Panel - Linked Records Navigation
                with st.expander("🔗 Quick View Related Asset", expanded=False):
                    # Check if there's an Asset Serial column in issues
                    serial_col = None
                    for col in ["Asset Serial", "Serial Number", "Asset_Serial"]:
                        if col in filtered_issues.columns:
                            serial_col = col
                            break

                    if serial_col and len(filtered_issues) > 0:
                        serial_options = filtered_issues[serial_col].dropna().unique().tolist()
                        if serial_options:
                            iqv_col1, iqv_col2 = st.columns([3, 1])
                            with iqv_col1:
                                selected_issue_serial = st.selectbox(
                                    "Select Asset Serial from Issues",
                                    options=serial_options,
                                    key="issue_quick_view_serial"
                                )
                            with iqv_col2:
                                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("🔍 View Asset", key="issue_view_asset_btn", use_container_width=True):
                                    st.session_state.current_page = "Assets"
                                    st.session_state.asset_search_serial = selected_issue_serial
                                    safe_rerun()

                            # Show asset details if available
                            if selected_issue_serial and not ctx.assets_df.empty:
                                asset_info = ctx.assets_df[ctx.assets_df["Serial Number"] == selected_issue_serial]
                                if not asset_info.empty:
                                    asset_row = asset_info.iloc[0]
                                    st.markdown("---")
                                    st.markdown("**Asset Details:**")
                                    detail_col1, detail_col2, detail_col3 = st.columns(3)
                                    with detail_col1:
                                        st.markdown(f"**Serial:** {asset_row.get('Serial Number', 'N/A')}")
                                        st.markdown(f"**Type:** {asset_row.get('Asset Type', 'N/A')}")
                                    with detail_col2:
                                        st.markdown(f"**Brand:** {asset_row.get('Brand', 'N/A')}")
                                        st.markdown(f"**Model:** {asset_row.get('Model', 'N/A')}")
                                    with detail_col3:
                                        st.markdown(f"**Status:** {asset_row.get('Current Status', 'N/A')}")
                                        st.markdown(f"**Location:** {asset_row.get('Current Location', 'N/A')}")
                        else:
                            st.info("No asset serials in current issues")
                    else:
                        st.info("Issue records don't have linked asset serial numbers")

                # Apply pagination
                paginated_issues = paginate_dataframe(filtered_issues, "issues_table", show_controls=True)
                st.dataframe(paginated_issues[available_cols], hide_index=True)
                render_page_navigation("issues_table")

                # Export
                exp_c1, exp_c2, exp_spacer = st.columns([1, 1, 3])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                with exp_c1:
                    try:
                        from database.excel_utils import export_dataframe_to_excel
                        excel_buf = export_dataframe_to_excel(filtered_issues, "Issues")
                        st.download_button("📥 Excel", excel_buf.getvalue(),
                            f"issues_{timestamp}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
                    except Exception:
                        pass
                with exp_c2:
                    st.download_button("📥 CSV", filtered_issues.to_csv(index=False),
                        f"issues_{timestamp}.csv", "text/csv",
                        use_container_width=True)
            else:
                render_empty_state("no_issues", show_action=False)

        with tab2:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #f59e0b;">
                <div style="width: 4px; height: 20px; background: #f59e0b; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Repair Records</span>
            </div>
            """, unsafe_allow_html=True)

            if not ctx.repairs_df.empty:
                display_cols = ["Repair Reference", "Sent Date", "Received Date", "Status", "Repair Description"]
                available_cols = [c for c in display_cols if c in ctx.repairs_df.columns]

                # Results count
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                    <span style="font-size: 14px; color: #374151; font-weight: 500;">Total</span>
                    <span style="font-size: 16px; color: #f59e0b; font-weight: 700;">{len(ctx.repairs_df)}</span>
                    <span style="font-size: 14px; color: #6b7280;">repair records</span>
                </div>
                """, unsafe_allow_html=True)
                # Apply pagination
                paginated_repairs = paginate_dataframe(ctx.repairs_df, "repairs_table", show_controls=True)
                st.dataframe(paginated_repairs[available_cols], hide_index=True)
                render_page_navigation("repairs_table")

                # Export
                exp_c1, exp_c2, exp_spacer = st.columns([1, 1, 3])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                with exp_c1:
                    try:
                        from database.excel_utils import export_dataframe_to_excel
                        excel_buf = export_dataframe_to_excel(ctx.repairs_df, "Repairs")
                        st.download_button("📥 Excel", excel_buf.getvalue(),
                            f"repairs_{timestamp}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
                    except Exception:
                        pass
                with exp_c2:
                    st.download_button("📥 CSV", ctx.repairs_df.to_csv(index=False),
                        f"repairs_{timestamp}.csv", "text/csv",
                        use_container_width=True)
            else:
                render_empty_state("no_repairs", show_action=False)

        with tab3:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Log New Issue</span>
            </div>
            """, unsafe_allow_html=True)

            with st.form("log_issue_form"):
                col1, col2 = st.columns(2)

                with col1:
                    issue_title = st.text_input("Issue Title *", placeholder="e.g., Blue screen error")
                    asset_options = ctx.assets_df["Serial Number"].tolist() if not ctx.assets_df.empty and "Serial Number" in ctx.assets_df.columns else []
                    selected_asset = st.selectbox("Select Asset *", [""] + asset_options)
                    issue_type = st.selectbox("Issue Type *", ["Software", "Hardware"])

                with col2:
                    reported_date = st.date_input("Reported Date", value=date.today())
                    issue_category = st.selectbox("Issue Category", [""] + ISSUE_CATEGORIES)
                    severity = st.selectbox("Severity *", ["Low", "Medium", "High", "Critical"])

                description = st.text_area("Description", placeholder="Describe the issue in detail...")

                submitted = st.form_submit_button("Log Issue", type="primary")

                if submitted:
                    if not issue_title or not selected_asset:
                        st.error("Issue Title and Asset are required!")
                    else:
                        record = {
                            "Issue Title": issue_title,
                            "Issue Type": issue_type,
                            "Severity": severity,
                            "Status": "Open",
                            "Reported Date": reported_date.isoformat()
                        }

                        if issue_category: record["Issue Category"] = issue_category
                        if description: record["Description"] = description

                        try:
                            table = get_table("issues")
                            table.create(record)
                            clear_cache(["issues"])  # Targeted invalidation
                            st.success("Issue logged successfully!")
                        except Exception as e:
                            error_id = log_error(e, "create_issue_airtable", st.session_state.get('user_role'))
                            st.error(f"Unable to log issue. Please try again. (Ref: {error_id})")

    # CLIENTS PAGE

