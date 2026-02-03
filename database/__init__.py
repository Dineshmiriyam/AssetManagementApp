"""
Database Package
Provides MySQL database connectivity and utilities
"""
from .config import DB_CONFIG, DATA_SOURCE
from .db import (
    DatabaseConnection,
    get_all_assets,
    get_asset_by_id,
    get_asset_current_status_db,
    create_asset,
    update_asset_status_db,
    update_asset,
    get_all_clients,
    create_client,
    get_all_assignments,
    create_assignment,
    get_all_issues,
    create_issue,
    get_all_repairs,
    create_repair,
    log_state_change_db,
    get_state_change_log,
    execute_query,
    get_dashboard_stats
)

__all__ = [
    'DB_CONFIG',
    'DATA_SOURCE',
    'DatabaseConnection',
    'get_all_assets',
    'get_asset_by_id',
    'get_asset_current_status_db',
    'create_asset',
    'update_asset_status_db',
    'update_asset',
    'get_all_clients',
    'create_client',
    'get_all_assignments',
    'create_assignment',
    'get_all_issues',
    'create_issue',
    'get_all_repairs',
    'create_repair',
    'log_state_change_db',
    'get_state_change_log',
    'execute_query',
    'get_dashboard_stats'
]
