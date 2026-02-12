"""
Production error handling & logging utilities.
Extracted from app.py — provides centralized error handling for the application.
"""
import streamlit as st
import logging
import traceback
from datetime import datetime
from functools import wraps

logger = logging.getLogger("AssetManagement")

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
