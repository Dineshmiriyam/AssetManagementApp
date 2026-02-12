"""
Asset Lifecycle Management System v2.4
A Streamlit web application with Airtable/MySQL support
Enhanced with role-based analytics, SLA indicators, and RBAC
Production-hardened with centralized error handling
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pyairtable import Api, Table
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go
import os
import logging
import traceback
from functools import wraps
from dotenv import load_dotenv
from streamlit_plotly_events import plotly_events
from config.constants import (
    SESSION_TIMEOUT_HOURS, INACTIVITY_TIMEOUT_MINUTES,
    USER_ROLES, SLA_CONFIG, PAGINATION_CONFIG, CACHE_CONFIG, QUERY_LIMITS,
    BILLING_CONFIG, ASSET_STATUSES, STATUS_COLORS, ALLOWED_TRANSITIONS,
    STATUS_DISPLAY_NAMES, VALID_INITIAL_STATUSES, CRITICAL_ACTIONS,
)
from config.styles import get_anti_flicker_css, get_login_css, get_dashboard_css
from core.errors import (
    USER_SAFE_MESSAGES, get_error_id, log_error, classify_error,
    safe_execute, handle_db_error,
)
from core.data import (
    safe_rerun, get_table, TABLES, _get_empty_data_structure,
    get_pagination_state, paginate_dataframe, render_pagination_controls,
    render_page_navigation, reset_pagination,
    get_cache_key, invalidate_cache_for, get_cached_dataframe,
    fetch_all_data, clear_cache,
)
from config.permissions import (
    PERMISSIONS, PAGE_ACCESS_CONTROL, ACTION_PERMISSIONS, ACTION_DISPLAY_NAMES,
    ActionResult, has_permission, check_page_access,
    can_view_billing, can_view_revenue, can_create_asset,
    can_perform_lifecycle_action, can_manage_repairs, can_override_billing,
    validate_action, get_permitted_actions, render_access_denied,
)
from services.billing_service import (
    get_asset_billing_status, get_billable_assets, get_paused_billing_assets,
    calculate_billing_metrics, validate_billing_override, get_billing_impact,
)
from services.asset_service import (
    validate_state_transition, get_asset_current_status,
    update_asset_status, create_repair_record,
    create_assignment_record, create_issue_record,
)
from services.sla_service import (
    calculate_sla_status, get_sla_counts, filter_assets_by_role,
)
from services.audit_service import (
    generate_audit_id, get_session_id, log_state_change,
    log_activity_event, get_audit_summary,
)
from components.charts import create_analytics_bar_chart
from components.empty_states import (
    EMPTY_STATES, EMPTY_STATE_ICONS, render_empty_state,
    render_success_state, get_system_health_summary,
)
from components.loading import (
    render_loading_skeleton, render_skeleton_card, render_skeleton_table,
    render_skeleton_chart, render_skeleton_metrics, render_loading_overlay,
    init_loading_state, set_loading, is_loading,
)
from components.feedback import (
    render_billing_status_badge, render_error_state,
    render_inline_error, render_inline_warning,
    with_error_handling, render_action_button,
)
from components.confirmation import (
    init_action_confirmation, request_action_confirmation,
    clear_action_confirmation, render_confirmation_dialog,
)

# Load environment variables
load_dotenv()

# ============================================
# PRODUCTION ERROR HANDLING & LOGGING
# ============================================
# Configure logging - technical errors go to file, not UI
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding='utf-8'),
        logging.StreamHandler() if os.getenv("DEBUG", "false").lower() == "true" else logging.NullHandler()
    ]
)
logger = logging.getLogger("AssetManagement")

# Error tracking for session
if 'error_count' not in st.session_state:
    st.session_state.error_count = 0

# ============================================
# DATA SOURCE CONFIGURATION
# ============================================
# Toggle between "airtable" and "mysql"
# Set via environment variable or change default here
DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql")  # Options: "airtable", "mysql"

# MySQL imports (only if needed)
if DATA_SOURCE == "mysql":
    try:
        from database.db import (
            DatabaseConnection,
            get_all_assets as mysql_get_assets,
            get_all_clients as mysql_get_clients,
            get_all_assignments as mysql_get_assignments,
            get_all_issues as mysql_get_issues,
            get_all_repairs as mysql_get_repairs,
            get_asset_current_status_db,
            update_asset_status_db,
            create_asset as mysql_create_asset,
            create_assignment as mysql_create_assignment,
            create_issue as mysql_create_issue,
            create_repair as mysql_create_repair,
            log_state_change_db,
            update_asset as mysql_update_asset,
            log_activity as db_log_activity,
            get_activity_log as db_get_activity_log,
            get_activity_stats as db_get_activity_stats,
            ACTION_TYPES, BILLING_ACTIONS, BILLING_STATES,
            # Billing period functions
            get_billing_period,
            get_billing_period_status,
            is_billing_period_closed,
            get_all_billing_periods,
            close_billing_period,
            reopen_billing_period,
            can_modify_billing_data,
            get_current_billing_period,
            # Database setup functions
            setup_database,
            check_tables_exist,
            get_table_stats
        )
        from database.config import DB_CONFIG
        from database.auth import (
            authenticate_user,
            create_user,
            get_all_users,
            update_user,
            change_password,
            deactivate_user,
            activate_user,
            get_user_count,
            invalidate_session,
            validate_session,
            is_database_available
        )
        MYSQL_AVAILABLE = True
        AUTH_AVAILABLE = True

        # Auto-setup database tables on startup
        if 'db_setup_done' not in st.session_state:
            success, tables = check_tables_exist()
            required_tables = ['assets', 'clients', 'assignments', 'issues', 'repairs']
            if success:
                missing_tables = [t for t in required_tables if t not in tables]
                if missing_tables:
                    setup_success, setup_msg = setup_database()
                    if setup_success:
                        st.session_state.db_setup_done = True
                        st.toast("Database tables initialized successfully!")
                    else:
                        st.error(f"Database setup failed: {setup_msg}")
                else:
                    st.session_state.db_setup_done = True
            else:
                # Try to setup anyway
                setup_success, setup_msg = setup_database()
                if setup_success:
                    st.session_state.db_setup_done = True

    except ImportError as e:
        MYSQL_AVAILABLE = False
        AUTH_AVAILABLE = False
        st.warning(f"MySQL module not available: {e}. Using Airtable.")
        DATA_SOURCE = "airtable"
else:
    MYSQL_AVAILABLE = False
    AUTH_AVAILABLE = False

# ============================================
# AUTHENTICATION & SESSION MANAGEMENT
# ============================================
def init_auth_session():
    """Initialize authentication session state with security defaults"""
    defaults = {
        'authenticated': False,
        'user_id': None,
        'username': None,
        'user_email': None,
        'user_full_name': None,
        'user_role': None,
        'login_time': None,
        'last_activity': None,
        'session_token': None,
        'login_error': None,
        'login_processing': False,
        'last_session_validation': None,
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def check_session_timeout():
    """
    Check if session has timed out (absolute or inactivity).
    Returns True if session was invalidated.
    """
    if not st.session_state.authenticated:
        return False

    now = datetime.now()

    # Check absolute session timeout (8 hours)
    if st.session_state.login_time:
        elapsed = now - st.session_state.login_time
        if elapsed.total_seconds() > (SESSION_TIMEOUT_HOURS * 3600):
            logout_user(reason="session_expired")
            return True

    # Check inactivity timeout (30 minutes)
    if st.session_state.last_activity:
        inactive = now - st.session_state.last_activity
        if inactive.total_seconds() > (INACTIVITY_TIMEOUT_MINUTES * 60):
            logout_user(reason="inactivity")
            return True

    # Update last activity timestamp
    st.session_state.last_activity = now
    return False


def validate_current_session():
    """
    Validate the current session against server-side state.
    Prevents session manipulation and ensures session is still valid.
    Uses caching to avoid validating on every single page refresh.
    """
    if not st.session_state.authenticated:
        return False

    if not AUTH_AVAILABLE:
        return True  # Skip validation if auth module unavailable

    user_id = st.session_state.user_id
    session_token = st.session_state.session_token

    if not user_id or not session_token:
        logout_user(reason="invalid_session")
        return False

    # Only validate every 5 minutes to avoid database calls on every refresh
    VALIDATION_INTERVAL_SECONDS = 300  # 5 minutes
    now = datetime.now()

    last_validation = st.session_state.get('last_session_validation')
    if last_validation:
        elapsed = (now - last_validation).total_seconds()
        if elapsed < VALIDATION_INTERVAL_SECONDS:
            return True  # Skip validation, use cached result

    # Validate session token against server
    try:
        is_valid, user_data, _err = validate_session(user_id, session_token)
        if not is_valid:
            if _err:
                return True  # Transient DB error — don't logout, retry later
            logout_user(reason="session_invalidated")
            return False

        # Update role in case it was changed by admin
        if user_data:
            st.session_state.user_role = user_data.get('role', st.session_state.user_role)

        # Cache the validation time
        st.session_state.last_session_validation = now
        return True
    except Exception:
        # Don't crash or logout on validation errors, just continue
        # This prevents logout on transient database issues
        return True


def login_user(user_data: dict):
    """
    Set session state after successful login.
    Stores session token for server-side validation.
    Note: Caller is responsible for setting st.query_params["sid"] separately.
    """
    st.session_state.authenticated = True
    st.session_state.user_id = user_data['id']
    st.session_state.username = user_data['username']
    st.session_state.user_email = user_data.get('email', '')
    st.session_state.user_full_name = user_data.get('full_name', user_data['username'])
    st.session_state.user_role = user_data.get('role', 'operations')
    st.session_state.login_time = datetime.now()
    st.session_state.last_activity = datetime.now()
    st.session_state.session_token = user_data.get('session_token')
    st.session_state.last_session_validation = datetime.now()  # Set initial validation time
    st.session_state.login_error = None
    st.session_state.login_processing = False


def logout_user(reason: str = None):
    """
    Clear session state on logout and invalidate server-side session.
    Note: Caller is responsible for clearing st.query_params separately.
    """
    # Invalidate server-side session
    if AUTH_AVAILABLE and st.session_state.user_id:
        try:
            invalidate_session(st.session_state.user_id)
        except Exception:
            pass  # Don't fail logout if invalidation fails

    # Clear all session state
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.user_email = None
    st.session_state.user_full_name = None
    st.session_state.user_role = None
    st.session_state.login_time = None
    st.session_state.last_activity = None
    st.session_state.session_token = None
    st.session_state.login_processing = False

    # Set appropriate message based on reason
    if reason == "session_expired":
        st.session_state.login_error = "Your session has expired. Please sign in again."
    elif reason == "inactivity":
        st.session_state.login_error = "You were logged out due to inactivity."
    elif reason == "session_invalidated":
        st.session_state.login_error = "Your session is no longer valid. Please sign in again."


def render_login_page():
    """
    Render login page matching mis.nxtby.com reference design.
    """
    # Check auth system availability
    auth_system_available = AUTH_AVAILABLE
    if auth_system_available:
        try:
            auth_system_available = is_database_available()
        except Exception:
            auth_system_available = False

    # Complete CSS matching reference design
    st.markdown(get_login_css(), unsafe_allow_html=True)

    # Top spacing
    st.markdown("<div style='height: 4vh;'></div>", unsafe_allow_html=True)

    # Brand/Logo section (ABOVE the card) - nxtby.com branding
    st.markdown("""
    <div class="login-brand">
        <img src="https://cdn-media.nxtby.com/media/logo/stores/1/nxtby_orange_1.png" alt="nxtby.com" class="login-brand-logo-img" />
        <p class="login-brand-tagline">Asset Management System</p>
    </div>
    """, unsafe_allow_html=True)

    # Center column for white card
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Service unavailable state
        if not auth_system_available:
            st.markdown("""
            <div class="service-unavailable">
                <p>Authentication service temporarily unavailable.<br/>Please try again later.</p>
            </div>
            <div class="login-footer">
                <p class="login-footer-brand">Powered by <span>nxtby.com</span></p>
            </div>
            """, unsafe_allow_html=True)
            return

        # Session expiry warning
        if st.session_state.login_error:
            st.markdown(f"""
            <div class="session-warning">
                <p>{st.session_state.login_error}</p>
            </div>
            """, unsafe_allow_html=True)
            st.session_state.login_error = None

        # Login form - white card with SIGN IN header inside
        with st.form("login_form", clear_on_submit=False):
            # SIGN IN header inside the form
            st.markdown("""
            <div class="login-card-header">
                <h2>SIGN IN</h2>
            </div>
            """, unsafe_allow_html=True)

            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="login_username",
                disabled=st.session_state.login_processing
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password",
                disabled=st.session_state.login_processing
            )

            button_text = "Log In" if not st.session_state.login_processing else "Logging in..."
            submit = st.form_submit_button(
                button_text,
                use_container_width=True,
                type="primary",
                disabled=st.session_state.login_processing
            )

            if submit and not st.session_state.login_processing:
                username_clean = username.strip() if username else ""
                password_provided = bool(password)

                if not username_clean or not password_provided:
                    st.error("Please enter your credentials")
                elif len(username_clean) < 2:
                    st.error("Please enter a valid username")
                else:
                    st.session_state.login_processing = True
                    try:
                        success, user_data, message = authenticate_user(username_clean, password)
                        if success and user_data:
                            login_user(user_data)
                            # Persist session token in URL for hard refresh recovery
                            token = user_data.get('session_token')
                            if token:
                                st.query_params["sid"] = f"{user_data['id']}:{token}"
                                logger.info("Session token set in URL query params")
                            else:
                                logger.warning("No session_token in user_data after login")
                                safe_rerun()
                        else:
                            st.session_state.login_processing = False
                            st.error(message)
                    except Exception as e:
                        logger.error(f"Login error: {e}")
                        st.session_state.login_processing = False
                        st.error("An error occurred. Please try again.")

        # Autofocus script
        st.markdown("""
        <script>
        setTimeout(function() {
            var el = window.parent.document.querySelector('input[aria-label="Username"]');
            if (el) el.focus();
        }, 150);
        </script>
        """, unsafe_allow_html=True)


# Page configuration
st.set_page_config(
    page_title="Asset Management System",
    page_icon="🟠",
    layout="wide",
    initial_sidebar_state="expanded"  # Sidebar visible after login; opacity:0 hides flash
)

# ============================================
# CRITICAL: HIDE ALL UI UNTIL AUTH IS RESOLVED
# ============================================
# This CSS runs FIRST to prevent any visual flash during auth check
# It will be overridden by login page CSS or main app CSS
st.markdown(get_anti_flicker_css(), unsafe_allow_html=True)

# ============================================
# EARLY AUTH CHECK - BEFORE ANY UI RENDERING
# ============================================
# This MUST run before any other st.* calls to prevent login flash

# 1. Initialize auth session state defaults
init_auth_session()

# 2. Try to restore session from URL query params (survives hard refresh)
#    On hard refresh, Streamlit session state is lost but URL params persist.
#    If a valid session token is in the URL, restore the session automatically.
if not st.session_state.authenticated:
    _sid = st.query_params.get("sid")
    _clear_sid = False  # Flag to clear sid OUTSIDE try/except
    if _sid and AUTH_AVAILABLE:
        try:
            _parts = _sid.split(":", 1)
            if len(_parts) == 2:
                _restore_uid = int(_parts[0])
                _restore_token = _parts[1]
                _is_valid, _user_data, _err_type = validate_session(_restore_uid, _restore_token)
                if _is_valid and _user_data:
                    # Restore session from persisted token
                    _user_data['session_token'] = _restore_token
                    login_user(_user_data)
                elif _err_type:
                    # DB/connection error — keep sid in URL for retry on next load
                    pass
                else:
                    # Token is explicitly invalid/expired — flag for clearing
                    _clear_sid = True
        except ValueError:
            # Malformed sid param (bad format) — flag for clearing
            _clear_sid = True
        except Exception:
            # Network/DB error — keep sid in URL so next page load can retry
            pass

    # Clear invalid sid OUTSIDE try/except so it's not silently caught
    if _clear_sid:
        st.query_params.clear()
        logger.info("Cleared invalid/expired sid from URL")

# 3. If STILL not authenticated, render login page and STOP immediately
# This prevents ANY main app UI from rendering
if not st.session_state.authenticated:
    render_login_page()
    st.stop()

# 4. User IS authenticated from this point forward
# Navigation is handled via sidebar buttons and session state
# ============================================

# Professional Dashboard Theme CSS - Matching Reference Design
st.markdown(get_dashboard_css(), unsafe_allow_html=True)

# Airtable Configuration (credentials from environment only)
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")

def validate_credentials() -> dict:
    """Validate all required credentials are present."""
    issues = []

    if DATA_SOURCE == "airtable":
        if not AIRTABLE_API_KEY:
            issues.append("AIRTABLE_API_KEY not configured")
        if not AIRTABLE_BASE_ID:
            issues.append("AIRTABLE_BASE_ID not configured")
    elif DATA_SOURCE == "mysql":
        if not MYSQL_AVAILABLE:
            issues.append("MySQL module not available")

    return {"valid": len(issues) == 0, "issues": issues}

ASSET_TYPES = ["Laptop", "Phone", "Printer", "Other"]
BRANDS = ["Lenovo", "Apple", "HP", "Dell", "Other"]
STORAGE_TYPES = ["SSD", "HDD"]
OS_OPTIONS = ["Windows 10 Pro", "Windows 11 Pro", "macOS"]

ISSUE_CATEGORIES = [
    "VPN Connection Issue", "Windows Reset Problem", "OS Installation Issue",
    "Driver Issue", "Blue Screen / Restart", "Display Issue",
    "HDMI Port Issue", "Keyboard Issue", "Physical Damage", "Battery Issue"
]

# Primary action per role - visually emphasized in sidebar
ROLE_PRIMARY_ACTION = {
    "operations": "Issues & Repairs",
    "finance": "Billing",
    "admin": "Dashboard"
}

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

# ============================================
# SESSION SECURITY CHECKS (Auth already verified at top of file)
# ============================================
# Note: init_auth_session() and login check are handled BEFORE global CSS
# to prevent login page flash. See lines after st.set_page_config()

# Perform security checks for authenticated sessions
# Check for session timeout (absolute and inactivity)
session_timed_out = check_session_timeout()

# If not timed out, validate session against server
if not session_timed_out:
    validate_current_session()

# SAFETY CHECK: If user was logged out by timeout/validation, redirect to login
# This prevents code from continuing with invalid session state
if not st.session_state.authenticated:
    render_login_page()
    st.stop()

# Initialize session state for navigation (if not already set by query params)
if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

# User role is now set from login (no need for default)

# Check API/Database connection first
if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
    # MySQL mode - check database connection
    api = True  # Set to True so existing checks pass
    try:
        db_connected, db_msg = DatabaseConnection.test_connection()
    except:
        db_connected = False
else:
    # Airtable mode
    api = get_airtable_api()
    db_connected = api is not None

# ============================================
# PROFESSIONAL SIDEBAR NAVIGATION
# ============================================

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

# Fetch all data with session state caching for faster navigation
if api:
    # Initialize data error state
    if 'data_load_error' not in st.session_state:
        st.session_state.data_load_error = None
    if 'data_load_error_id' not in st.session_state:
        st.session_state.data_load_error_id = None

    # Only fetch data if not in session state or marked as stale
    if 'all_data' not in st.session_state or st.session_state.get('data_stale', True):
        try:
            with st.spinner('Loading data...'):
                st.session_state.all_data = fetch_all_data()
                st.session_state.data_stale = False
                st.session_state.data_load_error = None
                st.session_state.data_load_error_id = None
        except Exception as e:
            # Log technical error, store user-safe message
            error_id = log_error(e, "main_data_load", st.session_state.get('user_role'))
            error_type = classify_error(e)
            st.session_state.data_load_error = USER_SAFE_MESSAGES.get(error_type, USER_SAFE_MESSAGES["default"])
            st.session_state.data_load_error_id = error_id
            st.session_state.all_data = _get_empty_data_structure()

    # Check for retry request
    if st.session_state.get('retry_data_load', False):
        st.session_state.retry_data_load = False
        st.session_state.data_stale = True
        safe_rerun()

    all_data = st.session_state.all_data
else:
    all_data = _get_empty_data_structure()

assets_df = all_data.get("assets", pd.DataFrame())
clients_df = all_data.get("clients", pd.DataFrame())
issues_df = all_data.get("issues", pd.DataFrame())
repairs_df = all_data.get("repairs", pd.DataFrame())
assignments_df = all_data.get("assignments", pd.DataFrame())

# ============================================
# DASHBOARD PAGE
# ============================================
if page == "Dashboard":
    st.markdown('<p class="main-header">Asset Management Dashboard</p>', unsafe_allow_html=True)

    if not api:
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
    elif assets_df.empty:
        render_empty_state("no_assets")
    else:
        # Get system health summary for edge case handling
        system_health = get_system_health_summary(assets_df)

        # Check for critical edge cases
        if system_health["all_under_repair"]:
            st.markdown("""
            <div style="background: #fef2f2; border: 2px solid #ef4444; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                <strong style="color: #991b1b;">Critical: All Assets Under Repair</strong><br>
                <span style="color: #7f1d1d;">All your assets are currently with repair vendors. No assets available for deployment or billing.</span>
            </div>
            """, unsafe_allow_html=True)
        # Calculate metrics
        total = len(assets_df)
        with_client = len(assets_df[assets_df.get("Current Status", pd.Series()) == "WITH_CLIENT"]) if "Current Status" in assets_df.columns else 0
        in_stock = len(assets_df[assets_df.get("Current Status", pd.Series()) == "IN_STOCK_WORKING"]) if "Current Status" in assets_df.columns else 0
        under_repair = len(assets_df[assets_df.get("Current Status", pd.Series()) == "WITH_VENDOR_REPAIR"]) if "Current Status" in assets_df.columns else 0
        returned = len(assets_df[assets_df.get("Current Status", pd.Series()) == "RETURNED_FROM_CLIENT"]) if "Current Status" in assets_df.columns else 0
        sold = len(assets_df[assets_df.get("Current Status", pd.Series()) == "SOLD"]) if "Current Status" in assets_df.columns else 0
        disposed = len(assets_df[assets_df.get("Current Status", pd.Series()) == "DISPOSED"]) if "Current Status" in assets_df.columns else 0
        testing_count = len(assets_df[assets_df["Current Status"] == "IN_OFFICE_TESTING"]) if "Current Status" in assets_df.columns else 0

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
            sla_counts = get_sla_counts(assets_df)
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
                if st.button("View", key="sla_critical_btn", use_container_width=True):
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
                if st.button("View", key="sla_warning_btn", use_container_width=True):
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
                if st.button("View", key="returns_backlog_btn", use_container_width=True):
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
                if st.button("View", key="repair_backlog_btn", use_container_width=True):
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
            admin_billing = calculate_billing_metrics(assets_df)
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
            sla_counts = get_sla_counts(assets_df)
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
            finance_billing = calculate_billing_metrics(assets_df)
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
            if st.button("View All", key="kpi_total", use_container_width=True):
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
            if st.button("View Deployed", key="kpi_deployed", use_container_width=True):
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
            if st.button("View Available", key="kpi_available", use_container_width=True):
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
            if st.button("View Repairs", key="kpi_repair", use_container_width=True):
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
            if st.button("View Returned", key="kpi_returned", use_container_width=True):
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
            if st.button("View Sold", key="kpi_sold", use_container_width=True):
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
            if st.button("View Disposed", key="kpi_disposed", use_container_width=True):
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
        can_assign = in_stock > 0 and not clients_df.empty  # Assets available AND clients exist
        can_return = with_client > 0  # Assets with clients
        testing_count = len(assets_df[assets_df["Current Status"] == "IN_OFFICE_TESTING"]) if "Current Status" in assets_df.columns else 0
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
            sla_counts = get_sla_counts(assets_df)

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
                if st.button("View →", key="analytics_sla_critical", use_container_width=True):
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
                if st.button("View →", key="analytics_sla_warning", use_container_width=True):
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
                if st.button("View →", key="analytics_sla_ok", use_container_width=True):
                    st.session_state.current_page = "Assets"
                    st.session_state.sla_filter = "ok"
                    safe_rerun()

        if role_config["show_billing"]:
            # Billing Insights for Finance and Admin - using centralized calculations
            insight_billing = calculate_billing_metrics(assets_df)
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
                    if st.button("View Billable", key="finance_billable_btn", use_container_width=True):
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
                    if st.button("View Billing", key="finance_revenue_btn", use_container_width=True):
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
                    if st.button("View Paused", key="finance_paused_btn", use_container_width=True):
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
                    if st.button("View Billing", key="admin_revenue_btn", use_container_width=True):
                        st.session_state.current_page = "Billing"
                        safe_rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        # Filter data based on role for charts
        if current_role == "finance":
            chart_df = assets_df[assets_df["Current Status"].isin(["WITH_CLIENT", "SOLD"])] if "Current Status" in assets_df.columns else assets_df
            chart_title_suffix = " (Billable Focus)"
        elif current_role == "operations":
            chart_df = assets_df[assets_df["Current Status"].isin(["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR", "IN_OFFICE_TESTING"])] if "Current Status" in assets_df.columns else assets_df
            chart_title_suffix = " (Operations Focus)"
        else:
            chart_df = assets_df
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
                brand_chart_df = chart_df if not chart_df.empty else assets_df
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
                        use_container_width=True,
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
                status_chart_df = chart_df if not chart_df.empty else assets_df
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
                        use_container_width=True,
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

            attention_df = assets_df[assets_df["Current Status"].isin(["RETURNED_FROM_CLIENT", "IN_OFFICE_TESTING", "WITH_VENDOR_REPAIR"])] if "Current Status" in assets_df.columns else pd.DataFrame()

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

# ============================================
# ASSETS PAGE
# ============================================
elif page == "Assets":
    st.markdown('<p class="main-header">All Assets</p>', unsafe_allow_html=True)

    # Summary badges (quick status overview at the top)
    if not assets_df.empty and "Current Status" in assets_df.columns:
        total_count = len(assets_df)
        deployed_count = len(assets_df[assets_df["Current Status"] == "WITH_CLIENT"])
        available_count = len(assets_df[assets_df["Current Status"] == "IN_STOCK_WORKING"])
        returned_count = len(assets_df[assets_df["Current Status"] == "RETURNED_FROM_CLIENT"])
        repair_count = len(assets_df[assets_df["Current Status"] == "WITH_VENDOR_REPAIR"])
        testing_count = len(assets_df[assets_df["Current Status"] == "IN_OFFICE_TESTING"])

        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 8px 0 16px 0;">
            <span style="font-size: 14px; color: #6b7280;">Total: <strong style="color: #111827; font-size: 16px;">{total_count}</strong></span>
            <span style="color: #e5e7eb;">|</span>
            <span style="font-size: 12px; font-weight: 600; color: #FF6B35; padding: 3px 10px; background: #FF6B3515; border-radius: 12px;">{deployed_count} Deployed</span>
            <span style="font-size: 12px; font-weight: 600; color: #4CAF50; padding: 3px 10px; background: #4CAF5015; border-radius: 12px;">{available_count} Available</span>
            <span style="font-size: 12px; font-weight: 600; color: #2196F3; padding: 3px 10px; background: #2196F315; border-radius: 12px;">{returned_count} Returned</span>
            <span style="font-size: 12px; font-weight: 600; color: #FF9800; padding: 3px 10px; background: #FF980015; border-radius: 12px;">{repair_count} In Repair</span>
            <span style="font-size: 12px; font-weight: 600; color: #9C27B0; padding: 3px 10px; background: #9C27B015; border-radius: 12px;">{testing_count} Testing</span>
        </div>
        """, unsafe_allow_html=True)

    if not api:
        st.warning("Please configure your Airtable API key in Settings first.")
    elif st.session_state.get('data_load_error'):
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load assets data. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    elif assets_df.empty:
        render_empty_state("no_assets")
    else:
        # Get filters from session state (set by KPI card or chart clicks)
        default_status_filter = st.session_state.get("asset_filter", "All")
        default_brand_filter = st.session_state.get("brand_filter", "All")
        sla_filter_value = st.session_state.get("sla_filter", None)
        billing_paused_filter = st.session_state.get("billing_paused_filter", False)
        client_location_filter = st.session_state.get("client_location_filter", None)

        # Clear the filters after using them
        if "asset_filter" in st.session_state:
            del st.session_state.asset_filter
        if "brand_filter" in st.session_state:
            del st.session_state.brand_filter
        if "sla_filter" in st.session_state:
            del st.session_state.sla_filter
        if "billing_paused_filter" in st.session_state:
            del st.session_state.billing_paused_filter
        if "client_location_filter" in st.session_state:
            del st.session_state.client_location_filter

        # Show active filter banner if SLA or billing paused filter is applied
        if sla_filter_value:
            sla_labels = {"critical": "SLA Critical", "warning": "SLA Warning", "ok": "SLA OK"}
            sla_colors = {"critical": "#dc2626", "warning": "#f59e0b", "ok": "#16a34a"}
            st.info(f"🔍 Showing assets with **{sla_labels.get(sla_filter_value, sla_filter_value)}** status. Clear filters to see all assets.")
        elif billing_paused_filter:
            st.info("🔍 Showing assets with **Billing Paused** (Returned/Under Repair). Clear filters to see all assets.")
        elif client_location_filter:
            st.info(f"🔗 Showing assets at **{client_location_filter}**. Clear filters to see all assets.")

        # Handle linked record navigation - pre-fill search with serial number
        linked_serial = st.session_state.get("asset_search_serial", None)
        if linked_serial:
            st.session_state.assets_search = linked_serial
            del st.session_state.asset_search_serial
            st.info(f"🔗 Navigated from linked record. Showing asset: **{linked_serial}**")

        # Clear filters flag check BEFORE form (callback + flag pattern)
        if st.session_state.get('clear_asset_filters_flag', False):
            for key in ["assets_search", "asset_filter", "brand_filter"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.clear_asset_filters_flag = False

        # Search and Filters (wrapped in form to prevent rerun on every keystroke)
        with st.form(key="assets_search_form"):
            search = st.text_input("🔍 Search (Serial Number, Brand, Model)", key="assets_search", placeholder="Type to search...")

            # Filters row
            col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

            with col1:
                filter_options = ["All"] + ASSET_STATUSES
                default_index = filter_options.index(default_status_filter) if default_status_filter in filter_options else 0
                status_filter = st.selectbox("Status", filter_options, index=default_index)

            with col2:
                brand_list = sorted(list(assets_df["Brand"].dropna().unique())) if "Brand" in assets_df.columns else []
                brand_options = ["All"] + brand_list
                default_brand_index = brand_options.index(default_brand_filter) if default_brand_filter in brand_options else 0
                brand_filter = st.selectbox("Brand", brand_options, index=default_brand_index)

            with col3:
                type_list = sorted(list(assets_df["Asset Type"].dropna().unique())) if "Asset Type" in assets_df.columns else []
                type_filter = st.selectbox("Type", ["All"] + type_list)

            with col4:
                location_list = sorted(list(assets_df["Current Location"].dropna().unique())) if "Current Location" in assets_df.columns else []
                location_filter = st.selectbox("Location", ["All"] + location_list)

            # Search and Clear buttons side by side inside form
            btn_col1, btn_col2 = st.columns([3, 1])
            with btn_col1:
                search_submitted = st.form_submit_button("🔍 Search", use_container_width=True, type="primary")
            with btn_col2:
                clear_submitted = st.form_submit_button("Clear Filters", use_container_width=True)

        # Handle clear - set flag and rerun so flag check above clears state
        if clear_submitted:
            st.session_state.clear_asset_filters_flag = True
            safe_rerun()

        # Active filter indicator pills
        active_filters = []
        if status_filter != "All":
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Status:</span> {status_filter}</span>')
        if brand_filter != "All":
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Brand:</span> {brand_filter}</span>')
        if type_filter != "All":
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Type:</span> {type_filter}</span>')
        if location_filter != "All":
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Location:</span> {location_filter}</span>')
        if search:
            active_filters.append(f'<span class="filter-pill"><span class="filter-pill-label">Search:</span> {search}</span>')

        if active_filters:
            pills_html = ''.join(active_filters)
            st.markdown(f"""
            <div class="filter-pills-container">
                <span class="filter-pills-title">Active filters:</span>
                {pills_html}
            </div>
            """, unsafe_allow_html=True)

        # Apply filters
        filtered_df = assets_df.copy()

        if status_filter != "All" and "Current Status" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Current Status"] == status_filter]

        if brand_filter != "All" and "Brand" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Brand"] == brand_filter]

        if type_filter != "All" and "Asset Type" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Asset Type"] == type_filter]

        if location_filter != "All" and "Current Location" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Current Location"] == location_filter]

        # Apply SLA filter if set from dashboard click
        if sla_filter_value and "Current Status" in filtered_df.columns:
            # SLA only applies to certain statuses
            sla_statuses = ["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR", "IN_OFFICE_TESTING"]
            filtered_df = filtered_df[filtered_df["Current Status"].isin(sla_statuses)]

            if "Days in Status" in filtered_df.columns:
                def get_sla_level(row):
                    status = row.get("Current Status", "")
                    days = row.get("Days in Status", 0)
                    if pd.isna(days):
                        days = 0
                    days = int(days)

                    # Get SLA thresholds for this status
                    if status in SLA_CONFIG:
                        warning_threshold = SLA_CONFIG[status].get("warning", 999)
                        critical_threshold = SLA_CONFIG[status].get("critical", 999)

                        if days >= critical_threshold:
                            return "critical"
                        elif days >= warning_threshold:
                            return "warning"
                        else:
                            return "ok"
                    return "ok"

                # Add SLA level column and filter
                filtered_df = filtered_df.copy()
                filtered_df["_sla_level"] = filtered_df.apply(get_sla_level, axis=1)
                filtered_df = filtered_df[filtered_df["_sla_level"] == sla_filter_value]
                filtered_df = filtered_df.drop(columns=["_sla_level"])

        # Apply billing paused filter if set from dashboard click
        if billing_paused_filter and "Current Status" in filtered_df.columns:
            paused_statuses = ["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR"]
            filtered_df = filtered_df[filtered_df["Current Status"].isin(paused_statuses)]

        # Apply client location filter if set from Billing page navigation
        if client_location_filter and "Current Location" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Current Location"] == client_location_filter]

        # Enhanced search - searches multiple columns
        if search:
            search_mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
            if "Serial Number" in filtered_df.columns:
                search_mask |= filtered_df["Serial Number"].str.contains(search, case=False, na=False)
            if "Brand" in filtered_df.columns:
                search_mask |= filtered_df["Brand"].str.contains(search, case=False, na=False)
            if "Model" in filtered_df.columns:
                search_mask |= filtered_df["Model"].str.contains(search, case=False, na=False)
            filtered_df = filtered_df[search_mask]

        # Results count bar with export button
        results_col1, results_col2 = st.columns([3, 1])
        with results_col1:
            is_filtered = len(filtered_df) != len(assets_df)
            count_style = "font-size: 18px; color: #f97316; font-weight: 700;" if is_filtered else "font-size: 16px; color: #3b82f6; font-weight: 700;"
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; padding: 12px 0;">
                <span style="font-size: 14px; color: #374151; font-weight: 500;">Showing</span>
                <span style="{count_style}">{len(filtered_df)}</span>
                <span style="font-size: 14px; color: #6b7280;">of {len(assets_df)} assets</span>
                <span style="margin-left: 12px; display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="font-size: 11px; color: #4CAF50; font-weight: 600; padding: 2px 8px; background: #4CAF5020; border-radius: 4px;">In Stock</span>
                    <span style="font-size: 11px; color: #FF6B35; font-weight: 600; padding: 2px 8px; background: #FF6B3520; border-radius: 4px;">With Client</span>
                    <span style="font-size: 11px; color: #2196F3; font-weight: 600; padding: 2px 8px; background: #2196F320; border-radius: 4px;">Returned</span>
                    <span style="font-size: 11px; color: #9C27B0; font-weight: 600; padding: 2px 8px; background: #9C27B020; border-radius: 4px;">Testing</span>
                    <span style="font-size: 11px; color: #FF9800; font-weight: 600; padding: 2px 8px; background: #FF980020; border-radius: 4px;">Repair</span>
                </span>
            </div>
            """, unsafe_allow_html=True)
        with results_col2:
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Export CSV",
                data=csv,
                file_name=f"assets_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        # ========== BULK OPERATIONS SECTION ==========
        # Initialize session state for bulk selection
        if 'bulk_selected_assets' not in st.session_state:
            st.session_state.bulk_selected_assets = []

        # Display columns for table (prioritized order - most important first)
        display_cols = ["Serial Number", "Brand", "Model", "Current Status", "Current Location",
                       "Asset Type", "RAM (GB)", "Storage (GB)", "Office License Key", "Reuse Count"]
        available_cols = [c for c in display_cols if c in filtered_df.columns]

        if available_cols and len(filtered_df) > 0:
            # Create asset options for multiselect
            asset_options = []
            asset_map = {}  # Map display label to asset data
            for _, row in filtered_df.iterrows():
                serial = row.get('Serial Number', '')
                asset_type = row.get('Asset Type', '')
                brand = row.get('Brand', '')
                status = row.get('Current Status', '')
                asset_id = row.get('_id', '')
                label = f"{serial} | {asset_type} | {brand} | {status}"
                asset_options.append(label)
                asset_map[label] = {'_id': asset_id, 'serial': serial, 'status': status, 'row': row}

            # Bulk selection multiselect
            st.markdown("""
            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                Bulk Operations
            </div>
            """, unsafe_allow_html=True)

            # Check if we need to clear the selection (flag set by callback/previous action)
            if st.session_state.get('clear_bulk_selection_flag', False):
                st.session_state.bulk_asset_select = []
                st.session_state.clear_bulk_selection_flag = False

            selected_assets = st.multiselect(
                "Select Assets for Bulk Action",
                options=asset_options,
                default=[],
                key="bulk_asset_select",
                help="Select multiple assets to perform bulk actions"
            )

            # Show bulk operations panel if assets selected
            if selected_assets:
                selected_count = len(selected_assets)

                st.markdown(f"""
                <div style="background: #eff6ff; border: 1px solid #3b82f6; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                    <strong style="color: #1e40af;">📦 {selected_count} asset(s) selected</strong>
                </div>
                """, unsafe_allow_html=True)

                # Action selection
                bulk_col1, bulk_col2 = st.columns(2)

                with bulk_col1:
                    bulk_action = st.selectbox(
                        "Bulk Action",
                        ["Select Action...", "Change Status", "Assign to Client"],
                        key="bulk_action_select"
                    )

                # Action-specific options
                if bulk_action == "Change Status":
                    with bulk_col2:
                        new_status = st.selectbox("New Status", ASSET_STATUSES, key="bulk_new_status")

                    # Show current statuses of selected assets
                    current_statuses = set()
                    for label in selected_assets:
                        current_statuses.add(asset_map[label]['status'])
                    st.caption(f"Current statuses: {', '.join(current_statuses)}")

                    if st.button(f"🔄 Change Status for {selected_count} Assets", type="primary", use_container_width=True):
                        with st.spinner(f"Updating {selected_count} assets..."):
                            success_count = 0
                            fail_count = 0
                            errors = []

                            for label in selected_assets:
                                asset_data = asset_map[label]
                                asset_id = asset_data['_id']
                                serial = asset_data['serial']

                                try:
                                    success, error_msg = update_asset_status(asset_id, new_status)
                                    if success:
                                        success_count += 1
                                    else:
                                        fail_count += 1
                                        errors.append(f"{serial}: {error_msg}")
                                except Exception as e:
                                    fail_count += 1
                                    errors.append(f"{serial}: {str(e)}")

                            # Log bulk action
                            log_activity_event(
                                action_type="BULK_STATUS_CHANGE",
                                category="bulk_operation",
                                user_role=st.session_state.user_role,
                                description=f"Bulk status change to {new_status} for {success_count} assets",
                                success=success_count > 0,
                                metadata={"total": selected_count, "success": success_count, "failed": fail_count}
                            )

                            if success_count > 0:
                                st.success(f"✅ Successfully updated {success_count} assets to {new_status}")
                            if fail_count > 0:
                                st.warning(f"⚠️ {fail_count} assets failed to update")
                                with st.expander("View errors"):
                                    for err in errors[:10]:
                                        st.write(f"• {err}")

                            # Clear selection and refresh (use flag to avoid widget state error)
                            st.session_state.clear_bulk_selection_flag = True
                            safe_rerun()

                elif bulk_action == "Assign to Client":
                    # Get client list
                    if not clients_df.empty and "Client Name" in clients_df.columns:
                        client_list = sorted(clients_df["Client Name"].dropna().unique().tolist())
                    else:
                        client_list = []

                    with bulk_col2:
                        if client_list:
                            selected_client = st.selectbox("Select Client", client_list, key="bulk_client_select")
                        else:
                            st.warning("No clients available")
                            selected_client = None

                    # Check if selected assets are assignable (IN_STOCK_WORKING)
                    assignable_count = 0
                    non_assignable = []
                    for label in selected_assets:
                        if asset_map[label]['status'] == "IN_STOCK_WORKING":
                            assignable_count += 1
                        else:
                            non_assignable.append(asset_map[label]['serial'])

                    if non_assignable:
                        st.warning(f"⚠️ {len(non_assignable)} asset(s) not in IN_STOCK_WORKING status will be skipped")

                    if selected_client and assignable_count > 0:
                        # Optional shipment details
                        ship_col1, ship_col2 = st.columns(2)
                        with ship_col1:
                            shipment_date = st.date_input("Shipment Date", value=date.today(), key="bulk_ship_date")
                        with ship_col2:
                            tracking_number = st.text_input("Tracking Number (optional)", key="bulk_tracking")

                        if st.button(f"📦 Assign {assignable_count} Assets to {selected_client}", type="primary", use_container_width=True):
                            with st.spinner(f"Assigning {assignable_count} assets..."):
                                success_count = 0
                                fail_count = 0
                                errors = []

                                for label in selected_assets:
                                    asset_data = asset_map[label]
                                    if asset_data['status'] != "IN_STOCK_WORKING":
                                        continue

                                    asset_id = asset_data['_id']
                                    serial = asset_data['serial']

                                    try:
                                        # Update status to WITH_CLIENT
                                        success, error_msg = update_asset_status(asset_id, "WITH_CLIENT", selected_client)
                                        if success:
                                            # Create assignment record
                                            assignment_data = {
                                                "Serial Number": serial,
                                                "Client Name": selected_client,
                                                "Assignment Name": f"{serial} → {selected_client}",
                                                "Assignment Type": "Rental",
                                                "Shipment Date": shipment_date.isoformat() if shipment_date else None,
                                                "Tracking Number": tracking_number if tracking_number else None,
                                                "Status": "Active"
                                            }
                                            create_assignment_record(assignment_data, user_role=st.session_state.user_role)
                                            success_count += 1
                                        else:
                                            fail_count += 1
                                            errors.append(f"{serial}: {error_msg}")
                                    except Exception as e:
                                        fail_count += 1
                                        errors.append(f"{serial}: {str(e)}")

                                # Log bulk action
                                log_activity_event(
                                    action_type="BULK_ASSIGNMENT",
                                    category="bulk_operation",
                                    user_role=st.session_state.user_role,
                                    client_name=selected_client,
                                    description=f"Bulk assignment of {success_count} assets to {selected_client}",
                                    success=success_count > 0,
                                    metadata={"total": assignable_count, "success": success_count, "failed": fail_count, "client": selected_client}
                                )

                                if success_count > 0:
                                    st.success(f"✅ Successfully assigned {success_count} assets to {selected_client}")
                                if fail_count > 0:
                                    st.warning(f"⚠️ {fail_count} assets failed to assign")
                                    with st.expander("View errors"):
                                        for err in errors[:10]:
                                            st.write(f"• {err}")

                                # Clear selection and refresh (use flag to avoid widget state error)
                                st.session_state.clear_bulk_selection_flag = True
                                safe_rerun()

                # Clear selection button - uses callback to avoid widget state modification error
                def clear_bulk_selection_callback():
                    st.session_state.clear_bulk_selection_flag = True

                st.button("🗑️ Clear Selection", key="clear_bulk_selection", on_click=clear_bulk_selection_callback)

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

            # Apply pagination to filtered data
            paginated_df = paginate_dataframe(filtered_df, "assets_table", show_controls=True)

            # Enhanced color coding for status with better visibility
            def highlight_status(row):
                status = row.get("Current Status", "")
                color = STATUS_COLORS.get(status, "#6b7280")
                # Stronger background for status column, subtle tint for entire row
                styles = []
                for col in row.index:
                    if col == "Current Status":
                        styles.append(f'background-color: {color}40; color: {color}; font-weight: 600;')
                    else:
                        styles.append(f'background-color: {color}10;')
                return styles

            styled_df = paginated_df[available_cols].style.apply(highlight_status, axis=1)
            st.dataframe(styled_df, hide_index=True)
            render_page_navigation("assets_table")

        # ========== ASSET QUICK ACTIONS PANEL ==========
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        with st.expander("⚡ Asset Quick Actions", expanded=False):
            if "Serial Number" in filtered_df.columns and len(filtered_df) > 0:
                qa_serial_options = filtered_df["Serial Number"].dropna().unique().tolist()
                if qa_serial_options:
                    selected_qa_serial = st.selectbox(
                        "Select an asset",
                        options=qa_serial_options,
                        key="qa_asset_serial"
                    )

                    if selected_qa_serial:
                        qa_asset_info = filtered_df[filtered_df["Serial Number"] == selected_qa_serial]
                        if not qa_asset_info.empty:
                            qa_row = qa_asset_info.iloc[0]
                            qa_status = qa_row.get('Current Status', 'N/A')
                            qa_status_color = STATUS_COLORS.get(qa_status, '#6b7280')

                            # Asset detail card
                            st.markdown(f"""
                            <div class="asset-detail-card">
                                <div class="asset-detail-header">
                                    <span class="asset-detail-serial">{selected_qa_serial}</span>
                                    <span class="asset-detail-status" style="background: {qa_status_color}20; color: {qa_status_color};">{qa_status}</span>
                                </div>
                                <div class="asset-detail-grid">
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Brand / Model</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Brand', 'N/A')} {qa_row.get('Model', '')}</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Asset Type</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Asset Type', 'N/A')}</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Location</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Current Location', 'N/A')}</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">RAM / Storage</div>
                                        <div class="asset-detail-item-value">{qa_row.get('RAM (GB)', 'N/A')} GB / {qa_row.get('Storage (GB)', 'N/A')} GB</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Reuse Count</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Reuse Count', 0)}</div>
                                    </div>
                                    <div class="asset-detail-item">
                                        <div class="asset-detail-item-label">Notes</div>
                                        <div class="asset-detail-item-value">{qa_row.get('Notes', '-') or '-'}</div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # Quick action buttons
                            qa_action_col1, qa_action_col2, qa_action_col3 = st.columns(3)

                            with qa_action_col1:
                                qa_new_status = st.selectbox(
                                    "Change Status To",
                                    options=[s for s in ASSET_STATUSES if s != qa_status],
                                    key="qa_new_status"
                                )

                            with qa_action_col2:
                                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("🔄 Update Status", key="qa_update_status", type="primary", use_container_width=True):
                                    asset_id = qa_row.get('_id', '')
                                    if asset_id:
                                        success, error_msg = update_asset_status(asset_id, qa_new_status)
                                        if success:
                                            log_activity_event(
                                                action_type="STATUS_CHANGE",
                                                category="asset",
                                                user_role=st.session_state.user_role,
                                                description=f"Changed {selected_qa_serial} from {qa_status} to {qa_new_status}",
                                                success=True,
                                                metadata={"serial": selected_qa_serial, "old_status": qa_status, "new_status": qa_new_status}
                                            )
                                            st.success(f"Updated {selected_qa_serial} to {qa_new_status}")
                                            safe_rerun()
                                        else:
                                            st.error(f"Failed: {error_msg}")

                            with qa_action_col3:
                                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                                if st.button("📋 View Full History", key="qa_view_history", use_container_width=True):
                                    st.session_state.asset_search_serial = selected_qa_serial
                                    safe_rerun()
            else:
                st.info("No assets available.")

        # ========== VIEW ASSET HISTORY - LINKED RECORDS NAVIGATION ==========
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        with st.expander("🔗 View Asset History (Assignments & Issues)", expanded=False):
            if "Serial Number" in filtered_df.columns and len(filtered_df) > 0:
                serial_options = filtered_df["Serial Number"].dropna().unique().tolist()
                if serial_options:
                    hist_col1, hist_col2 = st.columns([3, 1])
                    with hist_col1:
                        selected_history_serial = st.selectbox(
                            "Select Asset to View History",
                            options=serial_options,
                            key="asset_history_serial"
                        )

                    if selected_history_serial:
                        # Show asset details
                        asset_info = filtered_df[filtered_df["Serial Number"] == selected_history_serial]
                        if not asset_info.empty:
                            asset_row = asset_info.iloc[0]
                            st.markdown("---")
                            st.markdown("**📦 Asset Details:**")
                            d_col1, d_col2, d_col3, d_col4 = st.columns(4)
                            with d_col1:
                                st.markdown(f"**Serial:** {asset_row.get('Serial Number', 'N/A')}")
                            with d_col2:
                                st.markdown(f"**Type:** {asset_row.get('Asset Type', 'N/A')}")
                            with d_col3:
                                st.markdown(f"**Brand:** {asset_row.get('Brand', 'N/A')} {asset_row.get('Model', '')}")
                            with d_col4:
                                st.markdown(f"**Status:** {asset_row.get('Current Status', 'N/A')}")

                        # Show assignment history
                        st.markdown("---")
                        st.markdown("**📋 Assignment History:**")
                        if not assignments_df.empty and "Serial Number" in assignments_df.columns:
                            asset_assignments = assignments_df[assignments_df["Serial Number"] == selected_history_serial]
                            if not asset_assignments.empty:
                                assign_cols = ["Client Name", "Assignment Type", "Status", "Shipment Date"]
                                available_assign_cols = [c for c in assign_cols if c in asset_assignments.columns]
                                st.dataframe(asset_assignments[available_assign_cols], hide_index=True)

                                # Quick link to Assignments page
                                if st.button("📋 View in Assignments Page", key="link_to_assignments"):
                                    st.session_state.current_page = "Assignments"
                                    st.session_state.assign_search = selected_history_serial
                                    safe_rerun()
                            else:
                                st.info("No assignment records found for this asset.")
                        else:
                            st.info("No assignment data available.")

                        # Show issues history
                        st.markdown("---")
                        st.markdown("**⚠️ Issue History:**")
                        if not issues_df.empty:
                            # Try different column names for serial
                            serial_col = None
                            for col in ["Asset Serial", "Serial Number", "Asset_Serial"]:
                                if col in issues_df.columns:
                                    serial_col = col
                                    break

                            if serial_col:
                                asset_issues = issues_df[issues_df[serial_col] == selected_history_serial]
                                if not asset_issues.empty:
                                    issue_cols = ["Issue Title", "Issue Type", "Severity", "Status", "Reported Date"]
                                    available_issue_cols = [c for c in issue_cols if c in asset_issues.columns]
                                    st.dataframe(asset_issues[available_issue_cols], hide_index=True)

                                    # Quick link to Issues page
                                    if st.button("⚠️ View in Issues Page", key="link_to_issues"):
                                        st.session_state.current_page = "Issues & Repairs"
                                        safe_rerun()
                                else:
                                    st.success("✅ No issues reported for this asset.")
                            else:
                                st.info("Issues don't have linked asset serial numbers.")
                        else:
                            st.info("No issues data available.")
            else:
                st.info("No assets available to view history.")

# ============================================
# QUICK ACTIONS PAGE
# ============================================
elif page == "Quick Actions":
    # Route-level access control (defense in depth)
    if not check_page_access("Quick Actions", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "operations"])
        st.stop()

    st.markdown('<p class="main-header">Quick Actions</p>', unsafe_allow_html=True)

    # Initialize confirmation system
    init_action_confirmation()
    current_role = st.session_state.user_role

    if not api:
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
            available_assets = assets_df[assets_df["Current Status"] == "IN_STOCK_WORKING"] if "Current Status" in assets_df.columns else pd.DataFrame()

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
                        client_options = sorted(clients_df["Client Name"].dropna().unique().tolist()) if not clients_df.empty and "Client Name" in clients_df.columns else []
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
            with_client_assets = assets_df[assets_df["Current Status"] == "WITH_CLIENT"] if "Current Status" in assets_df.columns else pd.DataFrame()

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
            returned_assets = assets_df[assets_df["Current Status"].isin(["RETURNED_FROM_CLIENT", "IN_OFFICE_TESTING"])] if "Current Status" in assets_df.columns else pd.DataFrame()

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
            repair_assets = assets_df[assets_df["Current Status"] == "WITH_VENDOR_REPAIR"] if "Current Status" in assets_df.columns else pd.DataFrame()

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

# ============================================
# ADD ASSET PAGE
# ============================================
elif page == "Add Asset":
    # Route-level access control (defense in depth)
    if not check_page_access("Add Asset", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "operations"])
        st.stop()  # Prevent further page rendering

    st.markdown('<p class="main-header">Add New Asset</p>', unsafe_allow_html=True)

    if not api:
        st.warning("Please configure your Airtable API key in Settings first.")
    else:
        with st.form("add_asset_form"):
            # Section: Asset Information
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
                <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Asset Information</span>
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                serial_number = st.text_input("Serial Number *", placeholder="e.g., PF1XLNM6")
                asset_type = st.selectbox("Asset Type *", ASSET_TYPES)
                brand = st.selectbox("Brand *", BRANDS)
                model = st.text_input("Model", placeholder="e.g., T495, MacBook Air")
                specs = st.text_input("Specs", placeholder="e.g., 16GB, 256GB SSD, i5")

            with col2:
                touch_screen = st.checkbox("Touch Screen")
                processor = st.text_input("Processor", placeholder="e.g., AMD Ryzen 5 Pro")
                ram = st.number_input("RAM (GB)", min_value=0, max_value=128, value=16)
                storage_type = st.selectbox("Storage Type", STORAGE_TYPES)
                storage_gb = st.number_input("Storage (GB)", min_value=0, max_value=4096, value=256)

            # Section: Software & License
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Software & License</span>
            </div>
            """, unsafe_allow_html=True)
            col1, col2 = st.columns(2)

            with col1:
                os_installed = st.selectbox("OS Installed", [""] + OS_OPTIONS)
                office_key = st.text_input("Office License Key", placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")

            with col2:
                password = st.text_input("Device Password")
                current_status = st.selectbox("Current Status *", VALID_INITIAL_STATUSES, index=0,
                                              help="New assets can only be added as 'In Stock' or 'With Client'")

            # Section: Location & Purchase
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #f59e0b;">
                <div style="width: 4px; height: 20px; background: #f59e0b; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Location & Purchase</span>
            </div>
            """, unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)

            with col1:
                current_location = st.text_input("Current Location", value="Office")

            with col2:
                purchase_date = st.date_input("Purchase Date", value=None)

            with col3:
                purchase_price = st.number_input("Purchase Price (₹)", min_value=0, value=0)

            # Additional Notes
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            notes = st.text_area("Notes", placeholder="Any additional information...")

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Add Asset", type="primary")

            if submitted:
                # Server-side RBAC validation (defense in depth)
                validation_result = validate_action("create_asset", st.session_state.user_role)
                if not validation_result.success:
                    st.error(validation_result.message)
                    log_activity_event(
                        action_type="ACCESS_DENIED",
                        category="security",
                        user_role=st.session_state.user_role,
                        description="Unauthorized asset creation attempt",
                        success=False
                    )
                elif not serial_number:
                    st.error("Serial Number is required.")
                else:
                    record = {
                        "Serial Number": serial_number,
                        "Asset Type": asset_type,
                        "Brand": brand,
                        "Current Status": current_status
                    }

                    if model: record["Model"] = model
                    if specs: record["Specs"] = specs
                    if touch_screen: record["Touch Screen"] = touch_screen
                    if processor: record["Processor"] = processor
                    if ram: record["RAM (GB)"] = ram
                    if storage_type: record["Storage Type"] = storage_type
                    if storage_gb: record["Storage (GB)"] = storage_gb
                    if os_installed: record["OS Installed"] = os_installed
                    if office_key: record["Office License Key"] = office_key
                    if password: record["Password"] = password
                    if current_location: record["Current Location"] = current_location
                    if purchase_date: record["Purchase Date"] = purchase_date.isoformat()
                    if purchase_price: record["Purchase Price"] = purchase_price
                    if notes: record["Notes"] = notes

                    try:
                        table = get_table("assets")
                        table.create(record)
                        clear_cache(["assets"])  # Targeted invalidation
                        # Log successful creation
                        log_activity_event(
                            action_type="ASSET_CREATED",
                            category="asset",
                            user_role=st.session_state.user_role,
                            description=f"Asset created: {serial_number}",
                            serial_number=serial_number,
                            success=True
                        )
                        st.success(f"Asset {serial_number} added successfully.")
                        st.balloons()
                    except Exception as e:
                        error_id = log_error(e, "create_asset_airtable", st.session_state.get('user_role'))
                        st.error(f"Unable to add asset. Please try again. (Ref: {error_id})")

# ============================================
# ASSIGNMENTS PAGE
# ============================================
elif page == "Assignments":
    st.markdown('<p class="main-header">Assignments</p>', unsafe_allow_html=True)

    if not api:
        st.warning("Please configure your Airtable API key in Settings first.")
    else:
        tab1, tab2 = st.tabs(["View Assignments", "Client Summary"])

        with tab1:
            if not assignments_df.empty:
                # Search bar
                assign_search = st.text_input("🔍 Search (Serial Number, Client Name)", key="assign_search", placeholder="Type to search...")

                # Filters row
                acol1, acol2, acol3, acol4 = st.columns([1, 1, 1, 0.5])

                with acol1:
                    client_list = sorted(list(assignments_df["Client Name"].dropna().unique())) if "Client Name" in assignments_df.columns else []
                    assign_client_filter = st.selectbox("Client", ["All"] + client_list, key="assign_client_filter")

                with acol2:
                    status_list = sorted(list(assignments_df["Status"].dropna().unique())) if "Status" in assignments_df.columns else []
                    assign_status_filter = st.selectbox("Status", ["All"] + status_list, key="assign_status_filter")

                with acol3:
                    type_list = sorted(list(assignments_df["Assignment Type"].dropna().unique())) if "Assignment Type" in assignments_df.columns else []
                    assign_type_filter = st.selectbox("Type", ["All"] + type_list, key="assign_type_filter")

                with acol4:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Clear", key="clear_assign_filters", use_container_width=True):
                        for key in ["assign_search", "assign_client_filter", "assign_status_filter", "assign_type_filter"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        safe_rerun()

                # Apply filters
                filtered_assignments = assignments_df.copy()

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
                    <span style="font-size: 14px; color: #6b7280;">of {len(assignments_df)} assignments</span>
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
                            if selected_serial and not assets_df.empty:
                                asset_info = assets_df[assets_df["Serial Number"] == selected_serial]
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

            if not assets_df.empty and "Current Location" in assets_df.columns:
                # Count assets by location (client)
                client_assets = assets_df[assets_df["Current Status"] == "WITH_CLIENT"].groupby("Current Location").size().reset_index(name="Asset Count")

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

# ============================================
# ISSUES & REPAIRS PAGE
# ============================================
elif page == "Issues & Repairs":
    # Route-level access control (defense in depth)
    if not check_page_access("Issues & Repairs", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "operations"])
        st.stop()

    st.markdown('<p class="main-header">Issues & Repairs</p>', unsafe_allow_html=True)

    if not api:
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

            if not issues_df.empty:
                # Search bar
                issue_search = st.text_input("🔍 Search (Issue Title, Category)", key="issue_search", placeholder="Type to search...")

                # Filter options
                icol1, icol2, icol3, icol4 = st.columns([1, 1, 1, 0.5])
                with icol1:
                    issue_status_filter = st.selectbox("Status", ["All", "Open", "In Progress", "Resolved", "Closed"], key="issue_status_filter")
                with icol2:
                    issue_type_filter = st.selectbox("Type", ["All", "Software", "Hardware"], key="issue_type_filter")
                with icol3:
                    severity_list = sorted(list(issues_df["Severity"].dropna().unique())) if "Severity" in issues_df.columns else []
                    issue_severity_filter = st.selectbox("Severity", ["All"] + severity_list, key="issue_severity_filter")
                with icol4:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Clear", key="clear_issue_filters", use_container_width=True):
                        for key in ["issue_search", "issue_status_filter", "issue_type_filter", "issue_severity_filter"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        safe_rerun()

                filtered_issues = issues_df.copy()
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
                    <span style="font-size: 14px; color: #6b7280;">of {len(issues_df)} issues</span>
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
                            if selected_issue_serial and not assets_df.empty:
                                asset_info = assets_df[assets_df["Serial Number"] == selected_issue_serial]
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

            if not repairs_df.empty:
                display_cols = ["Repair Reference", "Sent Date", "Received Date", "Status", "Repair Description"]
                available_cols = [c for c in display_cols if c in repairs_df.columns]

                # Results count
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                    <span style="font-size: 14px; color: #374151; font-weight: 500;">Total</span>
                    <span style="font-size: 16px; color: #f59e0b; font-weight: 700;">{len(repairs_df)}</span>
                    <span style="font-size: 14px; color: #6b7280;">repair records</span>
                </div>
                """, unsafe_allow_html=True)
                # Apply pagination
                paginated_repairs = paginate_dataframe(repairs_df, "repairs_table", show_controls=True)
                st.dataframe(paginated_repairs[available_cols], hide_index=True)
                render_page_navigation("repairs_table")
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
                    asset_options = assets_df["Serial Number"].tolist() if not assets_df.empty and "Serial Number" in assets_df.columns else []
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

# ============================================
# CLIENTS PAGE
# ============================================
elif page == "Clients":
    st.markdown('<p class="main-header">Clients</p>', unsafe_allow_html=True)

    if not api:
        st.warning("Please configure your Airtable API key in Settings first.")
    elif st.session_state.get('data_load_error'):
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load clients data. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    else:
        tab1, tab2 = st.tabs(["View Clients", "Add Client"])

        with tab1:
            if not clients_df.empty:
                # Search and filter row
                ccol1, ccol2, ccol3 = st.columns([2, 1, 0.5])

                with ccol1:
                    client_search = st.text_input("🔍 Search Client Name", key="client_search", placeholder="Type to search...")

                with ccol2:
                    client_type_list = sorted(list(clients_df["Client Type"].dropna().unique())) if "Client Type" in clients_df.columns else []
                    client_type_filter = st.selectbox("Type", ["All"] + client_type_list, key="client_type_filter")

                with ccol3:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Clear", key="clear_client_filters", use_container_width=True):
                        for key in ["client_search", "client_type_filter"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        safe_rerun()

                # Apply filters
                filtered_clients = clients_df.copy()

                if client_type_filter != "All" and "Client Type" in filtered_clients.columns:
                    filtered_clients = filtered_clients[filtered_clients["Client Type"] == client_type_filter]

                if client_search and "Client Name" in filtered_clients.columns:
                    filtered_clients = filtered_clients[filtered_clients["Client Name"].str.contains(client_search, case=False, na=False)]

                # Results count
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                    <span style="font-size: 14px; color: #374151; font-weight: 500;">Showing</span>
                    <span style="font-size: 16px; color: #3b82f6; font-weight: 700;">{len(filtered_clients)}</span>
                    <span style="font-size: 14px; color: #6b7280;">of {len(clients_df)} clients</span>
                </div>
                """, unsafe_allow_html=True)
                # Apply pagination to client list
                paginated_clients = paginate_dataframe(filtered_clients, "clients_table", show_controls=True)
                # Show client cards
                for idx, client in paginated_clients.iterrows():
                    with st.expander(f"**{client.get('Client Name', 'Unknown')}** - {client.get('Client Type', 'N/A')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Contact:** {client.get('Contact Person', 'N/A')}")
                            st.write(f"**Email:** {client.get('Email', 'N/A')}")
                            st.write(f"**Phone:** {client.get('Phone', 'N/A')}")
                        with col2:
                            st.write(f"**Type:** {client.get('Client Type', 'N/A')}")
                            st.write(f"**Active:** {'Yes' if client.get('Is Active', False) else 'No'}")

                            # Count assets with this client
                            if not assets_df.empty and "Current Location" in assets_df.columns:
                                asset_count = len(assets_df[assets_df["Current Location"] == client.get("Client Name", "")])
                                st.write(f"**Assets:** {asset_count}")
                render_page_navigation("clients_table")
            else:
                render_empty_state("no_clients", show_action=False)
                # Add client button inline
                if st.button("Add Your First Client", key="add_first_client_inline"):
                    st.session_state.show_add_client = True
                    safe_rerun()

        with tab2:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Add New Client</span>
            </div>
            """, unsafe_allow_html=True)

            with st.form("add_client_form"):
                col1, col2 = st.columns(2)

                with col1:
                    client_name = st.text_input("Client Name *", placeholder="e.g., X3i Solution")
                    contact_person = st.text_input("Contact Person")
                    email = st.text_input("Email")
                    phone = st.text_input("Phone")

                with col2:
                    client_type = st.selectbox("Client Type *", ["Rental", "Sale", "Both"])
                    is_active = st.checkbox("Active", value=True)
                    address = st.text_area("Address")

                submitted = st.form_submit_button("Add Client", type="primary")

                if submitted:
                    if not client_name:
                        st.error("Client Name is required!")
                    else:
                        record = {
                            "Client Name": client_name,
                            "Client Type": client_type,
                            "Is Active": is_active
                        }

                        if contact_person: record["Contact Person"] = contact_person
                        if email: record["Email"] = email
                        if phone: record["Phone"] = phone
                        if address: record["Address"] = address

                        try:
                            table = get_table("clients")
                            table.create(record)
                            clear_cache(["clients"])  # Targeted invalidation
                            st.success(f"Client {client_name} added successfully!")
                        except Exception as e:
                            error_id = log_error(e, "create_client_airtable", st.session_state.get('user_role'))
                            st.error(f"Unable to add client. Please try again. (Ref: {error_id})")

# ============================================
# REPORTS PAGE
# ============================================
elif page == "Reports":
    st.markdown('<p class="main-header">Reports & Analytics</p>', unsafe_allow_html=True)

    if not api:
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

            if not assets_df.empty:
                col1, col2 = st.columns(2)

                with col1:
                    # By status
                    st.markdown("""
                    <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                        By Status
                    </div>
                    """, unsafe_allow_html=True)
                    if "Current Status" in assets_df.columns:
                        status_summary = assets_df["Current Status"].value_counts().reset_index()
                        status_summary.columns = ["Status", "Count"]
                        st.dataframe(status_summary, hide_index=True)

                with col2:
                    # By brand and type
                    st.markdown("""
                    <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                        By Brand
                    </div>
                    """, unsafe_allow_html=True)
                    if "Brand" in assets_df.columns:
                        brand_summary = assets_df["Brand"].value_counts().reset_index()
                        brand_summary.columns = ["Brand", "Count"]
                        st.dataframe(brand_summary, hide_index=True)

                # Model breakdown
                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                st.markdown("""
                <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                    By Model (Top 10)
                </div>
                """, unsafe_allow_html=True)
                if "Model" in assets_df.columns:
                    model_summary = assets_df["Model"].value_counts().reset_index()
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
                report_billing = calculate_billing_metrics(assets_df)

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

            if not repairs_df.empty:
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Total Repairs", len(repairs_df))

                    if "Status" in repairs_df.columns:
                        repair_status = repairs_df["Status"].value_counts()
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
                    if "Is Replaced" in repairs_df.columns:
                        replaced = repairs_df["Is Replaced"].sum()
                        st.metric("Replaced Units", int(replaced) if pd.notna(replaced) else 0)
            else:
                st.info("No repair data available")

# ============================================
# BILLING PAGE (Finance and Admin only)
# ============================================
elif page == "Billing":
    # Route-level access control (defense in depth)
    if not check_page_access("Billing", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "finance"])
        st.stop()

    st.markdown('<p class="main-header">Billing & Revenue</p>', unsafe_allow_html=True)

    current_role = st.session_state.user_role

    if not api:
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
        billing_metrics = calculate_billing_metrics(assets_df)

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
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
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
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
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
                            if st.button("🔍 View Client Assets", key="billing_view_client_btn", use_container_width=True):
                                st.session_state.current_page = "Assets"
                                st.session_state.asset_filter = "WITH_CLIENT"
                                st.session_state.client_location_filter = selected_billing_client
                                safe_rerun()

                        # Show client's assets
                        if selected_billing_client and not assets_df.empty:
                            client_assets_df = assets_df[
                                (assets_df["Current Status"] == "WITH_CLIENT") &
                                (assets_df["Current Location"] == selected_billing_client)
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

            if not assets_df.empty and "Current Status" in assets_df.columns:
                # Create billing status view
                billing_view = assets_df[["Serial Number", "Brand", "Model", "Current Status", "Current Location"]].copy()

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
                    if st.button("Clear", key="clear_billing_filters", use_container_width=True):
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
                                if st.button("🔍 View in Assets", key="billing_view_asset_btn", use_container_width=True):
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

            paused_assets = get_paused_billing_assets(assets_df)

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
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE and len(billing_tabs) > 3:
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
                            custom_metrics = calculate_billing_metrics(assets_df, monthly_rate=custom_rate)
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

# ============================================
# ACTIVITY LOG PAGE (Audit Trail)
# ============================================
elif page == "Activity Log":
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
    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
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
                        audit_metadata_html = f'''
<div style="background:#f8fafc;border-top:1px solid #e2e8f0;margin-top:10px;padding:10px;border-radius:0 0 4px 4px;">
    <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">
        <div style="font-size:0.75rem;color:#64748b;">
            <span style="font-weight:600;">Audit Ref:</span> {audit_ref}
        </div>
        <div style="font-size:0.75rem;color:#64748b;">
            <span style="font-weight:600;">Performed By:</span> {role}
        </div>
        <div style="font-size:0.75rem;color:#64748b;">
            <span style="font-weight:600;">Affected Asset:</span> {asset or "N/A"}
        </div>
    </div>
</div>'''

                    # Critical action highlight
                    card_border = severity_style["border"] if is_critical else status_color
                    card_bg = "#fffbeb" if is_critical and not success else "#ffffff"

                    card_html = f'''<div style="background:{card_bg};border:1px solid #e2e8f0;border-left:4px solid {card_border};border-radius:6px;padding:12px;margin-bottom:8px;">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
<span style="font-weight:600;color:#1e293b;">{action}</span>
<span style="background:{status_bg};color:{status_color};padding:2px 8px;border-radius:4px;font-size:0.7rem;font-weight:500;">{status_text}</span>
{badges_html}
</div>
<span style="font-size:0.75rem;color:#64748b;font-family:monospace;">{time_str}</span>
</div>
<div style="color:#475569;font-size:0.9rem;margin-top:8px;">{detail_str}</div>
<div style="color:#94a3b8;font-size:0.8rem;margin-top:6px;">Category: {category}</div>
{error_html}
{audit_metadata_html}
</div>'''

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

# ============================================
# USER MANAGEMENT PAGE
# ============================================
elif page == "User Management":
    # Route-level access control (defense in depth)
    if not check_page_access("User Management", st.session_state.user_role):
        render_access_denied(required_roles=["admin"])
        st.stop()

    st.markdown('<p class="main-header">User Management</p>', unsafe_allow_html=True)

    # User Management Tabs
    user_tabs = st.tabs(["All Users", "Create User"])

    # TAB 1: All Users
    with user_tabs[0]:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Registered Users</span>
        </div>
        """, unsafe_allow_html=True)

        if AUTH_AVAILABLE:
            users = get_all_users()

            if users:
                # User stats
                total_users = len(users)
                active_users = len([u for u in users if u.get('is_active', False)])
                admin_count = len([u for u in users if u.get('role') == 'admin'])

                stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
                with stat_col1:
                    st.metric("Total Users", total_users)
                with stat_col2:
                    st.metric("Active Users", active_users)
                with stat_col3:
                    st.metric("Inactive Users", total_users - active_users)
                with stat_col4:
                    st.metric("Admins", admin_count)

                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

                # Users table
                for user in users:
                    user_id = user['id']
                    username = user['username']
                    email = user.get('email', 'N/A')
                    full_name = user.get('full_name', 'N/A')
                    role = user.get('role', 'operations')
                    is_active = user.get('is_active', False)
                    last_login = user.get('last_login', None)

                    # User card
                    status_color = "#10b981" if is_active else "#ef4444"
                    status_text = "Active" if is_active else "Inactive"

                    with st.expander(f"**{full_name or username}** ({username}) - {role.title()}", expanded=False):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write(f"**Username:** {username}")
                            st.write(f"**Email:** {email}")
                            st.write(f"**Full Name:** {full_name or 'Not set'}")

                        with col2:
                            st.write(f"**Role:** {role.title()}")
                            st.markdown(f"**Status:** <span style='color: {status_color};'>{status_text}</span>", unsafe_allow_html=True)
                            if last_login:
                                st.write(f"**Last Login:** {last_login}")
                            else:
                                st.write("**Last Login:** Never")

                        st.markdown("---")

                        # Action buttons (don't allow editing own account to prevent lockout)
                        if username != st.session_state.username:
                            action_col1, action_col2, action_col3, action_col4 = st.columns(4)

                            with action_col1:
                                # Change Role
                                new_role = st.selectbox(
                                    "Change Role",
                                    options=["admin", "operations", "finance"],
                                    index=["admin", "operations", "finance"].index(role) if role in ["admin", "operations", "finance"] else 1,
                                    key=f"role_{user_id}"
                                )
                                if new_role != role:
                                    if st.button("Update Role", key=f"update_role_{user_id}"):
                                        success, msg = update_user(user_id, {'role': new_role})
                                        if success:
                                            st.success(f"Role updated to {new_role}")
                                            safe_rerun()
                                        else:
                                            st.error(msg)

                            with action_col2:
                                # Reset Password
                                st.write("**Reset Password**")
                                new_pass = st.text_input("New Password", type="password", key=f"pass_{user_id}")
                                if new_pass:
                                    if st.button("Reset", key=f"reset_pass_{user_id}"):
                                        success, msg = change_password(user_id, new_pass)
                                        if success:
                                            st.success("Password reset successfully")
                                        else:
                                            st.error(msg)

                            with action_col3:
                                # Activate/Deactivate
                                if is_active:
                                    if st.button("Deactivate User", key=f"deactivate_{user_id}"):
                                        success, msg = deactivate_user(user_id)
                                        if success:
                                            st.success("User deactivated")
                                            safe_rerun()
                                        else:
                                            st.error(msg)
                                else:
                                    if st.button("Activate User", key=f"activate_{user_id}"):
                                        success, msg = activate_user(user_id)
                                        if success:
                                            st.success("User activated")
                                            safe_rerun()
                                        else:
                                            st.error(msg)
                        else:
                            st.info("This is your account. Use Settings to change your own password.")
            else:
                st.info("No users found in the database.")
        else:
            st.warning("Authentication module not available.")

    # TAB 2: Create User
    with user_tabs[1]:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
            <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Create New User</span>
        </div>
        """, unsafe_allow_html=True)

        if AUTH_AVAILABLE:
            with st.form("create_user_form"):
                col1, col2 = st.columns(2)

                with col1:
                    new_username = st.text_input("Username *", placeholder="e.g., john.doe")
                    new_email = st.text_input("Email *", placeholder="e.g., john@example.com")
                    new_password = st.text_input("Password *", type="password", placeholder="Minimum 6 characters")

                with col2:
                    new_full_name = st.text_input("Full Name", placeholder="e.g., John Doe")
                    new_role = st.selectbox("Role *", options=["operations", "finance", "admin"], index=0)
                    confirm_password = st.text_input("Confirm Password *", type="password")

                submitted = st.form_submit_button("Create User", type="primary")

                if submitted:
                    # Validation
                    errors = []
                    if not new_username:
                        errors.append("Username is required")
                    elif len(new_username) < 3:
                        errors.append("Username must be at least 3 characters")

                    if not new_email:
                        errors.append("Email is required")
                    elif "@" not in new_email:
                        errors.append("Invalid email format")

                    if not new_password:
                        errors.append("Password is required")
                    elif len(new_password) < 6:
                        errors.append("Password must be at least 6 characters")

                    if new_password != confirm_password:
                        errors.append("Passwords do not match")

                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        success, user_id, msg = create_user(
                            username=new_username,
                            email=new_email,
                            password=new_password,
                            full_name=new_full_name,
                            role=new_role
                        )

                        if success:
                            st.success(f"User '{new_username}' created successfully!")
                            # Log activity
                            log_activity_event(
                                action_type="USER_CREATED",
                                category="authentication",
                                user_role=st.session_state.user_role,
                                description=f"New user created: {new_username} (role: {new_role})",
                                success=True
                            )
                            # Refresh page to show new user in list
                            safe_rerun()
                        else:
                            st.error(f"Failed to create user: {msg}")
        else:
            st.warning("Authentication module not available.")

# ============================================
# IMPORT/EXPORT PAGE
# ============================================
elif page == "Import/Export":
    # Route-level access control (defense in depth)
    if not check_page_access("Import/Export", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "operations"])
        st.stop()

    # Import excel utilities
    from database.excel_utils import (
        export_assets_to_excel,
        generate_import_template,
        validate_import_data,
        import_assets_from_dataframe,
        EXCEL_COLUMNS
    )

    # Import QR code utilities
    from database.qr_utils import (
        generate_asset_qr,
        generate_asset_label_image,
        generate_bulk_qr_pdf
    )

    st.markdown('<p class="main-header">Import / Export Assets</p>', unsafe_allow_html=True)

    # Create three main sections
    export_section, import_section, qr_section = st.tabs(["📤 Export Data", "📥 Import Data", "📱 QR Codes"])

    # ========== EXPORT SECTION ==========
    with export_section:
        # Section header (matching other pages)
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Export Assets to File</span>
        </div>
        """, unsafe_allow_html=True)

        st.info("Download all assets data as Excel (.xlsx) or CSV file for reporting, backup, or offline analysis.")

        # Fetch current assets data
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
            export_assets = mysql_get_assets()
        else:
            export_assets = []

        # Convert to DataFrame
        export_df = pd.DataFrame(export_assets) if export_assets is not None else pd.DataFrame()

        if len(export_df) > 0:
            # Show summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Assets", len(export_df))
            with col2:
                st.metric("Columns", len(export_df.columns))
            with col3:
                st.metric("File Formats", "2", help="Excel and CSV")

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

            # Download Format sub-header
            st.markdown("""
            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                Download Format
            </div>
            """, unsafe_allow_html=True)

            export_col1, export_col2, export_col3 = st.columns([1, 1, 2])

            with export_col1:
                # Excel Export
                try:
                    excel_buffer = export_assets_to_excel(export_df)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                    st.download_button(
                        label="📥 Download Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"assets_export_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Failed to generate Excel: {str(e)}")

            with export_col2:
                # CSV Export
                csv_data = export_df.to_csv(index=False).encode('utf-8')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=f"assets_export_{timestamp}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # Preview section
            st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
            with st.expander("👁 Preview Export Data", expanded=False):
                # Select columns to show
                display_cols = ['Serial Number', 'Asset Type', 'Brand', 'Model', 'Current Status', 'Current Location']
                available_cols = [c for c in display_cols if c in export_df.columns]
                export_preview_source = export_df[available_cols] if available_cols else export_df.iloc[:, :6]

                # Paginated preview with page navigation
                paginated_export = paginate_dataframe(export_preview_source, "export_preview_table", show_controls=True)
                st.dataframe(paginated_export, use_container_width=True, height=400)
                render_page_navigation("export_preview_table")
        else:
            st.warning("No assets found in the database to export.")

    # ========== IMPORT SECTION ==========
    with import_section:
        # Section header (matching other pages)
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Import Assets from Excel</span>
        </div>
        """, unsafe_allow_html=True)

        st.info("Upload an Excel file (.xlsx) to bulk import assets. Download the template first to ensure correct format.")

        # Step 1: Download Template
        st.markdown("""
        <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
            Step 1: Download Import Template
        </div>
        """, unsafe_allow_html=True)
        st.caption("The template includes column headers, data validation dropdowns, and a sample row.")

        template_col1, template_col2 = st.columns([1, 3])
        with template_col1:
            try:
                template_buffer = generate_import_template()
                st.download_button(
                    label="📋 Download Template",
                    data=template_buffer.getvalue(),
                    file_name="asset_import_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Failed to generate template: {str(e)}")

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        # Step 2: Upload File
        st.markdown("""
        <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
            Step 2: Upload Filled Template
        </div>
        """, unsafe_allow_html=True)
        st.caption("Fill in the template with your asset data and upload it here.")

        uploaded_file = st.file_uploader(
            "Choose Excel file",
            type=['xlsx'],
            help="Upload .xlsx file only. Maximum 10MB.",
            key="import_file_uploader"
        )

        # Initialize session state for import
        if 'import_validated' not in st.session_state:
            st.session_state.import_validated = False
        if 'import_df' not in st.session_state:
            st.session_state.import_df = None
        if 'import_errors' not in st.session_state:
            st.session_state.import_errors = []
        if 'import_warnings' not in st.session_state:
            st.session_state.import_warnings = []

        if uploaded_file is not None:
            # Check file size (10MB limit)
            if uploaded_file.size > 10 * 1024 * 1024:
                st.error("File too large. Maximum size is 10MB.")
            else:
                try:
                    # Read the uploaded file
                    import_df = pd.read_excel(uploaded_file, sheet_name=0)

                    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

                    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

                    # Step 3: Preview & Validate
                    st.markdown("""
                    <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                        Step 3: Preview & Validate
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption("Review your data and check for any validation errors.")

                    # Show preview
                    st.markdown("**Data Preview** (first 10 rows)")
                    preview_cols = ['Serial Number', 'Asset Type', 'Brand', 'Model', 'Current Status']
                    available_preview = [c for c in preview_cols if c in import_df.columns]
                    if available_preview:
                        st.dataframe(import_df[available_preview].head(10), use_container_width=True)
                    else:
                        st.dataframe(import_df.head(10), use_container_width=True)

                    st.caption(f"Total rows: {len(import_df)}")

                    # Validate button
                    if st.button("🔍 Validate Data", use_container_width=True, type="primary"):
                        with st.spinner("Validating data..."):
                            is_valid, errors, warnings, valid_df = validate_import_data(import_df)
                            st.session_state.import_errors = errors
                            st.session_state.import_warnings = warnings
                            st.session_state.import_df = valid_df
                            st.session_state.import_validated = True
                            st.rerun()

                    # Show validation results
                    if st.session_state.import_validated:
                        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

                        errors = st.session_state.import_errors
                        warnings = st.session_state.import_warnings
                        valid_df = st.session_state.import_df

                        # Validation summary
                        valid_count = len(valid_df) if valid_df is not None else 0
                        error_count = len(errors)
                        warning_count = len(warnings)

                        # Validation Summary using standard metrics
                        summary_col1, summary_col2, summary_col3 = st.columns(3)
                        with summary_col1:
                            st.metric("✅ Valid Records", valid_count)
                        with summary_col2:
                            st.metric("❌ Errors", error_count)
                        with summary_col3:
                            st.metric("⚠️ Warnings", warning_count)

                        # Show errors if any
                        if errors:
                            with st.expander("❌ Errors (must fix)", expanded=True):
                                for err in errors[:20]:  # Show first 20 errors
                                    row_info = f"Row {err['row']}" if err.get('row') else ""
                                    field_info = f"[{err['field']}]" if err.get('field') else ""
                                    st.markdown(f"• {row_info} {field_info}: {err.get('message', 'Unknown error')}")
                                if len(errors) > 20:
                                    st.caption(f"...and {len(errors) - 20} more errors")

                        # Show warnings if any
                        if warnings:
                            with st.expander("⚠️ Warnings", expanded=False):
                                for warn in warnings[:20]:
                                    row_info = f"Row {warn['row']}" if warn.get('row') else ""
                                    field_info = f"[{warn['field']}]" if warn.get('field') else ""
                                    st.markdown(f"• {row_info} {field_info}: {warn.get('message', 'Warning')}")
                                if len(warnings) > 20:
                                    st.caption(f"...and {len(warnings) - 20} more warnings")

                        # Step 4: Import
                        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                        st.markdown("""
                        <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                            Step 4: Import Assets
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption("Click the button below to import valid records into the database.")

                        if valid_count > 0:
                            if st.button(f"📥 Import {valid_count} Assets", use_container_width=True, type="primary"):
                                with st.spinner(f"Importing {valid_count} assets..."):
                                    result = import_assets_from_dataframe(valid_df)

                                    if result['success'] > 0:
                                        st.success(f"✅ Successfully imported {result['success']} assets!")

                                        # Log activity
                                        log_activity_event(
                                            action_type="BULK_IMPORT",
                                            category="data_management",
                                            user_role=st.session_state.user_role,
                                            description=f"Imported {result['success']} assets from Excel",
                                            success=True
                                        )

                                        # CRITICAL: Mark data as stale to refresh dashboard
                                        st.session_state.data_stale = True

                                    if result['failed'] > 0:
                                        st.warning(f"⚠️ {result['failed']} assets failed to import.")
                                        if result.get('errors'):
                                            with st.expander("View import errors"):
                                                for err in result['errors'][:10]:
                                                    serial = err.get('serial', 'Unknown')
                                                    error_msg = err.get('error', 'Unknown error')
                                                    st.write(f"• {serial}: {error_msg}")

                                    # Reset import state
                                    st.session_state.import_validated = False
                                    st.session_state.import_df = None
                                    st.session_state.import_errors = []
                                    st.session_state.import_warnings = []
                        else:
                            st.warning("No valid records to import. Please fix the errors above and re-validate.")

                        # Reset validation button
                        if st.button("🔄 Reset & Upload New File"):
                            st.session_state.import_validated = False
                            st.session_state.import_df = None
                            st.session_state.import_errors = []
                            st.session_state.import_warnings = []
                            st.rerun()

                except Exception as e:
                    st.error(f"Failed to read file: {str(e)}")
                    st.info("Please make sure you're uploading a valid Excel (.xlsx) file.")

    # ========== QR CODES SECTION ==========
    with qr_section:
        # Section header (matching other pages)
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Generate QR Codes</span>
        </div>
        """, unsafe_allow_html=True)

        st.info("Generate QR codes for assets. QR codes contain the serial number for easy scanning and identification.")

        # Fetch assets for QR generation
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
            qr_assets = mysql_get_assets()
        else:
            qr_assets = []

        qr_df = pd.DataFrame(qr_assets) if qr_assets is not None else pd.DataFrame()

        if len(qr_df) > 0:
            # ===== SINGLE ASSET QR =====
            st.markdown("""
            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                Single Asset QR Code
            </div>
            """, unsafe_allow_html=True)

            # Create asset options for dropdown
            asset_options = []
            for _, row in qr_df.iterrows():
                serial = row.get('Serial Number', '')
                asset_type = row.get('Asset Type', '')
                brand = row.get('Brand', '')
                model = row.get('Model', '')
                label = f"{serial} - {asset_type} - {brand} {model}"
                asset_options.append(label)

            selected_asset_label = st.selectbox(
                "Select Asset",
                options=asset_options,
                key="qr_asset_select"
            )

            if selected_asset_label:
                # Get the selected asset data
                selected_idx = asset_options.index(selected_asset_label)
                selected_asset = qr_df.iloc[selected_idx].to_dict()

                serial = selected_asset.get('Serial Number', '')
                asset_type = selected_asset.get('Asset Type', '')
                brand = selected_asset.get('Brand', '')
                model = selected_asset.get('Model', '')
                status = selected_asset.get('Current Status', '')

                # Display QR code and info side by side
                qr_col1, qr_col2 = st.columns([1, 2])

                with qr_col1:
                    # Generate and display QR code
                    qr_buffer = generate_asset_qr(serial, size=200)
                    st.image(qr_buffer, caption="Scan to get Serial Number", width=200)

                with qr_col2:
                    st.markdown(f"""
                    <div style="padding: 16px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb;">
                        <div style="margin-bottom: 12px;">
                            <span style="color: #6b7280; font-size: 12px;">SERIAL NUMBER</span><br>
                            <span style="font-size: 18px; font-weight: 700; color: #111827;">{serial}</span>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <span style="color: #6b7280; font-size: 12px;">TYPE</span><br>
                            <span style="font-size: 14px; color: #374151;">{asset_type}</span>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <span style="color: #6b7280; font-size: 12px;">BRAND / MODEL</span><br>
                            <span style="font-size: 14px; color: #374151;">{brand} {model}</span>
                        </div>
                        <div>
                            <span style="color: #6b7280; font-size: 12px;">STATUS</span><br>
                            <span style="font-size: 14px; color: #374151;">{status}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # Download buttons
                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                dl_col1, dl_col2, dl_col3 = st.columns([1, 1, 2])

                with dl_col1:
                    qr_png = generate_asset_qr(serial, size=300)
                    st.download_button(
                        label="📥 Download QR (PNG)",
                        data=qr_png.getvalue(),
                        file_name=f"qr_{serial}.png",
                        mime="image/png",
                        use_container_width=True
                    )

                with dl_col2:
                    qr_label = generate_asset_label_image(selected_asset)
                    st.download_button(
                        label="📥 Download with Label",
                        data=qr_label.getvalue(),
                        file_name=f"qr_label_{serial}.png",
                        mime="image/png",
                        use_container_width=True
                    )

            # ===== BULK QR GENERATION =====
            st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                Bulk QR Labels (PDF)
            </div>
            """, unsafe_allow_html=True)
            st.caption("Generate a printable PDF with QR code labels for multiple assets.")

            # Filters
            filter_col1, filter_col2 = st.columns(2)

            with filter_col1:
                status_options = ["All"] + sorted(qr_df['Current Status'].dropna().unique().tolist())
                selected_status = st.selectbox("Filter by Status", options=status_options, key="qr_status_filter")

            with filter_col2:
                brand_options = ["All"] + sorted(qr_df['Brand'].dropna().unique().tolist())
                selected_brand = st.selectbox("Filter by Brand", options=brand_options, key="qr_brand_filter")

            # Apply filters
            filtered_qr_df = qr_df.copy()
            if selected_status != "All":
                filtered_qr_df = filtered_qr_df[filtered_qr_df['Current Status'] == selected_status]
            if selected_brand != "All":
                filtered_qr_df = filtered_qr_df[filtered_qr_df['Brand'] == selected_brand]

            # Show count
            st.markdown(f"**{len(filtered_qr_df)}** assets match the filters")

            # Select all checkbox
            select_all = st.checkbox(f"Select All ({len(filtered_qr_df)} assets)", key="qr_select_all")

            # Multi-select for assets
            if select_all:
                default_selection = filtered_qr_df['Serial Number'].tolist()
            else:
                default_selection = []

            # Create options with more info
            bulk_options = []
            for _, row in filtered_qr_df.iterrows():
                serial = row.get('Serial Number', '')
                asset_type = row.get('Asset Type', '')
                brand = row.get('Brand', '')
                bulk_options.append(f"{serial} - {asset_type} - {brand}")

            selected_bulk = st.multiselect(
                "Select Assets for PDF",
                options=bulk_options,
                default=[f"{s} - {filtered_qr_df[filtered_qr_df['Serial Number']==s].iloc[0]['Asset Type']} - {filtered_qr_df[filtered_qr_df['Serial Number']==s].iloc[0]['Brand']}" for s in default_selection] if select_all else [],
                key="qr_bulk_select"
            )

            # Labels per row option
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            labels_per_row = st.selectbox("Labels per Row", options=[2, 3, 4], index=1, key="qr_labels_per_row")

            # Generate PDF button
            if selected_bulk:
                # Get selected asset data
                selected_serials = [opt.split(" - ")[0] for opt in selected_bulk]
                selected_assets_data = filtered_qr_df[filtered_qr_df['Serial Number'].isin(selected_serials)].to_dict('records')

                if st.button(f"📄 Generate PDF ({len(selected_bulk)} labels)", type="primary", use_container_width=True):
                    with st.spinner("Generating PDF..."):
                        pdf_buffer = generate_bulk_qr_pdf(selected_assets_data, labels_per_row=labels_per_row)
                        st.session_state.qr_pdf_buffer = pdf_buffer
                        st.session_state.qr_pdf_count = len(selected_bulk)
                        st.success(f"PDF generated with {len(selected_bulk)} QR labels!")

                # Show download button if PDF was generated
                if 'qr_pdf_buffer' in st.session_state and st.session_state.qr_pdf_buffer:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                    st.download_button(
                        label=f"📥 Download PDF ({st.session_state.qr_pdf_count} labels)",
                        data=st.session_state.qr_pdf_buffer.getvalue(),
                        file_name=f"qr_labels_{timestamp}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            else:
                st.info("Select assets above to generate PDF labels.")

        else:
            st.warning("No assets found in the database.")

# ============================================
# SETTINGS PAGE
# ============================================
elif page == "Settings":
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
        current_source = "MySQL" if DATA_SOURCE == "mysql" else "Airtable"
        source_badge_color = "#10b981" if DATA_SOURCE == "mysql" else "#f59e0b"
        st.markdown(f"""
        <div style="background: {source_badge_color}; color: white; padding: 10px 20px;
                    border-radius: 8px; text-align: center; font-weight: bold;">
            Active Data Source: {current_source}
        </div>
        """, unsafe_allow_html=True)

    with source_col2:
        mysql_status = "Available" if MYSQL_AVAILABLE else "Not configured"
        mysql_status_color = "#10b981" if MYSQL_AVAILABLE else "#ef4444"
        st.markdown(f"""
        <div style="background: #1e293b; color: white; padding: 10px 20px;
                    border-radius: 8px; text-align: center;">
            MySQL Module: <span style="color: {mysql_status_color}; font-weight: 600;">{mysql_status}</span>
        </div>
        """, unsafe_allow_html=True)

    st.caption("To switch data source, set the `DATA_SOURCE` environment variable to 'mysql' or 'airtable'")

    st.markdown("---")

    # MySQL Connection (if available)
    if MYSQL_AVAILABLE:
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
                            base = airtable_api.base(AIRTABLE_BASE_ID)

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
        st.text_input("Base ID", value=AIRTABLE_BASE_ID, disabled=True)

    with col2:
        api_status = "Connected" if api else "Not configured"
        st.text_input("API Status", value=api_status, disabled=True)

    if st.button("Test Airtable Connection", key="test_airtable"):
        if api:
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

    if api:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Assets", len(assets_df))
        col2.metric("Clients", len(clients_df))
        col3.metric("Issues", len(issues_df))
        col4.metric("Repairs", len(repairs_df))

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #6b7280;">
        <div style="width: 4px; height: 20px; background: #6b7280; border-radius: 2px;"></div>
        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Quick Links</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    - [Open Airtable Base](https://airtable.com/{AIRTABLE_BASE_ID})
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

# Footer
st.sidebar.markdown("""
<div class="sidebar-footer">
    <div class="version">Asset Management v2.4</div>
    <div class="tech">Streamlit + MySQL</div>
</div>
""", unsafe_allow_html=True)
