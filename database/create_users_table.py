"""
Create Users Table
Run this to create the users table in the database
"""
import mysql.connector
from mysql.connector import Error
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import DB_CONFIG

def create_users_table():
    """Create the users table"""
    print("\n" + "=" * 50)
    print("CREATE USERS TABLE")
    print("=" * 50)

    try:
        conn = mysql.connector.connect(**DB_CONFIG, buffered=True)
        cursor = conn.cursor()

        print(f"\n[CONNECT] Connected to {DB_CONFIG['host']}/{DB_CONFIG['database']}")

        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100),
            role VARCHAR(20) DEFAULT 'operations',
            is_active BOOLEAN DEFAULT TRUE,
            last_login TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_username (username),
            INDEX idx_email (email),
            INDEX idx_role (role)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()

        print("[OK] Users table created successfully")

        # Verify
        cursor.execute("DESCRIBE users")
        columns = cursor.fetchall()
        print("\n[INFO] Table structure:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]}")

        cursor.close()
        conn.close()

        print("\n" + "=" * 50)
        print("DONE!")
        print("=" * 50)
        print("\nNow run: python database/create_admin.py")

        return True

    except Error as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == "__main__":
    create_users_table()
