"""
Pages package for Asset Lifecycle Management System.
Each module exposes a render(ctx: AppContext) function.
"""

from views.dashboard import render as render_dashboard
from views.assets import render as render_assets
from views.quick_actions import render as render_quick_actions
from views.add_asset import render as render_add_asset
from views.assignments import render as render_assignments
from views.issues_repairs import render as render_issues_repairs
from views.clients import render as render_clients
from views.reports import render as render_reports
from views.billing import render as render_billing
from views.activity_log import render as render_activity_log
from views.user_management import render as render_user_management
from views.import_export import render as render_import_export
from views.settings import render as render_settings

# Map page display names to their render functions
PAGE_REGISTRY = {
    "Dashboard": render_dashboard,
    "Assets": render_assets,
    "Quick Actions": render_quick_actions,
    "Add Asset": render_add_asset,
    "Assignments": render_assignments,
    "Issues & Repairs": render_issues_repairs,
    "Clients": render_clients,
    "Reports": render_reports,
    "Billing": render_billing,
    "Activity Log": render_activity_log,
    "User Management": render_user_management,
    "Import/Export": render_import_export,
    "Settings": render_settings,
}
