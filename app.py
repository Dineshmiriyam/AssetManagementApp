"""
Asset Lifecycle Management System v2.4
A Streamlit web application with Airtable/MySQL support
Enhanced with role-based analytics, SLA indicators, and RBAC
Production-hardened with centralized error handling
"""

import streamlit as st
import pandas as pd
from pyairtable import Api
from datetime import datetime, timedelta
import os
import logging
from dotenv import load_dotenv
from config.constants import (
    SESSION_TIMEOUT_HOURS, INACTIVITY_TIMEOUT_MINUTES,
    USER_ROLES, ROLE_PRIMARY_ACTION,
)
from config.styles import get_anti_flicker_css, get_login_css, get_dashboard_css
from core.errors import log_error, get_error_id
from core.data import (
    safe_rerun, get_airtable_api, _get_empty_data_structure,
    fetch_all_data, clear_cache,
)
from config.permissions import check_page_access, render_access_denied
from services.audit_service import log_activity_event
from views import PAGE_REGISTRY
from views.context import AppContext

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
# PAGE DISPATCH
# ============================================
ctx = AppContext(
    api=api,
    data_source=DATA_SOURCE,
    mysql_available=MYSQL_AVAILABLE,
    auth_available=AUTH_AVAILABLE,
    assets_df=assets_df,
    clients_df=clients_df,
    issues_df=issues_df,
    repairs_df=repairs_df,
    assignments_df=assignments_df,
    airtable_base_id=AIRTABLE_BASE_ID,
    airtable_api_key=AIRTABLE_API_KEY,
)

page_renderer = PAGE_REGISTRY.get(page)
if page_renderer:
    page_renderer(ctx)
else:
    st.error(f"Unknown page: {page}")

# Footer
st.sidebar.markdown("""
<div class="sidebar-footer">
    <div class="version">Asset Management v2.4</div>
    <div class="tech">Streamlit + MySQL</div>
</div>
""", unsafe_allow_html=True)
