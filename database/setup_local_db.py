"""
Local Database Setup Script
Run this after installing MySQL locally (or XAMPP)

Usage:
    python database/setup_local_db.py

This script will:
1. Connect to MySQL as root
2. Create the assetmgmt_db database
3. Create all required tables
4. Verify the setup
"""
import mysql.connector
from mysql.connector import Error
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_root_password():
    """Get MySQL root password from user"""
    print("\n" + "=" * 50)
    print("LOCAL MySQL DATABASE SETUP")
    print("=" * 50)
    print("\nThis script will create the database and tables.")
    print("You need MySQL root access.\n")

    password = input("Enter MySQL root password (press Enter if none): ").strip()
    return password

def create_database(cursor):
    """Create the database"""
    print("\n📦 Creating database 'assetmgmt_db'...")
    cursor.execute("CREATE DATABASE IF NOT EXISTS assetmgmt_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute("USE assetmgmt_db")
    print("   ✅ Database created")

def create_tables(cursor):
    """Create all tables"""
    print("\n📋 Creating tables...")

    # Read schema file
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')

    if os.path.exists(schema_path):
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()

        # Split by semicolons and execute each statement
        statements = schema.split(';')
        tables_created = 0

        for statement in statements:
            statement = statement.strip()
            if statement and not statement.startswith('--') and not statement.startswith('/*'):
                # Skip problematic statements for basic setup
                if 'DELIMITER' in statement or 'CREATE PROCEDURE' in statement:
                    continue
                if 'CREATE DATABASE' in statement or 'USE ' in statement.upper():
                    continue

                try:
                    cursor.execute(statement)
                    if 'CREATE TABLE' in statement.upper():
                        tables_created += 1
                except Error as e:
                    if 'already exists' not in str(e).lower():
                        print(f"   ⚠️ Warning: {e}")

        print(f"   ✅ Created {tables_created} tables")
    else:
        print("   ❌ Schema file not found. Creating basic tables...")
        create_basic_tables(cursor)

def create_basic_tables(cursor):
    """Create basic tables if schema file is missing"""

    # Assets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INT AUTO_INCREMENT PRIMARY KEY,
        serial_number VARCHAR(100) UNIQUE NOT NULL,
        asset_type VARCHAR(50) DEFAULT 'Laptop',
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
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("   ✅ assets table")

    # Clients table
    cursor.execute("""
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
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("   ✅ clients table")

    # Assignments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        asset_id INT,
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
        FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
        FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("   ✅ assignments table")

    # Issues table
    cursor.execute("""
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("   ✅ issues table")

    # Repairs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS repairs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        asset_id INT,
        repair_reference VARCHAR(100),
        sent_date DATE,
        return_date DATE,
        expected_return DATE,
        vendor_name VARCHAR(200),
        repair_description TEXT,
        repair_cost DECIMAL(10,2),
        status VARCHAR(50) DEFAULT 'WITH_VENDOR',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("   ✅ repairs table")

    # State change log table
    cursor.execute("""
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
        FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    print("   ✅ state_change_log table")

def verify_setup(cursor):
    """Verify the database setup"""
    print("\n🔍 Verifying setup...")

    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    print(f"\n   Tables in assetmgmt_db:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"   - {table[0]}: {count} records")

def main():
    """Main setup function"""
    password = get_root_password()

    try:
        # Connect to MySQL
        print("\n🔌 Connecting to MySQL...")
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=password
        )

        if conn.is_connected():
            print("   ✅ Connected to MySQL")

            cursor = conn.cursor()

            # Create database and tables
            create_database(cursor)
            create_tables(cursor)

            conn.commit()

            # Verify
            verify_setup(cursor)

            cursor.close()
            conn.close()

            print("\n" + "=" * 50)
            print("✅ DATABASE SETUP COMPLETE!")
            print("=" * 50)
            print("\nNext steps:")
            print("1. Update database/config.py if needed")
            print("   - Set root password if you have one")
            print("2. Set DATA_SOURCE=mysql in your .env file")
            print("3. Run migration: python database/migrate_data.py")
            print("4. Restart the Streamlit app")

    except Error as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("- Make sure MySQL is running")
        print("- Check if the root password is correct")
        print("- For XAMPP, the default root password is empty")
        return False

    return True

if __name__ == "__main__":
    main()
