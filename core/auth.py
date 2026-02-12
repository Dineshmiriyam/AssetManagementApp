"""
Authentication & session management for Asset Lifecycle Management System.
Handles login, logout, session validation, timeout checks, and session restore.
"""
import logging
from datetime import datetime

import streamlit as st

from config.constants import SESSION_TIMEOUT_HOURS, INACTIVITY_TIMEOUT_MINUTES
from config.styles import get_login_css
from core.data import safe_rerun

logger = logging.getLogger("AssetManagement")

# Database auth — conditionally available (same pattern as services/)
_AUTH_AVAILABLE = False
try:
    from database.auth import (
        authenticate_user,
        validate_session,
        invalidate_session,
        is_database_available,
    )
    _AUTH_AVAILABLE = True
except ImportError:
    authenticate_user = None
    validate_session = None
    invalidate_session = None
    is_database_available = None


def is_auth_available() -> bool:
    """Public accessor for auth availability."""
    return _AUTH_AVAILABLE


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

    if not _AUTH_AVAILABLE:
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
    if _AUTH_AVAILABLE and st.session_state.user_id:
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
    auth_system_available = _AUTH_AVAILABLE
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


def restore_session_from_url():
    """
    Try to restore session from URL query params (survives hard refresh).
    On hard refresh, Streamlit session state is lost but URL params persist.
    If a valid session token is in the URL, restore the session automatically.
    """
    if st.session_state.authenticated:
        return  # Already authenticated

    _sid = st.query_params.get("sid")
    _clear_sid = False  # Flag to clear sid OUTSIDE try/except

    if _sid and _AUTH_AVAILABLE:
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
