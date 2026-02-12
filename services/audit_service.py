"""
Audit trail logging — extracted from app.py.
Handles state change logging, activity events, and audit summaries.
"""

import os
import hashlib
import logging
from datetime import datetime

import streamlit as st

from config.constants import STATUS_DISPLAY_NAMES, CRITICAL_ACTIONS

logger = logging.getLogger("AssetManagement")

# Database logging — conditionally available
try:
    from database.db import log_activity as db_log_activity
except ImportError:
    db_log_activity = None

DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql")


def _mysql_available():
    """Check if MySQL is available at runtime."""
    return db_log_activity is not None and DATA_SOURCE == "mysql"


def generate_audit_id() -> str:
    """Generate a unique, immutable audit ID for each log entry."""
    timestamp = datetime.now().isoformat()
    random_part = os.urandom(8).hex()
    raw = f"{timestamp}-{random_part}"
    return f"AUD-{hashlib.sha256(raw.encode()).hexdigest()[:12].upper()}"


def get_session_id() -> str:
    """Get or create a session ID for tracking."""
    if 'audit_session_id' not in st.session_state:
        st.session_state.audit_session_id = f"SES-{os.urandom(6).hex().upper()}"
    return st.session_state.audit_session_id


def log_state_change(serial_number, old_status, new_status, user_role, success, error_message=None, asset_id=None):
    """Log every state change attempt with timestamp"""

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
    if _mysql_available():
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
    if _mysql_available():
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
