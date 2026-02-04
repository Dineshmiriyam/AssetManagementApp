"""
Asset Lifecycle Management System v2.4
A Streamlit web application with Airtable/MySQL support
Enhanced with role-based analytics, SLA indicators, and RBAC
Production-hardened with centralized error handling
"""

import streamlit as st
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
import streamlit.components.v1 as components

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

# User-safe error messages (hide technical details)
USER_SAFE_MESSAGES = {
    "database": "Unable to connect to the database. Please try again later or contact support.",
    "network": "Network connection issue. Please check your connection and try again.",
    "permission": "You don't have permission to perform this action.",
    "validation": "The data provided is invalid. Please check your input.",
    "timeout": "The operation took too long. Please try again.",
    "not_found": "The requested resource was not found.",
    "conflict": "This operation conflicts with existing data.",
    "default": "An unexpected error occurred. Please try again or contact support."
}

def get_error_id() -> str:
    """Generate unique error ID for support reference."""
    import hashlib
    timestamp = datetime.now().isoformat()
    return hashlib.md5(timestamp.encode()).hexdigest()[:8].upper()

def log_error(error: Exception, context: str = "", user_role: str = None) -> str:
    """
    Log technical error details to file and return error ID for user reference.

    Args:
        error: The exception that occurred
        context: Additional context about what was being attempted
        user_role: Current user's role for audit purposes

    Returns:
        Error ID for user reference
    """
    error_id = get_error_id()
    st.session_state.error_count += 1

    logger.error(
        f"ERROR_ID={error_id} | "
        f"CONTEXT={context} | "
        f"ROLE={user_role or 'unknown'} | "
        f"TYPE={type(error).__name__} | "
        f"MESSAGE={str(error)} | "
        f"TRACE={traceback.format_exc()}"
    )

    return error_id

def classify_error(error: Exception) -> str:
    """Classify error type to determine user-safe message."""
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    # Database errors
    if any(x in error_str for x in ['mysql', 'database', 'connection', 'pool', 'cursor', 'query']):
        return "database"
    if any(x in error_type for x in ['operational', 'interface', 'programming', 'integrity']):
        return "database"

    # Network errors
    if any(x in error_str for x in ['timeout', 'timed out', 'connection refused', 'network']):
        return "network"
    if any(x in error_type for x in ['timeout', 'connection']):
        return "timeout" if 'timeout' in error_type else "network"

    # Permission errors
    if any(x in error_str for x in ['permission', 'denied', 'unauthorized', 'forbidden', 'access']):
        return "permission"

    # Validation errors
    if any(x in error_str for x in ['invalid', 'validation', 'required', 'missing']):
        return "validation"

    # Not found errors
    if any(x in error_str for x in ['not found', '404', 'does not exist']):
        return "not_found"

    return "default"

def safe_execute(func=None, context: str = "", fallback=None, show_error: bool = True):
    """
    Decorator/function for safe execution with error handling.

    Can be used as decorator:
        @safe_execute(context="Loading assets")
        def load_assets(): ...

    Or as wrapper:
        result = safe_execute(lambda: risky_operation(), context="Risky op", fallback={})
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                user_role = st.session_state.get('user_role', 'unknown')
                error_id = log_error(e, context or f.__name__, user_role)
                error_type = classify_error(e)

                if show_error:
                    user_message = USER_SAFE_MESSAGES.get(error_type, USER_SAFE_MESSAGES["default"])
                    st.error(f"{user_message} (Ref: {error_id})")

                return fallback() if callable(fallback) else fallback
        return wrapper

    # Allow use as @safe_execute or @safe_execute(context="...")
    if func is not None:
        return decorator(func)
    return decorator

def handle_db_error(error: Exception, operation: str) -> tuple:
    """
    Handle database errors consistently.
    Returns (success: bool, user_message: str, error_id: str)
    """
    user_role = st.session_state.get('user_role', 'unknown')
    error_id = log_error(error, f"DB:{operation}", user_role)
    error_type = classify_error(error)
    user_message = USER_SAFE_MESSAGES.get(error_type, USER_SAFE_MESSAGES["default"])

    return False, f"{user_message} (Ref: {error_id})", error_id

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

# Compatibility helper for st.rerun (works with older and newer Streamlit versions)
def safe_rerun():
    """Rerun the app - compatible with all Streamlit versions"""
    if hasattr(st, 'rerun'):
        st.rerun()
    elif hasattr(st, 'experimental_rerun'):
        st.experimental_rerun()
    else:
        # Fallback: use newer Streamlit internal API
        from streamlit import runtime
        runtime.get_instance().request_rerun()

# ============================================
# AUTHENTICATION & SESSION MANAGEMENT
# ============================================
SESSION_TIMEOUT_HOURS = 8  # Auto-logout after 8 hours
INACTIVITY_TIMEOUT_MINUTES = 30  # Auto-logout after 30 minutes of inactivity

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

    # Validate session token against server
    try:
        is_valid, user_data = validate_session(user_id, session_token)
        if not is_valid:
            logout_user(reason="session_invalidated")
            return False

        # Update role in case it was changed by admin
        if user_data:
            st.session_state.user_role = user_data.get('role', st.session_state.user_role)

        return True
    except Exception:
        # Don't crash on validation errors, just continue
        return True


def login_user(user_data: dict):
    """
    Set session state after successful login.
    Stores session token for server-side validation.
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
    st.session_state.login_error = None
    st.session_state.login_processing = False


def logout_user(reason: str = None):
    """
    Clear session state on logout and invalidate server-side session.
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
    st.markdown("""
    <style>
    /* Hide Streamlit defaults */
    #MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] {
        display: none !important;
    }

    /* Page background - clean light gray */
    .stApp {
        background: #f5f5f5 !important;
        min-height: 100vh;
    }

    /* ============ BRAND SECTION (Above Card) ============ */
    .login-brand {
        text-align: center;
        margin-bottom: 1.25rem;
    }

    .login-brand-logo-img {
        height: 48px;
        width: auto;
        margin-bottom: 0.5rem;
    }

    .login-brand-tagline {
        color: #6b7280;
        font-size: 0.875rem;
        margin: 0;
    }

    /* ============ WHITE CARD - Single unified card ============ */
    /* Header is just text inside the form, not separate */
    .login-card-header {
        text-align: center;
        padding: 0 0 1.25rem 0;
        margin: 0;
        background: transparent;
    }

    .login-card-header h2 {
        color: #111827;
        font-size: 1.125rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: 0.05em;
    }

    /* Form IS the white card */
    [data-testid="stForm"] {
        background: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 2rem !important;
        margin-left: auto !important;
        margin-right: auto !important;
        max-width: 380px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1) !important;
    }

    /* Hide "Press Enter to submit form" hint */
    [data-testid="InputInstructions"],
    div[data-testid="InputInstructions"],
    .stTextInput [data-testid="InputInstructions"],
    [data-testid="stForm"] [data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        overflow: hidden !important;
    }

    /* Input Fields - Full rectangular border like reference */
    .stTextInput {
        margin-bottom: 1.25rem !important;
    }

    .stTextInput > label {
        color: #374151 !important;
        font-size: 0.875rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.5rem !important;
    }

    /* Input container - FULL BORDER */
    .stTextInput > div > div,
    .stTextInput [data-baseweb="base-input"],
    .stTextInput [data-baseweb="input"] {
        background: #ffffff !important;
        border: 1px solid #d1d5db !important;
        border-top: 1px solid #d1d5db !important;
        border-right: 1px solid #d1d5db !important;
        border-bottom: 1px solid #d1d5db !important;
        border-left: 1px solid #d1d5db !important;
        border-radius: 6px !important;
        box-shadow: none !important;
        outline: none !important;
    }

    .stTextInput > div > div:hover,
    .stTextInput [data-baseweb="base-input"]:hover {
        border: 1px solid #9ca3af !important;
        border-color: #9ca3af !important;
    }

    .stTextInput > div > div:focus-within,
    .stTextInput [data-baseweb="base-input"]:focus-within {
        border: 1px solid #f97316 !important;
        border-color: #f97316 !important;
        box-shadow: none !important;
    }

    /* Input element */
    .stTextInput input {
        color: #111827 !important;
        font-size: 0.95rem !important;
        padding: 0.75rem 1rem !important;
        background: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }

    .stTextInput input::placeholder {
        color: #9ca3af !important;
    }

    /* Password eye button - seamless with input */
    .stTextInput button,
    .stTextInput [data-testid="passwordShowButton"],
    .stTextInput [data-testid="baseButton-secondary"] {
        color: #6b7280 !important;
        border: none !important;
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
        outline: none !important;
        padding: 0.5rem !important;
        margin: 0 !important;
    }

    .stTextInput button:hover {
        color: #f97316 !important;
        background: transparent !important;
    }

    .stTextInput button:focus {
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* Remove any background from button container */
    .stTextInput > div > div > div:last-child,
    .stTextInput [data-baseweb="input"] > div:last-child {
        background: transparent !important;
        border: none !important;
    }

    /* Submit Button - Orange like nxtby.com */
    .stFormSubmitButton > button,
    .stFormSubmitButton > button:focus,
    .stFormSubmitButton > button:active,
    [data-testid="stForm"] .stFormSubmitButton > button,
    [data-testid="stFormSubmitButton"] > button {
        background: #f97316 !important;
        background-color: #f97316 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.875rem 1.5rem !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        margin-top: 1rem !important;
        box-shadow: none !important;
    }

    .stFormSubmitButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        background: #ea580c !important;
        background-color: #ea580c !important;
    }

    .stFormSubmitButton > button:disabled {
        background: #d1d5db !important;
        background-color: #d1d5db !important;
    }

    /* Alerts */
    .stAlert {
        background: #fef2f2 !important;
        border: 1px solid #fecaca !important;
        border-radius: 6px !important;
        margin-top: 0.75rem !important;
    }

    .stAlert p {
        color: #dc2626 !important;
        font-size: 0.85rem !important;
    }

    .session-warning {
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-radius: 6px;
        padding: 0.625rem 1rem;
        margin-bottom: 1rem;
        text-align: center;
    }

    .session-warning p {
        color: #b45309;
        font-size: 0.85rem;
        margin: 0;
    }

    .service-unavailable {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 6px;
        padding: 1rem;
        text-align: center;
    }

    .service-unavailable p {
        color: #dc2626;
        font-size: 0.85rem;
        margin: 0;
    }

    /* Responsive */
    @media (max-width: 480px) {
        .login-card-header {
            max-width: 100%;
            border-radius: 0;
            margin: 0;
        }
        [data-testid="stForm"] {
            max-width: 100% !important;
            border-radius: 0 !important;
            margin: 0 !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

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
                            safe_rerun()
                        else:
                            st.session_state.login_processing = False
                            st.error(message)
                    except Exception:
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

# ============================================
# ROLE-BASED CONFIGURATION
# ============================================
USER_ROLES = {
    "operations": {
        "name": "Operations",
        "focus_states": ["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR", "IN_OFFICE_TESTING"],
        "show_sla": True,
        "show_billing": False,
        "can_drill_down": True,
        "description": "Focus on returns and repairs"
    },
    "finance": {
        "name": "Finance",
        "focus_states": ["WITH_CLIENT", "SOLD"],
        "show_sla": False,
        "show_billing": True,
        "can_drill_down": False,
        "description": "Focus on billable assets"
    },
    "admin": {
        "name": "Admin",
        "focus_states": None,  # All states visible
        "show_sla": True,
        "show_billing": True,
        "can_drill_down": True,
        "description": "Full system access"
    }
}

# SLA Configuration (in days)
SLA_CONFIG = {
    "RETURNED_FROM_CLIENT": {"warning": 3, "critical": 7},
    "WITH_VENDOR_REPAIR": {"warning": 7, "critical": 14},
    "IN_OFFICE_TESTING": {"warning": 2, "critical": 5}
}

# ============================================
# PERFORMANCE & PAGINATION CONFIGURATION
# ============================================
PAGINATION_CONFIG = {
    "default_page_size": 25,
    "page_size_options": [10, 25, 50, 100],
    "max_records": 1000,  # Prevent full-table scans
}

CACHE_CONFIG = {
    "ttl_dashboard": 300,      # 5 minutes for dashboard KPIs
    "ttl_assets": 600,         # 10 minutes for asset list
    "ttl_clients": 900,        # 15 minutes for client list (rarely changes)
    "ttl_reports": 1800,       # 30 minutes for reports
    "enabled": True,           # Global cache toggle
}

# Query limits to prevent performance issues
QUERY_LIMITS = {
    "assets": 500,
    "clients": 200,
    "assignments": 500,
    "issues": 300,
    "repairs": 300,
    "activity_log": 200,
}


# ============================================
# CENTRALIZED BILLING CONFIGURATION
# ============================================
# All billing rules are defined here - DO NOT duplicate elsewhere
BILLING_CONFIG = {
    # Default monthly rate per asset (can be overridden per client)
    "default_monthly_rate": 3000,

    # States where billing is ACTIVE
    "billable_states": ["WITH_CLIENT"],

    # States where billing is PAUSED (was billing, now paused)
    "paused_states": ["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR"],

    # States where billing is NOT APPLICABLE (never billed or terminal)
    "non_billable_states": [
        "IN_STOCK_WORKING",
        "IN_STOCK_DEFECTIVE",
        "IN_OFFICE_TESTING",
        "SOLD",
        "DISPOSED"
    ],

    # Roles that can override billing (e.g., adjust rates, force billing status)
    "billing_override_roles": ["admin"],

    # Billing status labels
    "status_labels": {
        "active": "Billing Active",
        "paused": "Billing Paused",
        "not_applicable": "Not Billable"
    },

    # Billing status colors for UI
    "status_colors": {
        "active": "#22c55e",      # Green
        "paused": "#f59e0b",      # Amber/Warning
        "not_applicable": "#64748b"  # Gray
    },

    # Billing status icons
    "status_icons": {
        "active": "●",
        "paused": "◐",
        "not_applicable": "○"
    }
}


def get_asset_billing_status(asset_status: str) -> dict:
    """
    Determine billing status for an asset based on its lifecycle state.
    This is the SINGLE SOURCE OF TRUTH for billing status.

    Returns:
        dict with keys: status, label, color, icon, reason
    """
    if asset_status in BILLING_CONFIG["billable_states"]:
        return {
            "status": "active",
            "label": BILLING_CONFIG["status_labels"]["active"],
            "color": BILLING_CONFIG["status_colors"]["active"],
            "icon": BILLING_CONFIG["status_icons"]["active"],
            "reason": "Asset is deployed with client",
            "is_billable": True
        }
    elif asset_status in BILLING_CONFIG["paused_states"]:
        reason_map = {
            "RETURNED_FROM_CLIENT": "Asset returned from client",
            "WITH_VENDOR_REPAIR": "Asset sent for repair"
        }
        return {
            "status": "paused",
            "label": BILLING_CONFIG["status_labels"]["paused"],
            "color": BILLING_CONFIG["status_colors"]["paused"],
            "icon": BILLING_CONFIG["status_icons"]["paused"],
            "reason": reason_map.get(asset_status, "Billing temporarily paused"),
            "is_billable": False
        }
    else:
        reason_map = {
            "IN_STOCK_WORKING": "Asset in stock - not deployed",
            "IN_STOCK_DEFECTIVE": "Asset defective - not deployable",
            "IN_OFFICE_TESTING": "Asset under testing",
            "SOLD": "Asset sold - final billing completed",
            "DISPOSED": "Asset disposed"
        }
        return {
            "status": "not_applicable",
            "label": BILLING_CONFIG["status_labels"]["not_applicable"],
            "color": BILLING_CONFIG["status_colors"]["not_applicable"],
            "icon": BILLING_CONFIG["status_icons"]["not_applicable"],
            "reason": reason_map.get(asset_status, "Not in billable state"),
            "is_billable": False
        }


def can_override_billing(role: str) -> bool:
    """Check if a role can override billing rules."""
    return role in BILLING_CONFIG["billing_override_roles"]


def get_billable_assets(assets_df, strict: bool = True):
    """
    Filter assets that are currently billable.

    Args:
        assets_df: DataFrame of assets
        strict: If True, only return assets in billable states.
                If False (Admin override), can include paused states.

    Returns:
        DataFrame of billable assets
    """
    if assets_df.empty or "Current Status" not in assets_df.columns:
        return assets_df.iloc[0:0]  # Return empty DataFrame with same columns

    billable_states = BILLING_CONFIG["billable_states"]
    return assets_df[assets_df["Current Status"].isin(billable_states)]


def get_paused_billing_assets(assets_df):
    """Get assets with paused billing (returned or in repair)."""
    if assets_df.empty or "Current Status" not in assets_df.columns:
        return assets_df.iloc[0:0]

    paused_states = BILLING_CONFIG["paused_states"]
    return assets_df[assets_df["Current Status"].isin(paused_states)]


def calculate_billing_metrics(assets_df, monthly_rate: float = None) -> dict:
    """
    Calculate all billing metrics from assets DataFrame.
    This is the SINGLE SOURCE OF TRUTH for billing calculations.

    Args:
        assets_df: DataFrame of assets
        monthly_rate: Optional override rate (Admin only), defaults to config rate

    Returns:
        dict with all billing metrics
    """
    rate = monthly_rate or BILLING_CONFIG["default_monthly_rate"]

    # Get counts by billing status
    billable_df = get_billable_assets(assets_df)
    paused_df = get_paused_billing_assets(assets_df)

    billable_count = len(billable_df)
    paused_count = len(paused_df)
    total_count = len(assets_df) if not assets_df.empty else 0

    # Calculate revenues
    monthly_revenue = billable_count * rate
    daily_rate = rate / 30
    annual_revenue = monthly_revenue * 12

    # Calculate by client if location data available
    client_breakdown = {}
    if not billable_df.empty and "Current Location" in billable_df.columns:
        client_counts = billable_df.groupby("Current Location").size()
        for client, count in client_counts.items():
            client_breakdown[client] = {
                "asset_count": count,
                "monthly_rate": rate,
                "monthly_revenue": count * rate,
                "annual_revenue": count * rate * 12
            }

    return {
        "billable_count": billable_count,
        "paused_count": paused_count,
        "total_count": total_count,
        "utilization_rate": (billable_count / total_count * 100) if total_count > 0 else 0,
        "monthly_rate": rate,
        "daily_rate": daily_rate,
        "monthly_revenue": monthly_revenue,
        "annual_revenue": annual_revenue,
        "client_breakdown": client_breakdown
    }


def create_analytics_bar_chart(
    x_data: list,
    y_data: list,
    x_label: str,
    y_label: str,
    title: str = None,
    height: int = 350,
    hover_context: str = "Count",
    total_for_percent: int = None,
    click_key: str = None
) -> go.Figure:
    """
    Create an analytics-grade bar chart with clarity-focused design.

    Features:
    - Clear axis labels with proper typography
    - Light, non-distracting gridlines
    - Muted base color with hover highlight
    - Rich tooltips with context and percentages
    - Smooth 200ms transitions
    - Click-to-filter support via session state

    Args:
        x_data: List of x-axis values (categories)
        y_data: List of y-axis values (counts)
        x_label: Label for x-axis
        y_label: Label for y-axis
        title: Optional chart title
        height: Chart height in pixels
        hover_context: Context label for hover (e.g., "Assets", "Count")
        total_for_percent: Total value for percentage calculation in tooltip
        click_key: Session state key for click filtering

    Returns:
        Plotly Figure object with analytics-grade styling
    """
    # Calculate percentages if total provided
    if total_for_percent and total_for_percent > 0:
        percentages = [(v / total_for_percent * 100) for v in y_data]
        hover_template = (
            '<b style="font-size:14px">%{x}</b><br>'
            f'<span style="color:#6B7280">{hover_context}:</span> '
            '<b>%{y:,}</b><br>'
            '<span style="color:#6B7280">Share:</span> '
            '<b>%{customdata:.1f}%</b>'
            '<extra></extra>'
        )
        customdata = percentages
    else:
        hover_template = (
            '<b style="font-size:14px">%{x}</b><br>'
            f'<span style="color:#6B7280">{hover_context}:</span> '
            '<b>%{y:,}</b>'
            '<extra></extra>'
        )
        customdata = None

    # Professional color palette - vibrant but clean
    colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#EC4899', '#84CC16']
    bar_colors = [colors[i % len(colors)] for i in range(len(x_data))]

    # Create bar trace
    bar_trace = go.Bar(
        x=x_data,
        y=y_data,
        marker=dict(
            color=bar_colors,
            line=dict(width=0)
        ),
        hovertemplate=hover_template,
        customdata=customdata,
        hoverlabel=dict(
            bgcolor='#1F2937',
            bordercolor='#374151',
            font=dict(
                family='Inter, -apple-system, sans-serif',
                size=13,
                color='#FFFFFF'
            ),
            align='left'
        )
    )

    fig = go.Figure(data=[bar_trace])

    # Analytics-grade layout
    fig.update_layout(
        height=height,
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
        font=dict(
            family='Inter, -apple-system, sans-serif',
            size=12,
            color='#374151'
        ),
        margin=dict(t=20, b=60, l=50, r=20),
        showlegend=False,

        # X-axis styling
        xaxis=dict(
            title=dict(
                text=x_label,
                font=dict(size=12, color='#4B5563'),
                standoff=12
            ),
            tickfont=dict(size=11, color='#6B7280'),
            showgrid=False,
            showline=True,
            linecolor='#E5E7EB',
            linewidth=1,
            type='category',
            tickangle=0 if len(x_data) <= 6 else -45
        ),

        # Y-axis styling with light gridlines
        yaxis=dict(
            title=dict(
                text=y_label,
                font=dict(size=12, color='#4B5563'),
                standoff=12
            ),
            tickfont=dict(size=11, color='#9CA3AF'),
            showgrid=True,
            gridcolor='#F3F4F6',
            gridwidth=1,
            griddash='solid',
            showline=True,
            linecolor='#E5E7EB',
            linewidth=1,
            rangemode='tozero',
            zeroline=True,
            zerolinecolor='#E5E7EB',
            zerolinewidth=1
        ),

        # Bar spacing
        bargap=0.3,

        # Smooth transitions
        transition=dict(
            duration=200,
            easing='cubic-in-out'
        ),

        # Hover mode - closest bar, no spike line
        hovermode='closest',
        hoverdistance=30
    )

    # Disable spike lines completely
    fig.update_xaxes(
        showspikes=False,
        spikemode=None
    )
    fig.update_yaxes(
        showspikes=False,
        spikemode=None
    )

    # Update hover behavior
    fig.update_traces(
        hoverlabel=dict(namelength=0),
        selector=dict(type='bar')
    )

    return fig


def render_billing_status_badge(asset_status: str) -> str:
    """
    Generate HTML for billing status badge.

    Args:
        asset_status: The asset's current lifecycle state

    Returns:
        HTML string for the billing status badge
    """
    billing = get_asset_billing_status(asset_status)
    return f"""
    <span style="
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
        background: {billing['color']}20;
        color: {billing['color']};
    ">
        {billing['icon']} {billing['label']}
    </span>
    """


def validate_billing_override(role: str, action: str) -> tuple:
    """
    Validate if a billing override action is allowed.

    Args:
        role: User's role
        action: The override action being attempted

    Returns:
        tuple: (allowed: bool, message: str)
    """
    if not can_override_billing(role):
        return False, f"Billing override not permitted for {role} role. Admin access required."

    return True, "Override permitted"


# ============================================
# EMPTY STATE CONFIGURATION
# ============================================
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


def render_loading_skeleton(skeleton_type: str = "table", rows: int = 5) -> None:
    """Render loading skeleton placeholders."""
    if skeleton_type == "table":
        skeleton_html = '<div style="padding: 16px;">'
        # Header row
        skeleton_html += '<div style="height: 32px; background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%); background-size: 200% 100%; animation: skeleton-pulse 1.5s ease-in-out infinite; border-radius: 4px; margin-bottom: 12px;"></div>'
        # Data rows
        for _ in range(rows):
            skeleton_html += '<div style="height: 44px; background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%); background-size: 200% 100%; animation: skeleton-pulse 1.5s ease-in-out infinite; border-radius: 4px; margin-bottom: 8px;"></div>'
        skeleton_html += '</div>'
        st.markdown(skeleton_html, unsafe_allow_html=True)

    elif skeleton_type == "chart":
        st.markdown("""
        <div style="height: 250px; background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%); background-size: 200% 100%; animation: skeleton-pulse 1.5s ease-in-out infinite; border-radius: 8px; display: flex; align-items: center; justify-content: center;">
            <span style="color: #94a3b8; font-size: 14px;">Loading chart...</span>
        </div>
        """, unsafe_allow_html=True)

    elif skeleton_type == "cards":
        cols = st.columns(4)
        for col in cols:
            with col:
                st.markdown("""
                <div style="height: 100px; background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%); background-size: 200% 100%; animation: skeleton-pulse 1.5s ease-in-out infinite; border-radius: 8px;"></div>
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


# ============================================
# LOADING & ERROR HANDLING CONFIGURATION
# ============================================

def render_skeleton_card(width: str = "100%", height: str = "120px"):
    """Render a skeleton loader for metric cards."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        width: {width};
        height: {height};
    "></div>
    <style>
        @keyframes shimmer {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_skeleton_table(rows: int = 5, cols: int = 4):
    """Render a skeleton loader for data tables."""
    header_html = "".join([f'<div class="skeleton-cell" style="flex: 1;"></div>' for _ in range(cols)])
    rows_html = ""
    for _ in range(rows):
        cells = "".join([f'<div class="skeleton-cell" style="flex: 1; height: 20px;"></div>' for _ in range(cols)])
        rows_html += f'<div class="skeleton-row">{cells}</div>'

    st.markdown(f"""
    <div class="skeleton-table">
        <div class="skeleton-header">{header_html}</div>
        {rows_html}
    </div>
    <style>
        .skeleton-table {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }}
        .skeleton-header {{
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .skeleton-row {{
            display: flex;
            gap: 15px;
            margin-bottom: 10px;
        }}
        .skeleton-cell {{
            background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 4px;
            height: 30px;
        }}
        @keyframes shimmer {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_skeleton_chart(height: str = "300px"):
    """Render a skeleton loader for charts."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        height: {height};
        display: flex;
        align-items: center;
        justify-content: center;
    ">
        <div style="color: #94a3b8; font-size: 0.9rem;">Loading chart...</div>
    </div>
    <style>
        @keyframes shimmer {{
            0% {{ background-position: 200% 0; }}
            100% {{ background-position: -200% 0; }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_skeleton_metrics(count: int = 4):
    """Render skeleton loaders for a row of metric cards."""
    cols = st.columns(count)
    for col in cols:
        with col:
            render_skeleton_card(height="100px")


def render_error_state(
    error_message: str,
    error_type: str = "general",
    show_retry: bool = True,
    retry_key: str = None,
    technical_details: str = None,
    error_id: str = None
):
    """
    Render a professional error state with optional retry.
    Production-safe: Shows error reference ID instead of technical details.

    Args:
        error_message: User-friendly error message
        error_type: Type of error (general, connection, data, permission, database)
        show_retry: Whether to show retry button
        retry_key: Unique key for retry button
        technical_details: Technical error details (only shown in debug mode)
        error_id: Error reference ID for support
    """
    error_configs = {
        "general": {"icon": "⚠️", "color": "#ef4444", "bg": "#fef2f2", "border": "#fecaca"},
        "connection": {"icon": "🔌", "color": "#f59e0b", "bg": "#fffbeb", "border": "#fde68a"},
        "database": {"icon": "🗄️", "color": "#f59e0b", "bg": "#fffbeb", "border": "#fde68a"},
        "data": {"icon": "📊", "color": "#3b82f6", "bg": "#eff6ff", "border": "#bfdbfe"},
        "permission": {"icon": "🔒", "color": "#8b5cf6", "bg": "#f5f3ff", "border": "#ddd6fe"},
        "timeout": {"icon": "⏱️", "color": "#6366f1", "bg": "#eef2ff", "border": "#c7d2fe"}
    }

    config = error_configs.get(error_type, error_configs["general"])

    # Get error ID from session state if not provided
    display_error_id = error_id or st.session_state.get('data_load_error_id', '')
    ref_text = f"<br><small style='color: #9ca3af;'>Reference: {display_error_id}</small>" if display_error_id else ""

    st.markdown(f"""
    <div style="
        background: {config['bg']};
        border: 1px solid {config['border']};
        border-left: 4px solid {config['color']};
        border-radius: 8px;
        padding: 20px;
        margin: 15px 0;
    ">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <div style="font-size: 1.5rem;">{config['icon']}</div>
            <div style="flex: 1;">
                <div style="font-weight: 600; color: {config['color']}; margin-bottom: 5px;">
                    Something went wrong
                </div>
                <div style="color: #374151; font-size: 0.95rem;">
                    {error_message}{ref_text}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Only show technical details in debug mode (not in production)
    is_debug = os.getenv("DEBUG", "false").lower() == "true"
    if technical_details and is_debug:
        with st.expander("Technical Details (Debug Mode)", expanded=False):
            st.code(technical_details, language="text")

    # Show retry button if applicable
    if show_retry and retry_key:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Try Again", key=f"btn_{retry_key}"):
                st.session_state[retry_key] = True
                st.cache_data.clear()
                safe_rerun()


def render_loading_overlay(message: str = "Processing..."):
    """Render a loading overlay for async operations."""
    st.markdown(f"""
    <div style="
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 30px;
        text-align: center;
        margin: 20px 0;
    ">
        <div style="
            width: 40px;
            height: 40px;
            border: 3px solid #e2e8f0;
            border-top: 3px solid #f97316;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px auto;
        "></div>
        <div style="color: #64748b; font-size: 0.95rem;">{message}</div>
    </div>
    <style>
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_inline_error(message: str, show_icon: bool = True):
    """Render a compact inline error message."""
    icon = "⚠️ " if show_icon else ""
    st.markdown(f"""
    <div style="
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 6px;
        padding: 10px 15px;
        color: #991b1b;
        font-size: 0.9rem;
        margin: 8px 0;
    ">
        {icon}{message}
    </div>
    """, unsafe_allow_html=True)


def render_inline_warning(message: str, show_icon: bool = True):
    """Render a compact inline warning message."""
    icon = "⚡ " if show_icon else ""
    st.markdown(f"""
    <div style="
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-radius: 6px;
        padding: 10px 15px;
        color: #92400e;
        font-size: 0.9rem;
        margin: 8px 0;
    ">
        {icon}{message}
    </div>
    """, unsafe_allow_html=True)


def with_error_handling(func, error_message: str = "An error occurred", retry_key: str = None):
    """
    Decorator/wrapper for error handling with retry capability.

    Usage:
        result = with_error_handling(
            lambda: some_risky_operation(),
            error_message="Failed to load data",
            retry_key="retry_data"
        )
    """
    try:
        return func(), None
    except Exception as e:
        render_error_state(
            error_message=error_message,
            show_retry=retry_key is not None,
            retry_key=retry_key,
            technical_details=str(e)
        )
        return None, str(e)


def init_loading_state(key: str):
    """Initialize a loading state in session state."""
    if f"loading_{key}" not in st.session_state:
        st.session_state[f"loading_{key}"] = False


def set_loading(key: str, is_loading: bool):
    """Set loading state for a specific operation."""
    st.session_state[f"loading_{key}"] = is_loading


def is_loading(key: str) -> bool:
    """Check if an operation is currently loading."""
    return st.session_state.get(f"loading_{key}", False)


def render_action_button(
    label: str,
    key: str,
    loading_key: str = None,
    button_type: str = "primary",
    disabled: bool = False,
    width: str = 'stretch'
) -> bool:
    """
    Render an action button that disables during loading.

    Returns:
        True if button was clicked and not loading
    """
    is_btn_loading = is_loading(loading_key) if loading_key else False

    if is_btn_loading:
        st.button(
            f"⏳ {label}...",
            key=f"{key}_loading",
            disabled=True,
            width=width
        )
        return False
    else:
        return st.button(
            label,
            key=key,
            type=button_type,
            disabled=disabled,
            width=width
        )


# Page configuration
st.set_page_config(
    page_title="Asset Management System",
    page_icon="🟠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional Dashboard Theme CSS - Matching Reference Design
st.markdown("""
<style>
    /* ==========================================================================
       DESIGN SYSTEM - Enterprise Asset Management Dashboard
       Version: 2.0

       This design system provides consistent tokens for colors, typography,
       spacing, and motion across the entire application.
       ========================================================================== */

    :root {
        /* ------------------------------------------------------------------
           1. COLOR TOKENS
           ------------------------------------------------------------------ */

        /* Neutral Background Scale (Light → Dark) */
        --color-bg-primary: #ffffff;           /* Main content background */
        --color-bg-secondary: #f8fafc;         /* Cards, elevated surfaces */
        --color-bg-tertiary: #f1f5f9;          /* Subtle backgrounds, hover states */
        --color-bg-muted: #e2e8f0;             /* Borders, dividers */

        /* Neutral Background Scale (Dark - Sidebar) */
        --color-sidebar-bg: #1a2332;           /* Sidebar primary */
        --color-sidebar-hover: #232f42;        /* Sidebar hover state */
        --color-sidebar-active: rgba(249, 115, 22, 0.15);  /* Active nav item */
        --color-sidebar-border: #2d3748;       /* Sidebar dividers */

        /* Text Colors */
        --color-text-primary: #1e293b;         /* Headings, primary text */
        --color-text-secondary: #475569;       /* Body text, labels */
        --color-text-tertiary: #64748b;        /* Captions, metadata */
        --color-text-muted: #94a3b8;           /* Placeholders, disabled */
        --color-text-inverse: #ffffff;         /* Text on dark backgrounds */

        /* Brand / Accent */
        --color-brand-primary: #f97316;        /* Primary orange */
        --color-brand-hover: #ea580c;          /* Orange hover */
        --color-brand-light: rgba(249, 115, 22, 0.1);  /* Orange tint */

        /* Semantic Colors - Success */
        --color-success: #22c55e;
        --color-success-dark: #16a34a;
        --color-success-light: #dcfce7;
        --color-success-bg: #f0fdf4;

        /* Semantic Colors - Warning */
        --color-warning: #f59e0b;
        --color-warning-dark: #d97706;
        --color-warning-light: #fef3c7;
        --color-warning-bg: #fffbeb;

        /* Semantic Colors - Critical / Error */
        --color-critical: #ef4444;
        --color-critical-dark: #dc2626;
        --color-critical-light: #fee2e2;
        --color-critical-bg: #fef2f2;

        /* Semantic Colors - Info / Active */
        --color-info: #3b82f6;
        --color-info-dark: #2563eb;
        --color-info-light: #dbeafe;
        --color-info-bg: #eff6ff;

        /* Semantic Colors - Neutral (for non-semantic states) */
        --color-neutral: #64748b;
        --color-neutral-dark: #475569;
        --color-neutral-light: #e2e8f0;
        --color-neutral-bg: #f8fafc;

        /* Data Visualization Colors (Muted, accessible palette) */
        --color-data-1: #6366f1;              /* Indigo */
        --color-data-2: #8b5cf6;              /* Violet */
        --color-data-3: #ec4899;              /* Pink */
        --color-data-4: #f97316;              /* Orange (brand) */
        --color-data-5: #14b8a6;              /* Teal */
        --color-data-6: #64748b;              /* Slate */

        /* Border Colors */
        --color-border-light: #e2e8f0;
        --color-border-default: #cbd5e1;
        --color-border-dark: #94a3b8;

        /* Shadow Colors */
        --shadow-color: rgba(15, 23, 42, 0.08);
        --shadow-color-heavy: rgba(15, 23, 42, 0.12);

        /* ------------------------------------------------------------------
           2. TYPOGRAPHY
           ------------------------------------------------------------------ */

        /* Font Family */
        --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        --font-family-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;

        /* Font Sizes - Clear hierarchy */
        --font-size-xs: 0.6875rem;            /* 11px - Micro labels */
        --font-size-sm: 0.75rem;              /* 12px - Captions, metadata */
        --font-size-base: 0.875rem;           /* 14px - Body text */
        --font-size-md: 1rem;                 /* 16px - Emphasized body */
        --font-size-lg: 1.125rem;             /* 18px - Card titles */
        --font-size-xl: 1.25rem;              /* 20px - Section headers */
        --font-size-2xl: 1.5rem;              /* 24px - Page titles */
        --font-size-3xl: 2rem;                /* 32px - Large numbers */
        --font-size-4xl: 2.5rem;              /* 40px - Hero numbers */

        /* Font Weights */
        --font-weight-normal: 400;
        --font-weight-medium: 500;
        --font-weight-semibold: 600;
        --font-weight-bold: 700;

        /* Line Heights */
        --line-height-tight: 1.1;             /* Numbers, headings */
        --line-height-snug: 1.25;             /* Compact text */
        --line-height-normal: 1.5;            /* Body text */
        --line-height-relaxed: 1.625;         /* Readable paragraphs */

        /* Letter Spacing */
        --letter-spacing-tight: -0.025em;     /* Large headings */
        --letter-spacing-normal: 0;
        --letter-spacing-wide: 0.025em;       /* All caps labels */
        --letter-spacing-wider: 0.05em;       /* Section headers */

        /* ------------------------------------------------------------------
           3. SPACING (8px Grid System)
           ------------------------------------------------------------------ */

        --space-0: 0;
        --space-1: 0.25rem;                   /* 4px */
        --space-2: 0.5rem;                    /* 8px - Base unit */
        --space-3: 0.75rem;                   /* 12px */
        --space-4: 1rem;                      /* 16px */
        --space-5: 1.25rem;                   /* 20px */
        --space-6: 1.5rem;                    /* 24px */
        --space-8: 2rem;                      /* 32px */
        --space-10: 2.5rem;                   /* 40px */
        --space-12: 3rem;                     /* 48px */
        --space-16: 4rem;                     /* 64px */

        /* Component-specific spacing */
        --card-padding: var(--space-5);       /* 20px */
        --card-padding-sm: var(--space-4);    /* 16px */
        --section-gap: var(--space-6);        /* 24px between sections */
        --element-gap: var(--space-3);        /* 12px between elements */

        /* ------------------------------------------------------------------
           4. BORDERS & RADIUS
           ------------------------------------------------------------------ */

        --radius-sm: 4px;
        --radius-md: 6px;
        --radius-lg: 8px;
        --radius-xl: 12px;
        --radius-2xl: 16px;
        --radius-full: 9999px;

        --border-width: 1px;
        --border-width-thick: 2px;
        --border-accent-width: 4px;           /* Left accent borders */

        /* ------------------------------------------------------------------
           5. SHADOWS (Elevation)
           ------------------------------------------------------------------ */

        --shadow-xs: 0 1px 2px var(--shadow-color);
        --shadow-sm: 0 1px 3px var(--shadow-color), 0 1px 2px var(--shadow-color);
        --shadow-md: 0 4px 6px -1px var(--shadow-color), 0 2px 4px -1px var(--shadow-color);
        --shadow-lg: 0 10px 15px -3px var(--shadow-color), 0 4px 6px -2px var(--shadow-color);
        --shadow-xl: 0 20px 25px -5px var(--shadow-color-heavy), 0 10px 10px -5px var(--shadow-color);

        /* Hover elevation */
        --shadow-hover: 0 8px 20px var(--shadow-color-heavy);

        /* ------------------------------------------------------------------
           6. MOTION / TRANSITIONS
           ------------------------------------------------------------------ */

        /* Duration */
        --duration-instant: 0ms;
        --duration-fast: 100ms;
        --duration-normal: 200ms;
        --duration-slow: 300ms;

        /* Easing */
        --ease-default: cubic-bezier(0.4, 0, 0.2, 1);    /* Smooth deceleration */
        --ease-in: cubic-bezier(0.4, 0, 1, 1);
        --ease-out: cubic-bezier(0, 0, 0.2, 1);
        --ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1); /* Only for special emphasis */

        /* Standard transitions */
        --transition-fast: var(--duration-fast) var(--ease-default);
        --transition-normal: var(--duration-normal) var(--ease-default);
        --transition-slow: var(--duration-slow) var(--ease-default);

        /* Hover transforms */
        --hover-lift: translateY(-2px);
        --hover-lift-subtle: translateY(-1px);
        --active-press: translateY(1px);
    }

    /* ==========================================================================
       BASE STYLES - Applied globally
       ========================================================================== */

    /* Typography Defaults */
    .main .block-container {
        font-family: var(--font-family) !important;
        color: var(--color-text-secondary);
        line-height: var(--line-height-normal);
    }

    /* Page Title */
    .page-header-title {
        font-size: var(--font-size-2xl) !important;
        font-weight: var(--font-weight-bold) !important;
        color: var(--color-text-primary) !important;
        line-height: var(--line-height-tight) !important;
        letter-spacing: var(--letter-spacing-tight) !important;
        margin: 0 !important;
    }

    /* Section Title */
    .section-title {
        font-size: var(--font-size-xs) !important;
        font-weight: var(--font-weight-semibold) !important;
        color: var(--color-text-tertiary) !important;
        text-transform: uppercase !important;
        letter-spacing: var(--letter-spacing-wider) !important;
        display: flex !important;
        align-items: center !important;
        gap: var(--space-2) !important;
        margin-bottom: var(--space-4) !important;
        padding: 0 !important;
    }

    .section-title-icon {
        width: 6px;
        height: 6px;
        background: var(--color-brand-primary);
        border-radius: var(--radius-full);
    }

    /* Card Title */
    .card-title {
        font-size: var(--font-size-base) !important;
        font-weight: var(--font-weight-semibold) !important;
        color: var(--color-text-primary) !important;
        margin-bottom: var(--space-1) !important;
    }

    /* Card Subtitle / Meta */
    .card-subtitle, .card-meta {
        font-size: var(--font-size-sm) !important;
        color: var(--color-text-muted) !important;
        font-weight: var(--font-weight-normal) !important;
    }

    /* Numeric Values - More prominent than labels */
    .value-primary {
        font-size: var(--font-size-4xl) !important;
        font-weight: var(--font-weight-bold) !important;
        line-height: var(--line-height-tight) !important;
        color: var(--color-text-primary) !important;
    }

    .value-secondary {
        font-size: var(--font-size-3xl) !important;
        font-weight: var(--font-weight-bold) !important;
        line-height: var(--line-height-tight) !important;
    }

    .value-label {
        font-size: var(--font-size-sm) !important;
        font-weight: var(--font-weight-medium) !important;
        color: var(--color-text-secondary) !important;
    }

    /* Standard Card */
    .ds-card {
        background: var(--color-bg-primary);
        border: var(--border-width) solid var(--color-border-light);
        border-radius: var(--radius-xl);
        padding: var(--card-padding);
        transition: all var(--transition-normal);
    }

    .ds-card:hover {
        border-color: var(--color-border-default);
        box-shadow: var(--shadow-hover);
        transform: var(--hover-lift-subtle);
    }

    /* Semantic Status Indicators */
    .status-success { color: var(--color-success); }
    .status-warning { color: var(--color-warning); }
    .status-critical { color: var(--color-critical); }
    .status-info { color: var(--color-info); }
    .status-neutral { color: var(--color-neutral); }

    .bg-success { background: var(--color-success-bg); }
    .bg-warning { background: var(--color-warning-bg); }
    .bg-critical { background: var(--color-critical-bg); }
    .bg-info { background: var(--color-info-bg); }
    .bg-neutral { background: var(--color-neutral-bg); }

    /* Accent Borders */
    .border-success { border-left: var(--border-accent-width) solid var(--color-success) !important; }
    .border-warning { border-left: var(--border-accent-width) solid var(--color-warning) !important; }
    .border-critical { border-left: var(--border-accent-width) solid var(--color-critical) !important; }
    .border-info { border-left: var(--border-accent-width) solid var(--color-info) !important; }
    .border-neutral { border-left: var(--border-accent-width) solid var(--color-neutral) !important; }

    /* Badge / Pill */
    .ds-badge {
        display: inline-flex;
        align-items: center;
        padding: var(--space-1) var(--space-2);
        font-size: var(--font-size-xs);
        font-weight: var(--font-weight-medium);
        border-radius: var(--radius-full);
        line-height: 1;
    }

    .ds-badge-success {
        background: var(--color-success-light);
        color: var(--color-success-dark);
    }

    .ds-badge-warning {
        background: var(--color-warning-light);
        color: var(--color-warning-dark);
    }

    .ds-badge-critical {
        background: var(--color-critical-light);
        color: var(--color-critical-dark);
    }

    .ds-badge-info {
        background: var(--color-info-light);
        color: var(--color-info-dark);
    }

    /* ===== SIDEBAR - Dark Theme ===== */
    [data-testid="stSidebar"] {
        background-color: var(--color-sidebar-bg) !important;
    }

    [data-testid="stSidebar"] > div:first-child {
        background-color: var(--color-sidebar-bg) !important;
    }

    /* Sidebar Section Headers */
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--color-text-tertiary) !important;
        font-size: var(--font-size-xs) !important;
        font-weight: var(--font-weight-semibold) !important;
        letter-spacing: var(--letter-spacing-wide) !important;
        text-transform: uppercase !important;
        margin-top: var(--space-6) !important;
        margin-bottom: var(--space-2) !important;
        padding-left: var(--space-3) !important;
    }

    [data-testid="stSidebar"] .stMarkdown p {
        color: var(--color-text-muted) !important;
    }

    /* ===== SIDEBAR NAVIGATION BUTTONS ===== */
    /* Base container styles - remove all focus indicators */
    [data-testid="stSidebar"] .stButton,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Default button style (non-selected) */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: var(--color-text-muted) !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        border-radius: 0 8px 8px 0 !important;
        padding: var(--space-3) var(--space-4) !important;
        font-weight: var(--font-weight-normal) !important;
        font-size: var(--font-size-base) !important;
        text-align: left !important;
        justify-content: flex-start !important;
        cursor: pointer !important;
        transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Hover state - only shows while mouse is actually hovering */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
        background: rgba(249, 115, 22, 0.08) !important;
        color: #f97316 !important;
        border-left: 3px solid transparent !important;
    }

    /* Secondary button (non-active pages) - ALWAYS transparent unless hovering */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"],
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:link,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:visited {
        background: transparent !important;
        color: var(--color-text-muted) !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Secondary button focus/active/focus-within - FORCE transparent */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:focus,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:focus-visible,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:focus-within,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:active,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:target,
    [data-testid="stSidebar"] .stButton > button[kind="secondary"][data-focus],
    [data-testid="stSidebar"] .stButton > button[kind="secondary"][aria-selected="true"] {
        background: transparent !important;
        color: var(--color-text-muted) !important;
        border: none !important;
        border-left: 3px solid transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Secondary button - not hover state specifically */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:not(:hover) {
        background: transparent !important;
        color: var(--color-text-muted) !important;
    }

    /* Primary button (ACTIVE/SELECTED page) - this is the only one with highlight */
    [data-testid="stSidebar"] .stButton > button[kind="primary"],
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:focus,
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:focus-visible,
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:active {
        background: rgba(249, 115, 22, 0.15) !important;
        color: #f97316 !important;
        font-weight: 500 !important;
        border: none !important;
        border-left: 3px solid #f97316 !important;
        border-radius: 0 8px 8px 0 !important;
        outline: none !important;
        box-shadow: none !important;
    }

    /* Primary button hover - slightly darker */
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: rgba(249, 115, 22, 0.2) !important;
    }

    /* Remove ALL focus rings globally in sidebar */
    [data-testid="stSidebar"] button:focus,
    [data-testid="stSidebar"] button:focus-visible,
    [data-testid="stSidebar"] button:focus-within,
    [data-testid="stSidebar"] *:focus,
    [data-testid="stSidebar"] *:focus-visible {
        outline: none !important;
        box-shadow: none !important;
    }

    /* Override any Streamlit default active/focus backgrounds for secondary buttons */
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:focus,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:active,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] button:focus,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] button:active {
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* ===== SIDEBAR BRAND ===== */
    .sidebar-brand {
        padding: var(--space-5) var(--space-4);
        margin-bottom: var(--space-3);
        border-bottom: var(--border-width) solid var(--color-sidebar-border);
    }

    .sidebar-brand h1 {
        color: var(--color-brand-primary) !important;
        font-size: var(--font-size-lg) !important;
        margin: 0 !important;
        font-weight: var(--font-weight-semibold) !important;
        display: flex !important;
        align-items: center !important;
        gap: var(--space-2) !important;
    }

    .sidebar-brand p {
        color: var(--color-text-tertiary) !important;
        font-size: var(--font-size-sm) !important;
        margin: var(--space-1) 0 0 0 !important;
    }

    /* ===== CONNECTION STATUS ===== */
    .connection-status {
        padding: var(--space-2) var(--space-3);
        border-radius: var(--radius-md);
        margin: var(--space-2) var(--space-4);
        font-size: var(--font-size-sm);
        font-weight: var(--font-weight-medium);
        display: flex;
        align-items: center;
        gap: var(--space-2);
    }

    .status-connected {
        background: rgba(34, 197, 94, 0.1);
        color: var(--color-success);
    }

    .status-disconnected {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
    }

    /* ===== MAIN CONTENT AREA ===== */
    .main .block-container {
        background-color: #f8fafc;
        padding: 1.5rem 2rem;
        max-width: 100%;
    }

    /* ===== PAGE HEADER ===== */
    .main-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 1.5rem;
    }

    .sub-header {
        font-size: 1rem;
        font-weight: 600;
        color: #1e293b;
        margin: 1.5rem 0 1rem 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* ===== METRIC CARDS ===== */
    [data-testid="stMetric"] {
        background: #ffffff;
        padding: 1.25rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        cursor: pointer;
        transition: all 0.2s ease;
    }

    [data-testid="stMetric"]:hover {
        border-color: #3b82f6;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        transform: translateY(-2px);
    }

    [data-testid="stMetric"]::after {
        content: "Click to view details";
        position: absolute;
        bottom: -24px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 11px;
        color: #64748b;
        opacity: 0;
        transition: opacity 0.2s ease;
        white-space: nowrap;
    }

    [data-testid="stMetric"]:hover::after {
        opacity: 1;
    }

    [data-testid="stMetricLabel"] {
        color: #64748b !important;
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.3px !important;
    }

    [data-testid="stMetricValue"] {
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 1.75rem !important;
    }

    /* ===== LOADING SKELETONS ===== */
    @keyframes skeleton-pulse {
        0%, 100% { opacity: 0.4; }
        50% { opacity: 0.8; }
    }

    .skeleton {
        background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
        background-size: 200% 100%;
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        border-radius: 4px;
    }

    .skeleton-row {
        height: 40px;
        margin-bottom: 8px;
        background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
        background-size: 200% 100%;
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        border-radius: 4px;
    }

    .skeleton-chart {
        height: 200px;
        background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
        background-size: 200% 100%;
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        border-radius: 8px;
    }

    /* ===== EMPTY STATE ===== */
    .empty-state {
        text-align: center;
        padding: 48px 24px;
        background: #f8fafc;
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
    }

    .empty-state-title {
        font-size: 16px;
        font-weight: 600;
        color: #475569;
        margin-bottom: 8px;
    }

    .empty-state-message {
        font-size: 14px;
        color: #64748b;
        margin: 0;
    }

    /* ===== CLICKABLE CARDS ===== */
    .clickable-card {
        cursor: pointer;
        transition: all 0.2s ease;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }

    .clickable-card:hover {
        border-color: #3b82f6;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.12);
        transform: translateY(-1px);
    }

    /* ===== TABLE HOVER ===== */
    [data-testid="stDataFrame"] tbody tr {
        transition: background-color 0.15s ease;
    }

    [data-testid="stDataFrame"] tbody tr:hover {
        background-color: #f1f5f9 !important;
    }

    /* ===== BUTTONS ===== */
    .main .stButton > button {
        background: #22c55e;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
        font-size: 0.875rem;
        transition: all 0.15s ease;
    }

    .main .stButton > button:hover {
        background: #16a34a;
    }

    /* ===== TAB STYLING ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background-color: transparent;
        border-bottom: 1px solid #e2e8f0;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 0;
        padding: 12px 20px;
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        color: #64748b !important;
        font-weight: 500;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: #1e293b !important;
    }

    .stTabs [aria-selected="true"] {
        background: transparent !important;
        color: #f97316 !important;
        border-bottom: 2px solid #f97316 !important;
    }

    /* ===== ALERTS ===== */
    .stAlert {
        border-radius: 8px;
        border: none;
    }

    /* ===== DATA TABLE ===== */
    .stDataFrame {
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
    }

    /* ===== FORM ===== */
    .stForm {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }

    /* ===== EXPANDER ===== */
    .streamlit-expanderHeader {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        font-weight: 500;
        color: #1e293b;
    }

    /* ===== INPUT FIELDS ===== */
    .stSelectbox > div > div,
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stDateInput > div > div > input {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        color: #1e293b !important;
    }

    .stSelectbox > div > div:focus-within,
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #f97316 !important;
        box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1) !important;
    }

    /* ===== PLOTLY CHARTS ===== */
    .stPlotlyChart {
        background-color: transparent;
        border-radius: 0;
        padding: 0;
        border: none;
    }

    /* Hide Plotly modebar (toolbar) for cleaner look */
    .js-plotly-plot .plotly .modebar,
    .modebar-container,
    .modebar,
    .modebar-group,
    [data-title="Zoom"],
    [data-title="Pan"],
    [data-title="Box Select"],
    [data-title="Lasso Select"],
    .plotly .modebar {
        display: none !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* Also hide for iframe-based plotly charts */
    iframe[title*="plotly"] .modebar {
        display: none !important;
    }

    /* ===== DIVIDER ===== */
    hr {
        border: none !important;
        border-top: 1px solid #e2e8f0 !important;
        margin: 1.5rem 0 !important;
    }

    /* ===== STREAMLIT SPINNER ===== */
    .stSpinner > div {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2rem;
    }

    .stSpinner > div > div {
        border-color: #f97316 !important;
        border-right-color: transparent !important;
    }

    /* Page transition effect */
    .main .block-container {
        animation: fadeIn 0.3s ease-in-out;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    ::-webkit-scrollbar-track {
        background: transparent;
    }

    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }

    /* ===== CHECKBOX ===== */
    .stCheckbox label {
        color: #1e293b !important;
        font-weight: 400;
    }

    /* ===== DOWNLOAD BUTTON ===== */
    .stDownloadButton > button {
        background: transparent !important;
        color: #f97316 !important;
        border: 1px solid #f97316 !important;
    }

    .stDownloadButton > button:hover {
        background: rgba(249, 115, 22, 0.1) !important;
    }

    /* ===== DASHBOARD SECTIONS ===== */
    .dashboard-section {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
    }

    .section-title {
        font-size: 1rem;
        font-weight: 600;
        color: #1e293b;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .section-title:first-of-type {
        margin-top: 0;
    }

    .section-title-icon {
        width: 8px;
        height: 8px;
        background: #f97316;
        border-radius: 2px;
    }

    /* ===== ADMIN DASHBOARD HIERARCHY ===== */
    .admin-section {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
    }

    .admin-section.critical {
        border-left: 4px solid #dc2626;
        background: linear-gradient(to right, #fef2f2 0%, #ffffff 100%);
    }

    .admin-section.operational {
        border-left: 4px solid #3b82f6;
        background: linear-gradient(to right, #eff6ff 0%, #ffffff 100%);
    }

    .admin-section.revenue {
        border-left: 4px solid #10b981;
        background: linear-gradient(to right, #ecfdf5 0%, #ffffff 100%);
    }

    .admin-section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
    }

    .admin-section-icon {
        font-size: 1.25rem;
    }

    .admin-section-title {
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    .admin-section.critical .admin-section-title {
        color: #dc2626;
    }

    .admin-section.operational .admin-section-title {
        color: #3b82f6;
    }

    .admin-section.revenue .admin-section-title {
        color: #10b981;
    }

    .admin-section-subtitle {
        font-size: 0.75rem;
        color: #6b7280;
        margin-left: auto;
    }

    .priority-badge {
        font-size: 0.65rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .priority-badge.high {
        background: #fef2f2;
        color: #dc2626;
    }

    .priority-badge.medium {
        background: #eff6ff;
        color: #3b82f6;
    }

    .priority-badge.low {
        background: #ecfdf5;
        color: #10b981;
    }

    /* ===== KPI CARD BUTTONS ===== */
    .kpi-button-container .stButton > button {
        background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%) !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 1.25rem 1rem !important;
        min-height: 120px !important;
        color: #1e293b !important;
        font-size: 0.85rem !important;
        white-space: pre-line !important;
        text-align: center !important;
        line-height: 1.6 !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
        position: relative !important;
        overflow: hidden !important;
    }

    .kpi-button-container .stButton > button::before {
        content: '' !important;
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        height: 3px !important;
        background: linear-gradient(90deg, #f97316, #fb923c) !important;
        opacity: 0 !important;
        transition: opacity 0.25s ease !important;
    }

    .kpi-button-container .stButton > button:hover {
        border-color: #f97316 !important;
        box-shadow: 0 8px 24px rgba(249, 115, 22, 0.15) !important;
        transform: translateY(-4px) !important;
        background: linear-gradient(135deg, #fffbf7 0%, #fff7f0 100%) !important;
    }

    .kpi-button-container .stButton > button:hover::before {
        opacity: 1 !important;
    }

    .kpi-button-container .stButton > button:active {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(249, 115, 22, 0.12) !important;
    }

    .kpi-button-container .stButton > button:focus {
        outline: 2px solid #f97316 !important;
        outline-offset: 2px !important;
    }

    /* ===== ALERT CARDS ===== */
    .alert-card {
        background: #ffffff;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        border-left: 4px solid;
        margin-bottom: 0.5rem;
    }

    .alert-card.warning {
        border-left-color: #f59e0b;
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    }

    .alert-card.success {
        border-left-color: #22c55e;
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    }

    .alert-card.info {
        border-left-color: #3b82f6;
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    }

    /* ===== CLICKABLE ALERT BUTTONS ===== */
    .alert-button-container .stButton > button {
        background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%) !important;
        border: 1px solid #e2e8f0 !important;
        border-left: 4px solid #22c55e !important;
        border-radius: 10px !important;
        padding: 1rem 1.25rem !important;
        min-height: 80px !important;
        color: #1e293b !important;
        font-size: 0.85rem !important;
        white-space: pre-line !important;
        text-align: left !important;
        line-height: 1.5 !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03) !important;
        cursor: pointer !important;
    }

    .alert-button-container .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(0,0,0,0.08) !important;
    }

    .alert-button-container .stButton > button:focus {
        outline: 2px solid #f97316 !important;
        outline-offset: 2px !important;
    }

    .alert-button-container .stButton > button:active {
        transform: translateY(-1px) !important;
    }

    /* Alert button variants */
    .alert-warning .stButton > button {
        border-left-color: #f59e0b !important;
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%) !important;
    }

    .alert-warning .stButton > button:hover {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%) !important;
        box-shadow: 0 6px 16px rgba(245, 158, 11, 0.15) !important;
    }

    .alert-success .stButton > button {
        border-left-color: #22c55e !important;
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%) !important;
    }

    .alert-success .stButton > button:hover {
        background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%) !important;
        box-shadow: 0 6px 16px rgba(34, 197, 94, 0.15) !important;
    }

    .alert-info .stButton > button {
        border-left-color: #3b82f6 !important;
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%) !important;
    }

    .alert-info .stButton > button:hover {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
        box-shadow: 0 6px 16px rgba(59, 130, 246, 0.15) !important;
    }

    /* ===== QUICK ACTION SECTION ===== */
    .quick-action-wrapper {
        background: linear-gradient(135deg, var(--color-sidebar-bg) 0%, #334155 100%);
        border-radius: var(--radius-xl) var(--radius-xl) 0 0;
        padding: var(--space-3) var(--space-5);
        margin-top: var(--space-2);
        margin-bottom: -1px;
    }

    .quick-action-title {
        color: var(--color-text-muted);
        font-size: var(--font-size-xs);
        font-weight: var(--font-weight-semibold);
        letter-spacing: var(--letter-spacing-wide);
        text-transform: uppercase;
        margin: 0;
    }

    .qa-buttons-row {
        background: linear-gradient(135deg, var(--color-sidebar-bg) 0%, #334155 100%);
        border-radius: 0 0 var(--radius-xl) var(--radius-xl);
        padding: 0 var(--space-4) var(--space-4) var(--space-4);
        margin-top: calc(-1 * var(--space-4));
    }

    .qa-buttons-row .stButton > button {
        background: rgba(255, 255, 255, 0.1) !important;
        color: var(--color-text-inverse) !important;
        border: var(--border-width) solid rgba(255, 255, 255, 0.2) !important;
        border-radius: var(--radius-lg) !important;
        padding: var(--space-3) var(--space-3) !important;
        font-size: var(--font-size-base) !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        min-height: 50px !important;
    }

    .qa-buttons-row .stButton > button:hover {
        background: #f97316 !important;
        border-color: #f97316 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(249, 115, 22, 0.4) !important;
    }

    .qa-buttons-row .stButton > button:focus {
        outline: 2px solid #fb923c !important;
        outline-offset: 2px !important;
    }

    .qa-buttons-row .stButton > button:disabled {
        background: rgba(100, 116, 139, 0.2) !important;
        color: rgba(255, 255, 255, 0.4) !important;
        border-color: rgba(255, 255, 255, 0.1) !important;
        cursor: not-allowed !important;
        transform: none !important;
    }

    .qa-buttons-row .stButton > button:disabled:hover {
        background: rgba(100, 116, 139, 0.2) !important;
        transform: none !important;
        box-shadow: none !important;
    }

    .qa-buttons-row p, .qa-buttons-row .stCaption p {
        color: rgba(255, 255, 255, 0.5) !important;
        font-size: 0.7rem !important;
        margin-top: 0.25rem !important;
    }

    /* ===== BILLING INSIGHTS SECTION ===== */
    .billing-container {
        background: linear-gradient(135deg, #fefefe 0%, #f8fafc 100%);
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid #e2e8f0;
        display: flex;
        gap: 1.5rem;
        align-items: stretch;
    }

    .billing-card {
        flex: 1;
        background: #ffffff;
        border-radius: 10px;
        padding: 1.25rem;
        border: 1px solid #e2e8f0;
        position: relative;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
    }

    .billing-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }

    .billing-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(180deg, #22c55e, #16a34a);
        border-radius: 4px 0 0 4px;
    }

    .billing-card.revenue::before {
        background: linear-gradient(180deg, #f97316, #ea580c);
    }

    .billing-card-icon {
        width: 40px;
        height: 40px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
        margin-bottom: 0.75rem;
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    }

    .billing-card.revenue .billing-card-icon {
        background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
    }

    .billing-card-label {
        color: #64748b;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }

    .billing-card-value {
        color: #1e293b;
        font-size: 1.75rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
        line-height: 1.2;
    }

    .billing-card-subtitle {
        color: #94a3b8;
        font-size: 0.75rem;
        margin-bottom: 0.75rem;
    }

    .billing-card-footer {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding-top: 0.75rem;
        border-top: 1px solid #f1f5f9;
        color: #64748b;
        font-size: 0.7rem;
    }

    .billing-card-footer .dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #22c55e;
    }

    .billing-card.revenue .billing-card-footer .dot {
        background: #f97316;
    }

    .billing-info-card {
        flex: 1.2;
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 10px;
        padding: 1.25rem;
        color: #ffffff;
    }

    .billing-info-title {
        color: #94a3b8;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }

    .billing-info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }

    .billing-info-row:last-child {
        border-bottom: none;
        padding-top: 0.75rem;
        margin-top: 0.25rem;
    }

    .billing-info-label {
        color: #94a3b8;
        font-size: 0.8rem;
    }

    .billing-info-value {
        color: #ffffff;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .billing-info-row.total .billing-info-label {
        color: #f97316;
        font-weight: 600;
    }

    .billing-info-row.total .billing-info-value {
        color: #f97316;
        font-size: 1.1rem;
    }

    /* ===== ATTENTION TABLE STYLES ===== */
    .priority-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
    }

    .priority-high {
        background: #fef2f2;
        color: #dc2626;
        border: 1px solid #fecaca;
    }

    .priority-medium {
        background: #fffbeb;
        color: #d97706;
        border: 1px solid #fde68a;
    }

    .priority-low {
        background: #f0fdf4;
        color: #16a34a;
        border: 1px solid #bbf7d0;
    }

    .attention-row {
        background: #ffffff;
        border-radius: 8px;
        padding: 0.875rem 1rem;
        margin-bottom: 0.5rem;
        border: 1px solid #e2e8f0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: all 0.2s ease;
    }

    .attention-row:hover {
        border-color: #cbd5e1;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    .attention-row.urgent {
        border-left: 4px solid #dc2626;
    }

    .attention-row.warning {
        border-left: 4px solid #f59e0b;
    }

    .attention-row.normal {
        border-left: 4px solid #22c55e;
    }

    .attention-info {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .attention-title {
        font-weight: 600;
        color: #1e293b;
        font-size: 0.9rem;
    }

    .attention-subtitle {
        color: #64748b;
        font-size: 0.8rem;
    }

    .attention-meta {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .attention-days {
        font-size: 0.8rem;
        color: #64748b;
    }

    .attention-days.urgent {
        color: #dc2626;
        font-weight: 600;
    }

    .attention-actions {
        display: flex;
        gap: 0.5rem;
    }

    /* Attention row action buttons */
    div[data-testid="column"]:has(button[key^="fix_"]) .stButton > button,
    div[data-testid="column"]:has(button[key^="vendor_"]) .stButton > button {
        font-size: 0.75rem !important;
        padding: 0.4rem 0.5rem !important;
        min-height: auto !important;
    }

    /* ===== CONFIRMATION MODAL STYLES ===== */
    .confirm-modal {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        margin: 1rem 0;
    }

    .confirm-modal-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #f1f5f9;
    }

    .confirm-modal-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
    }

    .confirm-modal-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1e293b;
    }

    .confirm-modal-subtitle {
        font-size: 0.85rem;
        color: #64748b;
    }

    .confirm-state-change {
        background: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1rem;
    }

    .confirm-state {
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .confirm-state.current {
        background: #fee2e2;
        color: #dc2626;
    }

    .confirm-state.next {
        background: #dcfce7;
        color: #16a34a;
    }

    .confirm-arrow {
        color: #94a3b8;
        font-size: 1.25rem;
    }

    .confirm-details {
        background: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }

    .confirm-detail-row {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid #e2e8f0;
    }

    .confirm-detail-row:last-child {
        border-bottom: none;
    }

    .confirm-detail-label {
        color: #64748b;
        font-size: 0.85rem;
    }

    .confirm-detail-value {
        color: #1e293b;
        font-size: 0.85rem;
        font-weight: 500;
    }

    .confirm-timestamp {
        text-align: center;
        color: #94a3b8;
        font-size: 0.75rem;
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #f1f5f9;
    }

    /* ===== CHART FILTER BUTTONS ===== */
    div[data-testid="column"]:has(button[key^="status_btn_"]) .stButton > button,
    div[data-testid="column"]:has(button[key^="brand_btn_"]) .stButton > button {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
        color: #374151 !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 0.5rem 0.75rem !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        min-height: 40px !important;
        transition: all 0.2s ease !important;
    }

    div[data-testid="column"]:has(button[key^="status_btn_"]) .stButton > button:hover,
    div[data-testid="column"]:has(button[key^="brand_btn_"]) .stButton > button:hover {
        background: linear-gradient(135deg, #f97316 0%, #fb923c 100%) !important;
        color: #ffffff !important;
        border-color: #f97316 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(249, 115, 22, 0.25) !important;
    }

    /* ===== ROLE BADGE ===== */
    .role-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.4rem 0.85rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    .role-operations {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
        color: #1e40af;
        border: 1px solid #93c5fd;
    }

    .role-finance {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        color: #065f46;
        border: 1px solid #6ee7b7;
    }

    .role-admin {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        color: #92400e;
        border: 1px solid #fcd34d;
    }

    /* ===== SLA INDICATORS ===== */
    .sla-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
    }

    .sla-ok {
        background: #dcfce7;
        color: #166534;
    }

    .sla-warning {
        background: #fef3c7;
        color: #92400e;
    }

    .sla-critical {
        background: #fee2e2;
        color: #dc2626;
        animation: pulse-critical 2s infinite;
    }

    @keyframes pulse-critical {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    /* ===== ANALYTICS INSIGHT CARDS ===== */
    .insight-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid #e2e8f0;
        margin-bottom: 0.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
        position: relative;
    }

    .insight-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }

    .insight-card.warning {
        border-left: 4px solid #f59e0b;
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    }

    .insight-card.critical {
        border-left: 4px solid #dc2626;
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    }

    .insight-card.success {
        border-left: 4px solid #22c55e;
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    }

    .insight-card.info {
        border-left: 4px solid #3b82f6;
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    }

    .insight-icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
        display: block;
    }

    .insight-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.5rem;
    }

    .insight-title {
        font-size: 0.7rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }

    .insight-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.2;
    }

    .insight-subtitle {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 0.35rem;
    }

    /* Loading Spinner */
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem;
        min-height: 200px;
    }

    .loading-spinner {
        width: 40px;
        height: 40px;
        border: 3px solid #e2e8f0;
        border-top-color: #f97316;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }

    .loading-text {
        margin-top: 1rem;
        color: #64748b;
        font-size: 0.9rem;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* Skeleton Loading */
    .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
    }

    .skeleton-card {
        height: 120px;
        margin-bottom: 1rem;
    }

    .skeleton-chart {
        height: 300px;
    }

    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    /* Last Updated Badge */
    .last-updated {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 0.75rem;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        font-size: 0.75rem;
        color: #64748b;
    }

    .last-updated .dot {
        width: 6px;
        height: 6px;
        background: #22c55e;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* Empty State */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        background: #f8fafc;
        border-radius: 12px;
        border: 2px dashed #e2e8f0;
    }

    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }

    .empty-state-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #374151;
        margin-bottom: 0.5rem;
    }

    .empty-state-text {
        font-size: 0.9rem;
        color: #64748b;
        margin-bottom: 1rem;
    }

    /* ===== ANALYTICS SECTION ===== */
    .analytics-section {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.5rem;
        border: none;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.03);
        margin-bottom: 1.5rem;
    }

    .analytics-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.25rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #f1f5f9;
    }

    .analytics-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1e293b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .analytics-subtitle {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 0.25rem;
    }

    /* ===== CHART CONTAINER ===== */
    .chart-container {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.25rem;
        border: none;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .chart-title {
        font-size: 0.75rem;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 0.5rem;
        padding: 0.5rem 0;
        border-bottom: none;
    }

    /* ===== CHARTS WRAPPER ===== */
    .charts-row {
        display: flex;
        gap: 1.5rem;
        margin-top: 1rem;
    }

    .chart-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid #f1f5f9;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ===== ANALYTICS BAR CHART STYLES ===== */
    /* Smooth transitions for bar hover effects */
    .js-plotly-plot .plotly .bars .point path {
        transition: opacity 200ms ease-in-out, fill 200ms ease-in-out;
    }

    /* Muted non-hovered bars when any bar is hovered */
    .js-plotly-plot .plotly:hover .bars .point path {
        opacity: 0.5;
    }

    /* Highlight hovered bar */
    .js-plotly-plot .plotly .bars .point:hover path {
        opacity: 1 !important;
        filter: brightness(0.85);
    }

    /* Cursor pointer on bars */
    .js-plotly-plot .plotly .bars .point {
        cursor: pointer;
    }

    /* Tooltip styling enhancement */
    .js-plotly-plot .hoverlayer .hovertext {
        transition: opacity 150ms ease-in-out;
    }

    /* ===== INVENTORY OVERVIEW KPI CARDS (Reference Style) ===== */
    .kpi-row {
        display: flex;
        gap: 16px;
        margin-bottom: 0;
    }

    .kpi-card {
        background: #ffffff;
        border-radius: 10px;
        padding: 24px 20px;
        border: none;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
        transition: transform 180ms ease-out, box-shadow 180ms ease-out;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        cursor: pointer;
        outline: none;
        -webkit-tap-highlight-color: transparent;
        user-select: none;
        min-height: 130px;
    }

    /* Title - Uppercase, muted, at top */
    .kpi-card-title {
        font-size: 11px;
        font-weight: 600;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 12px;
    }

    /* Value - Large, bold, colored, center focus */
    .kpi-card-value {
        font-size: 42px;
        font-weight: 700;
        line-height: 1;
        margin-bottom: 8px;
        letter-spacing: -1.5px;
    }

    /* Color variants - only applied to value */
    .kpi-card.neutral .kpi-card-value { color: #374151; }
    .kpi-card.blue .kpi-card-value { color: #2563eb; }
    .kpi-card.green .kpi-card-value { color: #16a34a; }
    .kpi-card.amber .kpi-card-value { color: #d97706; }
    .kpi-card.red .kpi-card-value { color: #dc2626; }

    /* Label - Small, muted, below value */
    .kpi-card-label {
        font-size: 13px;
        font-weight: 500;
        color: #6b7280;
        margin: 0;
    }

    /* ===== HOVER STATE (Subtle elevation) ===== */
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08), 0 2px 4px rgba(0, 0, 0, 0.04);
    }

    /* ===== ACTIVE STATE (Pressed) ===== */
    .kpi-card:active {
        transform: translateY(0);
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
        transition-duration: 80ms;
    }

    /* ===== KEYBOARD FOCUS (Minimal) ===== */
    .kpi-card:focus-visible,
    .kpi-card.kpi-focused {
        outline: 2px solid #3b82f6;
        outline-offset: 2px;
    }

    /* ===== TOUCH DEVICES ===== */
    @media (hover: none) {
        .kpi-card {
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        .kpi-card:active {
            background: #fafafa;
        }
    }

    /* ===== RESPONSIVE ===== */
    @media (max-width: 768px) {
        .kpi-card {
            padding: 20px 16px;
            min-height: 110px;
        }
        .kpi-card-value {
            font-size: 32px;
        }
    }

    /* KPI Cards Row Layout - Flexbox for clean single row */
    .kpi-cards-row {
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
    }
    .kpi-cards-row .kpi-card {
        flex: 1;
        min-width: 0;
    }

</style>
""", unsafe_allow_html=True)

# JavaScript to hide Plotly modebar and setup KPI card clicks
components.html("""
<script>
(function() {
    const parentDoc = window.parent.document;

    function hideModebar() {
        const modebars = parentDoc.querySelectorAll('.modebar-container, .modebar, .modebar-group, [class*="modebar"]');
        modebars.forEach(el => el.style.display = 'none');
    }

    function hideKpiButtons() {
        // Hide all buttons that contain "kpi_" in their text
        const allButtons = parentDoc.querySelectorAll('button');
        allButtons.forEach(btn => {
            const text = btn.textContent.trim();
            if (text.includes('kpi_') && text.includes('_btn')) {
                // Hide the button's parent container completely
                let container = btn.closest('[data-testid="stBaseButton-secondary"]') ||
                               btn.closest('.stButton') ||
                               btn.parentElement;
                if (container) {
                    container.style.cssText = 'display:none!important;height:0!important;overflow:hidden!important;';
                }
                // Also hide the column containing it
                let column = btn.closest('[data-testid="column"]');
                if (column) {
                    column.style.cssText = 'display:none!important;height:0!important;overflow:hidden!important;';
                }
            }
        });

        // Hide the entire row containing kpi buttons
        const horizontalBlocks = parentDoc.querySelectorAll('[data-testid="stHorizontalBlock"]');
        horizontalBlocks.forEach(block => {
            const buttons = block.querySelectorAll('button');
            let hasKpiBtn = false;
            buttons.forEach(btn => {
                if (btn.textContent.includes('kpi_') && btn.textContent.includes('_btn')) {
                    hasKpiBtn = true;
                }
            });
            if (hasKpiBtn) {
                block.style.cssText = 'display:none!important;height:0!important;overflow:hidden!important;';
            }
        });
    }

    function setupKpiCards() {
        const kpiCards = parentDoc.querySelectorAll('.kpi-cards-row .kpi-card[data-kpi]');
        const btnTextMap = {
            'total': 'kpi_total_btn',
            'deployed': 'kpi_deployed_btn',
            'available': 'kpi_available_btn',
            'repair': 'kpi_repair_btn',
            'returned': 'kpi_returned_btn'
        };

        kpiCards.forEach(card => {
            if (card.dataset.ready === 'true') return;

            const kpiType = card.dataset.kpi;
            const btnText = btnTextMap[kpiType];
            if (!btnText) return;

            // Find the button by its text content
            const allButtons = parentDoc.querySelectorAll('button');
            let targetBtn = null;
            allButtons.forEach(btn => {
                if (btn.textContent.trim() === btnText) {
                    targetBtn = btn;
                }
            });

            if (!targetBtn) return;

            card.dataset.ready = 'true';
            card.style.cursor = 'pointer';
            card.setAttribute('tabindex', '0');
            card.setAttribute('role', 'button');

            card.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                targetBtn.click();
            };
            card.onkeydown = (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    targetBtn.click();
                }
            };
        });
    }

    // Run immediately
    hideModebar();
    hideKpiButtons();
    setupKpiCards();

    // Keep running
    setInterval(hideModebar, 500);
    setInterval(hideKpiButtons, 100);
    setInterval(setupKpiCards, 300);
})();
</script>
""", height=0)

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

# Table names
TABLES = {
    "assets": "Assets",
    "clients": "Clients",
    "assignments": "Assignments",
    "issues": "Issues",
    "repairs": "Repairs",
    "vendors": "Vendors",
    "invoices": "Invoices"
}

# Status options
ASSET_STATUSES = [
    "IN_STOCK_WORKING",
    "WITH_CLIENT",
    "RETURNED_FROM_CLIENT",
    "IN_OFFICE_TESTING",
    "WITH_VENDOR_REPAIR",
    "SOLD",
    "DISPOSED"
]

# High-contrast colors for pie charts and status indicators
STATUS_COLORS = {
    "IN_STOCK_WORKING": "#4CAF50",      # Green - Available
    "WITH_CLIENT": "#FF6B35",           # Orange - Primary action
    "RETURNED_FROM_CLIENT": "#2196F3",  # Blue - Needs attention
    "IN_OFFICE_TESTING": "#9C27B0",     # Purple - Testing
    "WITH_VENDOR_REPAIR": "#FF9800",    # Amber - Under repair
    "SOLD": "#607D8B",                  # Blue Grey - Completed
    "DISPOSED": "#F44336"               # Red - Disposed
}

# ============================================================================
# LIFECYCLE STATE TRANSITION VALIDATION
# ============================================================================
# Define allowed state transitions - prevents skipping lifecycle steps
ALLOWED_TRANSITIONS = {
    "IN_STOCK_WORKING": ["WITH_CLIENT"],                          # Can only be assigned to client
    "WITH_CLIENT": ["RETURNED_FROM_CLIENT", "SOLD"],              # Can be returned or sold
    "RETURNED_FROM_CLIENT": ["IN_STOCK_WORKING", "WITH_VENDOR_REPAIR", "IN_OFFICE_TESTING"],  # Restock, repair, or test
    "IN_OFFICE_TESTING": ["IN_STOCK_WORKING", "WITH_VENDOR_REPAIR"],  # Pass testing or send to repair
    "WITH_VENDOR_REPAIR": ["IN_STOCK_WORKING", "DISPOSED"],       # Fixed or disposed
    "SOLD": [],                                                    # Terminal state
    "DISPOSED": []                                                 # Terminal state
}

# Human-readable status names for error messages
STATUS_DISPLAY_NAMES = {
    "IN_STOCK_WORKING": "In Stock (Working)",
    "WITH_CLIENT": "With Client",
    "RETURNED_FROM_CLIENT": "Returned from Client",
    "IN_OFFICE_TESTING": "In Office Testing",
    "WITH_VENDOR_REPAIR": "With Vendor (Repair)",
    "SOLD": "Sold",
    "DISPOSED": "Disposed"
}

def validate_state_transition(current_status, new_status):
    """
    Validate if a state transition is allowed.
    Returns (is_valid, error_message)
    """
    # Same status - no change needed
    if current_status == new_status:
        return True, None

    # Check if current status exists in allowed transitions
    if current_status not in ALLOWED_TRANSITIONS:
        return False, f"Unknown current status: {current_status}"

    # Check if new status is in the allowed list
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status in allowed:
        return True, None

    # Build helpful error message
    current_display = STATUS_DISPLAY_NAMES.get(current_status, current_status)
    new_display = STATUS_DISPLAY_NAMES.get(new_status, new_status)

    if not allowed:
        return False, f"Cannot change status from '{current_display}' - this is a terminal state"

    allowed_display = [STATUS_DISPLAY_NAMES.get(s, s) for s in allowed]
    return False, f"Invalid transition: '{current_display}' → '{new_display}'. Allowed transitions: {', '.join(allowed_display)}"

def log_state_change(serial_number, old_status, new_status, user_role, success, error_message=None, asset_id=None):
    """Log every state change attempt with timestamp"""
    from datetime import datetime

    if 'state_change_log' not in st.session_state:
        st.session_state.state_change_log = []

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "serial_number": serial_number,
        "old_status": old_status,
        "new_status": new_status,
        "user_role": user_role,
        "success": success,
        "error_message": error_message
    }

    st.session_state.state_change_log.append(log_entry)

    # Keep only last 100 entries to prevent memory issues
    if len(st.session_state.state_change_log) > 100:
        st.session_state.state_change_log = st.session_state.state_change_log[-100:]

    # Also log to persistent activity_log table (MySQL only)
    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
        old_display = STATUS_DISPLAY_NAMES.get(old_status, old_status)
        new_display = STATUS_DISPLAY_NAMES.get(new_status, new_status)
        description = f"Status changed: {old_display} -> {new_display}"
        if not success:
            description = f"BLOCKED: {old_display} -> {new_display}"

        db_log_activity(
            action_type="STATE_CHANGE",
            action_category="asset",
            user_role=user_role,
            asset_id=asset_id,
            serial_number=serial_number,
            old_value=old_status,
            new_value=new_status,
            description=description,
            success=success,
            error_message=error_message
        )

    return log_entry


# ============================================
# AUDIT TRAIL CONFIGURATION
# ============================================
# Critical actions that require enhanced audit logging
CRITICAL_ACTIONS = {
    "ASSET_ASSIGNED": {"severity": "high", "billing_impact": True},
    "ASSET_RETURNED": {"severity": "high", "billing_impact": True},
    "REPAIR_CREATED": {"severity": "medium", "billing_impact": True},
    "REPAIR_COMPLETED": {"severity": "medium", "billing_impact": True},
    "BILLING_OVERRIDE": {"severity": "critical", "billing_impact": True},
    "ASSET_CREATED": {"severity": "medium", "billing_impact": False},
    "ASSET_DELETED": {"severity": "critical", "billing_impact": False},
    "STATUS_CHANGE": {"severity": "medium", "billing_impact": True},
    "ACCESS_DENIED": {"severity": "critical", "billing_impact": False},
    "ASSIGNMENT_CREATED": {"severity": "high", "billing_impact": True},
}


def generate_audit_id() -> str:
    """Generate a unique, immutable audit ID for each log entry."""
    import hashlib
    from datetime import datetime
    timestamp = datetime.now().isoformat()
    random_part = os.urandom(8).hex()
    raw = f"{timestamp}-{random_part}"
    return f"AUD-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def get_session_id() -> str:
    """Get or create a session ID for tracking."""
    if 'audit_session_id' not in st.session_state:
        st.session_state.audit_session_id = f"SES-{os.urandom(6).hex().upper()}"
    return st.session_state.audit_session_id


def log_activity_event(
    action_type: str,
    category: str,
    user_role: str,
    description: str,
    asset_id: int = None,
    serial_number: str = None,
    client_id: int = None,
    client_name: str = None,
    old_value: str = None,
    new_value: str = None,
    success: bool = True,
    error_message: str = None,
    metadata: dict = None
):
    """
    Log any activity to the audit trail with enhanced metadata.
    This function logs to both session state (for immediate UI) and MySQL (for persistence).

    Audit entries are append-only and immutable - each entry receives a unique audit ID
    that can be used for compliance and forensic purposes.
    """
    from datetime import datetime

    # Initialize session activity log
    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []

    # Generate immutable audit identifiers
    audit_id = generate_audit_id()
    session_id = get_session_id()
    timestamp = datetime.now()

    # Determine if this is a critical action
    action_config = CRITICAL_ACTIONS.get(action_type, {"severity": "low", "billing_impact": False})
    is_critical = action_config["severity"] in ["high", "critical"]
    has_billing_impact = action_config["billing_impact"]

    # Build enhanced audit metadata
    audit_metadata = {
        "audit_id": audit_id,
        "session_id": session_id,
        "severity": action_config["severity"],
        "is_critical": is_critical,
        "billing_impact": has_billing_impact,
        "performed_by": user_role,
        "affected_asset": serial_number,
        "affected_client": client_name,
        **(metadata or {})
    }

    # Create immutable log entry
    log_entry = {
        # Core audit fields
        "audit_id": audit_id,
        "timestamp": timestamp.isoformat(),
        "timestamp_utc": datetime.utcnow().isoformat(),

        # Action details
        "action_type": action_type,
        "category": category,
        "description": description,

        # Actor information
        "performed_by": user_role,
        "session_id": session_id,

        # Affected entities
        "asset_id": asset_id,
        "serial_number": serial_number,
        "client_id": client_id,
        "client_name": client_name,

        # State change tracking
        "old_value": old_value,
        "new_value": new_value,

        # Audit classification
        "severity": action_config["severity"],
        "is_critical": is_critical,
        "billing_impact": has_billing_impact,

        # Outcome
        "success": success,
        "error_message": error_message,

        # Extended metadata
        "metadata": audit_metadata,

        # Immutability marker
        "_immutable": True,
        "_created_at": timestamp.isoformat()
    }

    # Append to session log (append-only)
    st.session_state.activity_log.append(log_entry)

    # Keep session log manageable but preserve critical entries
    if len(st.session_state.activity_log) > 500:
        # Keep all critical entries plus recent entries
        critical_entries = [e for e in st.session_state.activity_log if e.get('is_critical', False)]
        recent_entries = st.session_state.activity_log[-300:]
        # Merge and deduplicate by audit_id
        seen = set()
        merged = []
        for entry in critical_entries + recent_entries:
            aid = entry.get('audit_id')
            if aid not in seen:
                seen.add(aid)
                merged.append(entry)
        st.session_state.activity_log = merged

    # Log to MySQL if available
    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
        db_log_activity(
            action_type=action_type,
            action_category=category,
            user_role=user_role,
            asset_id=asset_id,
            serial_number=serial_number,
            client_id=client_id,
            client_name=client_name,
            old_value=old_value,
            new_value=new_value,
            description=description,
            success=success,
            error_message=error_message,
            metadata=audit_metadata
        )

    return log_entry


def get_audit_summary() -> dict:
    """Get summary statistics for audit log."""
    if 'activity_log' not in st.session_state:
        return {"total": 0, "critical": 0, "failed": 0, "billing_impact": 0}

    log = st.session_state.activity_log
    return {
        "total": len(log),
        "critical": len([e for e in log if e.get('is_critical', False)]),
        "failed": len([e for e in log if not e.get('success', True)]),
        "billing_impact": len([e for e in log if e.get('billing_impact', False)]),
        "by_action": {},
        "by_severity": {}
    }


# ============================================
# PAGINATION HELPERS
# ============================================
def get_pagination_state(key: str) -> dict:
    """Get or initialize pagination state for a specific table."""
    state_key = f"pagination_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "page": 0,
            "page_size": PAGINATION_CONFIG["default_page_size"],
            "total_records": 0,
            "total_pages": 0
        }
    return st.session_state[state_key]


def paginate_dataframe(df: pd.DataFrame, key: str, show_controls: bool = True) -> pd.DataFrame:
    """
    Apply pagination to a DataFrame without changing UI layout.

    Args:
        df: DataFrame to paginate
        key: Unique key for this table's pagination state
        show_controls: Whether to show pagination controls

    Returns:
        Paginated DataFrame slice
    """
    if df.empty:
        return df

    total_records = len(df)
    state = get_pagination_state(key)

    # Update total records
    state["total_records"] = total_records
    page_size = state["page_size"]
    state["total_pages"] = max(1, (total_records + page_size - 1) // page_size)

    # Ensure current page is valid
    if state["page"] >= state["total_pages"]:
        state["page"] = max(0, state["total_pages"] - 1)

    # Show pagination controls if enabled
    if show_controls and total_records > page_size:
        render_pagination_controls(key, state, total_records)

    # Calculate slice indices
    start_idx = state["page"] * page_size
    end_idx = min(start_idx + page_size, total_records)

    return df.iloc[start_idx:end_idx]


def render_pagination_controls(key: str, state: dict, total_records: int):
    """Render pagination controls matching existing UI style."""
    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])

    with col1:
        # Page size selector
        new_size = st.selectbox(
            "Rows",
            options=PAGINATION_CONFIG["page_size_options"],
            index=PAGINATION_CONFIG["page_size_options"].index(state["page_size"]) if state["page_size"] in PAGINATION_CONFIG["page_size_options"] else 1,
            key=f"page_size_{key}",
            label_visibility="collapsed"
        )
        if new_size != state["page_size"]:
            state["page_size"] = new_size
            state["page"] = 0  # Reset to first page
            state["total_pages"] = max(1, (total_records + new_size - 1) // new_size)

    with col2:
        # Page info
        start = state["page"] * state["page_size"] + 1
        end = min((state["page"] + 1) * state["page_size"], total_records)
        st.markdown(f"<div style='text-align: center; padding: 8px; color: #64748b; font-size: 0.85rem;'>Showing {start}-{end} of {total_records}</div>", unsafe_allow_html=True)

    with col3:
        # Page navigation
        nav_cols = st.columns(4)
        with nav_cols[0]:
            if st.button("«", key=f"first_{key}", disabled=state["page"] == 0):
                state["page"] = 0
        with nav_cols[1]:
            if st.button("‹", key=f"prev_{key}", disabled=state["page"] == 0):
                state["page"] = max(0, state["page"] - 1)
        with nav_cols[2]:
            if st.button("›", key=f"next_{key}", disabled=state["page"] >= state["total_pages"] - 1):
                state["page"] = min(state["total_pages"] - 1, state["page"] + 1)
        with nav_cols[3]:
            if st.button("»", key=f"last_{key}", disabled=state["page"] >= state["total_pages"] - 1):
                state["page"] = state["total_pages"] - 1

    with col4:
        # Page indicator
        st.markdown(f"<div style='text-align: right; padding: 8px; color: #64748b; font-size: 0.85rem;'>Page {state['page'] + 1}/{state['total_pages']}</div>", unsafe_allow_html=True)


def reset_pagination(key: str = None):
    """Reset pagination state. If key is None, reset all pagination."""
    if key:
        state_key = f"pagination_{key}"
        if state_key in st.session_state:
            st.session_state[state_key]["page"] = 0
    else:
        for k in list(st.session_state.keys()):
            if k.startswith("pagination_"):
                st.session_state[k]["page"] = 0


# ============================================
# ENHANCED CACHING HELPERS
# ============================================
def get_cache_key(data_type: str, filters: dict = None) -> str:
    """Generate a cache key based on data type and filters."""
    import hashlib
    key_parts = [data_type]
    if filters:
        for k, v in sorted(filters.items()):
            key_parts.append(f"{k}:{v}")
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()[:12]


def invalidate_cache_for(data_types: list = None):
    """
    Invalidate cache for specific data types.
    Called after write operations to ensure fresh data.
    """
    # Clear the main fetch_all_data cache
    fetch_all_data.clear()

    # Mark session data as stale
    if 'data_stale' in st.session_state:
        st.session_state.data_stale = True

    # Clear any specific cached DataFrames
    if data_types:
        for dtype in data_types:
            cache_key = f"cached_{dtype}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]

    # Reset pagination for affected tables
    if data_types:
        for dtype in data_types:
            reset_pagination(dtype)


def get_cached_dataframe(data_type: str, fetch_func, ttl_key: str = "ttl_assets") -> pd.DataFrame:
    """
    Get DataFrame with caching support.
    Uses session state for fast access with TTL-based invalidation.
    """
    cache_key = f"cached_{data_type}"
    timestamp_key = f"cached_{data_type}_time"
    ttl = CACHE_CONFIG.get(ttl_key, 600)

    # Check if cache is valid
    if cache_key in st.session_state and timestamp_key in st.session_state:
        cache_time = st.session_state[timestamp_key]
        if (datetime.now() - cache_time).total_seconds() < ttl:
            return st.session_state[cache_key]

    # Fetch fresh data
    df = fetch_func()

    # Apply query limit
    limit = QUERY_LIMITS.get(data_type, PAGINATION_CONFIG["max_records"])
    if len(df) > limit:
        df = df.head(limit)

    # Store in cache
    st.session_state[cache_key] = df
    st.session_state[timestamp_key] = datetime.now()

    return df


def get_asset_current_status(record_id):
    """Get the current status of an asset by record ID"""
    table = get_table("assets")
    if table:
        try:
            record = table.get(record_id)
            if record and 'fields' in record:
                return record['fields'].get('Current Status'), record['fields'].get('Serial Number', 'Unknown')
        except Exception:
            pass
    return None, None

# Valid initial statuses when creating a new asset
# Restricts users from creating assets directly in terminal or mid-lifecycle states
VALID_INITIAL_STATUSES = [
    "IN_STOCK_WORKING",   # Default - new asset in inventory
    "WITH_CLIENT"         # Edge case - adding an already deployed asset
]

# ============================================================================
# ACTION CONFIRMATION SYSTEM
# ============================================================================
def get_billing_impact(current_status, new_status, asset_info=None):
    """
    Calculate billing impact of a state transition.
    Uses centralized BILLING_CONFIG for consistency.
    """
    impacts = []

    # Get billing status for both states
    current_billing = get_asset_billing_status(current_status)
    new_billing = get_asset_billing_status(new_status)

    # Transition TO billable state (starts billing)
    if new_status in BILLING_CONFIG["billable_states"] and current_status not in BILLING_CONFIG["billable_states"]:
        impacts.append({
            "type": "positive",
            "icon": BILLING_CONFIG["status_icons"]["active"],
            "message": "Billing will START for this asset",
            "detail": f"Asset enters billable state. Rate: ₹{BILLING_CONFIG['default_monthly_rate']:,}/month"
        })

    # Transition FROM billable TO paused (billing paused)
    elif current_status in BILLING_CONFIG["billable_states"] and new_status in BILLING_CONFIG["paused_states"]:
        impacts.append({
            "type": "warning",
            "icon": BILLING_CONFIG["status_icons"]["paused"],
            "message": "Billing will PAUSE for this asset",
            "detail": "Final billing calculated on transition date. Resumes when redeployed."
        })

    # Transition TO repair from non-billable (no billing impact)
    elif new_status == "WITH_VENDOR_REPAIR" and current_status not in BILLING_CONFIG["billable_states"]:
        impacts.append({
            "type": "info",
            "icon": "🔧",
            "message": "Asset sent for repair",
            "detail": "No billing impact - asset was not in billable state"
        })

    # Transition FROM paused TO ready for deployment
    elif current_status in BILLING_CONFIG["paused_states"] and new_status == "IN_STOCK_WORKING":
        impacts.append({
            "type": "positive",
            "icon": "✅",
            "message": "Asset available for deployment",
            "detail": "Can be assigned to clients. Billing starts when deployed."
        })

    # Disposed - permanent removal
    elif new_status == "DISPOSED":
        impacts.append({
            "type": "critical",
            "icon": "🗑️",
            "message": "Asset will be PERMANENTLY removed from inventory",
            "detail": "This action cannot be undone"
        })

    return impacts

def init_action_confirmation():
    """Initialize confirmation state in session"""
    if 'pending_action' not in st.session_state:
        st.session_state.pending_action = None

def request_action_confirmation(action_type, asset_serial, record_id, current_status, new_status,
                                 extra_data=None, asset_info=None):
    """Request confirmation for an action"""
    st.session_state.pending_action = {
        "action_type": action_type,
        "asset_serial": asset_serial,
        "record_id": record_id,
        "current_status": current_status,
        "new_status": new_status,
        "extra_data": extra_data or {},
        "asset_info": asset_info or {},
        "requested_at": datetime.now().isoformat()
    }

def clear_action_confirmation():
    """Clear pending action confirmation"""
    st.session_state.pending_action = None

def render_confirmation_dialog(role):
    """
    Render confirmation dialog based on role.
    Admin: Full confirmation with all details
    Operations: Lightweight confirmation
    Returns: (confirmed: bool, cancelled: bool)
    """
    if 'pending_action' not in st.session_state or st.session_state.pending_action is None:
        return False, False

    action = st.session_state.pending_action
    is_admin = role == "admin"

    # Get display names
    current_display = STATUS_DISPLAY_NAMES.get(action["current_status"], action["current_status"])
    new_display = STATUS_DISPLAY_NAMES.get(action["new_status"], action["new_status"])

    # Action type labels (consistent wording)
    action_labels = {
        "assign": ("Assign to Client", "📤"),
        "return": ("Receive Return", "📥"),
        "repair": ("Send to Vendor", "🔧"),
        "fix": ("Complete Repair", "✅"),
        "dispose": ("Dispose Asset", "🗑️")
    }

    label, icon = action_labels.get(action["action_type"], ("Action", "⚡"))

    # Confirmation container
    st.markdown("---")

    if is_admin:
        # Full confirmation for Admin
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
                    border: 2px solid #f59e0b; border-radius: 12px; padding: 20px; margin: 10px 0;">
            <div style="color: #f59e0b; font-size: 1.2em; font-weight: bold; margin-bottom: 15px;">
                {icon} CONFIRM: {label}
            </div>
            <div style="background: rgba(255,255,255,0.1); border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                <table style="width: 100%; color: white;">
                    <tr>
                        <td style="padding: 5px; color: #94a3b8;">Asset ID:</td>
                        <td style="padding: 5px; font-weight: bold;">{action["asset_serial"]}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; color: #94a3b8;">Current State:</td>
                        <td style="padding: 5px;"><span style="background: #374151; padding: 3px 8px; border-radius: 4px;">{current_display}</span></td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; color: #94a3b8;">New State:</td>
                        <td style="padding: 5px;"><span style="background: #059669; padding: 3px 8px; border-radius: 4px;">{new_display}</span></td>
                    </tr>
                </table>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Show billing impact for admin
        impacts = get_billing_impact(action["current_status"], action["new_status"], action.get("asset_info"))
        if impacts:
            st.markdown("**Billing Impact:**")
            for impact in impacts:
                if impact["type"] == "positive":
                    st.success(f"{impact['icon']} {impact['message']}")
                    st.caption(impact['detail'])
                elif impact["type"] == "warning":
                    st.warning(f"{impact['icon']} {impact['message']}")
                    st.caption(impact['detail'])
                elif impact["type"] == "critical":
                    st.error(f"{impact['icon']} {impact['message']}")
                    st.caption(impact['detail'])
                else:
                    st.info(f"{impact['icon']} {impact['message']}")
                    st.caption(impact['detail'])

        # Show extra details if available
        if action.get("extra_data"):
            with st.expander("Additional Details", expanded=False):
                for key, value in action["extra_data"].items():
                    st.text(f"{key}: {value}")

    else:
        # Lightweight confirmation for Operations
        st.markdown(f"""
        <div style="background: #1e293b; border: 1px solid #3b82f6; border-radius: 8px; padding: 15px; margin: 10px 0;">
            <div style="color: #3b82f6; font-weight: bold; margin-bottom: 10px;">
                {icon} Confirm {label}
            </div>
            <div style="color: white;">
                <strong>{action["asset_serial"]}</strong>: {current_display} → {new_display}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Show billing impact briefly
        impacts = get_billing_impact(action["current_status"], action["new_status"])
        if impacts:
            for impact in impacts:
                st.caption(f"{impact['icon']} {impact['message']}")

    # Confirmation buttons
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        confirm_label = "Confirm & Execute" if is_admin else "Confirm"
        if st.button(confirm_label, key="confirm_action_btn", type="primary"):
            return True, False

    with col2:
        if st.button("Cancel", key="cancel_action_btn"):
            clear_action_confirmation()
            return False, True

    return False, False

ASSET_TYPES = ["Laptop", "Phone", "Printer", "Other"]
BRANDS = ["Lenovo", "Apple", "HP", "Dell", "Other"]
STORAGE_TYPES = ["SSD", "HDD"]
OS_OPTIONS = ["Windows 10 Pro", "Windows 11 Pro", "macOS"]

ISSUE_CATEGORIES = [
    "VPN Connection Issue", "Windows Reset Problem", "OS Installation Issue",
    "Driver Issue", "Blue Screen / Restart", "Display Issue",
    "HDMI Port Issue", "Keyboard Issue", "Physical Damage", "Battery Issue"
]

# Initialize Airtable connection
@st.cache_resource
def get_airtable_api():
    if not AIRTABLE_API_KEY or AIRTABLE_API_KEY == "your_api_key_here":
        return None
    return Api(AIRTABLE_API_KEY)

def get_table(table_name):
    api = get_airtable_api()
    if api:
        return api.table(AIRTABLE_BASE_ID, TABLES[table_name])
    return None

# Data fetching functions with query limits and error handling
def _get_empty_data_structure() -> dict:
    """Return empty data structure for fallback scenarios."""
    return {
        "assets": pd.DataFrame(),
        "clients": pd.DataFrame(),
        "assignments": pd.DataFrame(),
        "issues": pd.DataFrame(),
        "repairs": pd.DataFrame(),
        "vendors": pd.DataFrame(),
        "invoices": pd.DataFrame()
    }

@st.cache_data(ttl=CACHE_CONFIG.get("ttl_assets", 600))
def fetch_all_data():
    """
    Fetch all data from configured data source (Airtable or MySQL).
    Applies query limits to prevent full-table scans on large datasets.
    Returns empty data structure on failure to prevent crashes.
    """
    data = _get_empty_data_structure()

    try:
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
            # Fetch from MySQL with individual error handling per table
            try:
                data["assets"] = mysql_get_assets()
            except Exception as e:
                log_error(e, "fetch_assets")
                data["assets"] = pd.DataFrame()

            try:
                data["clients"] = mysql_get_clients()
            except Exception as e:
                log_error(e, "fetch_clients")
                data["clients"] = pd.DataFrame()

            try:
                data["assignments"] = mysql_get_assignments()
            except Exception as e:
                log_error(e, "fetch_assignments")
                data["assignments"] = pd.DataFrame()

            try:
                data["issues"] = mysql_get_issues()
            except Exception as e:
                log_error(e, "fetch_issues")
                data["issues"] = pd.DataFrame()

            try:
                data["repairs"] = mysql_get_repairs()
            except Exception as e:
                log_error(e, "fetch_repairs")
                data["repairs"] = pd.DataFrame()

        else:
            # Fetch from Airtable (original logic) with error handling
            for key in TABLES.keys():
                try:
                    table = get_table(key)
                    if table:
                        limit = QUERY_LIMITS.get(key, PAGINATION_CONFIG["max_records"])
                        records = table.all(max_records=limit)
                        items = []
                        for record in records:
                            fields = record.get("fields", {})
                            fields["_id"] = record.get("id")
                            items.append(fields)
                        data[key] = pd.DataFrame(items) if items else pd.DataFrame()
                    else:
                        data[key] = pd.DataFrame()
                except Exception as e:
                    log_error(e, f"fetch_airtable_{key}")
                    data[key] = pd.DataFrame()

        # Apply query limits to each DataFrame
        for key in data:
            if not data[key].empty:
                limit = QUERY_LIMITS.get(key, PAGINATION_CONFIG["max_records"])
                if len(data[key]) > limit:
                    data[key] = data[key].head(limit)

    except Exception as e:
        # Critical failure - log and return empty structure
        log_error(e, "fetch_all_data_critical")
        return _get_empty_data_structure()

    return data


def clear_cache(data_types: list = None):
    """
    Clear cache and mark data as stale for session state refresh.
    Optionally specify which data types to invalidate.

    Args:
        data_types: List of data types to invalidate (e.g., ["assets", "assignments"]).
                   If None, clears all caches.
    """
    # Clear main cache
    fetch_all_data.clear()

    # Mark session data as stale
    if 'data_stale' in st.session_state:
        st.session_state.data_stale = True

    # Clear specific cached DataFrames
    if data_types:
        for dtype in data_types:
            cache_key = f"cached_{dtype}"
            timestamp_key = f"cached_{dtype}_time"
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            if timestamp_key in st.session_state:
                del st.session_state[timestamp_key]
        # Reset pagination for affected tables
        for dtype in data_types:
            reset_pagination(dtype)

def update_asset_status(record_id, new_status, location="", skip_validation=False, skip_rbac=False):
    """
    Update asset status with lifecycle and RBAC validation.
    Supports both Airtable and MySQL based on DATA_SOURCE.

    Args:
        record_id: Record ID (Airtable ID or MySQL ID)
        new_status: Target status
        location: Optional new location
        skip_validation: If True, skip transition validation (use only for data fixes)
        skip_rbac: If True, skip role-based access control (use only for system operations)

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    user_role = st.session_state.get('user_role', 'unknown')

    # RBAC Validation - Determine action based on new_status
    if not skip_rbac:
        # Map status changes to required actions
        status_to_action = {
            "WITH_CLIENT": "assign_to_client",
            "RETURNED_FROM_CLIENT": "receive_return",
            "WITH_VENDOR_REPAIR": "send_for_repair",
            "IN_STOCK_WORKING": "mark_repaired",  # or change_status
            "IN_OFFICE_TESTING": "change_status",
            "SOLD": "change_status",
            "DISPOSED": "change_status",
        }
        required_action = status_to_action.get(new_status, "change_status")
        validation_result = validate_action(required_action, user_role)
        if not validation_result.success:
            log_activity_event(
                action_type="ACCESS_DENIED",
                category="security",
                user_role=user_role,
                description=f"Unauthorized status change attempt: {new_status}",
                success=False
            )
            return False, validation_result.message

    # Get current status for validation
    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
        current_status, serial_number = get_asset_current_status_db(record_id)
    else:
        current_status, serial_number = get_asset_current_status(record_id)

    # Get asset_id for MySQL or use record_id
    asset_id = record_id if DATA_SOURCE == "mysql" else None

    if current_status is None:
        log_state_change(serial_number or "Unknown", "Unknown", new_status, user_role, False, "Asset not found", asset_id=asset_id)
        return False, "Asset not found"

    # Validate state transition (unless explicitly skipped)
    if not skip_validation:
        is_valid, error_message = validate_state_transition(current_status, new_status)
        if not is_valid:
            log_state_change(serial_number, current_status, new_status, user_role, False, error_message, asset_id=asset_id)
            return False, error_message

    # Perform the update based on data source
    try:
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
            success, error = update_asset_status_db(record_id, new_status, location)
            if success:
                clear_cache(["assets", "assignments"])  # Targeted invalidation
                log_state_change(serial_number, current_status, new_status, user_role, True, asset_id=asset_id)
                # Also log to MySQL state_change_log (legacy table)
                log_state_change_db(record_id, serial_number, current_status, new_status, user_role, True)
                return True, None
            else:
                log_state_change(serial_number, current_status, new_status, user_role, False, error, asset_id=asset_id)
                return False, error
        else:
            # Airtable update
            table = get_table("assets")
            if not table:
                return False, "Database connection error"

            update_fields = {"Current Status": new_status}
            if location:
                update_fields["Current Location"] = location
            table.update(record_id, update_fields)
            clear_cache(["assets", "assignments"])  # Targeted invalidation

            # Log successful state change
            log_state_change(serial_number, current_status, new_status, user_role, True, asset_id=asset_id)
            return True, None

    except Exception as e:
        error_msg = f"Database update failed: {str(e)}"
        log_state_change(serial_number, current_status, new_status, user_role, False, error_msg, asset_id=asset_id)
        return False, error_msg

def create_repair_record(data, user_role="admin", skip_rbac=False):
    """Create a new repair record (supports Airtable and MySQL)"""
    # RBAC Validation
    if not skip_rbac:
        validation_result = validate_action("create_repair", user_role)
        if not validation_result.success:
            log_activity_event(
                action_type="ACCESS_DENIED",
                category="security",
                user_role=user_role,
                description="Unauthorized repair record creation attempt",
                success=False
            )
            return False

    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
        success, repair_id, error = mysql_create_repair(data)
        if success:
            clear_cache(["repairs", "assets"])  # Targeted invalidation
            # Log activity
            log_activity_event(
                action_type="REPAIR_CREATED",
                category="asset",
                user_role=user_role,
                description=f"Repair created: {data.get('Repair Reference', 'N/A')}",
                serial_number=data.get("Serial Number"),
                old_value=None,
                new_value=data.get("Status", "WITH_VENDOR"),
                success=True
            )
        return success
    else:
        table = get_table("repairs")
        if table:
            table.create(data)
            clear_cache(["repairs", "assets"])  # Targeted invalidation
            return True
        return False

def create_assignment_record(data, user_role="admin", skip_rbac=False):
    """Create a new assignment record (supports Airtable and MySQL)"""
    # RBAC Validation
    if not skip_rbac:
        validation_result = validate_action("assign_to_client", user_role)
        if not validation_result.success:
            log_activity_event(
                action_type="ACCESS_DENIED",
                category="security",
                user_role=user_role,
                description="Unauthorized assignment creation attempt",
                success=False
            )
            return False

    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
        success, assignment_id, error = mysql_create_assignment(data)
        if success:
            clear_cache(["assignments", "assets"])  # Targeted invalidation
            # Log activity - this is a billing-impacting event
            log_activity_event(
                action_type="ASSIGNMENT_CREATED",
                category="assignment",
                user_role=user_role,
                description=f"Asset assigned: {data.get('Assignment Name', 'N/A')}",
                serial_number=data.get("Serial Number"),
                client_name=data.get("Client Name"),
                old_value=None,
                new_value="ACTIVE",
                success=True
            )
        return success
    else:
        table = get_table("assignments")
        if table:
            table.create(data)
            clear_cache(["assignments", "assets"])  # Targeted invalidation
            return True
        return False


def create_issue_record(data, user_role="admin", skip_rbac=False):
    """Create a new issue record (supports Airtable and MySQL)"""
    # RBAC Validation
    if not skip_rbac:
        validation_result = validate_action("log_issue", user_role)
        if not validation_result.success:
            log_activity_event(
                action_type="ACCESS_DENIED",
                category="security",
                user_role=user_role,
                description="Unauthorized issue creation attempt",
                success=False
            )
            return False

    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
        success, issue_id, error = mysql_create_issue(data)
        if success:
            clear_cache(["issues"])  # Targeted invalidation
            # Log activity
            log_activity_event(
                action_type="ISSUE_CREATED",
                category="asset",
                user_role=user_role,
                description=f"Issue reported: {data.get('Issue Title', 'N/A')}",
                serial_number=data.get("Serial Number"),
                old_value=None,
                new_value=data.get("Status", "Open"),
                success=True
            )
        return success
    else:
        table = get_table("issues")
        if table:
            table.create(data)
            clear_cache(["issues"])  # Targeted invalidation
            return True
        return False

def calculate_sla_status(status, days_in_status):
    """Calculate SLA status based on asset state and days"""
    if status not in SLA_CONFIG:
        return "ok", 0

    config = SLA_CONFIG[status]
    if days_in_status >= config["critical"]:
        return "critical", config["critical"]
    elif days_in_status >= config["warning"]:
        return "warning", config["warning"]
    return "ok", config["warning"]

def get_sla_counts(assets_df):
    """Get count of assets in each SLA category"""
    sla_counts = {"ok": 0, "warning": 0, "critical": 0}

    if assets_df.empty or "Current Status" not in assets_df.columns:
        return sla_counts

    today = date.today()

    for _, asset in assets_df.iterrows():
        status = asset.get("Current Status", "")
        if status in SLA_CONFIG:
            # Try to get status change date
            status_date = None
            if "Status Changed Date" in asset and pd.notna(asset.get("Status Changed Date")):
                try:
                    status_date = datetime.strptime(str(asset["Status Changed Date"])[:10], "%Y-%m-%d").date()
                except:
                    pass
            elif "Returned Date" in asset and pd.notna(asset.get("Returned Date")) and status == "RETURNED_FROM_CLIENT":
                try:
                    status_date = datetime.strptime(str(asset["Returned Date"])[:10], "%Y-%m-%d").date()
                except:
                    pass

            if status_date:
                days = (today - status_date).days
            else:
                days = 0

            sla_status, _ = calculate_sla_status(status, days)
            sla_counts[sla_status] += 1

    return sla_counts

def filter_assets_by_role(assets_df, role):
    """Filter assets based on user role focus states"""
    role_config = USER_ROLES.get(role, USER_ROLES["admin"])
    focus_states = role_config.get("focus_states")

    if focus_states is None or assets_df.empty:
        return assets_df

    if "Current Status" not in assets_df.columns:
        return assets_df

    return assets_df[assets_df["Current Status"].isin(focus_states)]

# Primary action per role - visually emphasized in sidebar
ROLE_PRIMARY_ACTION = {
    "operations": "Issues & Repairs",
    "finance": "Billing",
    "admin": "Dashboard"
}

# ============================================
# ROLE-BASED ACCESS CONTROL (RBAC) SYSTEM
# ============================================

# Permission definitions
PERMISSIONS = {
    # Page access permissions
    "page.add_asset": ["admin", "operations"],
    "page.quick_actions": ["admin", "operations"],
    "page.issues_repairs": ["admin", "operations"],
    "page.billing": ["admin", "finance"],
    "page.users": ["admin"],
    "page.settings": ["admin"],

    # Action permissions
    "action.create_asset": ["admin", "operations"],
    "action.edit_asset": ["admin", "operations"],
    "action.delete_asset": ["admin"],
    "action.assign_to_client": ["admin", "operations"],
    "action.receive_return": ["admin", "operations"],
    "action.send_for_repair": ["admin", "operations"],
    "action.mark_repaired": ["admin", "operations"],
    "action.change_status": ["admin", "operations"],
    "action.log_issue": ["admin", "operations"],
    "action.create_repair": ["admin", "operations"],

    # View permissions
    "view.billing": ["admin", "finance"],
    "view.revenue": ["admin", "finance"],
    "view.settings": ["admin"],
    "view.sla": ["admin", "operations"],
}

# Page to permission mapping
PAGE_ACCESS_CONTROL = {
    "Add Asset": "page.add_asset",
    "Quick Actions": "page.quick_actions",
    "Issues & Repairs": "page.issues_repairs",
    "Billing": "page.billing",
    "Settings": "page.settings",
}

def has_permission(permission, role):
    """Check if a role has a specific permission.
    Returns True if permission is granted, False otherwise.
    """
    if permission not in PERMISSIONS:
        return True  # Unknown permissions default to allowed
    return role in PERMISSIONS[permission]

def check_page_access(page_name, role):
    """Check if a role has access to a specific page.
    Returns True if access is allowed, False otherwise.
    Pages not in PAGE_ACCESS_CONTROL are accessible to all roles.
    """
    if page_name not in PAGE_ACCESS_CONTROL:
        return True  # No restrictions, all roles can access
    permission = PAGE_ACCESS_CONTROL[page_name]
    return has_permission(permission, role)

def can_view_billing(role):
    """Check if role can view billing/revenue information."""
    return has_permission("view.billing", role)

def can_view_revenue(role):
    """Check if role can view revenue information."""
    return has_permission("view.revenue", role)

def can_create_asset(role):
    """Check if role can create new assets."""
    return has_permission("action.create_asset", role)

def can_perform_lifecycle_action(role):
    """Check if role can perform asset lifecycle actions (assign, return, repair)."""
    return has_permission("action.assign_to_client", role)

def can_manage_repairs(role):
    """Check if role can manage repairs and issues."""
    return has_permission("action.create_repair", role)


# ============================================
# CENTRALIZED ACTION VALIDATION (RBAC)
# ============================================
# Server-side validation - DO NOT rely on UI hiding alone

class ActionResult:
    """Result of an action validation or execution."""
    def __init__(self, success: bool, message: str, data: dict = None):
        self.success = success
        self.message = message
        self.data = data or {}

    def __bool__(self):
        return self.success


# Action-to-Permission mapping for validation
ACTION_PERMISSIONS = {
    # Asset lifecycle actions
    "assign_to_client": "action.assign_to_client",
    "receive_return": "action.receive_return",
    "send_for_repair": "action.send_for_repair",
    "mark_repaired": "action.mark_repaired",
    "change_status": "action.change_status",

    # Asset management
    "create_asset": "action.create_asset",
    "edit_asset": "action.edit_asset",
    "delete_asset": "action.delete_asset",

    # Issues and repairs
    "log_issue": "action.log_issue",
    "create_repair": "action.create_repair",

    # Billing (special handling)
    "billing_override": "billing_override",  # Uses BILLING_CONFIG
    "view_billing": "view.billing",
    "view_revenue": "view.revenue",
}

# Human-readable action names for error messages
ACTION_DISPLAY_NAMES = {
    "assign_to_client": "Assign Asset to Client",
    "receive_return": "Process Asset Return",
    "send_for_repair": "Send Asset for Repair",
    "mark_repaired": "Mark Asset as Repaired",
    "change_status": "Change Asset Status",
    "create_asset": "Create New Asset",
    "edit_asset": "Edit Asset",
    "delete_asset": "Delete Asset",
    "log_issue": "Log Issue",
    "create_repair": "Create Repair Record",
    "billing_override": "Override Billing",
    "view_billing": "View Billing Information",
    "view_revenue": "View Revenue Data",
}


def validate_action(action: str, role: str, context: dict = None) -> ActionResult:
    """
    Centralized action validation - enforces RBAC at the logic level.

    This function MUST be called before executing any protected action.
    It validates permissions regardless of UI state.

    Args:
        action: Action identifier (e.g., "assign_to_client", "billing_override")
        role: Current user role
        context: Optional context data for additional validation

    Returns:
        ActionResult with success=True if allowed, False with message if denied
    """
    context = context or {}
    action_name = ACTION_DISPLAY_NAMES.get(action, action.replace("_", " ").title())
    role_name = USER_ROLES.get(role, {}).get("name", role)

    # Special handling for billing override
    if action == "billing_override":
        if can_override_billing(role):
            return ActionResult(True, "Billing override permitted")
        return ActionResult(
            False,
            f"Access Denied: {action_name} requires Admin privileges. Your current role ({role_name}) does not have this permission."
        )

    # Get required permission for the action
    permission = ACTION_PERMISSIONS.get(action)
    if not permission:
        # Unknown action - log and deny by default for security
        return ActionResult(
            False,
            f"Access Denied: Unknown action '{action}'. Please contact an administrator."
        )

    # Check permission
    if has_permission(permission, role):
        return ActionResult(True, f"{action_name} permitted for {role_name}")

    # Permission denied - build informative message
    allowed_roles = PERMISSIONS.get(permission, [])
    allowed_role_names = [USER_ROLES.get(r, {}).get("name", r) for r in allowed_roles]

    return ActionResult(
        False,
        f"Access Denied: {action_name} is not permitted for your role ({role_name}). This action requires: {', '.join(allowed_role_names)}."
    )


def require_permission(action: str, role: str, context: dict = None) -> bool:
    """
    Decorator-style permission check that displays error in UI if denied.

    Usage:
        if not require_permission("assign_to_client", current_role):
            return  # Error already displayed
        # Proceed with action

    Returns:
        True if permitted (continue execution), False if denied (error shown)
    """
    result = validate_action(action, role, context)
    if not result.success:
        st.error(result.message)
        # Log unauthorized access attempt
        log_activity_event(
            action_type="ACCESS_DENIED",
            category="security",
            user_role=role,
            description=f"Unauthorized attempt: {action}",
            success=False
        )
        return False
    return True


def validate_and_execute(action: str, role: str, execute_func, context: dict = None, **kwargs):
    """
    Validate permission and execute action in one call.

    Args:
        action: Action identifier
        role: Current user role
        execute_func: Function to execute if permitted
        context: Optional context for validation
        **kwargs: Arguments to pass to execute_func

    Returns:
        Result of execute_func if permitted, None if denied
    """
    result = validate_action(action, role, context)
    if not result.success:
        st.error(result.message)
        log_activity_event(
            action_type="ACCESS_DENIED",
            category="security",
            user_role=role,
            description=f"Unauthorized attempt: {action}",
            success=False
        )
        return None

    try:
        return execute_func(**kwargs)
    except Exception as e:
        error_id = log_error(e, f"execute_action:{action}", role)
        error_type = classify_error(e)
        user_message = USER_SAFE_MESSAGES.get(error_type, USER_SAFE_MESSAGES["default"])
        st.error(f"{user_message} (Ref: {error_id})")
        return None


def get_permitted_actions(role: str) -> list:
    """
    Get list of all actions permitted for a role.
    Useful for debugging and displaying available actions.
    """
    permitted = []
    for action, permission in ACTION_PERMISSIONS.items():
        if permission == "billing_override":
            if can_override_billing(role):
                permitted.append(action)
        elif has_permission(permission, role):
            permitted.append(action)
    return permitted


def render_access_denied(required_roles=None):
    """Render access denied message and redirect option."""
    current_role = st.session_state.user_role
    role_name = USER_ROLES.get(current_role, {}).get("name", current_role)

    st.error("🚫 Access Denied")

    roles_text = ""
    if required_roles:
        role_names = [USER_ROLES.get(r, {}).get("name", r) for r in required_roles]
        roles_text = f"<p style='color: #6b7280; font-size: 0.875rem; margin-top: 10px;'>Required role(s): <strong>{', '.join(role_names)}</strong></p>"

    st.markdown(f"""
    <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <h3 style="color: #dc2626; margin: 0 0 10px 0;">You don't have permission to access this page</h3>
        <p style="color: #7f1d1d; margin: 0;">Your current role (<strong>{role_name}</strong>) does not have access to this feature.</p>
        {roles_text}
        <p style="color: #7f1d1d; margin: 10px 0 0 0; font-size: 0.875rem;">Contact an administrator if you believe this is an error.</p>
    </div>
    """, unsafe_allow_html=True)

    # Log unauthorized access attempt (for security auditing)
    if 'access_denied_log' not in st.session_state:
        st.session_state.access_denied_log = []
    st.session_state.access_denied_log.append({
        "timestamp": datetime.now().isoformat(),
        "role": current_role,
        "page": st.session_state.current_page,
    })

    if st.button("← Return to Dashboard"):
        st.session_state.current_page = "Dashboard"
        safe_rerun()

# Navigation menu structure with groups and role-based visibility
# "roles" key defines which roles can see each menu item
# If "roles" is not specified, item is visible to all roles
MENU_GROUPS = {
    "MAIN": [
        {"name": "Dashboard", "icon": "⊞", "key": "dashboard"},  # All roles
    ],
    "INVENTORY": [
        {"name": "Assets", "icon": "☐", "key": "assets"},  # All roles
        {"name": "Add Asset", "icon": "+", "key": "add_asset", "roles": ["admin", "operations"]},  # Finance cannot create
        {"name": "Quick Actions", "icon": "↻", "key": "quick_actions", "roles": ["admin", "operations"]},  # Finance cannot do actions
    ],
    "OPERATIONS": [
        {"name": "Assignments", "icon": "≡", "key": "assignments"},  # All roles
        {"name": "Issues & Repairs", "icon": "⚙", "key": "issues", "roles": ["admin", "operations"]},  # Finance cannot do repairs
        {"name": "Clients", "icon": "◉", "key": "clients"},  # All roles
    ],
    "BILLING": [
        {"name": "Billing", "icon": "₹", "key": "billing", "roles": ["admin", "finance"]},  # Finance and Admin only
    ],
    "REPORTS": [
        {"name": "Reports", "icon": "◫", "key": "reports"},  # All roles - reporting only
        {"name": "Activity Log", "icon": "◉", "key": "activity_log"},  # All roles - view based on role
    ],
    "SYSTEM": [
        {"name": "Import/Export", "icon": "↔", "key": "import_export", "roles": ["admin", "operations"]},  # Admin and Operations
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
# AUTHENTICATION CHECK
# ============================================
# Initialize auth session state
init_auth_session()

# Perform security checks for authenticated sessions
if st.session_state.authenticated:
    # Check for session timeout (absolute and inactivity)
    session_timed_out = check_session_timeout()

    # If not timed out, validate session against server
    if not session_timed_out:
        validate_current_session()

# Show login page if not authenticated
if not st.session_state.authenticated:
    render_login_page()
    st.stop()

# Initialize session state for navigation
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

# Sidebar brand header
st.sidebar.markdown("""
<div class="sidebar-brand">
    <img src="https://cdn-media.nxtby.com/media/logo/stores/1/nxtby_orange_1.png" alt="Nxtby.com" style="height: 32px; margin-bottom: 4px;">
    <p>Asset Management</p>
</div>
""", unsafe_allow_html=True)

# Connection status
if db_connected:
    st.sidebar.markdown("""
    <div class="connection-status status-connected">
        ● Connected
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.markdown("""
    <div class="connection-status status-disconnected">
        ○ Not Connected
    </div>
    """, unsafe_allow_html=True)

# User Info & Logout
user_display_name = st.session_state.user_full_name or st.session_state.username
user_role = st.session_state.user_role or "operations"
role_display = USER_ROLES.get(user_role, {}).get('name', user_role.title())

st.sidebar.markdown(f"""
<div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
    <div style="color: #F97316; font-weight: 600; font-size: 0.9rem;">
        Welcome, {user_display_name}
    </div>
    <div style="color: #94a3b8; font-size: 0.8rem; margin-top: 4px;">
        Role: {role_display}
    </div>
</div>
""", unsafe_allow_html=True)

# Logout button
if st.sidebar.button("Sign Out", key="logout_btn", use_container_width=True):
    # Log logout activity before clearing session
    log_activity_event(
        action_type="USER_LOGOUT",
        category="authentication",
        user_role=st.session_state.user_role,
        description=f"User signed out: {st.session_state.username}",
        success=True
    )
    # Invalidate session (server-side) and clear state
    logout_user()
    safe_rerun()

# Show role description
role_config = USER_ROLES[st.session_state.user_role]
role_class = f"role-{st.session_state.user_role}"
st.sidebar.markdown(f"""
<div class="role-badge {role_class}" style="margin: 8px 16px 16px 16px;">
    {role_config['name']}
</div>
<p style="margin: 0 16px 8px 16px; font-size: 0.75rem; color: #64748b;">
    {role_config['description']}
</p>
""", unsafe_allow_html=True)

# Navigation menu with groups - filter by role and collect button clicks
nav_clicked = None
current_role = st.session_state.user_role
visible_menu = get_visible_menu_items(current_role)

for group_name, items in visible_menu.items():
    st.sidebar.markdown(f"### {group_name}")

    for item in items:
        is_active = st.session_state.current_page == item["name"]
        is_primary_action = item["name"] == ROLE_PRIMARY_ACTION.get(current_role)

        # Primary action indicator shown above the button (subtle accent line)
        if is_primary_action and not is_active:
            st.sidebar.markdown(
                '<div style="height: 2px; background: linear-gradient(90deg, #f97316 0%, transparent 100%); margin: 4px 16px 2px 16px; border-radius: 1px;"></div>',
                unsafe_allow_html=True
            )

        if st.sidebar.button(
            f"{item['icon']}  {item['name']}",
            key=f"nav_{item['key']}_{current_role}",
                        type="primary" if is_active else "secondary",
            help="Recommended for your role" if is_primary_action and not is_active else None
        ):
            nav_clicked = item["name"]

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

            # SLA Breaches Row (highest priority)
            sla_col1, sla_col2, sla_col3, sla_col4 = st.columns(4)

            with sla_col1:
                critical_bg = "#fef2f2" if sla_counts['critical'] > 0 else "#ffffff"
                critical_border = "#fecaca" if sla_counts['critical'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card" style="background: {critical_bg}; border: 1px solid {critical_border}; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #dc2626; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA Critical</div>
                    <div style="font-size: 36px; font-weight: 700; color: #dc2626; line-height: 1;">{sla_counts['critical']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Exceeds threshold</div>
                </div>
                """, unsafe_allow_html=True)

            with sla_col2:
                warning_bg = "#fffbeb" if sla_counts['warning'] > 0 else "#ffffff"
                warning_border = "#fde68a" if sla_counts['warning'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card" style="background: {warning_bg}; border: 1px solid {warning_border}; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #d97706; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA Warning</div>
                    <div style="font-size: 36px; font-weight: 700; color: #d97706; line-height: 1;">{sla_counts['warning']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Approaching limit</div>
                </div>
                """, unsafe_allow_html=True)

            with sla_col3:
                return_bg = "#fef2f2" if returned > 0 else "#ffffff"
                return_border = "#fecaca" if returned > 0 else "#e5e7eb"
                return_color = "#ef4444" if returned > 0 else "#10b981"
                st.markdown(f"""
                <div class="metric-card" style="background: {return_bg}; border: 1px solid {return_border}; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Returns Backlog</div>
                    <div style="font-size: 36px; font-weight: 700; color: {return_color}; line-height: 1;">{returned}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Pending review</div>
                </div>
                """, unsafe_allow_html=True)

            with sla_col4:
                repair_bg = "#eff6ff" if under_repair > 0 else "#ffffff"
                repair_border = "#bfdbfe" if under_repair > 0 else "#e5e7eb"
                repair_color = "#3b82f6" if under_repair > 0 else "#10b981"
                st.markdown(f"""
                <div class="metric-card" style="background: {repair_bg}; border: 1px solid {repair_border}; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Repair Backlog</div>
                    <div style="font-size: 36px; font-weight: 700; color: {repair_color}; line-height: 1;">{under_repair}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">At vendor</div>
                </div>
                """, unsafe_allow_html=True)

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

        # KPI Cards - Cards only (no buttons in columns)
        st.markdown(f"""
        <div class="kpi-cards-row">
            <div class="kpi-card neutral" data-kpi="total" onclick="document.querySelector('#kpi-btn-total').click()">
                <div class="kpi-card-title">TOTAL ASSETS</div>
                <div class="kpi-card-value">{total}</div>
                <div class="kpi-card-label">All inventory</div>
            </div>
            <div class="kpi-card blue" data-kpi="deployed" onclick="document.querySelector('#kpi-btn-deployed').click()">
                <div class="kpi-card-title">DEPLOYED</div>
                <div class="kpi-card-value">{with_client}</div>
                <div class="kpi-card-label">With clients</div>
            </div>
            <div class="kpi-card green" data-kpi="available" onclick="document.querySelector('#kpi-btn-available').click()">
                <div class="kpi-card-title">AVAILABLE</div>
                <div class="kpi-card-value">{in_stock}</div>
                <div class="kpi-card-label">Ready to deploy</div>
            </div>
            <div class="kpi-card amber" data-kpi="repair" onclick="document.querySelector('#kpi-btn-repair').click()">
                <div class="kpi-card-title">IN REPAIR</div>
                <div class="kpi-card-value">{under_repair}</div>
                <div class="kpi-card-label">At vendor</div>
            </div>
            <div class="kpi-card red" data-kpi="returned" onclick="document.querySelector('#kpi-btn-returned').click()">
                <div class="kpi-card-title">RETURNED</div>
                <div class="kpi-card-value">{returned}</div>
                <div class="kpi-card-label">Needs review</div>
            </div>
        </div>
        <style>
        .kpi-cards-row {{
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-cards-row .kpi-card {{
            flex: 1;
            min-width: 0;
        }}
        </style>
        """, unsafe_allow_html=True)

        # Hidden buttons for KPI navigation (invisible but functional)
        st.markdown("""<div style="position:absolute;left:-9999px;height:0;overflow:hidden;">""", unsafe_allow_html=True)
        kbtn1, kbtn2, kbtn3, kbtn4, kbtn5 = st.columns(5)
        with kbtn1:
            if st.button("kpi_total_btn", key="kpi_total_nav"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "All"
                safe_rerun()
        with kbtn2:
            if st.button("kpi_deployed_btn", key="kpi_deployed_nav"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "WITH_CLIENT"
                safe_rerun()
        with kbtn3:
            if st.button("kpi_available_btn", key="kpi_available_nav"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "IN_STOCK_WORKING"
                safe_rerun()
        with kbtn4:
            if st.button("kpi_repair_btn", key="kpi_repair_nav"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "WITH_VENDOR_REPAIR"
                safe_rerun()
        with kbtn5:
            if st.button("kpi_returned_btn", key="kpi_returned_nav"):
                st.session_state.current_page = "Assets"
                st.session_state.asset_filter = "RETURNED_FROM_CLIENT"
                safe_rerun()
        st.markdown("""</div>""", unsafe_allow_html=True)

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
            # SLA Indicators for Operations and Admin
            sla_counts = get_sla_counts(assets_df)

            with insight_cols[0]:
                critical_bg = "#fef2f2" if sla_counts['critical'] > 0 else "#ffffff"
                critical_border = "#fecaca" if sla_counts['critical'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card" style="background: {critical_bg}; border: 1px solid {critical_border}; border-left: 4px solid #dc2626; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #dc2626; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA Critical</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{sla_counts['critical']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Exceeds threshold</div>
                </div>
                """, unsafe_allow_html=True)

            with insight_cols[1]:
                warning_bg = "#fffbeb" if sla_counts['warning'] > 0 else "#ffffff"
                warning_border = "#fde68a" if sla_counts['warning'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card" style="background: {warning_bg}; border: 1px solid {warning_border}; border-left: 4px solid #f59e0b; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #d97706; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA Warning</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{sla_counts['warning']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Approaching limit</div>
                </div>
                """, unsafe_allow_html=True)

            with insight_cols[2]:
                ok_bg = "#f0fdf4" if sla_counts['ok'] > 0 else "#ffffff"
                ok_border = "#bbf7d0" if sla_counts['ok'] > 0 else "#e5e7eb"
                st.markdown(f"""
                <div class="metric-card" style="background: {ok_bg}; border: 1px solid {ok_border}; border-left: 4px solid #16a34a; border-radius: 12px; padding: 20px;">
                    <div style="font-size: 11px; font-weight: 600; color: #16a34a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">SLA OK</div>
                    <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{sla_counts['ok']}</div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Within target</div>
                </div>
                """, unsafe_allow_html=True)

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
                    <div class="metric-card" style="background: #ffffff; border: 1px solid #e5e7eb; border-left: 4px solid #6366f1; border-radius: 12px; padding: 20px;">
                        <div style="font-size: 11px; font-weight: 600; color: #6366f1; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Billable Assets</div>
                        <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{billable_count}</div>
                        <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Currently deployed</div>
                    </div>
                    """, unsafe_allow_html=True)

                with insight_cols[1]:
                    st.markdown(f"""
                    <div class="metric-card" style="background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #16a34a; border-radius: 12px; padding: 20px;">
                        <div style="font-size: 11px; font-weight: 600; color: #16a34a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Est. Monthly Revenue</div>
                        <div style="font-size: 36px; font-weight: 700; color: #16a34a; line-height: 1;">₹{estimated_revenue:,}</div>
                        <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">@ ₹{monthly_rate:,}/asset</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Show paused billing count instead of sold
                with insight_cols[2]:
                    paused_bg = "#fffbeb" if paused_count > 0 else "#ffffff"
                    paused_border = "#fde68a" if paused_count > 0 else "#e5e7eb"
                    st.markdown(f"""
                    <div class="metric-card" style="background: {paused_bg}; border: 1px solid {paused_border}; border-left: 4px solid #f59e0b; border-radius: 12px; padding: 20px;">
                        <div style="font-size: 11px; font-weight: 600; color: #d97706; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Billing Paused</div>
                        <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">{paused_count}</div>
                        <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">Returned/Repair</div>
                    </div>
                    """, unsafe_allow_html=True)

            elif current_role == "admin":
                with insight_cols[3]:
                    st.markdown(f"""
                    <div class="metric-card" style="background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #3b82f6; border-radius: 12px; padding: 20px;">
                        <div style="font-size: 11px; font-weight: 600; color: #3b82f6; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">Est. Revenue</div>
                        <div style="font-size: 36px; font-weight: 700; color: #1f2937; line-height: 1;">₹{estimated_revenue:,}</div>
                        <div style="font-size: 12px; color: #6b7280; margin-top: 6px;">{billable_count} billable @ ₹{monthly_rate:,}</div>
                    </div>
                    """, unsafe_allow_html=True)

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

        # Clear the filters after using them
        if "asset_filter" in st.session_state:
            del st.session_state.asset_filter
        if "brand_filter" in st.session_state:
            del st.session_state.brand_filter

        # Filters row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            filter_options = ["All"] + ASSET_STATUSES
            default_index = filter_options.index(default_status_filter) if default_status_filter in filter_options else 0
            status_filter = st.selectbox("Filter by Status", filter_options, index=default_index)

        with col2:
            brand_list = list(assets_df["Brand"].dropna().unique()) if "Brand" in assets_df.columns else []
            brand_options = ["All"] + brand_list
            default_brand_index = brand_options.index(default_brand_filter) if default_brand_filter in brand_options else 0
            brand_filter = st.selectbox("Filter by Brand", brand_options, index=default_brand_index)

        with col3:
            type_list = list(assets_df["Asset Type"].dropna().unique()) if "Asset Type" in assets_df.columns else []
            type_filter = st.selectbox("Filter by Type", ["All"] + type_list)

        with col4:
            search = st.text_input("Search Serial Number")

        # Apply filters
        filtered_df = assets_df.copy()

        if status_filter != "All" and "Current Status" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Current Status"] == status_filter]

        if brand_filter != "All" and "Brand" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Brand"] == brand_filter]

        if type_filter != "All" and "Asset Type" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Asset Type"] == type_filter]

        if search and "Serial Number" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Serial Number"].str.contains(search, case=False, na=False)]

        # Results count with status legend
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 0; margin-bottom: 8px; flex-wrap: wrap; gap: 12px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 14px; color: #374151; font-weight: 500;">Showing</span>
                <span style="font-size: 16px; color: #3b82f6; font-weight: 700;">{len(filtered_df)}</span>
                <span style="font-size: 14px; color: #6b7280;">of {len(assets_df)} assets</span>
            </div>
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <span style="font-size: 11px; color: #4CAF50; font-weight: 600; padding: 2px 8px; background: #4CAF5020; border-radius: 4px;">In Stock</span>
                <span style="font-size: 11px; color: #FF6B35; font-weight: 600; padding: 2px 8px; background: #FF6B3520; border-radius: 4px;">With Client</span>
                <span style="font-size: 11px; color: #2196F3; font-weight: 600; padding: 2px 8px; background: #2196F320; border-radius: 4px;">Returned</span>
                <span style="font-size: 11px; color: #9C27B0; font-weight: 600; padding: 2px 8px; background: #9C27B020; border-radius: 4px;">Testing</span>
                <span style="font-size: 11px; color: #FF9800; font-weight: 600; padding: 2px 8px; background: #FF980020; border-radius: 4px;">Repair</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Display table with pagination
        display_cols = ["Serial Number", "Asset Type", "Brand", "Model", "RAM (GB)", "Storage (GB)",
                       "Current Status", "Current Location", "Office License Key", "Reuse Count"]
        available_cols = [c for c in display_cols if c in filtered_df.columns]

        if available_cols:
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

        # Export actions
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        export_col1, export_col2, export_col3 = st.columns([1, 1, 2])

        with export_col1:
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Export to CSV",
                data=csv,
                file_name=f"assets_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )

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
                        client_options = clients_df["Client Name"].tolist() if not clients_df.empty and "Client Name" in clients_df.columns else []
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
                # Results count
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                    <span style="font-size: 14px; color: #374151; font-weight: 500;">Total</span>
                    <span style="font-size: 16px; color: #3b82f6; font-weight: 700;">{len(assignments_df)}</span>
                    <span style="font-size: 14px; color: #6b7280;">assignments</span>
                </div>
                """, unsafe_allow_html=True)
                # Apply pagination
                paginated_assignments = paginate_dataframe(assignments_df, "assignments_table", show_controls=True)
                st.dataframe(paginated_assignments, hide_index=True)
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
                # Filter options
                col1, col2 = st.columns(2)
                with col1:
                    issue_status_filter = st.selectbox("Filter by Status", ["All", "Open", "In Progress", "Resolved", "Closed"])
                with col2:
                    issue_type_filter = st.selectbox("Filter by Type", ["All", "Software", "Hardware"])

                filtered_issues = issues_df.copy()
                if issue_status_filter != "All" and "Status" in filtered_issues.columns:
                    filtered_issues = filtered_issues[filtered_issues["Status"] == issue_status_filter]
                if issue_type_filter != "All" and "Issue Type" in filtered_issues.columns:
                    filtered_issues = filtered_issues[filtered_issues["Issue Type"] == issue_type_filter]

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
                # Apply pagination
                paginated_issues = paginate_dataframe(filtered_issues, "issues_table", show_controls=True)
                st.dataframe(paginated_issues[available_cols], hide_index=True)
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
                # Results count
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                    <span style="font-size: 14px; color: #374151; font-weight: 500;">Total</span>
                    <span style="font-size: 16px; color: #3b82f6; font-weight: 700;">{len(clients_df)}</span>
                    <span style="font-size: 14px; color: #6b7280;">clients</span>
                </div>
                """, unsafe_allow_html=True)
                # Apply pagination to client list
                paginated_clients = paginate_dataframe(clients_df, "clients_table", show_controls=True)
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

                # Filter options
                status_filter = st.selectbox(
                    "Filter by Billing Status",
                    ["All", "Billing Active", "Billing Paused", "Not Billable"],
                    key="billing_status_filter"
                )

                if status_filter != "All":
                    billing_view = billing_view[billing_view["Billing Status"] == status_filter]

                # Display with color coding
                def highlight_billing_status(row):
                    status = row["Billing Status"]
                    if status == "Billing Active":
                        return [f'background-color: {BILLING_CONFIG["status_colors"]["active"]}20'] * len(row)
                    elif status == "Billing Paused":
                        return [f'background-color: {BILLING_CONFIG["status_colors"]["paused"]}20'] * len(row)
                    return [''] * len(row)

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

    st.markdown('<p class="main-header">Import / Export Assets</p>', unsafe_allow_html=True)

    # Create two main sections
    export_section, import_section = st.tabs(["📤 Export Data", "📥 Import Data"])

    # ========== EXPORT SECTION ==========
    with export_section:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Export Assets to File</span>
        </div>
        """, unsafe_allow_html=True)

        st.info("Download all assets data as Excel (.xlsx) or CSV file for reporting, backup, or offline analysis.")

        # Fetch current assets data
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
            export_assets = get_all_assets()
        else:
            export_assets = []

        if export_assets:
            export_df = pd.DataFrame(export_assets)

            # Show summary
            st.markdown(f"""
            <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="font-size: 20px;">📊</span>
                    <span style="font-weight: 600; color: #166534;">Data Ready for Export</span>
                </div>
                <div style="color: #15803d;">
                    <strong>{len(export_df)}</strong> assets • <strong>{len(export_df.columns)}</strong> columns
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Export buttons
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
                display_cols = ['serial_number', 'asset_type', 'brand', 'model', 'current_status', 'current_location']
                available_cols = [c for c in display_cols if c in export_df.columns]
                st.dataframe(export_df[available_cols].head(10), use_container_width=True)
                st.caption(f"Showing first 10 of {len(export_df)} records")
        else:
            st.warning("No assets found in the database to export.")

    # ========== IMPORT SECTION ==========
    with import_section:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Import Assets from Excel</span>
        </div>
        """, unsafe_allow_html=True)

        st.info("Upload an Excel file (.xlsx) to bulk import assets. Download the template first to ensure correct format.")

        # Step 1: Download Template
        st.markdown("""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <div style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">Step 1: Download Import Template</div>
            <div style="color: #64748b; font-size: 14px;">The template includes column headers, data validation dropdowns, and a sample row.</div>
        </div>
        """, unsafe_allow_html=True)

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
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <div style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">Step 2: Upload Filled Template</div>
            <div style="color: #64748b; font-size: 14px;">Fill in the template with your asset data and upload it here.</div>
        </div>
        """, unsafe_allow_html=True)

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

                    # Step 3: Preview & Validate
                    st.markdown("""
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                        <div style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">Step 3: Preview & Validate</div>
                        <div style="color: #64748b; font-size: 14px;">Review your data and check for any validation errors.</div>
                    </div>
                    """, unsafe_allow_html=True)

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

                        summary_col1, summary_col2, summary_col3 = st.columns(3)
                        with summary_col1:
                            st.markdown(f"""
                            <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 12px; text-align: center;">
                                <div style="font-size: 24px; font-weight: bold; color: #166534;">{valid_count}</div>
                                <div style="color: #15803d; font-size: 14px;">Valid Records</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with summary_col2:
                            st.markdown(f"""
                            <div style="background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 12px; text-align: center;">
                                <div style="font-size: 24px; font-weight: bold; color: #991b1b;">{error_count}</div>
                                <div style="color: #dc2626; font-size: 14px;">Errors</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with summary_col3:
                            st.markdown(f"""
                            <div style="background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: 12px; text-align: center;">
                                <div style="font-size: 24px; font-weight: bold; color: #92400e;">{warning_count}</div>
                                <div style="color: #d97706; font-size: 14px;">Warnings</div>
                            </div>
                            """, unsafe_allow_html=True)

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
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                            <div style="font-weight: 600; color: #1e293b; margin-bottom: 8px;">Step 4: Import Assets</div>
                            <div style="color: #64748b; font-size: 14px;">Click the button below to import valid records into the database.</div>
                        </div>
                        """, unsafe_allow_html=True)

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
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align: center; padding: 12px 10px;">
    <small style="color: #64748b;">Asset Management v2.4</small><br>
    <small style="color: #f97316; font-weight: 500;">Streamlit + MySQL</small>
</div>
""", unsafe_allow_html=True)
