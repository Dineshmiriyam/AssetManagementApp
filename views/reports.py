"""Reports page — analytics and reporting."""

from datetime import datetime, date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.constants import STATUS_COLORS, STATUS_DISPLAY_NAMES, BILLING_CONFIG
from services.billing_service import calculate_billing_metrics
from components.charts import create_analytics_bar_chart
from components.empty_states import render_empty_state
from components.feedback import render_error_state, render_inline_error
from core.data import safe_rerun
from views.context import AppContext

def render(ctx: AppContext) -> None:
    """Render this page."""
    st.markdown('<p class="main-header">Reports & Analytics</p>', unsafe_allow_html=True)

    if not ctx.api:
        st.warning("Please configure your Airtable API key in Settings first.")
    elif st.session_state.get('data_load_error'):
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load reports data. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    else:
        # Role-based tabs: Operations cannot see Billing Summary
        current_role = st.session_state.user_role
        if current_role == "operations":
            tab1, tab3 = st.tabs(["Inventory Report", "Repair Analysis"])
            tab2 = None  # No billing tab for operations
        else:
            tab1, tab2, tab3 = st.tabs(["Inventory Report", "Billing Summary", "Repair Analysis"])

        with tab1:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
                <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Inventory Overview</span>
            </div>
            """, unsafe_allow_html=True)

            if not ctx.assets_df.empty:
                col1, col2 = st.columns(2)

                with col1:
                    # By status
                    st.markdown("""
                    <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                        By Status
                    </div>
                    """, unsafe_allow_html=True)
                    if "Current Status" in ctx.assets_df.columns:
                        status_summary = ctx.assets_df["Current Status"].value_counts().reset_index()
                        status_summary.columns = ["Status", "Count"]
                        st.dataframe(status_summary, hide_index=True)

                with col2:
                    # By brand and type
                    st.markdown("""
                    <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                        By Brand
                    </div>
                    """, unsafe_allow_html=True)
                    if "Brand" in ctx.assets_df.columns:
                        brand_summary = ctx.assets_df["Brand"].value_counts().reset_index()
                        brand_summary.columns = ["Brand", "Count"]
                        st.dataframe(brand_summary, hide_index=True)

                # Model breakdown
                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                st.markdown("""
                <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                    By Model (Top 10)
                </div>
                """, unsafe_allow_html=True)
                if "Model" in ctx.assets_df.columns:
                    model_summary = ctx.assets_df["Model"].value_counts().reset_index()
                    model_summary.columns = ["Model", "Count"]
                    top_10_models = model_summary.head(10)
                    total_model_count = top_10_models["Count"].sum()

                    # Create analytics-grade bar chart
                    fig = create_analytics_bar_chart(
                        x_data=top_10_models["Model"].tolist(),
                        y_data=top_10_models["Count"].tolist(),
                        x_label="Model",
                        y_label="Asset Count",
                        hover_context="Assets",
                        total_for_percent=total_model_count,
                        height=350
                    )

                    # Adjust x-axis for longer model names
                    fig.update_layout(
                        margin=dict(t=30, b=90, l=65, r=25),
                        xaxis=dict(tickangle=-45, tickfont=dict(size=10))
                    )

                    st.plotly_chart(
                        fig,
                                                config={'displayModeBar': False},
                        key="model_bar_chart"
                    )

                # Export inventory data
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                exp_c1, exp_c2, exp_spacer = st.columns([1, 1, 3])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                with exp_c1:
                    try:
                        from database.excel_utils import export_dataframe_to_excel
                        excel_buf = export_dataframe_to_excel(ctx.assets_df, "Inventory")
                        st.download_button("📥 Excel", excel_buf.getvalue(),
                            f"inventory_report_{timestamp}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
                    except Exception:
                        pass
                with exp_c2:
                    st.download_button("📥 CSV", ctx.assets_df.to_csv(index=False),
                        f"inventory_report_{timestamp}.csv", "text/csv",
                        use_container_width=True)

        # Billing tab only shown for admin and finance roles
        if tab2 is not None:
            with tab2:
                # Section header
                st.markdown("""
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                    <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                    <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Billing Summary (Assets with Clients)</span>
                </div>
                """, unsafe_allow_html=True)

                # Use centralized billing calculations
                report_billing = calculate_billing_metrics(ctx.assets_df)

                # Billing status legend
                st.markdown(f"""
                <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 10px;">
                    <span style="color: {BILLING_CONFIG['status_colors']['active']};">{BILLING_CONFIG['status_icons']['active']}</span> Active |
                    <span style="color: {BILLING_CONFIG['status_colors']['paused']};">{BILLING_CONFIG['status_icons']['paused']}</span> Paused ({report_billing['paused_count']}) |
                    Rate: ₹{report_billing['monthly_rate']:,}/asset/month
                </div>
                """, unsafe_allow_html=True)

                if report_billing['client_breakdown']:
                    # Build summary from centralized calculation
                    client_data = []
                    for client, data in report_billing['client_breakdown'].items():
                        client_data.append({
                            "Client": client,
                            "Asset Count": data['asset_count'],
                            "Monthly Rate (₹)": data['monthly_rate'],
                            "Monthly Revenue (₹)": data['monthly_revenue']
                        })

                    billing_summary = pd.DataFrame(client_data)
                    st.dataframe(billing_summary, hide_index=True)

                    # Export billing summary
                    exp_c1, exp_c2, exp_spacer = st.columns([1, 1, 3])
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                    with exp_c1:
                        try:
                            from database.excel_utils import export_dataframe_to_excel
                            excel_buf = export_dataframe_to_excel(billing_summary, "Billing")
                            st.download_button("📥 Excel", excel_buf.getvalue(),
                                f"billing_summary_{timestamp}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True)
                        except Exception:
                            pass
                    with exp_c2:
                        st.download_button("📥 CSV", billing_summary.to_csv(index=False),
                            f"billing_summary_{timestamp}.csv", "text/csv",
                            use_container_width=True)

                    # Summary metrics
                    metric_cols = st.columns(3)
                    with metric_cols[0]:
                        st.metric("Total Monthly Revenue", f"₹{report_billing['monthly_revenue']:,}")
                    with metric_cols[1]:
                        st.metric("Billable Assets", report_billing['billable_count'])
                    with metric_cols[2]:
                        st.metric("Utilization", f"{report_billing['utilization_rate']:.1f}%")
                else:
                    render_empty_state("no_billable_assets", show_action=True)

        with tab3:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #f59e0b;">
                <div style="width: 4px; height: 20px; background: #f59e0b; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Repair Analysis</span>
            </div>
            """, unsafe_allow_html=True)

            if not ctx.repairs_df.empty:
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Total Repairs", len(ctx.repairs_df))

                    if "Status" in ctx.repairs_df.columns:
                        repair_status = ctx.repairs_df["Status"].value_counts()
                        st.markdown("""
                        <div style="font-size: 14px; font-weight: 600; color: #374151; margin: 12px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                            By Status
                        </div>
                        """, unsafe_allow_html=True)
                        for status, count in repair_status.items():
                            st.markdown(f"""
                            <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #f3f4f6;">
                                <span style="color: #374151;">{status}</span>
                                <span style="font-weight: 600; color: #1f2937;">{count}</span>
                            </div>
                            """, unsafe_allow_html=True)

                with col2:
                    if "Repair Cost" in ctx.repairs_df.columns:
                        costs = pd.to_numeric(ctx.repairs_df["Repair Cost"], errors='coerce')
                        total_cost = costs.sum()
                        avg_cost = costs[costs > 0].mean() if (costs > 0).any() else 0
                        max_cost = costs.max()
                        repairs_with_cost = int(costs[costs > 0].count())

                        st.metric("Total Repair Cost", f"₹{total_cost:,.0f}" if pd.notna(total_cost) else "₹0")
                        st.metric("Avg Cost / Repair", f"₹{avg_cost:,.0f}" if pd.notna(avg_cost) else "₹0")

                        st.markdown("""
                        <div style="font-size: 14px; font-weight: 600; color: #374151; margin: 12px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                            Cost Breakdown
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #f3f4f6;">
                            <span style="color: #374151;">Highest Repair</span>
                            <span style="font-weight: 600; color: #1f2937;">₹{max_cost:,.0f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #f3f4f6;">
                            <span style="color: #374151;">Repairs with Cost</span>
                            <span style="font-weight: 600; color: #1f2937;">{repairs_with_cost} of {len(ctx.repairs_df)}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("No cost data available yet")

                # Vendor breakdown
                if "Vendor Name" in ctx.repairs_df.columns:
                    vendor_data = ctx.repairs_df[ctx.repairs_df["Vendor Name"].notna() & (ctx.repairs_df["Vendor Name"] != "")]
                    if not vendor_data.empty:
                        st.markdown("""
                        <div style="font-size: 14px; font-weight: 600; color: #374151; margin: 16px 0 8px 0; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                            By Vendor
                        </div>
                        """, unsafe_allow_html=True)
                        vendor_summary = vendor_data.groupby("Vendor Name").agg(
                            Repairs=("Vendor Name", "count"),
                        ).reset_index()
                        if "Repair Cost" in vendor_data.columns:
                            cost_agg = vendor_data.groupby("Vendor Name")["Repair Cost"].sum().reset_index()
                            cost_agg.columns = ["Vendor Name", "Total Cost"]
                            vendor_summary = vendor_summary.merge(cost_agg, on="Vendor Name", how="left")
                            vendor_summary["Total Cost"] = vendor_summary["Total Cost"].apply(
                                lambda x: f"₹{x:,.0f}" if pd.notna(x) and x > 0 else "-"
                            )
                        st.dataframe(vendor_summary, hide_index=True, use_container_width=True)

                # Export repair data
                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
                exp_c1, exp_c2, exp_spacer = st.columns([1, 1, 3])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                with exp_c1:
                    try:
                        from database.excel_utils import export_dataframe_to_excel
                        excel_buf = export_dataframe_to_excel(ctx.repairs_df, "Repairs")
                        st.download_button("📥 Excel", excel_buf.getvalue(),
                            f"repair_analysis_{timestamp}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
                    except Exception:
                        pass
                with exp_c2:
                    st.download_button("📥 CSV", ctx.repairs_df.to_csv(index=False),
                        f"repair_analysis_{timestamp}.csv", "text/csv",
                        use_container_width=True)
            else:
                st.info("No repair data available")

    # BILLING PAGE (Finance and Admin only)

