"""
Create Default Admin User
Run this script to create the initial admin account

Usage:
    python database/create_admin.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.auth import create_user, user_exists, get_user_count

# Default admin credentials
DEFAULT_ADMIN = {
    "username": "admin",
    "email": "admin@nxtby.com",
    "password": "admin123",  # User should change this after first login
    "full_name": "Administrator",
    "role": "admin"
}

def create_admin_user():
    """Create the default admin user"""
    print("\n" + "=" * 50)
    print("CREATE DEFAULT ADMIN USER")
    print("=" * 50)

    # Check if admin already exists
    if user_exists(DEFAULT_ADMIN["username"]):
        print(f"\n[INFO] Admin user '{DEFAULT_ADMIN['username']}' already exists.")
        print("No action needed.")
        return True

    # Create admin user
    print(f"\n[CREATE] Creating admin user...")
    success, user_id, message = create_user(
        username=DEFAULT_ADMIN["username"],
        email=DEFAULT_ADMIN["email"],
        password=DEFAULT_ADMIN["password"],
        full_name=DEFAULT_ADMIN["full_name"],
        role=DEFAULT_ADMIN["role"]
    )

    if success:
        print(f"[OK] Admin user created successfully!")
        print(f"\n" + "-" * 50)
        print("LOGIN CREDENTIALS:")
        print(f"  Username: {DEFAULT_ADMIN['username']}")
        print(f"  Password: {DEFAULT_ADMIN['password']}")
        print("-" * 50)
        print("\n[WARNING] Please change the password after first login!")
        return True
    else:
        print(f"[ERROR] Failed to create admin: {message}")
        return False

def show_user_stats():
    """Show current user statistics"""
    count = get_user_count()
    print(f"\n[INFO] Total users in database: {count}")

def main():
    """Main function"""
    try:
        create_admin_user()
        show_user_stats()
        print("\n" + "=" * 50)
        print("SETUP COMPLETE")
        print("=" * 50)
        print("\nYou can now start the app and login with the admin credentials.")
    except Exception as e:
        print(f"\n[ERROR] Setup failed: {e}")
        return False

    return True

if __name__ == "__main__":
    main()
