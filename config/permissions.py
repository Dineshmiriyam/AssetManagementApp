"""
Role-Based Access Control (RBAC) system.
Extracted from app.py — defines permissions, page access, and action validation.
"""
import streamlit as st
from datetime import datetime

from config.constants import USER_ROLES, BILLING_CONFIG
from core.data import safe_rerun

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

def can_override_billing(role: str) -> bool:
    """Check if a role can override billing rules."""
    return role in BILLING_CONFIG["billing_override_roles"]


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
