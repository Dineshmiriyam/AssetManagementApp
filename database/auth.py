"""
Authentication Module for Asset Management App
Handles user authentication, password hashing, and user management
"""
import bcrypt
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from typing import Optional, Tuple, Dict, List
from .config import DB_CONFIG

# ============================================
# PASSWORD HASHING
# ============================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt with salt"""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False

# ============================================
# DATABASE CONNECTION
# ============================================

def get_connection():
    """Get database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG, buffered=True)
        return conn
    except Error as e:
        print(f"[AUTH] Database connection error: {e}")
        return None

# ============================================
# USER AUTHENTICATION
# ============================================

def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[Dict], str]:
    """
    Authenticate a user with username and password
    Returns: (success, user_data, error_message)
    """
    conn = get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor(dictionary=True)

        # Get user by username
        cursor.execute("""
            SELECT id, username, email, password_hash, full_name, role, is_active, last_login
            FROM users
            WHERE username = %s
        """, (username,))

        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            return False, None, "Invalid username or password"

        # Check if user is active
        if not user.get('is_active', False):
            cursor.close()
            conn.close()
            return False, None, "Account is deactivated. Contact administrator."

        # Verify password
        if not verify_password(password, user['password_hash']):
            cursor.close()
            conn.close()
            return False, None, "Invalid username or password"

        # Update last login
        cursor.execute("""
            UPDATE users SET last_login = %s WHERE id = %s
        """, (datetime.now(), user['id']))
        conn.commit()

        # Remove password hash from returned data
        del user['password_hash']

        cursor.close()
        conn.close()

        return True, user, "Login successful"

    except Error as e:
        print(f"[AUTH] Authentication error: {e}")
        return False, None, "Authentication failed"

# ============================================
# USER MANAGEMENT
# ============================================

def create_user(username: str, email: str, password: str, full_name: str = "", role: str = "operations") -> Tuple[bool, Optional[int], str]:
    """
    Create a new user
    Returns: (success, user_id, message)
    """
    conn = get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, None, "Username already exists"

        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, None, "Email already exists"

        # Hash password
        password_hash = hash_password(password)

        # Insert user
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """, (username, email, password_hash, full_name, role))

        conn.commit()
        user_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return True, user_id, "User created successfully"

    except Error as e:
        print(f"[AUTH] Create user error: {e}")
        return False, None, f"Failed to create user: {str(e)}"

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, email, full_name, role, is_active, last_login, created_at
            FROM users WHERE id = %s
        """, (user_id,))

        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user

    except Error as e:
        print(f"[AUTH] Get user error: {e}")
        return None

def get_all_users() -> List[Dict]:
    """Get all users (for admin)"""
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, email, full_name, role, is_active, last_login, created_at
            FROM users
            ORDER BY created_at DESC
        """)

        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return users

    except Error as e:
        print(f"[AUTH] Get all users error: {e}")
        return []

def update_user(user_id: int, data: Dict) -> Tuple[bool, str]:
    """
    Update user details (not password)
    data can include: email, full_name, role, is_active
    """
    conn = get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Build update query dynamically
        allowed_fields = ['email', 'full_name', 'role', 'is_active']
        updates = []
        values = []

        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(data[field])

        if not updates:
            cursor.close()
            conn.close()
            return False, "No valid fields to update"

        values.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"

        cursor.execute(query, values)
        conn.commit()

        cursor.close()
        conn.close()

        return True, "User updated successfully"

    except Error as e:
        print(f"[AUTH] Update user error: {e}")
        return False, f"Failed to update user: {str(e)}"

def change_password(user_id: int, new_password: str) -> Tuple[bool, str]:
    """Change user's password"""
    conn = get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()

        password_hash = hash_password(new_password)

        cursor.execute("""
            UPDATE users SET password_hash = %s WHERE id = %s
        """, (password_hash, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        return True, "Password changed successfully"

    except Error as e:
        print(f"[AUTH] Change password error: {e}")
        return False, "Failed to change password"

def deactivate_user(user_id: int) -> Tuple[bool, str]:
    """Deactivate a user (soft delete)"""
    return update_user(user_id, {'is_active': False})

def activate_user(user_id: int) -> Tuple[bool, str]:
    """Activate a user"""
    return update_user(user_id, {'is_active': True})

def user_exists(username: str) -> bool:
    """Check if username exists"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists
    except Error:
        return False

def get_user_count() -> int:
    """Get total user count"""
    conn = get_connection()
    if not conn:
        return 0

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Error:
        return 0
