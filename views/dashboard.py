"""Dashboard page — analytics, KPIs, and role-based sections."""

import re
from datetime import datetime, date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.constants import (
    USER_ROLES, SLA_CONFIG, STATUS_COLORS, BILLING_CONFIG,
)
from config.permissions import (
    can_create_asset, can_perform_lifecycle_action, can_manage_repairs,
)
from services.sla_service import calculate_sla_status, get_sla_counts
from services.billing_service import (
    calculate_billing_metrics, get_billing_impact,
)
from services.asset_service import update_asset_status, create_repair_record
from components.charts import create_analytics_bar_chart
from components.empty_states import render_empty_state, get_system_health_summary
from components.feedback import render_error_state, render_inline_error
from core.data import safe_rerun, clear_cache
from views.context import AppContext

def render(ctx: AppContext) -> None:
    """Render this page."""
    st.markdown('<p class="main-header">Asset Management Dashboard</p>', unsafe_allow_html=True)

    if not ctx.api:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">🔌</div>
            <div class="empty-state-title">Not Connected</div>
            <div class="empty-state-text">Please configure your Airtable API key in Settings to get started.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("⚙️ Go to Settings", key="goto_settings"):
            st.session_state.current_page = "Settings"
            safe_rerun()
    elif st.session_state.get('data_load_error'):
        # Show error state with retry option
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load dashboard data. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    elif ctx.assets_df.empty:
        render_empty_state("no_assets")
    else:
        # Get system health summary for edge case handling
        system_health = get_system_health_summary(ctx.assets_df)

        # Check for critical edge cases
        if system_health["all_under_repair"]:
            st.markdown("""
            <div style="background: #fef2f2; border: 2px solid #ef4444; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                <strong style="color: #991b1b;">Critical: All Assets Under Repair</strong><br>
                <span style="color: #7f1d1d;">All your assets are currently with repair vendors. No assets available for deployment or billing.</span>
            </div>
            """, unsafe_allow_html=True)
        # Calculate metrics
        total = len(ctx.assets_df)
        with_client = len(ctx.assets_df[ctx.assets_df.get("Current Status", pd.Series()) == "WITH_CLIENT"]) if "Current Status" in ctx.assets_df.columns else 0
        in_stock = len(ctx.assets_df[ctx.assets_df.get("Current Status", pd.Series()) == "IN_STOCK_WORKING"]) if "Current Status" in ctx.assets_df.columns else 0
        under_repair = len(ctx.assets_df[ctx.assets_df.get("Current Status", pd.Series()) == "WITH_VENDOR_REPAIR"]) if "Current Status" in ctx.assets_df.columns else 0
        returned = len(ctx.assets_df[ctx.assets_df.get("Current Status", pd.Series()) == "RETURNED_FROM_CLIENT"]) if "Current Status" in ctx.assets_df.columns else 0
        sold = len(ctx.assets_df[ctx.assets_df.get("Current Status", pd.Series()) == "SOLD"]) if "Current Status" in ctx.assets_df.columns else 0
        disposed = len(ctx.assets_df[ctx.assets_df.get("Current Status", pd.Series()) == "DISPOSED"]) if "Current Status" in ctx.assets_df.columns else 0
        testing_count = len(ctx.assets_df[ctx.assets_df["Current Status"] == "IN_OFFICE_TESTING"]) if "Current Status" in ctx.assets_df.columns else 0

        # Get current role
        current_role = st.session_state.user_role

        # Last Updated timestamp with Refresh button
        last_updated = datetime.now().strftime("%I:%M %p")
        update_col1, update_col2 = st.columns([6, 1])
        with update_col1:
            st.markdown(f"""
            <div class="last-updated">
                <span class="dot"></span>
                <span>Last updated: {last_updated}</span>
            </div>
            """, unsafe_allow_html=True)
        with update_col2:
            if st.button("Refresh", key="refresh_data"):
                clear_cache()
                safe_rerun()

        # ============================================
        # ADMIN-SPECIFIC DASHBOARD LAYOUT
        # ============================================
        if current_role == "admin":
            # Calculate SLA counts for admin view
            sla_counts = get_sla_counts(ctx.assets_df)
            total_attention_needed = sla_counts['critical'] + sla_counts['warning'] + returned + under_repair

            # ========== SECTION 1: CRITICAL ADMIN ATTENTION ==========
            item_text = "item needs" if total_attention_needed == 1 else "items need"
            st.markdown(f"""
            <div class="admin-section critical">
                <div class="admin-section-header">
                    <span class="admin-section-icon">⚠</span>
                    <span class="admin-section-title">Critical Admin Attention</span>
                    <span class="priority-badge high">Priority 1</span>
                    <span class="admin-section-subtitle">{total_attention_needed} {item_text} review</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # SLA Breaches Row (highest priority) - Using buttons instead of anchor tags
            sla_col1, sla_col2, sla_col3, sla_col4 = st.columns(4)

            with sla_col1:
                critical_bg = "#fef2f2" if sla_counts['critical'] > 0 else "#ffffff"
                critical_border = "#fecaca" if sla_counts['critical'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card" style="background: {critical_bg}; border: 1px solid {critical_border}; border-radius: 12px; padding: 20px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;">
                    <div style="font-size: 11px; font-weight: 600; color: #dc2626; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA Critical</div>
                    <div style="font-size: 36px; font-weight: 700; color: #dc2626; line-height: 1;">{sla_counts['critical']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Exceeds threshold</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View", key="sla_critical_btn", width="stretch"):
                    st.session_state.current_page = "Assets"
                    st.session_state.sla_filter = "critical"
                    safe_rerun()

            with sla_col2:
                warning_bg = "#fffbeb" if sla_counts['warning'] > 0 else "#ffffff"
                warning_border = "#fde68a" if sla_counts['warning'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card" style="background: {warning_bg}; border: 1px solid {warning_border}; border-radius: 12px; padding: 20px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;">
                    <div style="font-size: 11px; font-weight: 600; color: #d97706; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA Warning</div>
                    <div style="font-size: 36px; font-weight: 700; color: #d97706; line-height: 1;">{sla_counts['warning']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Approaching limit</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View", key="sla_warning_btn", width="stretch"):
                    st.session_state.current_page = "Assets"
                    st.session_state.sla_filter = "warning"
                    safe_rerun()

            with sla_col3:
                return_bg = "#fef2f2" if returned > 0 else "#ffffff"
                return_border = "#fecaca" if returned > 0 else "#e5e7eb"
                return_color = "#ef4444" if returned > 0 else "#10b981"
                st.markdown(f"""
                <div class="metric-card" style="background: {return_bg}; border: 1px solid {return_border}; border-radius: 12px; padding: 20px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;">
                    <div style="font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Returns Backlog</div>
                    <div style="font-size: 36px; font-weight: 700; color: {return_color}; line-height: 1;">{returned}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Pending review</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View", key="returns_backlog_btn", width="stretch"):
                    st.session_state.current_page = "Assets"
                    st.session_state.asset_filter = "RETURNED_FROM_CLIENT"
                    safe_rerun()

            with sla_col4:
                repair_bg = "#eff6ff" if under_repair > 0 else "#ffffff"
                repair_border = "#bfdbfe" if under_repair > 0 else "#e5e7eb"
                repair_color = "#3b82f6" if under_repair > 0 else "#10b981"
                st.markdown(f"""
                <div class="metric-card" style="background: {repair_bg}; border: 1px solid {repair_border}; border-radius: 12px; padding: 20px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;">
                    <div style="font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Repair Backlog</div>
                    <div style="font-size: 36px; font-weight: 700; color: {repair_color}; line-height: 1;">{under_repair}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">At vendor</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View", key="repair_backlog_btn", width="stretch"):
                    st.session_state.current_page = "Assets"
                    st.session_state.asset_filter = "WITH_VENDOR_REPAIR"
                    safe_rerun()

            st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

            # ========== SECTION 2: OPERATIONAL OVERVIEW ==========
            st.markdown("""
            <div class="admin-section operational">
                <div class="admin-section-header">
                    <span class="admin-section-title">Operational Overview</span>
                    <span class="priority-badge medium">Priority 2</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Note: Inventory Overview KPI cards moved to unified section below (shown for all roles)

            # SLA OK count - fix grammar
            sla_asset_text = "asset" if sla_counts['ok'] == 1 else "assets"
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; padding: 10px 16px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; margin-bottom: 1rem;">
                <span style="color: #16a34a; font-size: 16px;">✓</span>
                <span style="color: #15803d; font-weight: 500;">{sla_counts['ok']} {sla_asset_text} within SLA targets</span>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

            # ========== SECTION 3: REVENUE IMPACT ==========
            # Use centralized billing calculations
            admin_billing = calculate_billing_metrics(ctx.assets_df)
            billable_count = admin_billing['billable_count']
            monthly_rate = admin_billing['monthly_rate']
            estimated_revenue = admin_billing['monthly_revenue']
            annual_projection = admin_billing['annual_revenue']

            st.markdown(f"""
            <div class="admin-section revenue">
                <div class="admin-section-header">
                    <span class="admin-section-title">Revenue Impact</span>
                    <span class="priority-badge low">Priority 3</span>
                    <span class="admin-section-subtitle">₹{estimated_revenue:,}/month projected</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            rev_col1, rev_col2, rev_col3, rev_col4 = st.columns(4)

            with rev_col1:
                st.markdown(f"""
                <div class="metric-card" style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Billable Assets</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{billable_count}</div>
                    <div style="font-size: 12px; color: #9ca3af; margin-top: 6px;">Generating revenue</div>
                </div>
                """, unsafe_allow_html=True)

            with rev_col2:
                st.markdown(f"""
                <div class="metric-card" style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #16a34a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Monthly Revenue</div>
                    <div style="font-size: 36px; font-weight: 700; color: #16a34a; line-height: 1;">₹{estimated_revenue:,}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">@ ₹{monthly_rate:,}/asset</div>
                </div>
                """, unsafe_allow_html=True)

            with rev_col3:
                st.markdown(f"""
                <div class="metric-card" style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Annual Projection</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">₹{annual_projection:,}</div>
                    <div style="font-size: 12px; color: #9ca3af; margin-top: 6px;">Estimated yearly</div>
                </div>
                """, unsafe_allow_html=True)

            with rev_col4:
                st.markdown(f"""
                <div class="metric-card" style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Assets Sold</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{sold}</div>
                    <div style="font-size: 12px; color: #9ca3af; margin-top: 6px;">Total lifetime</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

        # ============================================
        # OPERATIONS DASHBOARD LAYOUT
        # ============================================
        elif current_role == "operations":
            # Calculate SLA counts
            sla_counts = get_sla_counts(ctx.assets_df)
            total_attention = sla_counts['critical'] + sla_counts['warning'] + returned

            # ========== SECTION 1: ATTENTION REQUIRED ==========
            st.markdown(f"""
            <div class="admin-section critical">
                <div class="admin-section-header">
                    <span class="admin-section-icon">🚨</span>
                    <span class="admin-section-title">Attention Required</span>
                    <span class="priority-badge high">Priority 1</span>
                    <span class="admin-section-subtitle">{total_attention} items need action</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # SLA and Returns Row
            ops_col1, ops_col2, ops_col3, ops_col4 = st.columns(4)

            with ops_col1:
                critical_style = "background: #fef2f2; border: 2px solid #dc2626;" if sla_counts['critical'] > 0 else ""
                st.markdown(f"""
                <div class="insight-card critical" style="{critical_style}">
                    <span class="insight-icon">🔴</span>
                    <div class="insight-title">SLA Critical</div>
                    <div class="insight-value" style="color: #dc2626;">{sla_counts['critical']}</div>
                    <div class="insight-subtitle">Immediate action needed</div>
                </div>
                """, unsafe_allow_html=True)

            with ops_col2:
                warning_style = "background: #fffbeb; border: 2px solid #f59e0b;" if sla_counts['warning'] > 0 else ""
                st.markdown(f"""
                <div class="insight-card warning" style="{warning_style}">
                    <span class="insight-icon">🟠</span>
                    <div class="insight-title">SLA Warning</div>
                    <div class="insight-value" style="color: #f59e0b;">{sla_counts['warning']}</div>
                    <div class="insight-subtitle">Approaching deadline</div>
                </div>
                """, unsafe_allow_html=True)

            with ops_col3:
                returned_style = "background: #fef2f2; border: 2px solid #ef4444;" if returned > 0 else ""
                st.markdown(f"""
                <div class="insight-card" style="{returned_style}">
                    <span class="insight-icon">↩️</span>
                    <div class="insight-title">Returns Pending</div>
                    <div class="insight-value" style="color: {'#ef4444' if returned > 0 else '#10b981'};">{returned}</div>
                    <div class="insight-subtitle">Need processing</div>
                </div>
                """, unsafe_allow_html=True)

            with ops_col4:
                st.markdown(f"""
                <div class="insight-card success">
                    <span class="insight-icon">✅</span>
                    <div class="insight-title">SLA OK</div>
                    <div class="insight-value" style="color: #10b981;">{sla_counts['ok']}</div>
                    <div class="insight-subtitle">Within target</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

            # ========== SECTION 2: REPAIR STATUS ==========
            st.markdown(f"""
            <div class="admin-section operational">
                <div class="admin-section-header">
                    <span class="admin-section-icon">🔧</span>
                    <span class="admin-section-title">Repair & Testing Status</span>
                    <span class="priority-badge medium">Priority 2</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            repair_col1, repair_col2, repair_col3 = st.columns(3)

            with repair_col1:
                repair_style = "background: #eff6ff; border: 2px solid #3b82f6;" if under_repair > 0 else ""
                st.markdown(f"""
                <div class="insight-card" style="{repair_style}">
                    <span class="insight-icon">🔧</span>
                    <div class="insight-title">With Vendor</div>
                    <div class="insight-value" style="color: #3b82f6;">{under_repair}</div>
                    <div class="insight-subtitle">At repair vendor</div>
                </div>
                """, unsafe_allow_html=True)

            with repair_col2:
                st.markdown(f"""
                <div class="insight-card info">
                    <span class="insight-icon">🧪</span>
                    <div class="insight-title">In Testing</div>
                    <div class="insight-value">{testing_count}</div>
                    <div class="insight-subtitle">Office testing</div>
                </div>
                """, unsafe_allow_html=True)

            with repair_col3:
                st.markdown(f"""
                <div class="insight-card success">
                    <span class="insight-icon">📦</span>
                    <div class="insight-title">Ready to Deploy</div>
                    <div class="insight-value" style="color: #10b981;">{in_stock}</div>
                    <div class="insight-subtitle">Available stock</div>
                </div>
                """, unsafe_allow_html=True)

            # Note: Fleet Overview moved to unified Inventory Overview section below (shown for all roles)

        # ============================================
        # FINANCE DASHBOARD LAYOUT
        # ============================================
        elif current_role == "finance":
            # Use centralized billing calculations
            finance_billing = calculate_billing_metrics(ctx.assets_df)
            billable_assets = finance_billing['billable_count']
            monthly_rate = finance_billing['monthly_rate']
            estimated_monthly_revenue = finance_billing['monthly_revenue']
            daily_rate = finance_billing['daily_rate']
            annual_projection = finance_billing['annual_revenue']
            paused_billing_count = finance_billing['paused_count']

            # ========== SECTION 1: REVENUE OVERVIEW ==========
            st.markdown(f"""
            <div class="admin-section revenue">
                <div class="admin-section-header">
                    <span class="admin-section-icon">💰</span>
                    <span class="admin-section-title">Revenue Overview</span>
                    <span class="priority-badge high" style="background: #ecfdf5; color: #10b981;">Primary</span>
                    <span class="admin-section-subtitle">₹{estimated_monthly_revenue:,}/month projected</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            rev_col1, rev_col2, rev_col3, rev_col4 = st.columns(4)

            with rev_col1:
                st.markdown(f"""
                <div class="insight-card success" style="background: #ecfdf5; border: 2px solid #10b981;">
                    <span class="insight-icon">💰</span>
                    <div class="insight-title">Monthly Revenue</div>
                    <div class="insight-value" style="color: #10b981; font-size: 1.75rem;">₹{estimated_monthly_revenue:,}</div>
                    <div class="insight-subtitle">Estimated</div>
                </div>
                """, unsafe_allow_html=True)

            with rev_col2:
                st.markdown(f"""
                <div class="insight-card info">
                    <span class="insight-icon">📅</span>
                    <div class="insight-title">Annual Projection</div>
                    <div class="insight-value">₹{annual_projection:,}</div>
                    <div class="insight-subtitle">Yearly estimate</div>
                </div>
                """, unsafe_allow_html=True)

            with rev_col3:
                st.markdown(f"""
                <div class="insight-card info">
                    <span class="insight-icon">💼</span>
                    <div class="insight-title">Billable Assets</div>
                    <div class="insight-value">{billable_assets}</div>
                    <div class="insight-subtitle">With clients</div>
                </div>
                """, unsafe_allow_html=True)

            with rev_col4:
                st.markdown(f"""
                <div class="insight-card info">
                    <span class="insight-icon">📊</span>
                    <div class="insight-title">Rate per Asset</div>
                    <div class="insight-value">₹{monthly_rate:,}</div>
                    <div class="insight-subtitle">Per month</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

            # ========== SECTION 2: DEPLOYMENT STATUS ==========
            st.markdown("""
            <div class="admin-section operational">
                <div class="admin-section-header">
                    <span class="admin-section-icon">🏢</span>
                    <span class="admin-section-title">Deployment Status</span>
                    <span class="priority-badge medium">Secondary</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            deploy_col1, deploy_col2, deploy_col3 = st.columns(3)

            with deploy_col1:
                st.markdown(f"""
                <div class="insight-card success">
                    <span class="insight-icon">🏢</span>
                    <div class="insight-title">Deployed</div>
                    <div class="insight-value" style="color: #10b981;">{with_client}</div>
                    <div class="insight-subtitle">Generating revenue</div>
                </div>
                """, unsafe_allow_html=True)

            with deploy_col2:
                st.markdown(f"""
                <div class="insight-card info">
                    <span class="insight-icon">🏷️</span>
                    <div class="insight-title">Assets Sold</div>
                    <div class="insight-value">{sold}</div>
                    <div class="insight-subtitle">Total lifetime</div>
                </div>
                """, unsafe_allow_html=True)

            with deploy_col3:
                utilization = round((with_client/total)*100) if total > 0 else 0
                util_color = "#10b981" if utilization >= 70 else "#f59e0b" if utilization >= 50 else "#ef4444"
                st.markdown(f"""
                <div class="insight-card">
                    <span class="insight-icon">📈</span>
                    <div class="insight-title">Utilization Rate</div>
                    <div class="insight-value" style="color: {util_color};">{utilization}%</div>
                    <div class="insight-subtitle">Assets deployed</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

            # ========== SECTION 3: REVENUE BREAKDOWN ==========
            st.markdown("""
            <div class="admin-section critical" style="border-left-color: #6366f1; background: linear-gradient(to right, #eef2ff 0%, #ffffff 100%);">
                <div class="admin-section-header">
                    <span class="admin-section-icon">📋</span>
                    <span class="admin-section-title" style="color: #6366f1;">Revenue Breakdown</span>
                    <span class="priority-badge low">Details</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="billing-info-card" style="max-width: 400px;">
                <div class="billing-info-row">
                    <span class="billing-info-label">Rate per Asset</span>
                    <span class="billing-info-value">₹{monthly_rate:,}/month</span>
                </div>
                <div class="billing-info-row">
                    <span class="billing-info-label">Daily Equivalent</span>
                    <span class="billing-info-value">₹{daily_rate:,.0f}/day</span>
                </div>
                <div class="billing-info-row">
                    <span class="billing-info-label">Billable Units</span>
                    <span class="billing-info-value">{billable_assets} assets</span>
                </div>
                <div class="billing-info-row">
                    <span class="billing-info-label">Total Fleet</span>
                    <span class="billing-info-value">{total} assets</span>
                </div>
                <div class="billing-info-row total">
                    <span class="billing-info-label">Annual Projection</span>
                    <span class="billing-info-value">₹{annual_projection:,.0f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ========== INVENTORY OVERVIEW (Single Source - All Roles) ==========
        st.markdown("""
        <div class="section-title">
            <div class="section-title-icon"></div>
            INVENTORY OVERVIEW
        </div>
        """, unsafe_allow_html=True)

        # KPI Cards - Using Streamlit columns with buttons (no anchor tags to avoid page reload)
        kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)

        with kpi_col1:
            st.markdown(f"""
            <div class="kpi-card neutral" style="cursor: pointer;">
                <div class="kpi-card-title">TOTAL ASSETS</div>
                <div class="kpi-card-value">{total}</div>
                <div class="kpi-card-label">All inventory</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("View All", key="kpi_total", width="stretch"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "All"
                safe_rerun()

        with kpi_col2:
            st.markdown(f"""
            <div class="kpi-card blue" style="cursor: pointer;">
                <div class="kpi-card-title">DEPLOYED</div>
                <div class="kpi-card-value">{with_client}</div>
                <div class="kpi-card-label">With clients</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("View Deployed", key="kpi_deployed", width="stretch"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "WITH_CLIENT"
                safe_rerun()

        with kpi_col3:
            st.markdown(f"""
            <div class="kpi-card green" style="cursor: pointer;">
                <div class="kpi-card-title">AVAILABLE</div>
                <div class="kpi-card-value">{in_stock}</div>
                <div class="kpi-card-label">Ready to deploy</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("View Available", key="kpi_available", width="stretch"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "IN_STOCK_WORKING"
                safe_rerun()

        with kpi_col4:
            st.markdown(f"""
            <div class="kpi-card amber" style="cursor: pointer;">
                <div class="kpi-card-title">IN REPAIR</div>
                <div class="kpi-card-value">{under_repair}</div>
                <div class="kpi-card-label">At vendor</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("View Repairs", key="kpi_repair", width="stretch"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "WITH_VENDOR_REPAIR"
                safe_rerun()

        with kpi_col5:
            st.markdown(f"""
            <div class="kpi-card red" style="cursor: pointer;">
                <div class="kpi-card-title">RETURNED</div>
                <div class="kpi-card-value">{returned}</div>
                <div class="kpi-card-label">Needs review</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("View Returned", key="kpi_returned", width="stretch"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "RETURNED_FROM_CLIENT"
                safe_rerun()

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        # ========== RETIRED ASSETS (Sold + Disposed) ==========
        st.markdown("""
        <div class="section-title">
            <div class="section-title-icon" style="background: #6b7280;"></div>
            RETIRED ASSETS
        </div>
        """, unsafe_allow_html=True)

        retired_col1, retired_col2, retired_spacer1, retired_spacer2, retired_spacer3 = st.columns(5)

        with retired_col1:
            st.markdown(f"""
            <div class="kpi-card purple" style="cursor: pointer;">
                <div class="kpi-card-title">SOLD</div>
                <div class="kpi-card-value">{sold}</div>
                <div class="kpi-card-label">Permanently sold</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("View Sold", key="kpi_sold", width="stretch"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "SOLD"
                safe_rerun()

        with retired_col2:
            st.markdown(f"""
            <div class="kpi-card gray" style="cursor: pointer;">
                <div class="kpi-card-title">DISPOSED</div>
                <div class="kpi-card-value">{disposed}</div>
                <div class="kpi-card-label">End of life</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("View Disposed", key="kpi_disposed", width="stretch"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "DISPOSED"
                safe_rerun()

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        # Quick Actions Section
        st.markdown("""
        <div class="section-title">
            <div class="section-title-icon"></div>
            QUICK ACTIONS
        </div>
        """, unsafe_allow_html=True)

        # Check conditions for enabling/disabling buttons
        can_assign = in_stock > 0 and not ctx.clients_df.empty  # Assets available AND clients exist
        can_return = with_client > 0  # Assets with clients
        testing_count = len(ctx.assets_df[ctx.assets_df["Current Status"] == "IN_OFFICE_TESTING"]) if "Current Status" in ctx.assets_df.columns else 0
        can_send_repair = (returned > 0) or (testing_count > 0)

        # Role-based permission checks for quick actions
        role = st.session_state.user_role
        has_create_permission = can_create_asset(role)
        has_lifecycle_permission = can_perform_lifecycle_action(role)
        has_repair_permission = can_manage_repairs(role)

        # Dark container with action buttons
        st.markdown("""
        <div class="quick-action-wrapper">
            <div class="quick-action-title">Perform Actions</div>
        </div>
        """, unsafe_allow_html=True)

        # Functional buttons with enhanced styling
        st.markdown('<div class="qa-buttons-row">', unsafe_allow_html=True)
        qa_col1, qa_col2, qa_col3, qa_col4 = st.columns(4)

        with qa_col1:
            if st.button("Add Asset", key="qa_add_asset", disabled=not has_create_permission):
                st.session_state.current_page = "Add Asset"
                safe_rerun()
            if not has_create_permission:
                st.caption("No permission")

        with qa_col2:
            assign_disabled = not can_assign or not has_lifecycle_permission
            if st.button("Assign to Client", key="qa_assign", disabled=assign_disabled):
                st.session_state.current_page = "Quick Actions"
                st.session_state.quick_action_tab = "ship"
                safe_rerun()
            if not has_lifecycle_permission:
                st.caption("No permission")
            elif not can_assign:
                st.caption("No assets available" if in_stock == 0 else "No clients")

        with qa_col3:
            return_disabled = not can_return or not has_lifecycle_permission
            if st.button("Receive Return", key="qa_return", disabled=return_disabled):
                st.session_state.current_page = "Quick Actions"
                st.session_state.quick_action_tab = "return"
                safe_rerun()
            if not has_lifecycle_permission:
                st.caption("No permission")
            elif not can_return:
                st.caption("No assets with clients")

        with qa_col4:
            repair_disabled = not can_send_repair or not has_repair_permission
            if st.button("Send to Vendor", key="qa_repair", disabled=repair_disabled):
                st.session_state.current_page = "Quick Actions"
                st.session_state.quick_action_tab = "repair"
                safe_rerun()
            if not has_repair_permission:
                st.caption("No permission")
            elif not can_send_repair:
                st.caption("No assets need repair")

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Get current role configuration
        current_role = st.session_state.user_role
        role_config = USER_ROLES[current_role]
        role_class = f"role-{current_role}"

        # Analytics Section Title with Role Badge
        st.markdown(f"""
        <div class="analytics-section">
            <div class="analytics-header">
                <div>
                    <div class="analytics-title">ANALYTICS</div>
                    <div class="analytics-subtitle">{role_config['description']}</div>
                </div>
                <div class="role-badge {role_class}">
                    {role_config['name']} View
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Role-specific Insight Cards
        insight_cols = st.columns(4 if current_role == "admin" else 3)

        if role_config["show_sla"]:
            # SLA Indicators for Operations and Admin - Using buttons instead of anchor tags
            sla_counts = get_sla_counts(ctx.assets_df)

            with insight_cols[0]:
                critical_bg = "#fef2f2" if sla_counts['critical'] > 0 else "#ffffff"
                critical_border = "#fecaca" if sla_counts['critical'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card clickable-card" style="background: {critical_bg}; border: 1px solid {critical_border}; border-left: 4px solid #dc2626; border-radius: 12px; padding: 20px; cursor: pointer;">
                    <div style="font-size: 11px; font-weight: 600; color: #dc2626; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA Critical</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{sla_counts['critical']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Exceeds threshold</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View →", key="analytics_sla_critical", width="stretch"):
                    st.session_state.current_page = "Assets"
                    st.session_state.sla_filter = "critical"
                    safe_rerun()

            with insight_cols[1]:
                warning_bg = "#fffbeb" if sla_counts['warning'] > 0 else "#ffffff"
                warning_border = "#fde68a" if sla_counts['warning'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card clickable-card" style="background: {warning_bg}; border: 1px solid {warning_border}; border-left: 4px solid #f59e0b; border-radius: 12px; padding: 20px; cursor: pointer;">
                    <div style="font-size: 11px; font-weight: 600; color: #d97706; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA Warning</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{sla_counts['warning']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Approaching limit</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View →", key="analytics_sla_warning", width="stretch"):
                    st.session_state.current_page = "Assets"
                    st.session_state.sla_filter = "warning"
                    safe_rerun()

            with insight_cols[2]:
                ok_bg = "#f0fdf4" if sla_counts['ok'] > 0 else "#ffffff"
                ok_border = "#bbf7d0" if sla_counts['ok'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card clickable-card" style="background: {ok_bg}; border: 1px solid {ok_border}; border-left: 4px solid #16a34a; border-radius: 12px; padding: 20px; cursor: pointer;">
                    <div style="font-size: 11px; font-weight: 600; color: #16a34a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA OK</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{sla_counts['ok']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Within target</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View →", key="analytics_sla_ok", width="stretch"):
                    st.session_state.current_page = "Assets"
                    st.session_state.sla_filter = "ok"
                    safe_rerun()

        if role_config["show_billing"]:
            # Billing Insights for Finance and Admin - using centralized calculations
            insight_billing = calculate_billing_metrics(ctx.assets_df)
            billable_count = insight_billing['billable_count']
            monthly_rate = insight_billing['monthly_rate']
            estimated_revenue = insight_billing['monthly_revenue']
            paused_count = insight_billing['paused_count']

            col_idx = 3 if current_role == "admin" else 0

            if current_role == "finance":
                with insight_cols[0]:
                    st.markdown(f"""
                        <div class="metric-card clickable-card" style="background: #ffffff; border: 1px solid #e5e7eb; border-left: 4px solid #6366f1; border-radius: 12px; padding: 20px;">
                            <div style="font-size: 11px; font-weight: 600; color: #6366f1; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Billable Assets</div>
                            <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{billable_count}</div>
                            <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Currently deployed</div>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button("View Billable", key="finance_billable_btn", width="stretch"):
                        st.session_state.current_page = "Assets"
                        st.session_state.asset_filter = "WITH_CLIENT"
                        safe_rerun()

                with insight_cols[1]:
                    st.markdown(f"""
                        <div class="metric-card clickable-card" style="background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #16a34a; border-radius: 12px; padding: 20px;">
                            <div style="font-size: 11px; font-weight: 600; color: #16a34a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Est. Monthly Revenue</div>
                            <div style="font-size: 36px; font-weight: 700; color: #16a34a; line-height: 1;">₹{estimated_revenue:,}</div>
                            <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">@ ₹{monthly_rate:,}/asset</div>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button("View Billing", key="finance_revenue_btn", width="stretch"):
                        st.session_state.current_page = "Billing"
                        safe_rerun()

                # Show paused billing count instead of sold
                with insight_cols[2]:
                    paused_bg = "#fffbeb" if paused_count > 0 else "#ffffff"
                    paused_border = "#fde68a" if paused_count > 0 else "#e5e7eb"
                    st.markdown(f"""
                        <div class="metric-card clickable-card" style="background: {paused_bg}; border: 1px solid {paused_border}; border-left: 4px solid #f59e0b; border-radius: 12px; padding: 20px;">
                            <div style="font-size: 11px; font-weight: 600; color: #d97706; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Billing Paused</div>
                            <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{paused_count}</div>
                            <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Returned/Repair</div>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button("View Paused", key="finance_paused_btn", width="stretch"):
                        st.session_state.current_page = "Assets"
                        st.session_state.billing_paused_filter = True
                        safe_rerun()

            elif current_role == "admin":
                with insight_cols[3]:
                    st.markdown(f"""
                        <div class="metric-card clickable-card" style="background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #3b82f6; border-radius: 12px; padding: 20px;">
                            <div style="font-size: 11px; font-weight: 600; color: #3b82f6; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Est. Revenue</div>
                            <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">₹{estimated_revenue:,}</div>
                            <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">{billable_count} billable @ ₹{monthly_rate:,}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button("View Billing", key="admin_revenue_btn", width="stretch"):
                        st.session_state.current_page = "Billing"
                        safe_rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        # Filter data based on role for charts
        if current_role == "finance":
            chart_df = ctx.assets_df[ctx.assets_df["Current Status"].isin(["WITH_CLIENT", "SOLD"])] if "Current Status" in ctx.assets_df.columns else ctx.assets_df
            chart_title_suffix = " (Billable Focus)"
        elif current_role == "operations":
            chart_df = ctx.assets_df[ctx.assets_df["Current Status"].isin(["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR", "IN_OFFICE_TESTING"])] if "Current Status" in ctx.assets_df.columns else ctx.assets_df
            chart_title_suffix = " (Operations Focus)"
        else:
            chart_df = ctx.assets_df
            chart_title_suffix = ""

        st.caption(f"Click on any chart segment or bar to filter assets{chart_title_suffix}")

        # Charts row - Bar chart left, Donut chart right
        col1, col2 = st.columns(2)

        with col1:
            # ============================================
            # CHART: Assets by Brand (Analytics Bar Chart)
            # Style: Muted colors, clear labels, hover highlights
            # ============================================
            try:
                brand_chart_df = chart_df if not chart_df.empty else ctx.assets_df
                st.markdown('<div class="chart-title">ASSETS BY BRAND</div>', unsafe_allow_html=True)
                if "Brand" in brand_chart_df.columns and not brand_chart_df.empty:
                    # Sort descending - highest count first
                    brand_counts = brand_chart_df["Brand"].value_counts().sort_values(ascending=False)
                    brand_labels = list(brand_counts.index)
                    total_brand_assets = brand_counts.sum()

                    # Convert to lists for proper rendering
                    brand_names = list(brand_counts.index)
                    brand_values = list(brand_counts.values)

                    # Create analytics-grade bar chart
                    fig_brand = create_analytics_bar_chart(
                        x_data=brand_names,
                        y_data=brand_values,
                        x_label="Brand",
                        y_label="Asset Count",
                        hover_context="Assets",
                        total_for_percent=total_brand_assets,
                        height=380
                    )

                    # Render chart with click events enabled
                    st.plotly_chart(
                        fig_brand,
                        width="stretch",
                        config={
                            'displayModeBar': False,
                            'scrollZoom': False
                        },
                        key="brand_bar_chart"
                    )

                    # Keep click functionality separate
                    selected_brand = None

                    # Handle bar chart click
                    if selected_brand:
                        clicked_point = selected_brand[0]
                        point_index = clicked_point.get('pointIndex', clicked_point.get('pointNumber', None))
                        if point_index is not None and point_index < len(brand_labels):
                            clicked_brand = brand_labels[point_index]
                            st.session_state.current_page = "Assets"
                            st.session_state.brand_filter = clicked_brand
                            safe_rerun()
            except Exception as e:
                render_inline_error(f"Could not render brand chart: {str(e)}")

        with col2:
            # ============================================
            # CHART 1: Asset Lifecycle Distribution (Donut)
            # Purpose: Show where assets are stuck in lifecycle
            # ============================================
            try:
                status_chart_df = chart_df if not chart_df.empty else ctx.assets_df
                st.markdown('<div class="chart-title">ASSET LIFECYCLE DISTRIBUTION</div>', unsafe_allow_html=True)
                if "Current Status" in status_chart_df.columns and not status_chart_df.empty:

                    # Semantic color mapping (severity-based)
                    status_config = {
                        "WITH_VENDOR_REPAIR": {"label": "Under Repair", "color": "#EF4444", "order": 1},  # Red - Critical
                        "RETURNED_FROM_CLIENT": {"label": "Returned", "color": "#F59E0B", "order": 2},    # Yellow - Warning
                        "IN_OFFICE_TESTING": {"label": "Testing", "color": "#F97316", "order": 3},       # Orange - Attention
                        "IN_STOCK_WORKING": {"label": "In Stock", "color": "#22C55E", "order": 4},       # Green - Healthy
                        "WITH_CLIENT": {"label": "With Client", "color": "#10B981", "order": 5},         # Green - Healthy
                        "SOLD": {"label": "Sold", "color": "#6B7280", "order": 6},                       # Gray - Inactive
                        "DISPOSED": {"label": "Disposed", "color": "#9CA3AF", "order": 7}                # Light Gray - Inactive
                    }

                    # Get counts and sort by severity order
                    status_data = []
                    for status in status_chart_df["Current Status"].unique():
                        count = len(status_chart_df[status_chart_df["Current Status"] == status])
                        config = status_config.get(status, {"label": status, "color": "#94A3B8", "order": 99})
                        status_data.append({
                            "status": status,
                            "label": config["label"],
                            "count": count,
                            "color": config["color"],
                            "order": config["order"]
                        })

                    # Sort by severity order
                    status_data.sort(key=lambda x: x["order"])

                    # Calculate totals for center annotation
                    total_assets = sum(d["count"] for d in status_data)
                    healthy_statuses = ["IN_STOCK_WORKING", "WITH_CLIENT"]
                    healthy_count = sum(d["count"] for d in status_data if d["status"] in healthy_statuses)
                    health_pct = round((healthy_count / total_assets * 100)) if total_assets > 0 else 0

                    # Prepare chart data
                    donut_labels = [d["label"] for d in status_data]
                    donut_values = [d["count"] for d in status_data]
                    donut_colors = [d["color"] for d in status_data]
                    status_labels = [d["status"] for d in status_data]  # For click handling

                    # Calculate percentages for hover
                    donut_percentages = [(v / total_assets * 100) if total_assets > 0 else 0 for v in donut_values]

                    fig_status = go.Figure(data=[go.Pie(
                        labels=donut_labels,
                        values=donut_values,
                        hole=0.65,
                        marker=dict(
                            colors=donut_colors,
                            line=dict(color='#FFFFFF', width=2)
                        ),
                        textinfo='none',
                        hovertemplate='<b style="font-size:14px">%{label}</b><br><br>📊 Assets: <b>%{value}</b><br>📈 Share: <b>%{percent}</b><br><br><i style="color:#9CA3AF">Click to filter</i><extra></extra>',
                        direction='counterclockwise',
                        rotation=90,
                        sort=False
                    )])

                    # Add center annotation with total and health %
                    fig_status.add_annotation(
                        text=f"<b style='font-size:32px;color:#1F2937'>{total_assets}</b>",
                        x=0.5, y=0.55,
                        font=dict(size=32, color='#1F2937', family="Inter, -apple-system, sans-serif"),
                        showarrow=False,
                        xanchor='center',
                        yanchor='middle'
                    )
                    fig_status.add_annotation(
                        text=f"<span style='font-size:11px;color:#6B7280'>Total Assets</span>",
                        x=0.5, y=0.45,
                        font=dict(size=11, color='#6B7280', family="Inter, -apple-system, sans-serif"),
                        showarrow=False,
                        xanchor='center',
                        yanchor='middle'
                    )
                    fig_status.add_annotation(
                        text=f"<span style='color:#22C55E;font-weight:600'>{health_pct}%</span> <span style='color:#6B7280'>healthy</span>",
                        x=0.5, y=0.35,
                        font=dict(size=12, color='#6B7280', family="Inter, -apple-system, sans-serif"),
                        showarrow=False,
                        xanchor='center',
                        yanchor='middle'
                    )

                    fig_status.update_layout(
                        height=380,
                        paper_bgcolor='#FFFFFF',
                        plot_bgcolor='#FFFFFF',
                        font=dict(family="Inter, -apple-system, sans-serif", size=12, color='#374151'),
                        legend=dict(
                            orientation="h",
                            yanchor="top",
                            y=-0.05,
                            xanchor="center",
                            x=0.5,
                            font=dict(size=11, color='#374151', family="Inter, -apple-system, sans-serif"),
                            bgcolor='rgba(255,255,255,0)',
                            itemsizing='constant',
                            itemclick=False,
                            itemdoubleclick=False
                        ),
                        margin=dict(t=20, b=60, l=20, r=20),
                        showlegend=True,
                        hoverlabel=dict(
                            bgcolor='#374151',
                            font_size=12,
                            font_family="Inter, -apple-system, sans-serif",
                            font_color='#FFFFFF',
                            bordercolor='#374151'
                        )
                    )

                    # Render chart
                    st.plotly_chart(
                        fig_status,
                        width="stretch",
                        config={
                            'displayModeBar': False,
                            'scrollZoom': False
                        },
                        key="status_pie_chart"
                    )
            except Exception as e:
                render_inline_error(f"Could not render status chart: {str(e)}")

        # Assets Needing Attention Section - Only show for Operations and Admin
        if current_role != "finance":
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            <div class="section-title">
                <div class="section-title-icon"></div>
                ASSETS NEEDING ATTENTION
            </div>
            """, unsafe_allow_html=True)

            # Show SLA thresholds info for Operations users
            if current_role == "operations":
                st.caption(f"SLA Thresholds: Returned (Warning: {SLA_CONFIG['RETURNED_FROM_CLIENT']['warning']}d, Critical: {SLA_CONFIG['RETURNED_FROM_CLIENT']['critical']}d) | Repair (Warning: {SLA_CONFIG['WITH_VENDOR_REPAIR']['warning']}d, Critical: {SLA_CONFIG['WITH_VENDOR_REPAIR']['critical']}d)")

            # Initialize confirmation state
            if "confirm_action" not in st.session_state:
                st.session_state.confirm_action = None

            attention_df = ctx.assets_df[ctx.assets_df["Current Status"].isin(["RETURNED_FROM_CLIENT", "IN_OFFICE_TESTING", "WITH_VENDOR_REPAIR"])] if "Current Status" in ctx.assets_df.columns else pd.DataFrame()

            # Show confirmation modal if action is pending
            if st.session_state.confirm_action:
                action = st.session_state.confirm_action
                action_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                is_admin = current_role == "admin"

                if action["type"] == "fix":
                    icon = "✅"
                    title = "Confirm Fix Software"
                    subtitle = "Mark this asset as fixed and ready for deployment"
                    current_state = action["current_status"]
                    next_state = "IN_STOCK_WORKING"
                else:  # vendor
                    icon = "🔧"
                    title = "Confirm Send to Vendor"
                    subtitle = "Send this asset to vendor for repair"
                    current_state = action["current_status"]
                    next_state = "WITH_VENDOR_REPAIR"

                # Get billing impact
                billing_impacts = get_billing_impact(current_state, next_state)

                st.markdown(f"""
                <div class="confirm-modal">
                    <div class="confirm-modal-header">
                        <div class="confirm-modal-icon">{icon}</div>
                        <div>
                            <div class="confirm-modal-title">{title}</div>
                            <div class="confirm-modal-subtitle">{subtitle}</div>
                        </div>
                    </div>
                    <div class="confirm-details">
                        <div class="confirm-detail-row">
                            <span class="confirm-detail-label">Asset ID</span>
                            <span class="confirm-detail-value">{action["serial"]}</span>
                        </div>
                        <div class="confirm-detail-row">
                            <span class="confirm-detail-label">Device</span>
                            <span class="confirm-detail-value">{action["brand"]} {action["model"]}</span>
                        </div>
                    </div>
                    <div class="confirm-state-change">
                        <span class="confirm-state current">{current_state.replace("_", " ")}</span>
                        <span class="confirm-arrow">→</span>
                        <span class="confirm-state next">{next_state.replace("_", " ")}</span>
                    </div>
                    <div class="confirm-timestamp">
                        Action will be logged at: {action_time}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Show billing impact (full details for admin, brief for operations)
                if billing_impacts:
                    if is_admin:
                        st.markdown("**Billing Impact:**")
                        for impact in billing_impacts:
                            if impact["type"] == "positive":
                                st.success(f"{impact['icon']} {impact['message']}")
                                st.caption(impact['detail'])
                            elif impact["type"] == "warning":
                                st.warning(f"{impact['icon']} {impact['message']}")
                                st.caption(impact['detail'])
                            else:
                                st.info(f"{impact['icon']} {impact['message']}")
                                st.caption(impact['detail'])
                    else:
                        # Lightweight for operations
                        for impact in billing_impacts:
                            st.caption(f"{impact['icon']} {impact['message']}")

                # Confirmation buttons
                confirm_col1, confirm_col2, confirm_col3 = st.columns([1, 1, 2])

                with confirm_col1:
                    if st.button("Confirm", key="confirm_yes", type="primary"):
                        if action["type"] == "fix":
                            success, error_msg = update_asset_status(action["record_id"], "IN_STOCK_WORKING", "Office")
                            if success:
                                st.session_state.confirm_action = None
                                st.success(f"{action['serial']} repair completed. Logged at {action_time}")
                                safe_rerun()
                            else:
                                st.error(f"Cannot update status: {error_msg}")
                        else:  # vendor
                            success, error_msg = update_asset_status(action["record_id"], "WITH_VENDOR_REPAIR", "Vendor")
                            if success:
                                # Create repair record with timestamp
                                repair_data = {
                                    "Repair Reference": f"RPR-{datetime.now().strftime('%Y%m%d%H%M')}-{action['serial']}",
                                    "Sent Date": date.today().isoformat(),
                                    "Expected Return": (date.today() + timedelta(days=14)).isoformat(),
                                    "Repair Description": f"[{action_time}] Sent from dashboard - {action['notes'][:50] if action['notes'] else 'No notes'}",
                                    "Status": "WITH_VENDOR"
                                }
                                create_repair_record(repair_data, user_role=st.session_state.get('user_role', 'admin'))
                                st.session_state.confirm_action = None
                                st.success(f"{action['serial']} sent to vendor. Logged at {action_time}")
                                safe_rerun()
                            else:
                                st.error(f"Cannot update status: {error_msg}")

                with confirm_col2:
                    if st.button("Cancel", key="confirm_no"):
                        st.session_state.confirm_action = None
                        safe_rerun()

                st.markdown("---")

            if not attention_df.empty:
                # Calculate days since returned for each asset
                today = date.today()

                # Table header
                header_col1, header_col2, header_col3, header_col4, header_col5 = st.columns([2.5, 1.5, 1, 1.2, 1.8])
                with header_col1:
                    st.markdown("<span style='font-size: 0.75rem; color: #64748b; font-weight: 600;'>ASSET</span>", unsafe_allow_html=True)
                with header_col2:
                    st.markdown("<span style='font-size: 0.75rem; color: #64748b; font-weight: 600;'>STATUS</span>", unsafe_allow_html=True)
                with header_col3:
                    st.markdown("<span style='font-size: 0.75rem; color: #64748b; font-weight: 600;'>DAYS</span>", unsafe_allow_html=True)
                with header_col4:
                    st.markdown("<span style='font-size: 0.75rem; color: #64748b; font-weight: 600;'>PRIORITY</span>", unsafe_allow_html=True)
                with header_col5:
                    st.markdown("<span style='font-size: 0.75rem; color: #64748b; font-weight: 600;'>ACTIONS</span>", unsafe_allow_html=True)

                st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

                for idx, row in attention_df.iterrows():
                    serial = row.get("Serial Number", "Unknown")
                    brand = row.get("Brand", "N/A")
                    model = row.get("Model", "N/A")
                    status = row.get("Current Status", "")
                    notes = row.get("Notes", "") or ""
                    record_id = row.get("_id", "")

                    # Calculate days since status change
                    days_since = 0
                    try:
                        import re
                        date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', str(notes))
                        if date_match:
                            day, month, year = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                            returned_date = date(year, month, day)
                            days_since = (today - returned_date).days
                        else:
                            days_since = 5
                    except:
                        days_since = 5

                    # Determine priority using SLA config
                    sla_status, _ = calculate_sla_status(status, days_since)
                    if sla_status == "critical":
                        priority_label = "Critical"
                        priority_badge = "priority-high"
                    elif sla_status == "warning":
                        priority_label = "Warning"
                        priority_badge = "priority-medium"
                    else:
                        priority_label = "Normal"
                        priority_badge = "priority-low"

                    days_class = "urgent" if sla_status in ["critical", "warning"] else ""

                    # Create row with columns
                    col1, col2, col3, col4, col5 = st.columns([2.5, 1.5, 1, 1.2, 1.8])

                    with col1:
                        st.markdown(f"""
                        <div class="attention-info">
                            <span class="attention-title">{serial}</span>
                            <span class="attention-subtitle">{brand} {model}</span>
                        </div>
                        """, unsafe_allow_html=True)

                    with col2:
                        status_display = status.replace("_", " ").title()
                        st.markdown(f"<span style='font-size: 0.8rem; color: #64748b;'>{status_display}</span>", unsafe_allow_html=True)

                    with col3:
                        st.markdown(f"<span class='attention-days {days_class}'>{days_since} days</span>", unsafe_allow_html=True)

                    with col4:
                        st.markdown(f"<span class='priority-badge {priority_badge}'>{priority_label}</span>", unsafe_allow_html=True)

                    with col5:
                        # Only show action buttons if role has drill-down permission
                        if role_config["can_drill_down"]:
                            btn_col1, btn_col2 = st.columns(2)

                            # Fix Software - only for RETURNED_FROM_CLIENT
                            with btn_col1:
                                fix_disabled = status != "RETURNED_FROM_CLIENT"
                                if st.button("Fix", key=f"fix_{serial}", disabled=fix_disabled):
                                    st.session_state.confirm_action = {
                                        "type": "fix",
                                        "serial": serial,
                                        "brand": brand,
                                        "model": model,
                                        "current_status": status,
                                        "record_id": record_id,
                                        "notes": notes
                                    }
                                    safe_rerun()

                            # Send to Vendor - only for RETURNED_FROM_CLIENT or IN_OFFICE_TESTING
                            with btn_col2:
                                vendor_disabled = status not in ["RETURNED_FROM_CLIENT", "IN_OFFICE_TESTING"]
                                if st.button("Vendor", key=f"vendor_{serial}", disabled=vendor_disabled):
                                    st.session_state.confirm_action = {
                                        "type": "vendor",
                                        "serial": serial,
                                        "brand": brand,
                                        "model": model,
                                        "current_status": status,
                                        "record_id": record_id,
                                        "notes": notes
                                    }
                                    safe_rerun()
                        else:
                            st.markdown("<span style='font-size: 0.75rem; color: #94a3b8;'>View only</span>", unsafe_allow_html=True)

                    st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)

                # Summary footer
                urgent_count = len(attention_df)
                st.markdown(f"""
                <div style="text-align: right; padding: 0.5rem 0; color: #64748b; font-size: 0.8rem;">
                    Showing {urgent_count} asset(s) needing attention
                </div>
                """, unsafe_allow_html=True)

            else:
                st.markdown("""
                <div class="alert-card success" style="text-align: center; padding: 2rem;">
                    <strong style="font-size: 1.1rem;">✓ All Clear</strong><br>
                    <span style="font-size: 0.9rem; color: #166534;">No assets requiring immediate attention</span>
                </div>
                """, unsafe_allow_html=True)

    # ASSETS PAGE

