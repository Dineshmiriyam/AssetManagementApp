"""
Asset operations — extracted from app.py.
Handles state transitions, status updates, and record creation.
"""

import os
import logging

import streamlit as st

from config.constants import ALLOWED_TRANSITIONS, STATUS_DISPLAY_NAMES, VALID_INITIAL_STATUSES
from config.permissions import validate_action
from core.data import get_table, clear_cache
from services.audit_service import log_state_change, log_activity_event

logger = logging.getLogger("AssetManagement")

# Database functions — conditionally available
try:
    from database.db import (
        get_asset_current_status_db,
        update_asset_status_db,
        create_assignment as mysql_create_assignment,
        create_issue as mysql_create_issue,
        create_repair as mysql_create_repair,
        update_repair as mysql_update_repair,
        get_active_repair_by_asset_id as mysql_get_active_repair,
        log_state_change_db,
    )
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False

DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql")
MYSQL_AVAILABLE = _DB_AVAILABLE and DATA_SOURCE == "mysql"


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


def update_repair_record(repair_id, data, user_role="admin"):
    """Update an existing repair record (cost, notes, return date, status)."""
    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
        success, error = mysql_update_repair(int(repair_id), data)
        if success:
            clear_cache(["repairs"])
        return success, error
    return False, "MySQL not available"


def get_active_repair_for_asset(asset_id):
    """Get active (WITH_VENDOR) repair record for an asset."""
    if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
        return mysql_get_active_repair(int(asset_id))
    return None


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
