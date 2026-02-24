"""
Centralized configuration constants for Asset Lifecycle Management System.
Extracted from app.py — pure data, no runtime dependencies.
"""

# ============================================
# AUTHENTICATION & SESSION MANAGEMENT
# ============================================
SESSION_TIMEOUT_HOURS = 8  # Auto-logout after 8 hours
INACTIVITY_TIMEOUT_MINUTES = 30  # Auto-logout after 30 minutes of inactivity

# ============================================
# ROLE-BASED CONFIGURATION
# ============================================
USER_ROLES = {
    "operations": {
        "name": "Operations",
        "focus_states": ["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR", "IN_OFFICE_TESTING"],
        "show_sla": True,
        "show_billing": False,
        "can_drill_down": True,
        "description": "Focus on returns and repairs"
    },
    "finance": {
        "name": "Finance",
        "focus_states": ["WITH_CLIENT", "SOLD"],
        "show_sla": False,
        "show_billing": True,
        "can_drill_down": False,
        "description": "Focus on billable assets"
    },
    "admin": {
        "name": "Admin",
        "focus_states": None,  # All states visible
        "show_sla": True,
        "show_billing": True,
        "can_drill_down": True,
        "description": "Full system access"
    }
}

# SLA Configuration (in days)
SLA_CONFIG = {
    "RETURNED_FROM_CLIENT": {"warning": 3, "critical": 7},
    "WITH_VENDOR_REPAIR": {"warning": 7, "critical": 14},
    "IN_OFFICE_TESTING": {"warning": 2, "critical": 5}
}

# Email Configuration (Gmail SMTP)
EMAIL_CONFIG = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "timeout": 30,
    "subject_prefix": "[NXTBY]",
}

# ============================================
# PERFORMANCE & PAGINATION CONFIGURATION
# ============================================
PAGINATION_CONFIG = {
    "default_page_size": 25,
    "page_size_options": [10, 25, 50, 100],
    "max_records": 1000,  # Prevent full-table scans
}

CACHE_CONFIG = {
    "ttl_dashboard": 300,      # 5 minutes for dashboard KPIs
    "ttl_assets": 600,         # 10 minutes for asset list
    "ttl_clients": 900,        # 15 minutes for client list (rarely changes)
    "ttl_reports": 1800,       # 30 minutes for reports
    "enabled": True,           # Global cache toggle
}

# Query limits to prevent performance issues
QUERY_LIMITS = {
    "assets": 500,
    "clients": 200,
    "assignments": 500,
    "issues": 300,
    "repairs": 300,
    "activity_log": 200,
}


# ============================================
# CENTRALIZED BILLING CONFIGURATION
# ============================================
# All billing rules are defined here - DO NOT duplicate elsewhere
BILLING_CONFIG = {
    # Default monthly rate per asset (can be overridden per client)
    "default_monthly_rate": 3000,

    # States where billing is ACTIVE
    "billable_states": ["WITH_CLIENT"],

    # States where billing is PAUSED (was billing, now paused)
    "paused_states": ["RETURNED_FROM_CLIENT", "WITH_VENDOR_REPAIR"],

    # States where billing is NOT APPLICABLE (never billed or terminal)
    "non_billable_states": [
        "IN_STOCK_WORKING",
        "IN_STOCK_DEFECTIVE",
        "IN_OFFICE_TESTING",
        "SOLD",
        "DISPOSED"
    ],

    # Roles that can override billing (e.g., adjust rates, force billing status)
    "billing_override_roles": ["admin"],

    # Billing status labels
    "status_labels": {
        "active": "Billing Active",
        "paused": "Billing Paused",
        "not_applicable": "Not Billable"
    },

    # Billing status colors for UI
    "status_colors": {
        "active": "#22c55e",      # Green
        "paused": "#f59e0b",      # Amber/Warning
        "not_applicable": "#64748b"  # Gray
    },

    # Billing status icons
    "status_icons": {
        "active": "●",
        "paused": "◐",
        "not_applicable": "○"
    }
}

# ============================================
# ASSET STATUS CONFIGURATION
# ============================================
# Status options
ASSET_STATUSES = [
    "IN_STOCK_WORKING",
    "WITH_CLIENT",
    "RETURNED_FROM_CLIENT",
    "IN_OFFICE_TESTING",
    "WITH_VENDOR_REPAIR",
    "SOLD",
    "DISPOSED"
]

# High-contrast colors for pie charts and status indicators
STATUS_COLORS = {
    "IN_STOCK_WORKING": "#4CAF50",      # Green - Available
    "WITH_CLIENT": "#FF6B35",           # Orange - Primary action
    "RETURNED_FROM_CLIENT": "#2196F3",  # Blue - Needs attention
    "IN_OFFICE_TESTING": "#9C27B0",     # Purple - Testing
    "WITH_VENDOR_REPAIR": "#FF9800",    # Amber - Under repair
    "SOLD": "#607D8B",                  # Blue Grey - Completed
    "DISPOSED": "#F44336"               # Red - Disposed
}

# ============================================================================
# LIFECYCLE STATE TRANSITION VALIDATION
# ============================================================================
# Define allowed state transitions - prevents skipping lifecycle steps
ALLOWED_TRANSITIONS = {
    "IN_STOCK_WORKING": ["WITH_CLIENT"],                          # Can only be assigned to client
    "WITH_CLIENT": ["RETURNED_FROM_CLIENT", "SOLD"],              # Can be returned or sold
    "RETURNED_FROM_CLIENT": ["IN_STOCK_WORKING", "WITH_VENDOR_REPAIR", "IN_OFFICE_TESTING"],  # Restock, repair, or test
    "IN_OFFICE_TESTING": ["IN_STOCK_WORKING", "WITH_VENDOR_REPAIR"],  # Pass testing or send to repair
    "WITH_VENDOR_REPAIR": ["IN_STOCK_WORKING", "DISPOSED"],       # Fixed or disposed
    "SOLD": [],                                                    # Terminal state
    "DISPOSED": []                                                 # Terminal state
}

# Human-readable status names for error messages
STATUS_DISPLAY_NAMES = {
    "IN_STOCK_WORKING": "In Stock (Working)",
    "WITH_CLIENT": "With Client",
    "RETURNED_FROM_CLIENT": "Returned from Client",
    "IN_OFFICE_TESTING": "In Office Testing",
    "WITH_VENDOR_REPAIR": "With Vendor (Repair)",
    "SOLD": "Sold",
    "DISPOSED": "Disposed"
}

# Valid initial statuses when creating a new asset
# Restricts users from creating assets directly in terminal or mid-lifecycle states
VALID_INITIAL_STATUSES = [
    "IN_STOCK_WORKING",   # Default - new asset in inventory
    "WITH_CLIENT"         # Edge case - adding an already deployed asset
]

# Critical actions that require enhanced audit logging
CRITICAL_ACTIONS = {
    "ASSET_ASSIGNED": {"severity": "high", "billing_impact": True},
    "ASSET_RETURNED": {"severity": "high", "billing_impact": True},
    "REPAIR_CREATED": {"severity": "medium", "billing_impact": True},
    "REPAIR_COMPLETED": {"severity": "medium", "billing_impact": True},
    "BILLING_OVERRIDE": {"severity": "critical", "billing_impact": True},
    "ASSET_CREATED": {"severity": "medium", "billing_impact": False},
    "ASSET_DELETED": {"severity": "critical", "billing_impact": False},
    "STATUS_CHANGE": {"severity": "medium", "billing_impact": True},
    "ACCESS_DENIED": {"severity": "critical", "billing_impact": False},
    "ASSIGNMENT_CREATED": {"severity": "high", "billing_impact": True},
    "CLIENT_CREATED": {"severity": "low", "billing_impact": False},
    "CLIENT_UPDATED": {"severity": "low", "billing_impact": False},
    "CONTACT_ADDED": {"severity": "low", "billing_impact": False},
    "CONTACT_DELETED": {"severity": "low", "billing_impact": False},
}

# ============================================
# FORM / UI CONSTANTS
# ============================================
ASSET_TYPES = ["Laptop", "Phone", "Printer", "Other"]
BRANDS = ["Lenovo", "Apple", "HP", "Dell", "Other"]
STORAGE_TYPES = ["SSD", "HDD"]
OS_OPTIONS = ["Windows 10 Pro", "Windows 11 Pro", "macOS"]

ISSUE_CATEGORIES = [
    "VPN Connection Issue", "Windows Reset Problem", "OS Installation Issue",
    "Driver Issue", "Blue Screen / Restart", "Display Issue",
    "HDMI Port Issue", "Keyboard Issue", "Physical Damage", "Battery Issue"
]

# Primary action per role - visually emphasized in sidebar
ROLE_PRIMARY_ACTION = {
    "operations": "Issues & Repairs",
    "finance": "Billing",
    "admin": "Dashboard"
}
