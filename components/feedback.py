"""
Error, warning, and action feedback components — extracted from app.py.
Handles error states, inline messages, action buttons, and billing badges.
"""

import os

import streamlit as st

from services.billing_service import get_asset_billing_status
from core.data import safe_rerun
from components.loading import is_loading


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
