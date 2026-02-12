"""Assignments page — assignment tracking and history."""

from datetime import datetime

import pandas as pd
import streamlit as st

from components.charts import create_analytics_bar_chart
from components.empty_states import render_empty_state
from components.feedback import render_error_state
from core.data import safe_rerun, paginate_dataframe, render_page_navigation
from views.context import AppContext

def render(ctx: AppContext) -> None:
    """Render this page."""
    st.markdown('<p class="main-header">Assignments</p>', unsafe_allow_html=True)

    if not ctx.api:
        st.warning("Please configure your Airtable API key in Settings first.")
    else:
        tab1, tab2 = st.tabs(["View Assignments", "Client Summary"])

        with tab1:
            if not ctx.assignments_df.empty:
                # Search bar
                assign_search = st.text_input("🔍 Search (Serial Number, Client Name)", key="assign_search", placeholder="Type to search...")

                # Filters row
                acol1, acol2, acol3, acol4 = st.columns([1, 1, 1, 0.5])

                with acol1:
                    client_list = sorted(list(ctx.assignments_df["Client Name"].dropna().unique())) if "Client Name" in ctx.assignments_df.columns else []
                    assign_client_filter = st.selectbox("Client", ["All"] + client_list, key="assign_client_filter")

                with acol2:
                    status_list = sorted(list(ctx.assignments_df["Status"].dropna().unique())) if "Status" in ctx.assignments_df.columns else []
                    assign_status_filter = st.selectbox("Status", ["All"] + status_list, key="assign_status_filter")

                with acol3:
                    type_list = sorted(list(ctx.assignments_df["Assignment Type"].dropna().unique())) if "Assignment Type" in ctx.assignments_df.columns else []
                    assign_type_filter = st.selectbox("Type", ["All"] + type_list, key="assign_type_filter")

                with acol4:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Clear", key="clear_assign_filters", use_container_width=True):
                        for key in ["assign_search", "assign_client_filter", "assign_status_filter", "assign_type_filter"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        safe_rerun()

                # Apply filters
                filtered_assignments = ctx.assignments_df.copy()

                if assign_client_filter != "All" and "Client Name" in filtered_assignments.columns:
                    filtered_assignments = filtered_assignments[filtered_assignments["Client Name"] == assign_client_filter]

                if assign_status_filter != "All" and "Status" in filtered_assignments.columns:
                    filtered_assignments = filtered_assignments[filtered_assignments["Status"] == assign_status_filter]

                if assign_type_filter != "All" and "Assignment Type" in filtered_assignments.columns:
                    filtered_assignments = filtered_assignments[filtered_assignments["Assignment Type"] == assign_type_filter]

                # Search
                if assign_search:
                    search_mask = pd.Series([False] * len(filtered_assignments), index=filtered_assignments.index)
                    if "Serial Number" in filtered_assignments.columns:
                        search_mask |= filtered_assignments["Serial Number"].str.contains(assign_search, case=False, na=False)
                    if "Client Name" in filtered_assignments.columns:
                        search_mask |= filtered_assignments["Client Name"].str.contains(assign_search, case=False, na=False)
                    filtered_assignments = filtered_assignments[search_mask]

                # Results count
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                    <span style="font-size: 14px; color: #374151; font-weight: 500;">Showing</span>
                    <span style="font-size: 16px; color: #3b82f6; font-weight: 700;">{len(filtered_assignments)}</span>
                    <span style="font-size: 14px; color: #6b7280;">of {len(ctx.assignments_df)} assignments</span>
                </div>
                """, unsafe_allow_html=True)

                # Quick View Asset Panel - Linked Records Navigation
                with st.expander("🔗 Quick View Asset Details", expanded=False):
                    if "Serial Number" in filtered_assignments.columns and len(filtered_assignments) > 0:
                        serial_options = filtered_assignments["Serial Number"].dropna().unique().tolist()
                        if serial_options:
                            qv_col1, qv_col2 = st.columns([3, 1])
                            with qv_col1:
                                selected_serial = st.selectbox(
                                    "Select Asset Serial Number",
                                    options=serial_options,
                                    key="assign_quick_view_serial"
                                )
                            with qv_col2:
                                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("🔍 View Asset", key="assign_view_asset_btn", use_container_width=True):
                                    st.session_state.current_page = "Assets"
                                    st.session_state.asset_search_serial = selected_serial
                                    safe_rerun()

                            # Show asset details if available
                            if selected_serial and not ctx.assets_df.empty:
                                asset_info = ctx.assets_df[ctx.assets_df["Serial Number"] == selected_serial]
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
                            st.info("No assets in current view")
                    else:
                        st.info("No serial numbers available")

                # Apply pagination
                paginated_assignments = paginate_dataframe(filtered_assignments, "assignments_table", show_controls=True)
                st.dataframe(paginated_assignments, hide_index=True)
                render_page_navigation("assignments_table")
            else:
                render_empty_state("no_assignments")

        with tab2:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
                <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Assets per Client</span>
            </div>
            """, unsafe_allow_html=True)

            if not ctx.assets_df.empty and "Current Location" in ctx.assets_df.columns:
                # Count assets by location (client)
                client_assets = ctx.assets_df[ctx.assets_df["Current Status"] == "WITH_CLIENT"].groupby("Current Location").size().reset_index(name="Asset Count")

                if not client_assets.empty:
                    total_client_assets = client_assets["Asset Count"].sum()

                    # Create analytics-grade bar chart
                    fig = create_analytics_bar_chart(
                        x_data=client_assets["Current Location"].tolist(),
                        y_data=client_assets["Asset Count"].tolist(),
                        x_label="Client",
                        y_label="Asset Count",
                        hover_context="Assets",
                        total_for_percent=total_client_assets,
                        height=350
                    )

                    st.plotly_chart(
                        fig,
                                                config={'displayModeBar': False},
                        key="client_assets_bar_chart"
                    )

                    st.dataframe(client_assets, hide_index=True)
                else:
                    render_empty_state("no_billable_assets", show_action=True)

    # ISSUES & REPAIRS PAGE

