"""
Authentication Module for Asset Management App
Handles user authentication, password hashing, session management, and security controls

Security Features:
- bcrypt password hashing with configurable work factor
- Constant-time password comparison (via bcrypt)
- Login attempt rate limiting with account lockout
- Failed login attempt logging
- Secure session token generation
- Session invalidation support
"""
import bcrypt
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
import secrets
import hashlib
import logging

from .config import DB_CONFIG

# ============================================
# SECURITY CONFIGURATION
# ============================================
BCRYPT_ROUNDS = 12  # Work factor for bcrypt (12 = ~250ms per hash)
MAX_LOGIN_ATTEMPTS = 5  # Lock account after N failed attempts
LOCKOUT_DURATION_MINUTES = 15  # Account lockout duration
SESSION_TOKEN_BYTES = 32  # Length of session token

# Configure logging for security events (separate from user-facing messages)
logging.basicConfig(level=logging.INFO)
security_logger = logging.getLogger('auth.security')

# ============================================
# PASSWORD HASHING (Secure)
# ============================================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with salt.
    bcrypt automatically handles salt generation and storage.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash using constant-time comparison.
    bcrypt.checkpw uses constant-time comparison internally to prevent timing attacks.
    """
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except (ValueError, TypeError):
        # Invalid hash format or encoding error
        security_logger.warning("Invalid password hash format encountered")
        return False


# ============================================
# SESSION TOKEN MANAGEMENT
# ============================================

def generate_session_token() -> str:
    """
    Generate a cryptographically secure session token.
    Uses secrets module for secure random generation.
    """
    return secrets.token_hex(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """
    Hash session token for storage (one-way).
    We store hashed tokens to prevent session hijacking if DB is compromised.
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


# ============================================
# DATABASE CONNECTION
# ============================================

def get_connection():
    """Get database connection with error handling"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG, buffered=True, connection_timeout=10)
        return conn
    except Error as e:
        security_logger.error(f"Database connection error: {e}")
        return None


def is_database_available() -> bool:
    """Check if database is accessible"""
    conn = get_connection()
    if conn:
        try:
            conn.close()
            return True
        except:
            return False
    return False


# ============================================
# LOGIN ATTEMPT TRACKING & RATE LIMITING
# ============================================

def get_failed_attempts(username: str) -> Tuple[int, Optional[datetime]]:
    """
    Get failed login attempt count and last attempt time for a username.
    Returns: (attempt_count, last_attempt_time)
    """
    conn = get_connection()
    if not conn:
        return 0, None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT failed_login_attempts, last_failed_login, account_locked_until
            FROM users WHERE username = %s
        """, (username,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return (
                result.get('failed_login_attempts', 0) or 0,
                result.get('last_failed_login')
            )
        return 0, None

    except Error as e:
        security_logger.error(f"Error getting failed attempts: {e}")
        return 0, None


def is_account_locked(username: str) -> Tuple[bool, Optional[int]]:
    """
    Check if account is locked due to too many failed attempts.
    Returns: (is_locked, minutes_remaining)
    """
    conn = get_connection()
    if not conn:
        return False, None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT account_locked_until FROM users WHERE username = %s
        """, (username,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result.get('account_locked_until'):
            locked_until = result['account_locked_until']
            if isinstance(locked_until, datetime) and locked_until > datetime.now():
                remaining = (locked_until - datetime.now()).total_seconds() / 60
                return True, int(remaining) + 1

        return False, None

    except Error as e:
        security_logger.error(f"Error checking account lock: {e}")
        return False, None


def record_failed_login(username: str, ip_address: str = None):
    """
    Record a failed login attempt and potentially lock the account.
    """
    conn = get_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor(dictionary=True)

        # Get current failed attempts
        cursor.execute("""
            SELECT id, failed_login_attempts FROM users WHERE username = %s
        """, (username,))

        user = cursor.fetchone()

        if user:
            new_count = (user.get('failed_login_attempts', 0) or 0) + 1

            # Check if we should lock the account
            lock_until = None
            if new_count >= MAX_LOGIN_ATTEMPTS:
                lock_until = datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                security_logger.warning(
                    f"Account locked: {username} after {new_count} failed attempts"
                )

            # Update failed attempts
            cursor.execute("""
                UPDATE users
                SET failed_login_attempts = %s,
                    last_failed_login = %s,
                    account_locked_until = %s
                WHERE username = %s
            """, (new_count, datetime.now(), lock_until, username))

            conn.commit()

        # Log the failed attempt (always log, even for non-existent users)
        log_login_attempt(username, False, ip_address)

        cursor.close()
        conn.close()

    except Error as e:
        security_logger.error(f"Error recording failed login: {e}")


def reset_failed_attempts(username: str):
    """Reset failed login attempts after successful login"""
    conn = get_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET failed_login_attempts = 0,
                last_failed_login = NULL,
                account_locked_until = NULL
            WHERE username = %s
        """, (username,))
        conn.commit()
        cursor.close()
        conn.close()

    except Error as e:
        security_logger.error(f"Error resetting failed attempts: {e}")


def log_login_attempt(username: str, success: bool, ip_address: str = None):
    """
    Log login attempt to activity_log for audit trail.
    This is separate from user-facing error messages.
    """
    conn = get_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()

        action_type = "USER_LOGIN" if success else "LOGIN_FAILED"
        description = f"{'Successful' if success else 'Failed'} login attempt for user: {username}"

        cursor.execute("""
            INSERT INTO activity_log
            (action_type, action_category, description, user_role, user_identifier, ip_address, success, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            action_type,
            'authentication',
            description,
            'system',
            username,
            ip_address,
            success,
            datetime.now()
        ))

        conn.commit()
        cursor.close()
        conn.close()

    except Error as e:
        # Don't fail authentication if logging fails
        security_logger.error(f"Error logging login attempt: {e}")


# ============================================
# USER AUTHENTICATION (Secure)
# ============================================

def authenticate_user(username: str, password: str, ip_address: str = None) -> Tuple[bool, Optional[Dict], str]:
    """
    Authenticate a user with username and password.

    Security measures:
    - Rate limiting with account lockout
    - Constant-time password comparison
    - Generic error messages (no username/password hints)
    - Failed attempt logging
    - Session token generation

    Returns: (success, user_data, error_message)
    Error messages are generic to prevent username enumeration.
    """
    # Input validation
    if not username or not password:
        return False, None, "Please enter your credentials"

    # Sanitize username (prevent injection, limit length)
    username = username.strip()[:50]

    # Check database availability first
    conn = get_connection()
    if not conn:
        security_logger.error("Database unavailable during authentication")
        return False, None, "Service temporarily unavailable. Please try again."

    try:
        # Check if account is locked
        is_locked, minutes_remaining = is_account_locked(username)
        if is_locked:
            conn.close()
            return False, None, f"Account temporarily locked. Try again in {minutes_remaining} minutes."

        cursor = conn.cursor(dictionary=True)

        # Get user by username (single query, no timing leak)
        cursor.execute("""
            SELECT id, username, email, password_hash, full_name, role, is_active,
                   last_login, failed_login_attempts
            FROM users
            WHERE username = %s
        """, (username,))

        user = cursor.fetchone()

        # Use constant-time comparison path even if user doesn't exist
        # This prevents timing attacks for username enumeration
        if not user:
            # Perform a dummy hash comparison to maintain constant time
            verify_password(password, "$2b$12$" + "0" * 53)
            cursor.close()
            conn.close()
            record_failed_login(username, ip_address)
            return False, None, "Invalid credentials"

        # Check if user is active
        if not user.get('is_active', False):
            cursor.close()
            conn.close()
            return False, None, "Account is deactivated. Contact administrator."

        # Verify password (constant-time comparison via bcrypt)
        if not verify_password(password, user['password_hash']):
            cursor.close()
            conn.close()
            record_failed_login(username, ip_address)
            return False, None, "Invalid credentials"

        # Authentication successful
        # Generate session token
        session_token = generate_session_token()
        session_token_hash = hash_session_token(session_token)

        # Update last login and reset failed attempts
        cursor.execute("""
            UPDATE users
            SET last_login = %s,
                failed_login_attempts = 0,
                last_failed_login = NULL,
                account_locked_until = NULL,
                session_token_hash = %s,
                session_created_at = %s
            WHERE id = %s
        """, (datetime.now(), session_token_hash, datetime.now(), user['id']))
        conn.commit()

        # Log successful login
        log_login_attempt(username, True, ip_address)

        # Remove sensitive data from returned user object
        del user['password_hash']
        if 'failed_login_attempts' in user:
            del user['failed_login_attempts']

        # Add session token to user data (for client-side storage)
        user['session_token'] = session_token

        cursor.close()
        conn.close()

        return True, user, "Login successful"

    except Error as e:
        security_logger.error(f"Authentication error: {e}")
        return False, None, "Authentication service error. Please try again."


def validate_session(user_id: int, session_token: str) -> Tuple[bool, Optional[Dict]]:
    """
    Validate an existing session token.
    Returns: (is_valid, user_data)
    """
    if not user_id or not session_token:
        return False, None

    conn = get_connection()
    if not conn:
        return False, None

    try:
        cursor = conn.cursor(dictionary=True)

        # Get user and session info
        cursor.execute("""
            SELECT id, username, email, full_name, role, is_active,
                   session_token_hash, session_created_at
            FROM users
            WHERE id = %s AND is_active = TRUE
        """, (user_id,))

        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            return False, None

        # Verify session token
        stored_hash = user.get('session_token_hash')
        if not stored_hash:
            return False, None

        # Constant-time comparison of token hashes
        provided_hash = hash_session_token(session_token)
        if not secrets.compare_digest(stored_hash, provided_hash):
            return False, None

        # Remove sensitive data
        if 'session_token_hash' in user:
            del user['session_token_hash']
        if 'session_created_at' in user:
            del user['session_created_at']

        return True, user

    except Error as e:
        security_logger.error(f"Session validation error: {e}")
        return False, None


def invalidate_session(user_id: int) -> bool:
    """
    Invalidate a user's session (logout).
    """
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET session_token_hash = NULL, session_created_at = NULL
            WHERE id = %s
        """, (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True

    except Error as e:
        security_logger.error(f"Session invalidation error: {e}")
        return False


def invalidate_all_sessions(user_id: int) -> bool:
    """
    Invalidate all sessions for a user (e.g., password change).
    """
    return invalidate_session(user_id)


# ============================================
# USER MANAGEMENT
# ============================================

def create_user(username: str, email: str, password: str, full_name: str = "", role: str = "operations") -> Tuple[bool, Optional[int], str]:
    """
    Create a new user with secure password hashing.
    Returns: (success, user_id, message)
    """
    # Input validation
    if not username or len(username) < 3:
        return False, None, "Username must be at least 3 characters"
    if not email or '@' not in email:
        return False, None, "Valid email is required"
    if not password or len(password) < 6:
        return False, None, "Password must be at least 6 characters"
    if role not in ['admin', 'operations', 'finance']:
        return False, None, "Invalid role specified"

    conn = get_connection()
    if not conn:
        return False, None, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username.strip(),))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, None, "Username already exists"

        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email.strip().lower(),))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, None, "Email already exists"

        # Hash password securely
        password_hash = hash_password(password)

        # Insert user
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role, is_active, failed_login_attempts)
            VALUES (%s, %s, %s, %s, %s, TRUE, 0)
        """, (username.strip(), email.strip().lower(), password_hash, full_name.strip(), role))

        conn.commit()
        user_id = cursor.lastrowid

        cursor.close()
        conn.close()

        security_logger.info(f"New user created: {username} (role: {role})")
        return True, user_id, "User created successfully"

    except Error as e:
        security_logger.error(f"Create user error: {e}")
        return False, None, "Failed to create user"


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID (excludes sensitive data)"""
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
        security_logger.error(f"Get user error: {e}")
        return None


def get_all_users() -> List[Dict]:
    """Get all users for admin (excludes sensitive data)"""
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
        security_logger.error(f"Get all users error: {e}")
        return []


def update_user(user_id: int, data: Dict) -> Tuple[bool, str]:
    """
    Update user details (not password).
    data can include: email, full_name, role, is_active
    """
    conn = get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Build update query dynamically with allowed fields only
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
        security_logger.error(f"Update user error: {e}")
        return False, "Failed to update user"


def change_password(user_id: int, new_password: str) -> Tuple[bool, str]:
    """
    Change user's password securely.
    Also invalidates all existing sessions.
    """
    if not new_password or len(new_password) < 6:
        return False, "Password must be at least 6 characters"

    conn = get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()

        # Hash new password
        password_hash = hash_password(new_password)

        # Update password and invalidate sessions
        cursor.execute("""
            UPDATE users
            SET password_hash = %s,
                session_token_hash = NULL,
                session_created_at = NULL
            WHERE id = %s
        """, (password_hash, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        security_logger.info(f"Password changed for user ID: {user_id}")
        return True, "Password changed successfully"

    except Error as e:
        security_logger.error(f"Change password error: {e}")
        return False, "Failed to change password"


def deactivate_user(user_id: int) -> Tuple[bool, str]:
    """Deactivate a user (soft delete) and invalidate sessions"""
    conn = get_connection()
    if not conn:
        return False, "Database connection failed"

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET is_active = FALSE,
                session_token_hash = NULL,
                session_created_at = NULL
            WHERE id = %s
        """, (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "User deactivated"
    except Error as e:
        security_logger.error(f"Deactivate user error: {e}")
        return False, "Failed to deactivate user"


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
