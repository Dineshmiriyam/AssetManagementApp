"""
Data access, caching, and pagination utilities.
Extracted from app.py — handles data fetching, caching, and pagination.
"""
import os
import hashlib
import pandas as pd
import streamlit as st
from datetime import datetime
from pyairtable import Api

from config.constants import PAGINATION_CONFIG, CACHE_CONFIG, QUERY_LIMITS
from core.errors import log_error

# Data source configuration (read from env, same as app.py)
DATA_SOURCE = os.getenv("DATA_SOURCE", "mysql")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")

# MySQL imports (only if needed)
MYSQL_AVAILABLE = False
if DATA_SOURCE == "mysql":
    try:
        from database.db import (
            get_all_assets as mysql_get_assets,
            get_all_clients as mysql_get_clients,
            get_all_assignments as mysql_get_assignments,
            get_all_issues as mysql_get_issues,
            get_all_repairs as mysql_get_repairs,
        )
        MYSQL_AVAILABLE = True
    except ImportError:
        pass

# Table names (Airtable table mapping)
TABLES = {
    "assets": "Assets",
    "clients": "Clients",
    "assignments": "Assignments",
    "issues": "Issues",
    "repairs": "Repairs",
    "vendors": "Vendors",
    "invoices": "Invoices"
}


# ============================================
# AIRTABLE HELPERS
# ============================================
def get_airtable_api():
    if not AIRTABLE_API_KEY or AIRTABLE_API_KEY == "your_api_key_here":
        return None
    return Api(AIRTABLE_API_KEY)

def get_table(table_name):
    api = get_airtable_api()
    if api:
        return api.table(AIRTABLE_BASE_ID, TABLES[table_name])
    return None


# ============================================
# STREAMLIT RERUN COMPATIBILITY
# ============================================
# Compatibility helper for st.rerun (works with older and newer Streamlit versions)
def safe_rerun():
    """Rerun the app - compatible with all Streamlit versions"""
    if hasattr(st, 'rerun'):
        st.rerun()
    elif hasattr(st, 'experimental_rerun'):
        st.experimental_rerun()
    else:
        # Fallback: use newer Streamlit internal API
        from streamlit import runtime
        runtime.get_instance().request_rerun()


# ============================================
# PAGINATION
# ============================================
def get_pagination_state(key: str) -> dict:
    """Get or initialize pagination state for a specific table."""
    state_key = f"pagination_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "page": 0,
            "page_size": PAGINATION_CONFIG["default_page_size"],
            "total_records": 0,
            "total_pages": 0
        }
    return st.session_state[state_key]


def paginate_dataframe(df: pd.DataFrame, key: str, show_controls: bool = True) -> pd.DataFrame:
    """
    Apply pagination to a DataFrame without changing UI layout.

    Args:
        df: DataFrame to paginate
        key: Unique key for this table's pagination state
        show_controls: Whether to show pagination controls

    Returns:
        Paginated DataFrame slice
    """
    if df.empty:
        return df

    total_records = len(df)
    state = get_pagination_state(key)

    # Update total records
    state["total_records"] = total_records
    page_size = state["page_size"]
    state["total_pages"] = max(1, (total_records + page_size - 1) // page_size)

    # Ensure current page is valid
    if state["page"] >= state["total_pages"]:
        state["page"] = max(0, state["total_pages"] - 1)

    # Show top bar controls if enabled
    if show_controls and total_records > page_size:
        render_pagination_controls(key, state, total_records)

    # Calculate slice indices
    start_idx = state["page"] * page_size
    end_idx = min(start_idx + page_size, total_records)

    return df.iloc[start_idx:end_idx]


def render_pagination_controls(key: str, state: dict, total_records: int):
    """Render top pagination bar: page size dropdown + showing info."""
    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        # Page size selector
        new_size = st.selectbox(
            "Rows",
            options=PAGINATION_CONFIG["page_size_options"],
            index=PAGINATION_CONFIG["page_size_options"].index(state["page_size"]) if state["page_size"] in PAGINATION_CONFIG["page_size_options"] else 1,
            key=f"page_size_{key}",
            label_visibility="collapsed"
        )
        if new_size != state["page_size"]:
            state["page_size"] = new_size
            state["page"] = 0  # Reset to first page
            state["total_pages"] = max(1, (total_records + new_size - 1) // new_size)

    with col2:
        # Page info
        start = state["page"] * state["page_size"] + 1
        end = min((state["page"] + 1) * state["page_size"], total_records)
        st.markdown(f"<div style='text-align: center; padding: 8px; color: #64748b; font-size: 0.85rem;'>Showing {start}-{end} of {total_records}</div>", unsafe_allow_html=True)

    with col3:
        # Page indicator
        st.markdown(f"<div style='text-align: right; padding: 8px; color: #64748b; font-size: 0.85rem;'>Page {state['page'] + 1}/{state['total_pages']}</div>", unsafe_allow_html=True)


def render_page_navigation(key: str):
    """Render page number navigation buttons below the table."""
    state = get_pagination_state(key)
    total_pages = state.get("total_pages", 1)
    current_page = state.get("page", 0)

    if total_pages <= 1:
        return

    def go_to_page(page_num):
        get_pagination_state(key)["page"] = page_num

    # Build page number list with ellipsis for large page counts
    if total_pages <= 7:
        page_numbers = list(range(total_pages))
    else:
        page_numbers = []
        page_numbers.append(0)
        start = max(1, current_page - 1)
        end = min(total_pages - 1, current_page + 2)
        if end - start < 2 and start == 1:
            end = min(total_pages - 1, 3)
        elif end - start < 2 and end == total_pages - 1:
            start = max(1, total_pages - 4)
        if start > 1:
            page_numbers.append(-1)
        for i in range(start, end + 1):
            if i not in page_numbers:
                page_numbers.append(i)
        if end < total_pages - 2:
            page_numbers.append(-2)
        if total_pages - 1 not in page_numbers:
            page_numbers.append(total_pages - 1)

    # Centered navigation: spacer | Prev | pages | Next | page info | spacer
    num_nav_items = len(page_numbers) + 2  # Prev + pages + Next
    # Column widths: [spacer, prev, ...pages..., next, info, spacer]
    col_widths = [1.5, 1] + [0.6] * len(page_numbers) + [1, 2, 1.5]
    cols = st.columns(col_widths)

    # Previous button
    with cols[1]:
        st.button(
            "◀ Prev",
            key=f"pg_prev_{key}",
            on_click=go_to_page,
            args=(max(0, current_page - 1),),
            disabled=(current_page == 0),
            width="stretch"
        )

    # Page number buttons
    for i, page_num in enumerate(page_numbers):
        with cols[i + 2]:
            if page_num < 0:
                st.markdown("<div style='text-align: center; padding: 8px; color: #9ca3af; font-weight: 500;'>...</div>", unsafe_allow_html=True)
            elif page_num == current_page:
                st.button(
                    str(page_num + 1),
                    key=f"pg_{key}_{page_num}",
                    on_click=go_to_page,
                    args=(page_num,),
                    type="primary",
                    width="stretch"
                )
            else:
                st.button(
                    str(page_num + 1),
                    key=f"pg_{key}_{page_num}",
                    on_click=go_to_page,
                    args=(page_num,),
                    width="stretch"
                )

    # Next button
    with cols[len(page_numbers) + 2]:
        st.button(
            "Next ▶",
            key=f"pg_next_{key}",
            on_click=go_to_page,
            args=(min(total_pages - 1, current_page + 1),),
            disabled=(current_page >= total_pages - 1),
            width="stretch"
        )

    # Page info text
    start_record = current_page * state["page_size"] + 1
    end_record = min((current_page + 1) * state["page_size"], state.get("total_records", 0))
    with cols[len(page_numbers) + 3]:
        st.markdown(f"<div style='text-align: center; padding: 8px 0; color: #6b7280; font-size: 13px; white-space: nowrap;'>Page {current_page + 1} of {total_pages}</div>", unsafe_allow_html=True)


def reset_pagination(key: str = None):
    """Reset pagination state. If key is None, reset all pagination."""
    if key:
        state_key = f"pagination_{key}"
        if state_key in st.session_state:
            st.session_state[state_key]["page"] = 0
    else:
        for k in list(st.session_state.keys()):
            if k.startswith("pagination_"):
                st.session_state[k]["page"] = 0


# ============================================
# ENHANCED CACHING HELPERS
# ============================================
def get_cache_key(data_type: str, filters: dict = None) -> str:
    """Generate a cache key based on data type and filters."""
    key_parts = [data_type]
    if filters:
        for k, v in sorted(filters.items()):
            key_parts.append(f"{k}:{v}")
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()[:12]


def invalidate_cache_for(data_types: list = None):
    """
    Invalidate cache for specific data types.
    Called after write operations to ensure fresh data.
    """
    # Clear the main fetch_all_data cache
    fetch_all_data.clear()

    # Mark session data as stale
    if 'data_stale' in st.session_state:
        st.session_state.data_stale = True

    # Clear any specific cached DataFrames
    if data_types:
        for dtype in data_types:
            cache_key = f"cached_{dtype}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]

    # Reset pagination for affected tables
    if data_types:
        for dtype in data_types:
            reset_pagination(dtype)


def get_cached_dataframe(data_type: str, fetch_func, ttl_key: str = "ttl_assets") -> pd.DataFrame:
    """
    Get DataFrame with caching support.
    Uses session state for fast access with TTL-based invalidation.
    """
    cache_key = f"cached_{data_type}"
    timestamp_key = f"cached_{data_type}_time"
    ttl = CACHE_CONFIG.get(ttl_key, 600)

    # Check if cache is valid
    if cache_key in st.session_state and timestamp_key in st.session_state:
        cache_time = st.session_state[timestamp_key]
        if (datetime.now() - cache_time).total_seconds() < ttl:
            return st.session_state[cache_key]

    # Fetch fresh data
    df = fetch_func()

    # Apply query limit
    limit = QUERY_LIMITS.get(data_type, PAGINATION_CONFIG["max_records"])
    if len(df) > limit:
        df = df.head(limit)

    # Store in cache
    st.session_state[cache_key] = df
    st.session_state[timestamp_key] = datetime.now()

    return df


# ============================================
# DATA FETCHING
# ============================================
def _get_empty_data_structure() -> dict:
    """Return empty data structure for fallback scenarios."""
    return {
        "assets": pd.DataFrame(),
        "clients": pd.DataFrame(),
        "assignments": pd.DataFrame(),
        "issues": pd.DataFrame(),
        "repairs": pd.DataFrame(),
        "vendors": pd.DataFrame(),
        "invoices": pd.DataFrame()
    }

@st.cache_data(ttl=CACHE_CONFIG.get("ttl_assets", 600))
def fetch_all_data():
    """
    Fetch all data from configured data source (Airtable or MySQL).
    Applies query limits to prevent full-table scans on large datasets.
    Returns empty data structure on failure to prevent crashes.
    """
    data = _get_empty_data_structure()

    try:
        if DATA_SOURCE == "mysql" and MYSQL_AVAILABLE:
            # Fetch from MySQL with individual error handling per table
            try:
                data["assets"] = mysql_get_assets()
            except Exception as e:
                log_error(e, "fetch_assets")
                data["assets"] = pd.DataFrame()

            try:
                data["clients"] = mysql_get_clients()
            except Exception as e:
                log_error(e, "fetch_clients")
                data["clients"] = pd.DataFrame()

            try:
                data["assignments"] = mysql_get_assignments()
            except Exception as e:
                log_error(e, "fetch_assignments")
                data["assignments"] = pd.DataFrame()

            try:
                data["issues"] = mysql_get_issues()
            except Exception as e:
                log_error(e, "fetch_issues")
                data["issues"] = pd.DataFrame()

            try:
                data["repairs"] = mysql_get_repairs()
            except Exception as e:
                log_error(e, "fetch_repairs")
                data["repairs"] = pd.DataFrame()

        else:
            # Fetch from Airtable (original logic) with error handling
            for key in TABLES.keys():
                try:
                    table = get_table(key)
                    if table:
                        limit = QUERY_LIMITS.get(key, PAGINATION_CONFIG["max_records"])
                        records = table.all(max_records=limit)
                        items = []
                        for record in records:
                            fields = record.get("fields", {})
                            fields["_id"] = record.get("id")
                            items.append(fields)
                        data[key] = pd.DataFrame(items) if items else pd.DataFrame()
                    else:
                        data[key] = pd.DataFrame()
                except Exception as e:
                    log_error(e, f"fetch_airtable_{key}")
                    data[key] = pd.DataFrame()

        # Apply query limits to each DataFrame
        for key in data:
            if not data[key].empty:
                limit = QUERY_LIMITS.get(key, PAGINATION_CONFIG["max_records"])
                if len(data[key]) > limit:
                    data[key] = data[key].head(limit)

    except Exception as e:
        # Critical failure - log and return empty structure
        log_error(e, "fetch_all_data_critical")
        return _get_empty_data_structure()

    return data


def clear_cache(data_types: list = None):
    """
    Clear cache and mark data as stale for session state refresh.
    Optionally specify which data types to invalidate.

    Args:
        data_types: List of data types to invalidate (e.g., ["assets", "assignments"]).
                   If None, clears all caches.
    """
    # Clear main cache
    fetch_all_data.clear()

    # Mark session data as stale
    if 'data_stale' in st.session_state:
        st.session_state.data_stale = True

    # Clear specific cached DataFrames
    if data_types:
        for dtype in data_types:
            cache_key = f"cached_{dtype}"
            timestamp_key = f"cached_{dtype}_time"
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            if timestamp_key in st.session_state:
                del st.session_state[timestamp_key]
        # Reset pagination for affected tables
        for dtype in data_types:
            reset_pagination(dtype)
