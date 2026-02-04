"""
Migration: Add Security Columns to Users Table
Adds columns for rate limiting, session management, and audit tracking

Run this script to update your database schema:
    python database/migrate_auth_security.py
"""
import mysql.connector
from mysql.connector import Error
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import DB_CONFIG

def get_connection():
    """Get database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG, buffered=True)
        return conn
    except Error as e:
        print(f"[ERROR] Connection failed: {e}")
        return None

def column_exists(cursor, table, column):
    """Check if a column exists in a table"""
    cursor.execute(f"""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """, (DB_CONFIG.get('database', 'railway'), table, column))
    return cursor.fetchone()[0] > 0

def migrate():
    """Run migration to add security columns"""
    print("\n" + "=" * 60)
    print("SECURITY MIGRATION: Adding auth security columns")
    print("=" * 60)

    conn = get_connection()
    if not conn:
        print("[ERROR] Could not connect to database")
        return False

    try:
        cursor = conn.cursor()

        # List of columns to add
        columns_to_add = [
            ("failed_login_attempts", "INT DEFAULT 0"),
            ("last_failed_login", "TIMESTAMP NULL"),
            ("account_locked_until", "TIMESTAMP NULL"),
            ("session_token_hash", "VARCHAR(64) NULL"),
            ("session_created_at", "TIMESTAMP NULL"),
        ]

        added = 0
        skipped = 0

        for column_name, column_def in columns_to_add:
            if column_exists(cursor, 'users', column_name):
                print(f"   [SKIP] Column '{column_name}' already exists")
                skipped += 1
            else:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
                    print(f"   [OK] Added column '{column_name}'")
                    added += 1
                except Error as e:
                    print(f"   [ERROR] Failed to add '{column_name}': {e}")

        conn.commit()

        # Add index for session token lookup
        try:
            cursor.execute("""
                CREATE INDEX idx_session_token ON users(session_token_hash)
            """)
            print("   [OK] Added index 'idx_session_token'")
        except Error as e:
            if "Duplicate key name" in str(e):
                print("   [SKIP] Index 'idx_session_token' already exists")
            else:
                print(f"   [WARN] Index creation: {e}")

        cursor.close()
        conn.close()

        print("\n" + "-" * 60)
        print(f"Migration complete: {added} columns added, {skipped} skipped")
        print("-" * 60)

        return True

    except Error as e:
        print(f"[ERROR] Migration failed: {e}")
        return False

def verify():
    """Verify the migration"""
    print("\n[VERIFY] Checking users table structure...")

    conn = get_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        cursor.execute("DESCRIBE users")
        columns = cursor.fetchall()

        print("\n   Users table columns:")
        for col in columns:
            print(f"   - {col[0]}: {col[1]}")

        cursor.close()
        conn.close()

    except Error as e:
        print(f"[ERROR] Verification failed: {e}")

if __name__ == "__main__":
    if migrate():
        verify()
        print("\n[DONE] Database ready for secure authentication")
    else:
        print("\n[FAILED] Migration encountered errors")
