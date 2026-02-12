"""
Asset Lifecycle Management System v2.4
A Streamlit web application with Airtable/MySQL support
Enhanced with role-based analytics, SLA indicators, and RBAC
Production-hardened with centralized error handling
"""

import streamlit as st
import pandas as pd
import os
import logging
from dotenv import load_dotenv

from config.styles import get_anti_flicker_css, get_dashboard_css
from core.errors import log_error, classify_error, USER_SAFE_MESSAGES
from core.data import (
    safe_rerun, get_airtable_api, _get_empty_data_structure,
    fetch_all_data,
)
from core.auth import (
    init_auth_session, check_session_timeout, validate_current_session,
    render_login_page, restore_session_from_url, is_auth_available,
)
from core.navigation import render_sidebar, render_footer
from views import PAGE_REGISTRY
from views.context import AppContext

# Load environment variables
load_dotenv()

# ============================================
# PRODUCTION ERROR HANDLING & LOGGING
# ============================================
# Configure logging - technical errors go to file, not UI
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding='utf-8'),
        logging.StreamHandler() if os.getenv("DEBUG", "false").lower() == "true" else logging.NullHandler()
    ]
)
logger = logging.getLogger("AssetManagement")

# Error tracking for session
if 'error_count' not in st.session_state:
    st.session_state.error_count = 0

# ============================================
# DATA SOURCE CONFIGURATION
# ============================================
# Toggle between "airtable" and "mysql"
# Set via environment variable or change default here
DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql")  # Options: "airtable", "mysql"

MYSQL_AVAILABLE = False
AUTH_AVAILABLE = is_auth_available()

# MySQL imports (only what app.py still needs: connection test + DB setup)
if DATA_SOURCE == "mysql":
    try:
        from database.db import (
            DatabaseConnection,
            setup_database,
            check_tables_exist,
        )
        MYSQL_AVAILABLE = True

        # Auto-setup database tables on startup
        if 'db_setup_done' not in st.session_state:
            success, tables = check_tables_exist()
            required_tables = ['assets', 'clients', 'assignments', 'issues', 'repairs']
            if success:
                missing_tables = [t for t in required_tables if t not in tables]
                if missing_tables:
                    setup_success, setup_msg = setup_database()
                    if setup_success:
                        st.session_state.db_setup_done = True
                        st.toast("Database tables initialized successfully!")
                    else:
                        st.error(f"Database setup failed: {setup_msg}")
                else:
                    st.session_state.db_setup_done = True
            else:
                # Try to setup anyway
                setup_success, setup_msg = setup_database()
                if setup_success:
                    st.session_state.db_setup_done = True

    except ImportError as e:
        MYSQL_AVAILABLE = False
        AUTH_AVAILABLE = False
        st.warning(f"MySQL module not available: {e}. Using Airtable.")
        DATA_SOURCE = "airtable"
else:
    MYSQL_AVAILABLE = False
    AUTH_AVAILABLE = False

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Asset Management System",
    page_icon="🟠",
    layout="wide",
    initial_sidebar_state="expanded"  # Sidebar visible after login; opacity:0 hides flash
)

# Hide all UI until auth is resolved — prevents visual flash during auth check
st.markdown(get_anti_flicker_css(), unsafe_allow_html=True)

# ============================================
# AUTH FLOW — BEFORE ANY UI RENDERING
# ============================================
init_auth_session()
restore_session_from_url()

if not st.session_state.authenticated:
    render_login_page()
    st.stop()

# ============================================
# AUTHENTICATED — Dashboard CSS + Security Checks
# ============================================
st.markdown(get_dashboard_css(), unsafe_allow_html=True)

# Airtable Configuration (credentials from environment only)
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")

# Session security checks
session_timed_out = check_session_timeout()
if not session_timed_out:
    validate_current_session()

# If user was logged out by timeout/validation, redirect to login
if not st.session_state.authenticated:
    render_login_page()
    st.stop()

# Initialize navigation state
if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

# ============================================
# DATABASE CONNECTION CHECK
# ============================================
if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
    api = True  # Set to True so existing checks pass
    try:
        db_connected, db_msg = DatabaseConnection.test_connection()
    except:
        db_connected = False
else:
    api = get_airtable_api()
    db_connected = api is not None

# ============================================
# SIDEBAR NAVIGATION
# ============================================
page = render_sidebar(db_connected)

# ============================================
# DATA LOADING
# ============================================
if api:
    # Initialize data error state
    if 'data_load_error' not in st.session_state:
        st.session_state.data_load_error = None
    if 'data_load_error_id' not in st.session_state:
        st.session_state.data_load_error_id = None

    # Only fetch data if not in session state or marked as stale
    if 'all_data' not in st.session_state or st.session_state.get('data_stale', True):
        try:
            with st.spinner('Loading data...'):
                st.session_state.all_data = fetch_all_data()
                st.session_state.data_stale = False
                st.session_state.data_load_error = None
                st.session_state.data_load_error_id = None
        except Exception as e:
            # Log technical error, store user-safe message
            error_id = log_error(e, "main_data_load", st.session_state.get('user_role'))
            error_type = classify_error(e)
            st.session_state.data_load_error = USER_SAFE_MESSAGES.get(error_type, USER_SAFE_MESSAGES["default"])
            st.session_state.data_load_error_id = error_id
            st.session_state.all_data = _get_empty_data_structure()

    # Check for retry request
    if st.session_state.get('retry_data_load', False):
        st.session_state.retry_data_load = False
        st.session_state.data_stale = True
        safe_rerun()

    all_data = st.session_state.all_data
else:
    all_data = _get_empty_data_structure()

assets_df = all_data.get("assets", pd.DataFrame())
clients_df = all_data.get("clients", pd.DataFrame())
issues_df = all_data.get("issues", pd.DataFrame())
repairs_df = all_data.get("repairs", pd.DataFrame())
assignments_df = all_data.get("assignments", pd.DataFrame())

# ============================================
# PAGE DISPATCH
# ============================================
ctx = AppContext(
    api=api,
    data_source=DATA_SOURCE,
    mysql_available=MYSQL_AVAILABLE,
    auth_available=AUTH_AVAILABLE,
    assets_df=assets_df,
    clients_df=clients_df,
    issues_df=issues_df,
    repairs_df=repairs_df,
    assignments_df=assignments_df,
    airtable_base_id=AIRTABLE_BASE_ID,
    airtable_api_key=AIRTABLE_API_KEY,
)

page_renderer = PAGE_REGISTRY.get(page)
if page_renderer:
    page_renderer(ctx)
else:
    st.error(f"Unknown page: {page}")

# Footer
render_footer()
