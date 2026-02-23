"""
MySQL Database Utility Module
Provides functions for database operations similar to Airtable interface
"""
import logging
import mysql.connector
from mysql.connector import pooling, Error
import pandas as pd
from datetime import datetime, date
from typing import Optional, Dict, List, Any, Tuple
import streamlit as st

# Import configuration
try:
    from database.config import DB_CONFIG
except ImportError:
    from config import DB_CONFIG


def _query_to_df(query, conn, params=None):
    """Execute query and return DataFrame using cursor (avoids pandas SQLAlchemy warning)."""
    cursor = conn.cursor(dictionary=True)
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


class DatabaseConnection:
    """MySQL Database Connection Manager with Connection Pooling"""

    _pool = None

    @classmethod
    def get_pool(cls):
        """Get or create connection pool"""
        if cls._pool is None:
            try:
                cls._pool = pooling.MySQLConnectionPool(**DB_CONFIG)
            except Error as e:
                st.error(f"Failed to create connection pool: {e}")
                return None
        return cls._pool

    @classmethod
    def get_connection(cls):
        """Get a connection from the pool"""
        pool = cls.get_pool()
        if pool:
            try:
                return pool.get_connection()
            except Error as e:
                st.error(f"Failed to get connection: {e}")
        return None

    @classmethod
    def test_connection(cls) -> Tuple[bool, str]:
        """Test database connection"""
        try:
            conn = cls.get_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                conn.close()
                return True, "Connection successful"
            return False, "Could not establish connection"
        except Error as e:
            return False, str(e)


# ============================================
# ASSET FUNCTIONS
# ============================================

def get_all_assets() -> pd.DataFrame:
    """Fetch all assets from database"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        query = """
        SELECT
            id as _id,
            serial_number as `Serial Number`,
            asset_type as `Asset Type`,
            brand as `Brand`,
            model as `Model`,
            specs as `Specs`,
            touch_screen as `Touch Screen`,
            processor as `Processor`,
            ram_gb as `RAM (GB)`,
            storage_type as `Storage Type`,
            storage_gb as `Storage (GB)`,
            os_installed as `OS Installed`,
            office_license_key as `Office License Key`,
            device_password as `Password`,
            current_status as `Current Status`,
            current_location as `Current Location`,
            purchase_date as `Purchase Date`,
            purchase_price as `Purchase Price`,
            reuse_count as `Reuse Count`,
            notes as `Notes`,
            created_at,
            updated_at
        FROM assets
        ORDER BY updated_at DESC
        """
        df = _query_to_df(query, conn)
        return df
    except Error as e:
        st.error(f"Error fetching assets: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_asset_by_id(asset_id: int) -> Optional[Dict]:
    """Get a single asset by ID"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        # Convert numpy.int64 to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None
        cursor.execute("SELECT * FROM assets WHERE id = %s", (asset_id,))
        result = cursor.fetchone()
        cursor.close()
        return result
    except Error as e:
        st.error(f"Error fetching asset: {e}")
        return None
    finally:
        conn.close()


def get_asset_current_status_db(asset_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Get current status and serial number of an asset"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return None, None

    try:
        cursor = conn.cursor()
        # Convert numpy.int64 to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None
        cursor.execute(
            "SELECT current_status, serial_number FROM assets WHERE id = %s",
            (asset_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        if result:
            return result[0], result[1]
        return None, None
    except Error as e:
        return None, None
    finally:
        conn.close()


def create_asset(data: Dict) -> Tuple[bool, Optional[int], Optional[str]]:
    """Create a new asset"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Map field names to database columns
        # Supports both Airtable-style names and Excel import names
        field_mapping = {
            "Serial Number": "serial_number",
            "serial_number": "serial_number",  # Also accept db_field names
            "Asset Type": "asset_type",
            "asset_type": "asset_type",
            "Brand": "brand",
            "brand": "brand",
            "Model": "model",
            "model": "model",
            "Specs": "specs",
            "specs": "specs",
            "Touch Screen": "touch_screen",
            "touch_screen": "touch_screen",
            "Processor": "processor",
            "processor": "processor",
            "RAM (GB)": "ram_gb",
            "ram_gb": "ram_gb",
            "Storage Type": "storage_type",
            "storage_type": "storage_type",
            "Storage (GB)": "storage_gb",
            "storage_gb": "storage_gb",
            "OS Installed": "os_installed",
            "os_installed": "os_installed",
            "Office License Key": "office_license_key",
            "office_license_key": "office_license_key",
            "Password": "device_password",
            "Device Password": "device_password",  # Excel template uses this name
            "device_password": "device_password",
            "Current Status": "current_status",
            "current_status": "current_status",
            "Current Location": "current_location",
            "current_location": "current_location",
            "Purchase Date": "purchase_date",
            "purchase_date": "purchase_date",
            "Purchase Price": "purchase_price",
            "purchase_price": "purchase_price",
            "Notes": "notes",
            "notes": "notes"
        }

        # Build INSERT query
        columns = []
        values = []
        placeholders = []
        seen_columns = set()  # Track columns to avoid duplicates

        for input_field, db_column in field_mapping.items():
            if input_field in data and data[input_field] is not None:
                value = data[input_field]
                # Skip empty strings
                if isinstance(value, str) and not value.strip():
                    continue
                # Avoid duplicate columns
                if db_column not in seen_columns:
                    columns.append(db_column)
                    values.append(value)
                    placeholders.append("%s")
                    seen_columns.add(db_column)

        if not columns:
            # Provide more helpful error message
            provided_fields = [k for k, v in data.items() if v]
            if provided_fields:
                return False, None, f"No valid data mapped from fields: {', '.join(provided_fields[:5])}"
            return False, None, "No data provided"

        query = f"""
        INSERT INTO assets ({', '.join(columns)})
        VALUES ({', '.join(placeholders)})
        """

        cursor.execute(query, values)
        conn.commit()
        asset_id = cursor.lastrowid
        cursor.close()

        return True, asset_id, None
    except Error as e:
        return False, None, str(e)
    finally:
        conn.close()


def update_asset_status_db(asset_id: int, new_status: str, location: str = None) -> Tuple[bool, Optional[str]]:
    """Update asset status in database"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()
        # Convert numpy.int64 to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None

        if location:
            query = """
            UPDATE assets
            SET current_status = %s, current_location = %s, updated_at = NOW()
            WHERE id = %s
            """
            cursor.execute(query, (new_status, location, asset_id))
        else:
            query = """
            UPDATE assets
            SET current_status = %s, updated_at = NOW()
            WHERE id = %s
            """
            cursor.execute(query, (new_status, asset_id))

        conn.commit()
        affected = cursor.rowcount
        cursor.close()

        if affected > 0:
            return True, None
        return False, "Asset not found"
    except Error as e:
        return False, str(e)
    finally:
        conn.close()


def update_asset(asset_id: int, data: Dict) -> Tuple[bool, Optional[str]]:
    """Update asset fields"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()
        # Convert numpy.int64 to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None

        # Map Airtable field names to database columns
        field_mapping = {
            "Serial Number": "serial_number",
            "Asset Type": "asset_type",
            "Brand": "brand",
            "Model": "model",
            "Specs": "specs",
            "Touch Screen": "touch_screen",
            "Processor": "processor",
            "RAM (GB)": "ram_gb",
            "Storage Type": "storage_type",
            "Storage (GB)": "storage_gb",
            "OS Installed": "os_installed",
            "Office License Key": "office_license_key",
            "Password": "device_password",
            "Current Status": "current_status",
            "Current Location": "current_location",
            "Purchase Date": "purchase_date",
            "Purchase Price": "purchase_price",
            "Reuse Count": "reuse_count",
            "Notes": "notes"
        }

        # Build UPDATE query
        set_clauses = []
        values = []

        for airtable_field, db_column in field_mapping.items():
            if airtable_field in data:
                set_clauses.append(f"{db_column} = %s")
                values.append(data[airtable_field])

        if not set_clauses:
            return False, "No data to update"

        values.append(asset_id)
        query = f"""
        UPDATE assets
        SET {', '.join(set_clauses)}, updated_at = NOW()
        WHERE id = %s
        """

        cursor.execute(query, values)
        conn.commit()
        cursor.close()

        return True, None
    except Error as e:
        return False, str(e)
    finally:
        conn.close()


# ============================================
# CLIENT FUNCTIONS
# ============================================

def get_all_clients() -> pd.DataFrame:
    """Fetch all clients from database"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        query = """
        SELECT
            id as _id,
            client_name as `Client Name`,
            contact_person as `Contact Person`,
            email as `Email`,
            phone as `Phone`,
            address as `Address`,
            city as `City`,
            state as `State`,
            billing_rate as `Billing Rate`,
            status as `Status`,
            created_at,
            updated_at
        FROM clients
        WHERE status = 'ACTIVE'
        ORDER BY client_name
        """
        df = _query_to_df(query, conn)
        return df
    except Error as e:
        st.error(f"Error fetching clients: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def create_client(data: Dict) -> Tuple[bool, Optional[int], Optional[str]]:
    """Create a new client"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor()

        query = """
        INSERT INTO clients (client_name, contact_person, email, phone, address, city, state, billing_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data.get("Client Name"),
            data.get("Contact Person"),
            data.get("Email"),
            data.get("Phone"),
            data.get("Address"),
            data.get("City"),
            data.get("State"),
            data.get("Billing Rate", 0)
        ))

        conn.commit()
        client_id = cursor.lastrowid
        cursor.close()

        return True, client_id, None
    except Error as e:
        return False, None, str(e)
    finally:
        conn.close()


# ============================================
# ASSIGNMENT FUNCTIONS
# ============================================

def get_all_assignments() -> pd.DataFrame:
    """Fetch all assignments from database"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        query = """
        SELECT
            asn.id as _id,
            asn.assignment_name as `Assignment Name`,
            asn.assignment_type as `Assignment Type`,
            asn.shipment_date as `Shipment Date`,
            asn.return_date as `Return Date`,
            asn.tracking_number as `Tracking Number`,
            asn.monthly_rate as `Monthly Rate`,
            asn.status as `Status`,
            asn.notes as `Notes`,
            a.serial_number as `Serial Number`,
            c.client_name as `Client Name`
        FROM assignments asn
        LEFT JOIN assets a ON asn.asset_id = a.id
        LEFT JOIN clients c ON asn.client_id = c.id
        ORDER BY asn.created_at DESC
        """
        df = _query_to_df(query, conn)
        return df
    except Error as e:
        st.error(f"Error fetching assignments: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def create_assignment(data: Dict) -> Tuple[bool, Optional[int], Optional[str]]:
    """Create a new assignment"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Get asset_id from serial number if provided
        asset_id = data.get("asset_id")
        if not asset_id and data.get("Serial Number"):
            cursor.execute(
                "SELECT id FROM assets WHERE serial_number = %s",
                (data["Serial Number"],)
            )
            result = cursor.fetchone()
            if result:
                asset_id = result[0]

        # Get client_id from client name if provided
        client_id = data.get("client_id")
        if not client_id and data.get("Client Name"):
            cursor.execute(
                "SELECT id FROM clients WHERE client_name = %s",
                (data["Client Name"],)
            )
            result = cursor.fetchone()
            if result:
                client_id = result[0]

        # Convert numpy types to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None
        client_id = int(client_id) if client_id is not None else None

        query = """
        INSERT INTO assignments
            (asset_id, client_id, assignment_name, assignment_type, shipment_date, tracking_number, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            asset_id,
            client_id,
            data.get("Assignment Name"),
            data.get("Assignment Type", "Rental"),
            data.get("Shipment Date"),
            data.get("Tracking Number"),
            data.get("Status", "ACTIVE")
        ))

        conn.commit()
        assignment_id = cursor.lastrowid
        cursor.close()

        return True, assignment_id, None
    except Error as e:
        return False, None, str(e)
    finally:
        conn.close()


# ============================================
# ISSUE FUNCTIONS
# ============================================

def get_all_issues() -> pd.DataFrame:
    """Fetch all issues from database"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        query = """
        SELECT
            i.id as _id,
            i.issue_title as `Issue Title`,
            i.issue_type as `Issue Type`,
            i.issue_category as `Issue Category`,
            i.description as `Description`,
            i.reported_date as `Reported Date`,
            i.resolved_date as `Resolved Date`,
            i.severity as `Severity`,
            i.status as `Status`,
            a.serial_number as `Serial Number`
        FROM issues i
        LEFT JOIN assets a ON i.asset_id = a.id
        ORDER BY i.created_at DESC
        """
        df = _query_to_df(query, conn)
        return df
    except Error as e:
        st.error(f"Error fetching issues: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def create_issue(data: Dict) -> Tuple[bool, Optional[int], Optional[str]]:
    """Create a new issue"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Get asset_id from serial number if provided
        asset_id = data.get("asset_id")
        if not asset_id and data.get("Serial Number"):
            cursor.execute(
                "SELECT id FROM assets WHERE serial_number = %s",
                (data["Serial Number"],)
            )
            result = cursor.fetchone()
            if result:
                asset_id = result[0]

        # Convert numpy.int64 to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None

        query = """
        INSERT INTO issues
            (asset_id, issue_title, issue_type, issue_category, description, reported_date, severity, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            asset_id,
            data.get("Issue Title"),
            data.get("Issue Type"),
            data.get("Issue Category"),
            data.get("Description"),
            data.get("Reported Date"),
            data.get("Severity", "Medium"),
            data.get("Status", "Open")
        ))

        conn.commit()
        issue_id = cursor.lastrowid
        cursor.close()

        return True, issue_id, None
    except Error as e:
        return False, None, str(e)
    finally:
        conn.close()


# ============================================
# REPAIR FUNCTIONS
# ============================================

def get_all_repairs() -> pd.DataFrame:
    """Fetch all repairs from database"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        query = """
        SELECT
            r.id as _id,
            r.repair_reference as `Repair Reference`,
            r.sent_date as `Sent Date`,
            r.return_date as `Return Date`,
            r.expected_return as `Expected Return`,
            r.vendor_name as `Vendor Name`,
            r.repair_description as `Repair Description`,
            r.repair_cost as `Repair Cost`,
            r.repair_notes as `Repair Notes`,
            r.status as `Status`,
            a.serial_number as `Serial Number`
        FROM repairs r
        LEFT JOIN assets a ON r.asset_id = a.id
        ORDER BY r.created_at DESC
        """
        df = _query_to_df(query, conn)
        return df
    except Error as e:
        st.error(f"Error fetching repairs: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def create_repair(data: Dict) -> Tuple[bool, Optional[int], Optional[str]]:
    """Create a new repair record"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Get asset_id from serial number if provided
        asset_id = data.get("asset_id")
        if not asset_id and data.get("Serial Number"):
            cursor.execute(
                "SELECT id FROM assets WHERE serial_number = %s",
                (data["Serial Number"],)
            )
            result = cursor.fetchone()
            if result:
                asset_id = result[0]

        # Convert numpy.int64 to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None

        query = """
        INSERT INTO repairs
            (asset_id, repair_reference, sent_date, expected_return, repair_description, status, vendor_name, repair_cost)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            asset_id,
            data.get("Repair Reference"),
            data.get("Sent Date"),
            data.get("Expected Return"),
            data.get("Repair Description"),
            data.get("Status", "WITH_VENDOR"),
            data.get("Vendor Name"),
            data.get("Repair Cost")
        ))

        conn.commit()
        repair_id = cursor.lastrowid
        cursor.close()

        return True, repair_id, None
    except Error as e:
        return False, None, str(e)
    finally:
        conn.close()


def update_repair(repair_id: int, data: Dict) -> Tuple[bool, Optional[str]]:
    """Update repair record fields."""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()
        repair_id = int(repair_id) if repair_id is not None else None

        field_mapping = {
            "Repair Cost": "repair_cost",
            "Repair Notes": "repair_notes",
            "Return Date": "return_date",
            "Vendor Name": "vendor_name",
            "Status": "status",
            "Repair Description": "repair_description",
        }

        set_clauses = []
        values = []
        for display_field, db_column in field_mapping.items():
            if display_field in data:
                set_clauses.append(f"{db_column} = %s")
                values.append(data[display_field])

        if not set_clauses:
            return False, "No data to update"

        values.append(repair_id)
        query = f"UPDATE repairs SET {', '.join(set_clauses)}, updated_at = NOW() WHERE id = %s"
        cursor.execute(query, values)
        conn.commit()
        return True, None
    except Error as e:
        logging.error(f"update_repair error: {e}")
        return False, str(e)
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()


def get_active_repair_by_asset_id(asset_id: int) -> Optional[Dict]:
    """Find the active WITH_VENDOR repair record for an asset."""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        asset_id = int(asset_id) if asset_id is not None else None
        cursor.execute(
            "SELECT id, repair_reference, vendor_name, repair_cost FROM repairs WHERE asset_id = %s AND status = 'WITH_VENDOR' ORDER BY created_at DESC LIMIT 1",
            (asset_id,)
        )
        result = cursor.fetchone()
        return result
    except Error:
        return None
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()


# ============================================
# STATE CHANGE LOG FUNCTIONS
# ============================================

def log_state_change_db(
    asset_id: int,
    serial_number: str,
    old_status: str,
    new_status: str,
    user_role: str,
    success: bool,
    error_message: str = None
) -> bool:
    """Log state change to database"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        # Convert numpy.int64 to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None

        query = """
        INSERT INTO state_change_log
            (asset_id, serial_number, old_status, new_status, user_role, success, error_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            asset_id,
            serial_number,
            old_status,
            new_status,
            user_role,
            success,
            error_message
        ))
        conn.commit()
        cursor.close()
        return True
    except Error:
        return False
    finally:
        conn.close()


def get_state_change_log(limit: int = 100) -> pd.DataFrame:
    """Get recent state change logs"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        query = f"""
        SELECT * FROM state_change_log
        ORDER BY created_at DESC
        LIMIT {limit}
        """
        df = _query_to_df(query, conn)
        return df
    except Error as e:
        st.error(f"Error fetching logs: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


# ============================================
# UTILITY FUNCTIONS
# ============================================

def execute_query(query: str, params: tuple = None) -> Tuple[bool, Any, Optional[str]]:
    """Execute a custom query"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)

        if query.strip().upper().startswith("SELECT"):
            result = cursor.fetchall()
        else:
            conn.commit()
            result = cursor.rowcount

        cursor.close()
        return True, result, None
    except Error as e:
        return False, None, str(e)
    finally:
        conn.close()


# ============================================
# ACTIVITY LOG FUNCTIONS (IMMUTABLE AUDIT TRAIL)
# ============================================

# Action types for categorization
ACTION_TYPES = {
    "STATE_CHANGE": "State Change",
    "ASSET_CREATED": "Asset Created",
    "ASSET_UPDATED": "Asset Updated",
    "ASSIGNMENT_CREATED": "Assignment Created",
    "ASSIGNMENT_UPDATED": "Assignment Updated",
    "ASSIGNMENT_COMPLETED": "Assignment Completed",
    "ISSUE_CREATED": "Issue Created",
    "ISSUE_RESOLVED": "Issue Resolved",
    "REPAIR_CREATED": "Repair Created",
    "REPAIR_COMPLETED": "Repair Completed",
    "CLIENT_CREATED": "Client Created",
    "CLIENT_UPDATED": "Client Updated",
    "BILLING_GENERATED": "Billing Generated",
    "BILLING_PAID": "Billing Paid",
    "LOGIN": "Login",
    "ROLE_SWITCH": "Role Switch",
}

# Billing-related action types
BILLING_ACTIONS = [
    "ASSIGNMENT_CREATED", "ASSIGNMENT_COMPLETED",
    "BILLING_GENERATED", "BILLING_PAID",
    "STATE_CHANGE"  # Some state changes affect billing
]

# States that affect billing
BILLING_STATES = ["WITH_CLIENT", "RETURNED_FROM_CLIENT", "SOLD"]


def log_activity(
    action_type: str,
    action_category: str,
    user_role: str,
    asset_id: int = None,
    serial_number: str = None,
    client_id: int = None,
    client_name: str = None,
    old_value: str = None,
    new_value: str = None,
    description: str = None,
    user_identifier: str = None,
    success: bool = True,
    error_message: str = None,
    metadata: Dict = None
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Log an activity to the immutable audit trail.
    This is APPEND-ONLY - activities cannot be updated or deleted.
    """
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Convert numpy.int64 to Python int for MySQL compatibility
        asset_id = int(asset_id) if asset_id is not None else None
        client_id = int(client_id) if client_id is not None else None

        # Determine if this action has billing impact
        billing_impact = False
        if action_type in BILLING_ACTIONS:
            if action_type == "STATE_CHANGE":
                # Check if the state change involves billing states
                billing_impact = (old_value in BILLING_STATES or new_value in BILLING_STATES)
            else:
                billing_impact = True

        # Convert metadata to JSON string if provided
        import json
        metadata_json = json.dumps(metadata) if metadata else None

        query = """
        INSERT INTO activity_log (
            action_type, action_category, asset_id, serial_number,
            client_id, client_name, old_value, new_value,
            description, user_role, user_identifier, success,
            error_message, billing_impact, metadata
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        values = (
            action_type,
            action_category,
            asset_id,
            serial_number,
            client_id,
            client_name,
            old_value,
            new_value,
            description,
            user_role,
            user_identifier,
            success,
            error_message,
            billing_impact,
            metadata_json
        )

        cursor.execute(query, values)
        conn.commit()
        log_id = cursor.lastrowid
        cursor.close()

        return True, log_id, None
    except Error as e:
        return False, None, str(e)
    finally:
        conn.close()


def get_activity_log(
    limit: int = 50,
    role_filter: str = None,
    user_filter: str = None,
    category_filter: str = None,
    billing_only: bool = False,
    success_only: bool = None,
    asset_id: int = None,
    days_back: int = None
) -> pd.DataFrame:
    """
    Retrieve activity log entries with various filters.

    Parameters:
    - limit: Maximum records to return
    - role_filter: Filter by user role (e.g., 'admin', 'operations')
    - user_filter: Filter by user identifier
    - category_filter: Filter by action category
    - billing_only: If True, only return billing-related activities
    - success_only: If True/False, filter by success status
    - asset_id: Filter by specific asset
    - days_back: Only show activities from last N days
    """
    conn = DatabaseConnection.get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        conditions = []
        params = []

        if role_filter:
            conditions.append("user_role = %s")
            params.append(role_filter)

        if user_filter:
            conditions.append("user_identifier = %s")
            params.append(user_filter)

        if category_filter:
            conditions.append("action_category = %s")
            params.append(category_filter)

        if billing_only:
            conditions.append("billing_impact = TRUE")

        if success_only is not None:
            conditions.append("success = %s")
            params.append(success_only)

        if asset_id:
            conditions.append("asset_id = %s")
            params.append(asset_id)

        if days_back:
            conditions.append("created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)")
            params.append(days_back)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
        SELECT
            id,
            action_type as `Action`,
            action_category as `Category`,
            serial_number as `Asset`,
            client_name as `Client`,
            old_value as `From`,
            new_value as `To`,
            description as `Description`,
            user_role as `Role`,
            user_identifier as `User`,
            success as `Success`,
            error_message as `Error`,
            billing_impact as `Billing Impact`,
            created_at as `Timestamp`
        FROM activity_log
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s
        """
        params.append(limit)

        df = _query_to_df(query, conn, params=params)
        return df
    except Error as e:
        st.error(f"Error fetching activity log: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_activity_stats(days_back: int = 7) -> Dict:
    """Get activity statistics for the dashboard"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return {}

    try:
        cursor = conn.cursor(dictionary=True)
        stats = {}

        # Total activities in period
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM activity_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """, (days_back,))
        stats['total_activities'] = cursor.fetchone()['total']

        # Activities by type
        cursor.execute("""
            SELECT action_type, COUNT(*) as count
            FROM activity_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY action_type
            ORDER BY count DESC
            LIMIT 5
        """, (days_back,))
        stats['by_type'] = {row['action_type']: row['count'] for row in cursor.fetchall()}

        # Activities by role
        cursor.execute("""
            SELECT user_role, COUNT(*) as count
            FROM activity_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY user_role
        """, (days_back,))
        stats['by_role'] = {row['user_role']: row['count'] for row in cursor.fetchall()}

        # Failed activities
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM activity_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            AND success = FALSE
        """, (days_back,))
        stats['failed'] = cursor.fetchone()['count']

        # Billing-related activities
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM activity_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            AND billing_impact = TRUE
        """, (days_back,))
        stats['billing_related'] = cursor.fetchone()['count']

        cursor.close()
        return stats
    except Error as e:
        return {}
    finally:
        conn.close()


def get_dashboard_stats() -> Dict:
    """Get dashboard statistics"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return {}

    try:
        cursor = conn.cursor(dictionary=True)

        stats = {}

        # Asset counts by status
        cursor.execute("""
            SELECT current_status, COUNT(*) as count
            FROM assets
            GROUP BY current_status
        """)
        status_counts = {row['current_status']: row['count'] for row in cursor.fetchall()}
        stats['status_counts'] = status_counts
        stats['total_assets'] = sum(status_counts.values())

        # Client count
        cursor.execute("SELECT COUNT(*) as count FROM clients WHERE status = 'ACTIVE'")
        stats['total_clients'] = cursor.fetchone()['count']

        # Open issues
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE status = 'Open'")
        stats['open_issues'] = cursor.fetchone()['count']

        # Active repairs
        cursor.execute("SELECT COUNT(*) as count FROM repairs WHERE status = 'WITH_VENDOR'")
        stats['active_repairs'] = cursor.fetchone()['count']

        cursor.close()
        return stats
    except Error as e:
        st.error(f"Error fetching stats: {e}")
        return {}
    finally:
        conn.close()


# ============================================
# BILLING PERIOD FUNCTIONS
# ============================================

def get_billing_period(year: int, month: int) -> Optional[Dict]:
    """Get billing period record for a specific month."""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM billing_periods WHERE period_year = %s AND period_month = %s",
            (year, month)
        )
        result = cursor.fetchone()
        cursor.close()
        return result
    except Error:
        return None
    finally:
        conn.close()


def get_billing_period_status(year: int, month: int) -> str:
    """
    Check if a billing period is open or closed.
    Returns 'OPEN' or 'CLOSED'.
    """
    period = get_billing_period(year, month)
    if period:
        return period.get('status', 'OPEN')
    return 'OPEN'  # Default to open if no record exists


def is_billing_period_closed(year: int, month: int) -> bool:
    """Check if a billing period is closed."""
    return get_billing_period_status(year, month) == 'CLOSED'


def get_all_billing_periods(limit: int = 24) -> pd.DataFrame:
    """Get all billing periods with their status."""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        query = """
        SELECT
            id,
            period_year as `Year`,
            period_month as `Month`,
            status as `Status`,
            total_revenue as `Revenue`,
            total_assets as `Assets`,
            closed_by as `Closed By`,
            closed_at as `Closed At`,
            notes as `Notes`
        FROM billing_periods
        ORDER BY period_year DESC, period_month DESC
        LIMIT %s
        """
        df = _query_to_df(query, conn, params=(limit,))
        return df
    except Error:
        return pd.DataFrame()
    finally:
        conn.close()


def close_billing_period(
    year: int,
    month: int,
    closed_by: str,
    total_revenue: float = 0,
    total_assets: int = 0,
    notes: str = None
) -> Tuple[bool, Optional[str]]:
    """
    Close a billing period. Only creates/updates the period record.
    Returns (success, error_message).
    """
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Check if period exists
        existing = get_billing_period(year, month)

        if existing:
            # Update existing period
            if existing['status'] == 'CLOSED':
                return False, f"Period {month}/{year} is already closed"

            cursor.execute("""
                UPDATE billing_periods
                SET status = 'CLOSED',
                    closed_by = %s,
                    closed_at = NOW(),
                    total_revenue = %s,
                    total_assets = %s,
                    notes = %s
                WHERE period_year = %s AND period_month = %s
            """, (closed_by, total_revenue, total_assets, notes, year, month))
        else:
            # Create new period record
            cursor.execute("""
                INSERT INTO billing_periods
                    (period_year, period_month, status, closed_by, closed_at, total_revenue, total_assets, notes)
                VALUES (%s, %s, 'CLOSED', %s, NOW(), %s, %s, %s)
            """, (year, month, closed_by, total_revenue, total_assets, notes))

        conn.commit()
        cursor.close()
        return True, None
    except Error as e:
        return False, str(e)
    finally:
        conn.close()


def reopen_billing_period(
    year: int,
    month: int,
    reopened_by: str,
    notes: str = None
) -> Tuple[bool, Optional[str]]:
    """
    Reopen a closed billing period. Admin-only operation.
    Returns (success, error_message).
    """
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Check if period exists and is closed
        existing = get_billing_period(year, month)

        if not existing:
            return False, f"Period {month}/{year} not found"

        if existing['status'] == 'OPEN':
            return False, f"Period {month}/{year} is already open"

        # Reopen the period
        cursor.execute("""
            UPDATE billing_periods
            SET status = 'OPEN',
                reopened_by = %s,
                reopened_at = NOW(),
                notes = CONCAT(COALESCE(notes, ''), '\nReopened: ', %s)
            WHERE period_year = %s AND period_month = %s
        """, (reopened_by, notes or 'Admin override', year, month))

        conn.commit()
        cursor.close()
        return True, None
    except Error as e:
        return False, str(e)
    finally:
        conn.close()


def can_modify_billing_data(transaction_date, user_role: str) -> Tuple[bool, str]:
    """
    Check if billing data for a given date can be modified.

    Args:
        transaction_date: The date of the transaction (datetime, date, or string)
        user_role: The user's role

    Returns:
        Tuple of (can_modify: bool, reason: str)
    """
    from datetime import datetime, date

    # Parse date if string
    if isinstance(transaction_date, str):
        try:
            transaction_date = datetime.strptime(transaction_date[:10], "%Y-%m-%d").date()
        except:
            return True, "Could not parse date, allowing modification"

    if isinstance(transaction_date, datetime):
        transaction_date = transaction_date.date()

    year = transaction_date.year
    month = transaction_date.month

    # Check if period is closed
    if is_billing_period_closed(year, month):
        if user_role == 'admin':
            return True, "Period is closed but admin override allowed"
        return False, f"Billing period {month}/{year} is closed. Contact admin to modify."

    return True, "Period is open"


def get_current_billing_period() -> Dict:
    """Get the current month's billing period info."""
    from datetime import datetime
    now = datetime.now()
    period = get_billing_period(now.year, now.month)

    if period:
        return {
            "year": now.year,
            "month": now.month,
            "status": period['status'],
            "closed_at": period.get('closed_at'),
            "closed_by": period.get('closed_by')
        }

    return {
        "year": now.year,
        "month": now.month,
        "status": "OPEN",
        "closed_at": None,
        "closed_by": None
    }


# ============================================
# DATABASE SETUP / INITIALIZATION
# ============================================

def setup_database() -> Tuple[bool, str]:
    """Create all required tables if they don't exist"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, "Could not connect to database"

    try:
        cursor = conn.cursor()

        # Create tables
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS assets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                serial_number VARCHAR(100) UNIQUE NOT NULL,
                asset_type VARCHAR(50) NOT NULL DEFAULT 'Laptop',
                brand VARCHAR(50),
                model VARCHAR(100),
                specs TEXT,
                touch_screen BOOLEAN DEFAULT FALSE,
                processor VARCHAR(100),
                ram_gb INT,
                storage_type VARCHAR(20),
                storage_gb INT,
                os_installed VARCHAR(50),
                office_license_key VARCHAR(100),
                device_password VARCHAR(100),
                current_status VARCHAR(50) DEFAULT 'IN_STOCK_WORKING',
                current_location VARCHAR(200),
                purchase_date DATE,
                purchase_price DECIMAL(12,2),
                reuse_count INT DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_status (current_status),
                INDEX idx_serial (serial_number)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INT AUTO_INCREMENT PRIMARY KEY,
                client_name VARCHAR(200) NOT NULL,
                contact_person VARCHAR(100),
                email VARCHAR(100),
                phone VARCHAR(20),
                address TEXT,
                city VARCHAR(100),
                state VARCHAR(100),
                billing_rate DECIMAL(10,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_client_name (client_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS assignments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                asset_id INT NOT NULL,
                client_id INT,
                assignment_name VARCHAR(200),
                assignment_type VARCHAR(50) DEFAULT 'Rental',
                shipment_date DATE,
                return_date DATE,
                tracking_number VARCHAR(100),
                monthly_rate DECIMAL(10,2),
                status VARCHAR(50) DEFAULT 'ACTIVE',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_asset (asset_id),
                INDEX idx_client (client_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS issues (
                id INT AUTO_INCREMENT PRIMARY KEY,
                asset_id INT,
                issue_title VARCHAR(200),
                issue_type VARCHAR(50),
                issue_category VARCHAR(100),
                description TEXT,
                reported_date DATE,
                resolved_date DATE,
                severity VARCHAR(20) DEFAULT 'Medium',
                status VARCHAR(50) DEFAULT 'Open',
                resolution_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_asset (asset_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS repairs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                asset_id INT,
                repair_reference VARCHAR(100) UNIQUE,
                sent_date DATE,
                return_date DATE,
                expected_return DATE,
                vendor_name VARCHAR(200),
                repair_description TEXT,
                repair_cost DECIMAL(10,2),
                status VARCHAR(50) DEFAULT 'WITH_VENDOR',
                repair_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_asset (asset_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS state_change_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                asset_id INT,
                serial_number VARCHAR(100),
                old_status VARCHAR(50),
                new_status VARCHAR(50),
                changed_by VARCHAR(50),
                user_role VARCHAR(20),
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_asset (asset_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS activity_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                action_type VARCHAR(50) NOT NULL,
                action_category VARCHAR(30) NOT NULL,
                asset_id INT,
                serial_number VARCHAR(100),
                client_id INT,
                client_name VARCHAR(200),
                old_value VARCHAR(100),
                new_value VARCHAR(100),
                description TEXT,
                user_role VARCHAR(20) NOT NULL,
                user_identifier VARCHAR(100),
                ip_address VARCHAR(45),
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                billing_impact BOOLEAN DEFAULT FALSE,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_action_type (action_type),
                INDEX idx_asset (asset_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS billing_periods (
                id INT AUTO_INCREMENT PRIMARY KEY,
                period_year INT NOT NULL,
                period_month INT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
                closed_by VARCHAR(100),
                closed_at TIMESTAMP NULL,
                reopened_by VARCHAR(100),
                reopened_at TIMESTAMP NULL,
                total_revenue DECIMAL(12,2) DEFAULT 0,
                total_assets INT DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY idx_period (period_year, period_month)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS billing_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                client_id INT NOT NULL,
                billing_month DATE NOT NULL,
                total_assets INT DEFAULT 0,
                total_amount DECIMAL(12,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'PENDING',
                invoice_number VARCHAR(50),
                paid_date DATE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_client (client_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                role VARCHAR(20) DEFAULT 'operations',
                is_active BOOLEAN DEFAULT TRUE,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS import_mapping_profiles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                profile_name VARCHAR(100) NOT NULL UNIQUE,
                mapping JSON NOT NULL,
                created_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        ]

        created_tables = []
        for sql in tables_sql:
            try:
                cursor.execute(sql)
                # Extract table name from SQL
                table_name = sql.split("CREATE TABLE IF NOT EXISTS")[1].split("(")[0].strip()
                created_tables.append(table_name)
            except Error as e:
                print(f"Error creating table: {e}")

        conn.commit()
        cursor.close()
        conn.close()

        return True, f"Successfully created/verified {len(created_tables)} tables: {', '.join(created_tables)}"

    except Error as e:
        return False, f"Database setup error: {str(e)}"


def get_import_profiles() -> List[Dict]:
    """Return all saved column mapping profiles."""
    import json as _json
    conn = DatabaseConnection.get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, profile_name, mapping, created_by, created_at FROM import_mapping_profiles ORDER BY profile_name"
        )
        rows = cursor.fetchall()
        for row in rows:
            if isinstance(row.get("mapping"), str):
                try:
                    row["mapping"] = _json.loads(row["mapping"])
                except Exception:
                    row["mapping"] = {}
        return rows
    except Error as e:
        logging.error(f"get_import_profiles error: {e}")
        return []
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()


def save_import_profile(profile_name: str, mapping_dict: Dict, created_by: str = "") -> Tuple[bool, Optional[str]]:
    """Upsert a column mapping profile by name. Returns (success, error_msg)."""
    import json as _json
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, "Database connection failed"
    try:
        cursor = conn.cursor()
        mapping_json = _json.dumps(mapping_dict)
        cursor.execute(
            """
            INSERT INTO import_mapping_profiles (profile_name, mapping, created_by)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE mapping = VALUES(mapping), updated_at = CURRENT_TIMESTAMP
            """,
            (profile_name.strip(), mapping_json, created_by)
        )
        conn.commit()
        return True, None
    except Error as e:
        logging.error(f"save_import_profile error: {e}")
        return False, str(e)
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()


def delete_import_profile(profile_id: int) -> bool:
    """Delete a column mapping profile by id."""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM import_mapping_profiles WHERE id = %s", (profile_id,))
        conn.commit()
        return True
    except Error as e:
        logging.error(f"delete_import_profile error: {e}")
        return False
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()


def check_tables_exist() -> Tuple[bool, List[str]]:
    """Check which tables exist in the database"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return False, []

    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return True, tables
    except Error as e:
        return False, []


def get_table_stats() -> Dict[str, int]:
    """Get row counts for all tables"""
    conn = DatabaseConnection.get_connection()
    if not conn:
        return {}

    try:
        cursor = conn.cursor()
        stats = {}
        tables = ['assets', 'clients', 'assignments', 'issues', 'repairs',
                  'state_change_log', 'activity_log', 'billing_periods', 'billing_records', 'users']

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[table] = count
            except:
                stats[table] = -1  # Table doesn't exist

        cursor.close()
        conn.close()
        return stats
    except Error as e:
        return {}
