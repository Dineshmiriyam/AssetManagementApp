"""
Client operations — service layer.
Handles CRUD for clients and contacts with audit logging and cache invalidation.
"""

import os
import logging

import streamlit as st

from core.data import clear_cache
from services.audit_service import log_activity_event

logger = logging.getLogger("AssetManagement")

# Database functions — conditionally available
try:
    from database.db import (
        create_client as mysql_create_client,
        update_client as mysql_update_client,
        get_client_by_id as mysql_get_client,
        get_client_contacts as mysql_get_contacts,
        create_contact as mysql_create_contact,
        update_contact as mysql_update_contact,
        delete_contact as mysql_delete_contact,
    )
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False

DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql")
MYSQL_AVAILABLE = _DB_AVAILABLE and DATA_SOURCE == "mysql"


def create_client_record(data, user_role="admin"):
    """
    Create a new client. If Contact Person is provided, also creates
    a primary contact entry in client_contacts.
    Returns (success, client_id, error).
    """
    if not MYSQL_AVAILABLE:
        return False, None, "MySQL not available"

    success, client_id, error = mysql_create_client(data)
    if success:
        clear_cache(["clients"])

        # If contact person provided, create primary contact record
        contact_name = data.get("Contact Person")
        if contact_name:
            mysql_create_contact({
                "client_id": client_id,
                "contact_name": contact_name,
                "contact_role": "Primary",
                "email": data.get("Email"),
                "phone": data.get("Phone"),
                "is_primary": True,
            })

        log_activity_event(
            action_type="CLIENT_CREATED",
            category="client",
            user_role=user_role,
            description=f"Client created: {data.get('Client Name', 'N/A')}",
            client_name=data.get("Client Name"),
            success=True
        )
    return success, client_id, error


def update_client_record(client_id, data, user_role="admin"):
    """Update an existing client record."""
    if not MYSQL_AVAILABLE:
        return False, "MySQL not available"

    success, error = mysql_update_client(int(client_id), data)
    if success:
        clear_cache(["clients"])
        log_activity_event(
            action_type="CLIENT_UPDATED",
            category="client",
            user_role=user_role,
            description=f"Client updated: {data.get('Client Name', 'ID ' + str(client_id))}",
            client_name=data.get("Client Name"),
            success=True
        )
    return success, error


def add_contact(client_id, data, user_role="admin"):
    """
    Add a new contact for a client.
    Returns (success, contact_id, error).
    """
    if not MYSQL_AVAILABLE:
        return False, None, "MySQL not available"

    data["client_id"] = int(client_id)
    success, contact_id, error = mysql_create_contact(data)
    if success:
        clear_cache(["clients"])
        log_activity_event(
            action_type="CONTACT_ADDED",
            category="client",
            user_role=user_role,
            description=f"Contact added: {data.get('contact_name', 'N/A')} ({data.get('contact_role', 'Primary')})",
            success=True
        )
    return success, contact_id, error


def update_contact_record(contact_id, data, user_role="admin"):
    """Update a contact record."""
    if not MYSQL_AVAILABLE:
        return False, "MySQL not available"

    success, error = mysql_update_contact(int(contact_id), data)
    if success:
        clear_cache(["clients"])
    return success, error


def remove_contact(contact_id, user_role="admin"):
    """Delete a contact."""
    if not MYSQL_AVAILABLE:
        return False, "MySQL not available"

    success, error = mysql_delete_contact(int(contact_id))
    if success:
        clear_cache(["clients"])
        log_activity_event(
            action_type="CONTACT_DELETED",
            category="client",
            user_role=user_role,
            description=f"Contact deleted (ID: {contact_id})",
            success=True
        )
    return success, error
