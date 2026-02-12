"""
Sidebar navigation & footer for Asset Lifecycle Management System.
Renders the professional sidebar with role-based menus, user info, and logout.
"""
import logging
from datetime import datetime

import streamlit as st

from config.constants import ROLE_PRIMARY_ACTION, USER_ROLES
from core.auth import logout_user
from core.data import safe_rerun
from services.audit_service import log_activity_event

logger = logging.getLogger("AssetManagement")

# Navigation menu structure with groups and role-based visibility
# "roles" key defines which roles can see each menu item
# If "roles" is not specified, item is visible to all roles
MENU_GROUPS = {
    "MAIN": [
        {"name": "Dashboard", "icon": "▣", "key": "dashboard"},  # All roles
    ],
    "INVENTORY": [
        {"name": "Assets", "icon": "▢", "key": "assets"},  # All roles
        {"name": "Add Asset", "icon": "＋", "key": "add_asset", "roles": ["admin", "operations"]},  # Finance cannot create
        {"name": "Quick Actions", "icon": "⟲", "key": "quick_actions", "roles": ["admin", "operations"]},  # Finance cannot do actions
    ],
    "OPERATIONS": [
        {"name": "Assignments", "icon": "☰", "key": "assignments"},  # All roles
        {"name": "Issues & Repairs", "icon": "⚙", "key": "issues", "roles": ["admin", "operations"]},  # Finance cannot do repairs
        {"name": "Clients", "icon": "◈", "key": "clients"},  # All roles
    ],
    "BILLING": [
        {"name": "Billing", "icon": "₹", "key": "billing", "roles": ["admin", "finance"]},  # Finance and Admin only
    ],
    "REPORTS": [
        {"name": "Reports", "icon": "▤", "key": "reports"},  # All roles - reporting only
        {"name": "Activity Log", "icon": "◷", "key": "activity_log"},  # All roles - view based on role
    ],
    "SYSTEM": [
        {"name": "Import/Export", "icon": "⇄", "key": "import_export", "roles": ["admin", "operations"]},  # Admin and Operations
        {"name": "User Management", "icon": "◉", "key": "users", "roles": ["admin"]},  # Admin only
        {"name": "Settings", "icon": "⚙", "key": "settings", "roles": ["admin"]},  # Admin only
    ],
}


def get_visible_menu_items(role):
    """Filter menu items based on user role"""
    visible_groups = {}
    for group_name, items in MENU_GROUPS.items():
        visible_items = [
            item for item in items
            if "roles" not in item or role in item["roles"]
        ]
        if visible_items:  # Only include group if it has visible items
            visible_groups[group_name] = visible_items
    return visible_groups


def render_sidebar(db_connected: bool) -> str:
    """
    Render the full sidebar: brand, nav buttons, user info, logout.
    Returns the current page name after navigation handling.
    """
    # Brand Header
    st.sidebar.markdown("""
    <div class="sidebar-brand">
        <img src="https://cdn-media.nxtby.com/media/logo/stores/1/nxtby_orange_1.png" alt="Nxtby.com">
        <p>Asset Management</p>
    </div>
    """, unsafe_allow_html=True)

    # Navigation menu with groups - filter by role and collect button clicks
    nav_clicked = None
    current_role = st.session_state.user_role
    visible_menu = get_visible_menu_items(current_role)

    for group_name, items in visible_menu.items():
        # Compact section header
        st.sidebar.markdown(f'<div class="nav-section-header">{group_name}</div>', unsafe_allow_html=True)

        for item in items:
            is_active = st.session_state.current_page == item["name"]
            is_primary_action = item["name"] == ROLE_PRIMARY_ACTION.get(current_role)

            # Primary action indicator (subtle)
            if is_primary_action and not is_active:
                st.sidebar.markdown(
                    '<div style="height: 2px; background: linear-gradient(90deg, #f97316 0%, transparent 100%); margin: 2px 16px 2px 16px; border-radius: 1px;"></div>',
                    unsafe_allow_html=True
                )

            if st.sidebar.button(
                f"{item['icon']}  {item['name']}",
                key=f"nav_{item['key']}_{current_role}",
                type="primary" if is_active else "secondary",
                help="Recommended for your role" if is_primary_action and not is_active else None
            ):
                nav_clicked = item["name"]

    # ============================================
    # USER INFO SECTION (After Navigation)
    # ============================================
    st.sidebar.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)

    # User Info & Role
    user_display_name = st.session_state.user_full_name or st.session_state.username
    user_role = st.session_state.user_role or "operations"
    role_config = USER_ROLES[user_role]

    # Connection status (compact)
    connection_html = """<span class="connection-status status-connected">● Online</span>""" if db_connected else """<span class="connection-status status-disconnected">○ Offline</span>"""

    st.sidebar.markdown(f"""
    <div class="user-info-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <div>
                <div class="user-name">{user_display_name}</div>
                <div class="user-role">{role_config['description']}</div>
            </div>
            <span class="role-badge-compact {user_role}">{role_config['name']}</span>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            {connection_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Logout button (compact)
    if st.sidebar.button("Sign Out", key="logout_btn", use_container_width=True):
        log_activity_event(
            action_type="USER_LOGOUT",
            category="authentication",
            user_role=st.session_state.user_role,
            description=f"User signed out: {st.session_state.username}",
            success=True
        )
        logout_user()
        # Clear session token from URL
        st.query_params.clear()
        logger.info("Query params cleared on logout")
        safe_rerun()

    # Update page if navigation button was clicked
    if nav_clicked and nav_clicked != st.session_state.current_page:
        st.session_state.current_page = nav_clicked

    # Set page variable from session state
    page = st.session_state.current_page

    # Security check: Verify user has access to current page based on role
    # This handles cases where user navigates directly or was on a page before role change
    current_role = st.session_state.user_role
    accessible_pages = [item["name"] for items in get_visible_menu_items(current_role).values() for item in items]
    if page not in accessible_pages:
        # Log unauthorized access attempt
        if 'access_denied_log' not in st.session_state:
            st.session_state.access_denied_log = []
        st.session_state.access_denied_log.append({
            "timestamp": datetime.now().isoformat(),
            "role": current_role,
            "attempted_page": page,
            "action": "redirect_to_dashboard"
        })
        # Set warning flag to show on dashboard
        st.session_state.access_warning = f"Access denied to '{page}'. You have been redirected to Dashboard."
        st.session_state.current_page = "Dashboard"
        page = "Dashboard"
        safe_rerun()

    # Show access warning if redirected
    if 'access_warning' in st.session_state and st.session_state.access_warning:
        st.warning(st.session_state.access_warning)
        st.session_state.access_warning = None  # Clear after showing

    return page


def render_footer():
    """Render the sidebar footer with version info."""
    st.sidebar.markdown("""
    <div class="sidebar-footer">
        <div class="version">Asset Management v2.4</div>
        <div class="tech">Streamlit + MySQL</div>
    </div>
    """, unsafe_allow_html=True)
