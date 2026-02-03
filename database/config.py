"""
Database Configuration
Supports local development and cPanel production
"""
import os

# ============================================
# ENVIRONMENT DETECTION
# ============================================
# Set ENVIRONMENT to 'production' on cPanel, defaults to 'development'
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ============================================
# LOCAL DEVELOPMENT CONFIGURATION
# ============================================
# For local MySQL (XAMPP or MySQL Server)
LOCAL_DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "database": "assetmgmt_db",
    "user": "root",                    # Default MySQL root user
    "password": "",                     # XAMPP default is empty, MySQL may have password
    "charset": "utf8mb4",
    "autocommit": True,
    "pool_name": "asset_pool",
    "pool_size": 3
}

# ============================================
# CPANEL PRODUCTION CONFIGURATION
# ============================================
# All credentials MUST be set via environment variables
# No hardcoded defaults for security
PRODUCTION_DB_CONFIG = {
    "host": os.getenv("DB_HOST", ""),
    "port": int(os.getenv("DB_PORT", "3306")),
    "database": os.getenv("DB_NAME", ""),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
    "autocommit": True,
    "pool_name": "asset_pool",
    "pool_size": 5
}

def validate_db_config() -> dict:
    """Validate database configuration for production."""
    issues = []
    config = PRODUCTION_DB_CONFIG if ENVIRONMENT == "production" else LOCAL_DB_CONFIG

    if not config.get("host"):
        issues.append("DB_HOST not configured")
    if not config.get("database"):
        issues.append("DB_NAME not configured")
    if not config.get("user"):
        issues.append("DB_USER not configured")
    # Password can be empty for local development

    return {"valid": len(issues) == 0, "issues": issues, "environment": ENVIRONMENT}

# ============================================
# ACTIVE CONFIGURATION
# ============================================
# Automatically selects based on environment
if ENVIRONMENT == "production":
    DB_CONFIG = PRODUCTION_DB_CONFIG
else:
    DB_CONFIG = LOCAL_DB_CONFIG

# Data source toggle: "mysql" or "airtable"
# Set this to switch between databases
DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql")

# Debug: Print config on startup (remove in production later)
print(f"[CONFIG] Environment: {ENVIRONMENT}")
print(f"[CONFIG] Data Source: {DATA_SOURCE}")
print(f"[CONFIG] DB Host: {DB_CONFIG.get('host', 'NOT SET')}")
print(f"[CONFIG] DB Name: {DB_CONFIG.get('database', 'NOT SET')}")
print(f"[CONFIG] DB User: {DB_CONFIG.get('user', 'NOT SET')}")
print(f"[CONFIG] DB Port: {DB_CONFIG.get('port', 'NOT SET')}")
