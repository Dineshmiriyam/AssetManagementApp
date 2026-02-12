"""
Empty state and success state components — extracted from app.py.
Consistent UI for when data is missing or operations succeed.
"""

import streamlit as st

from core.data import safe_rerun


# Centralized empty state messages with suggested actions (no emojis)
EMPTY_STATES = {
    "no_assets": {
        "icon": "box",
        "title": "No Assets in System",
        "message": "Your asset inventory is empty. Add your first asset to get started.",
        "action": "Add Asset",
        "action_page": "Add Asset",
        "color": "#3b82f6"
    },
    "no_billable_assets": {
        "icon": "briefcase",
        "title": "No Billable Assets",
        "message": "No assets are currently deployed with clients. Assign assets to start generating revenue.",
        "action": "Assign Asset",
        "action_page": "Quick Actions",
        "color": "#f59e0b"
    },
    "all_under_repair": {
        "icon": "tool",
        "title": "All Assets Under Repair",
        "message": "All your assets are currently with repair vendors. No assets available for deployment.",
        "action": "Check Repair Status",
        "action_page": "Issues & Repairs",
        "color": "#ef4444"
    },
    "no_sla_issues": {
        "icon": "check",
        "title": "All Clear",
        "message": "No SLA warnings or critical items. All assets are within acceptable timeframes.",
        "action": None,
        "action_page": None,
        "color": "#10b981"
    },
    "no_clients": {
        "icon": "users",
        "title": "No Clients Yet",
        "message": "Add your first client to start assigning assets and generating revenue.",
        "action": "Add Client",
        "action_page": "Clients",
        "color": "#8b5cf6"
    },
    "no_issues": {
        "icon": "check",
        "title": "No Issues Reported",
        "message": "No issues have been logged. Your assets are running smoothly.",
        "action": None,
        "action_page": None,
        "color": "#10b981"
    },
    "no_repairs": {
        "icon": "check",
        "title": "No Active Repairs",
        "message": "No assets are currently in repair. All equipment is operational.",
        "action": None,
        "action_page": None,
        "color": "#10b981"
    },
    "no_assignments": {
        "icon": "clipboard",
        "title": "No Assignments Yet",
        "message": "No assets have been assigned to clients. Use Quick Actions to deploy assets.",
        "action": "Deploy Asset",
        "action_page": "Quick Actions",
        "color": "#6366f1"
    },
    "no_returns_pending": {
        "icon": "check",
        "title": "No Pending Returns",
        "message": "No assets are waiting to be processed after client return.",
        "action": None,
        "action_page": None,
        "color": "#10b981"
    },
    "no_stock_available": {
        "icon": "inbox",
        "title": "No Stock Available",
        "message": "All assets are either deployed, under repair, or unavailable. Consider procurement.",
        "action": "Add Asset",
        "action_page": "Add Asset",
        "color": "#f59e0b"
    },
    "no_activity": {
        "icon": "activity",
        "title": "No Recent Activity",
        "message": "No activity recorded for the selected time period.",
        "action": None,
        "action_page": None,
        "color": "#64748b"
    },
    "no_data": {
        "icon": "folder",
        "title": "No Data Available",
        "message": "Unable to load data. Check your connection or try refreshing.",
        "action": "Refresh",
        "action_page": None,
        "color": "#64748b"
    }
}


# SVG icon paths for empty states (no emojis)
EMPTY_STATE_ICONS = {
    "box": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line>',
    "briefcase": '<rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>',
    "tool": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path>',
    "clipboard": '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path><rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>',
    "inbox": '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>',
    "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>'
}


def render_empty_state(state_key: str, custom_message: str = None, show_action: bool = True) -> None:
    """
    Render a consistent empty state UI component.

    Args:
        state_key: Key from EMPTY_STATES config
        custom_message: Optional override for the message
        show_action: Whether to show the action button
    """
    state = EMPTY_STATES.get(state_key, EMPTY_STATES["no_data"])
    message = custom_message or state["message"]
    icon_path = EMPTY_STATE_ICONS.get(state['icon'], EMPTY_STATE_ICONS['folder'])

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {state['color']}08 0%, {state['color']}12 100%);
        border: 1px dashed {state['color']}40;
        border-radius: 12px;
        padding: 40px 30px;
        text-align: center;
        margin: 20px 0;
    ">
        <div style="margin-bottom: 16px;">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="{state['color']}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.7;">
                {icon_path}
            </svg>
        </div>
        <div style="font-size: 1.1rem; font-weight: 600; color: #1e293b; margin-bottom: 8px;">
            {state['title']}
        </div>
        <div style="font-size: 0.9rem; color: #64748b; max-width: 400px; margin: 0 auto;">
            {message}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Show action button if applicable
    if show_action and state["action"] and state["action_page"]:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(state['action'], key=f"empty_action_{state_key}"):
                st.session_state.current_page = state["action_page"]
                safe_rerun()


def render_success_state(title: str, message: str, icon: str = "check") -> None:
    """Render a success/all-clear state."""
    icon_path = EMPTY_STATE_ICONS.get(icon, EMPTY_STATE_ICONS['check'])

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #10b98108 0%, #10b98112 100%);
        border: 1px solid #10b98125;
        border-radius: 12px;
        padding: 30px 25px;
        text-align: center;
        margin: 15px 0;
    ">
        <div style="margin-bottom: 12px;">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.8;">
                {icon_path}
            </svg>
        </div>
        <div style="font-size: 1.05rem; font-weight: 600; color: #065f46; margin-bottom: 4px;">
            {title}
        </div>
        <div style="font-size: 0.875rem; color: #047857;">
            {message}
        </div>
    </div>
    """, unsafe_allow_html=True)


def get_system_health_summary(assets_df) -> dict:
    """
    Analyze system state and return health summary.
    Used to determine which empty states to show.
    """
    summary = {
        "has_assets": not assets_df.empty,
        "total_assets": len(assets_df) if not assets_df.empty else 0,
        "has_stock": False,
        "has_billable": False,
        "has_under_repair": False,
        "all_under_repair": False,
        "has_sla_issues": False,
        "has_returns_pending": False,
        "stock_count": 0,
        "billable_count": 0,
        "repair_count": 0,
        "return_count": 0
    }

    if assets_df.empty or "Current Status" not in assets_df.columns:
        return summary

    status_counts = assets_df["Current Status"].value_counts().to_dict()

    summary["stock_count"] = status_counts.get("IN_STOCK_WORKING", 0)
    summary["billable_count"] = status_counts.get("WITH_CLIENT", 0)
    summary["repair_count"] = status_counts.get("WITH_VENDOR_REPAIR", 0)
    summary["return_count"] = status_counts.get("RETURNED_FROM_CLIENT", 0)

    summary["has_stock"] = summary["stock_count"] > 0
    summary["has_billable"] = summary["billable_count"] > 0
    summary["has_under_repair"] = summary["repair_count"] > 0
    summary["has_returns_pending"] = summary["return_count"] > 0

    # Check if ALL assets are under repair
    if summary["total_assets"] > 0 and summary["repair_count"] == summary["total_assets"]:
        summary["all_under_repair"] = True

    return summary
