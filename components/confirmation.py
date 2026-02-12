"""
Action confirmation dialog system — extracted from app.py.
Role-based confirmation UI for asset lifecycle actions.
"""

from datetime import datetime

import streamlit as st

from config.constants import STATUS_DISPLAY_NAMES
from services.billing_service import get_billing_impact


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
