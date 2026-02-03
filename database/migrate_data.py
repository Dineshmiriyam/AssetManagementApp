"""
Data Migration Script: Airtable -> MySQL
Run this script to migrate all data from Airtable to MySQL

Usage:
    python database/migrate_data.py

Prerequisites:
    1. MySQL database created with schema.sql
    2. Database credentials configured in config.py
    3. Airtable API key configured in .env file
"""
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file from parent directory
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

from pyairtable import Api
import mysql.connector
from mysql.connector import Error

# Configuration
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")

# Import MySQL config
from config import DB_CONFIG


def get_airtable_api():
    """Get Airtable API instance"""
    if not AIRTABLE_API_KEY or AIRTABLE_API_KEY == "your_airtable_api_key":
        print("ERROR: AIRTABLE_API_KEY not configured")
        return None
    return Api(AIRTABLE_API_KEY)


def get_mysql_connection():
    """Get MySQL connection"""
    try:
        # Remove pool settings for single connection
        config = {k: v for k, v in DB_CONFIG.items()
                  if k not in ['pool_name', 'pool_size']}
        conn = mysql.connector.connect(**config)
        return conn
    except Error as e:
        print(f"ERROR: MySQL connection failed: {e}")
        return None


def migrate_assets(api, conn):
    """Migrate assets from Airtable to MySQL"""
    print("\n[+] Migrating Assets...")

    try:
        # Get Airtable data
        base = api.base(AIRTABLE_BASE_ID)
        table = base.table("Assets")
        records = table.all()

        print(f"   Found {len(records)} assets in Airtable")

        cursor = conn.cursor()
        migrated = 0
        skipped = 0

        for record in records:
            fields = record.get('fields', {})

            try:
                # Check if asset already exists
                cursor.execute(
                    "SELECT id FROM assets WHERE serial_number = %s",
                    (fields.get('Serial Number'),)
                )
                if cursor.fetchone():
                    skipped += 1
                    continue

                # Insert asset
                query = """
                INSERT INTO assets (
                    serial_number, asset_type, brand, model, specs,
                    touch_screen, processor, ram_gb, storage_type, storage_gb,
                    os_installed, office_license_key, device_password,
                    current_status, current_location, purchase_date,
                    purchase_price, reuse_count, notes
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """

                values = (
                    fields.get('Serial Number'),
                    fields.get('Asset Type', 'Laptop'),
                    fields.get('Brand'),
                    fields.get('Model'),
                    fields.get('Specs'),
                    fields.get('Touch Screen', False),
                    fields.get('Processor'),
                    fields.get('RAM (GB)'),
                    fields.get('Storage Type'),
                    fields.get('Storage (GB)'),
                    fields.get('OS Installed'),
                    fields.get('Office License Key'),
                    fields.get('Password'),
                    fields.get('Current Status', 'IN_STOCK_WORKING'),
                    fields.get('Current Location'),
                    fields.get('Purchase Date'),
                    fields.get('Purchase Price'),
                    fields.get('Reuse Count', 0),
                    fields.get('Notes')
                )

                cursor.execute(query, values)
                migrated += 1

            except Error as e:
                print(f"   [!] Error migrating asset {fields.get('Serial Number')}: {e}")

        conn.commit()
        cursor.close()
        print(f"   [OK] Migrated: {migrated}, Skipped (duplicates): {skipped}")
        return True

    except Exception as e:
        print(f"   [X] Migration failed: {e}")
        return False


def migrate_clients(api, conn):
    """Migrate clients from Airtable to MySQL"""
    print("\n[+] Migrating Clients...")

    try:
        base = api.base(AIRTABLE_BASE_ID)
        table = base.table("Clients")
        records = table.all()

        print(f"   Found {len(records)} clients in Airtable")

        cursor = conn.cursor()
        migrated = 0
        skipped = 0

        for record in records:
            fields = record.get('fields', {})

            try:
                # Check if client already exists
                cursor.execute(
                    "SELECT id FROM clients WHERE client_name = %s",
                    (fields.get('Client Name'),)
                )
                if cursor.fetchone():
                    skipped += 1
                    continue

                query = """
                INSERT INTO clients (
                    client_name, contact_person, email, phone, address
                ) VALUES (%s, %s, %s, %s, %s)
                """

                values = (
                    fields.get('Client Name'),
                    fields.get('Contact Person'),
                    fields.get('Email'),
                    fields.get('Phone'),
                    fields.get('Address')
                )

                cursor.execute(query, values)
                migrated += 1

            except Error as e:
                print(f"   [!] Error migrating client {fields.get('Client Name')}: {e}")

        conn.commit()
        cursor.close()
        print(f"   [OK] Migrated: {migrated}, Skipped (duplicates): {skipped}")
        return True

    except Exception as e:
        print(f"   [X] Migration failed: {e}")
        return False


def migrate_issues(api, conn):
    """Migrate issues from Airtable to MySQL"""
    print("\n[+] Migrating Issues...")

    try:
        base = api.base(AIRTABLE_BASE_ID)
        table = base.table("Issues")
        records = table.all()

        print(f"   Found {len(records)} issues in Airtable")

        cursor = conn.cursor()
        migrated = 0

        for record in records:
            fields = record.get('fields', {})

            try:
                # Get asset_id from serial number
                asset_id = None
                if fields.get('Serial Number'):
                    cursor.execute(
                        "SELECT id FROM assets WHERE serial_number = %s",
                        (fields.get('Serial Number'),)
                    )
                    result = cursor.fetchone()
                    if result:
                        asset_id = result[0]

                query = """
                INSERT INTO issues (
                    asset_id, issue_title, issue_type, issue_category,
                    description, reported_date, severity, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """

                values = (
                    asset_id,
                    fields.get('Issue Title'),
                    fields.get('Issue Type'),
                    fields.get('Issue Category'),
                    fields.get('Description'),
                    fields.get('Reported Date'),
                    fields.get('Severity', 'Medium'),
                    fields.get('Status', 'Open')
                )

                cursor.execute(query, values)
                migrated += 1

            except Error as e:
                print(f"   [!] Error migrating issue: {e}")

        conn.commit()
        cursor.close()
        print(f"   [OK] Migrated: {migrated}")
        return True

    except Exception as e:
        print(f"   [X] Migration failed: {e}")
        return False


def migrate_repairs(api, conn):
    """Migrate repairs from Airtable to MySQL"""
    print("\n[+] Migrating Repairs...")

    try:
        base = api.base(AIRTABLE_BASE_ID)
        table = base.table("Repairs")
        records = table.all()

        print(f"   Found {len(records)} repairs in Airtable")

        cursor = conn.cursor()
        migrated = 0

        for record in records:
            fields = record.get('fields', {})

            try:
                query = """
                INSERT INTO repairs (
                    repair_reference, sent_date, expected_return,
                    repair_description, status
                ) VALUES (%s, %s, %s, %s, %s)
                """

                values = (
                    fields.get('Repair Reference'),
                    fields.get('Sent Date'),
                    fields.get('Expected Return'),
                    fields.get('Repair Description'),
                    fields.get('Status', 'WITH_VENDOR')
                )

                cursor.execute(query, values)
                migrated += 1

            except Error as e:
                print(f"   [!] Error migrating repair: {e}")

        conn.commit()
        cursor.close()
        print(f"   [OK] Migrated: {migrated}")
        return True

    except Exception as e:
        print(f"   [X] Migration failed: {e}")
        return False


def migrate_assignments(api, conn):
    """Migrate assignments from Airtable to MySQL"""
    print("\n[+] Migrating Assignments...")

    try:
        base = api.base(AIRTABLE_BASE_ID)
        table = base.table("Assignments")
        records = table.all()

        print(f"   Found {len(records)} assignments in Airtable")

        cursor = conn.cursor()
        migrated = 0

        for record in records:
            fields = record.get('fields', {})

            try:
                # Get asset_id and client_id
                asset_id = None
                client_id = None

                # Parse assignment name to get serial and client
                assignment_name = fields.get('Assignment Name', '')
                if ' -> ' in assignment_name:
                    serial, client_name = assignment_name.split(' -> ', 1)

                    cursor.execute(
                        "SELECT id FROM assets WHERE serial_number = %s",
                        (serial,)
                    )
                    result = cursor.fetchone()
                    if result:
                        asset_id = result[0]

                    cursor.execute(
                        "SELECT id FROM clients WHERE client_name = %s",
                        (client_name,)
                    )
                    result = cursor.fetchone()
                    if result:
                        client_id = result[0]

                query = """
                INSERT INTO assignments (
                    asset_id, client_id, assignment_name, assignment_type,
                    shipment_date, tracking_number, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """

                values = (
                    asset_id,
                    client_id,
                    fields.get('Assignment Name'),
                    fields.get('Assignment Type', 'Rental'),
                    fields.get('Shipment Date'),
                    fields.get('Tracking Number'),
                    fields.get('Status', 'ACTIVE')
                )

                cursor.execute(query, values)
                migrated += 1

            except Error as e:
                print(f"   [!] Error migrating assignment: {e}")

        conn.commit()
        cursor.close()
        print(f"   [OK] Migrated: {migrated}")
        return True

    except Exception as e:
        print(f"   [X] Migration failed: {e}")
        return False


def verify_migration(conn):
    """Verify migration counts"""
    print("\n[*] Verifying Migration...")

    cursor = conn.cursor()

    tables = ['assets', 'clients', 'issues', 'repairs', 'assignments']

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {table}: {count} records")

    cursor.close()


def main():
    """Main migration function"""
    print("=" * 50)
    print("AIRTABLE -> MYSQL DATA MIGRATION")
    print("=" * 50)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Get connections
    api = get_airtable_api()
    if not api:
        print("\n[X] Cannot connect to Airtable. Check API key.")
        return

    conn = get_mysql_connection()
    if not conn:
        print("\n[X] Cannot connect to MySQL. Check credentials.")
        return

    print("\n[OK] Connected to both databases")

    # Run migrations in order (respecting foreign keys)
    success = True

    success = migrate_assets(api, conn) and success
    success = migrate_clients(api, conn) and success
    success = migrate_issues(api, conn) and success
    success = migrate_repairs(api, conn) and success
    success = migrate_assignments(api, conn) and success

    # Verify
    verify_migration(conn)

    # Close connection
    conn.close()

    print("\n" + "=" * 50)
    if success:
        print("[OK] MIGRATION COMPLETED SUCCESSFULLY")
        print("\nNext steps:")
        print("1. Update database/config.py with DATA_SOURCE = 'mysql'")
        print("2. Restart the Streamlit app")
        print("3. Verify data in the app")
    else:
        print("[!] MIGRATION COMPLETED WITH ERRORS")
        print("Check the log above for details")

    print("=" * 50)


if __name__ == "__main__":
    main()
