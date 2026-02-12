"""
Billing business logic — extracted from app.py.
Single source of truth for billing status, metrics, and impact calculations.
"""

from config.constants import BILLING_CONFIG
from config.permissions import can_override_billing


def get_asset_billing_status(asset_status: str) -> dict:
    """
    Determine billing status for an asset based on its lifecycle state.
    This is the SINGLE SOURCE OF TRUTH for billing status.

    Returns:
        dict with keys: status, label, color, icon, reason
    """
    if asset_status in BILLING_CONFIG["billable_states"]:
        return {
            "status": "active",
            "label": BILLING_CONFIG["status_labels"]["active"],
            "color": BILLING_CONFIG["status_colors"]["active"],
            "icon": BILLING_CONFIG["status_icons"]["active"],
            "reason": "Asset is deployed with client",
            "is_billable": True
        }
    elif asset_status in BILLING_CONFIG["paused_states"]:
        reason_map = {
            "RETURNED_FROM_CLIENT": "Asset returned from client",
            "WITH_VENDOR_REPAIR": "Asset sent for repair"
        }
        return {
            "status": "paused",
            "label": BILLING_CONFIG["status_labels"]["paused"],
            "color": BILLING_CONFIG["status_colors"]["paused"],
            "icon": BILLING_CONFIG["status_icons"]["paused"],
            "reason": reason_map.get(asset_status, "Billing temporarily paused"),
            "is_billable": False
        }
    else:
        reason_map = {
            "IN_STOCK_WORKING": "Asset in stock - not deployed",
            "IN_STOCK_DEFECTIVE": "Asset defective - not deployable",
            "IN_OFFICE_TESTING": "Asset under testing",
            "SOLD": "Asset sold - final billing completed",
            "DISPOSED": "Asset disposed"
        }
        return {
            "status": "not_applicable",
            "label": BILLING_CONFIG["status_labels"]["not_applicable"],
            "color": BILLING_CONFIG["status_colors"]["not_applicable"],
            "icon": BILLING_CONFIG["status_icons"]["not_applicable"],
            "reason": reason_map.get(asset_status, "Not in billable state"),
            "is_billable": False
        }


def get_billable_assets(assets_df, strict: bool = True):
    """
    Filter assets that are currently billable.

    Args:
        assets_df: DataFrame of assets
        strict: If True, only return assets in billable states.
                If False (Admin override), can include paused states.

    Returns:
        DataFrame of billable assets
    """
    if assets_df.empty or "Current Status" not in assets_df.columns:
        return assets_df.iloc[0:0]  # Return empty DataFrame with same columns

    billable_states = BILLING_CONFIG["billable_states"]
    return assets_df[assets_df["Current Status"].isin(billable_states)]


def get_paused_billing_assets(assets_df):
    """Get assets with paused billing (returned or in repair)."""
    if assets_df.empty or "Current Status" not in assets_df.columns:
        return assets_df.iloc[0:0]

    paused_states = BILLING_CONFIG["paused_states"]
    return assets_df[assets_df["Current Status"].isin(paused_states)]


def calculate_billing_metrics(assets_df, monthly_rate: float = None) -> dict:
    """
    Calculate all billing metrics from assets DataFrame.
    This is the SINGLE SOURCE OF TRUTH for billing calculations.

    Args:
        assets_df: DataFrame of assets
        monthly_rate: Optional override rate (Admin only), defaults to config rate

    Returns:
        dict with all billing metrics
    """
    rate = monthly_rate or BILLING_CONFIG["default_monthly_rate"]

    # Get counts by billing status
    billable_df = get_billable_assets(assets_df)
    paused_df = get_paused_billing_assets(assets_df)

    billable_count = len(billable_df)
    paused_count = len(paused_df)
    total_count = len(assets_df) if not assets_df.empty else 0

    # Calculate revenues
    monthly_revenue = billable_count * rate
    daily_rate = rate / 30
    annual_revenue = monthly_revenue * 12

    # Calculate by client if location data available
    client_breakdown = {}
    if not billable_df.empty and "Current Location" in billable_df.columns:
        client_counts = billable_df.groupby("Current Location").size()
        for client, count in client_counts.items():
            client_breakdown[client] = {
                "asset_count": count,
                "monthly_rate": rate,
                "monthly_revenue": count * rate,
                "annual_revenue": count * rate * 12
            }

    return {
        "billable_count": billable_count,
        "paused_count": paused_count,
        "total_count": total_count,
        "utilization_rate": (billable_count / total_count * 100) if total_count > 0 else 0,
        "monthly_rate": rate,
        "daily_rate": daily_rate,
        "monthly_revenue": monthly_revenue,
        "annual_revenue": annual_revenue,
        "client_breakdown": client_breakdown
    }


def validate_billing_override(role: str, action: str) -> tuple:
    """
    Validate if a billing override action is allowed.

    Args:
        role: User's role
        action: The override action being attempted

    Returns:
        tuple: (allowed: bool, message: str)
    """
    if not can_override_billing(role):
        return False, f"Billing override not permitted for {role} role. Admin access required."

    return True, "Override permitted"


def get_billing_impact(current_status, new_status, asset_info=None):
    """
    Calculate billing impact of a state transition.
    Uses centralized BILLING_CONFIG for consistency.
    """
    impacts = []

    # Get billing status for both states
    current_billing = get_asset_billing_status(current_status)
    new_billing = get_asset_billing_status(new_status)

    # Transition TO billable state (starts billing)
    if new_status in BILLING_CONFIG["billable_states"] and current_status not in BILLING_CONFIG["billable_states"]:
        impacts.append({
            "type": "positive",
            "icon": BILLING_CONFIG["status_icons"]["active"],
            "message": "Billing will START for this asset",
            "detail": f"Asset enters billable state. Rate: ₹{BILLING_CONFIG['default_monthly_rate']:,}/month"
        })

    # Transition FROM billable TO paused (billing paused)
    elif current_status in BILLING_CONFIG["billable_states"] and new_status in BILLING_CONFIG["paused_states"]:
        impacts.append({
            "type": "warning",
            "icon": BILLING_CONFIG["status_icons"]["paused"],
            "message": "Billing will PAUSE for this asset",
            "detail": "Final billing calculated on transition date. Resumes when redeployed."
        })

    # Transition TO repair from non-billable (no billing impact)
    elif new_status == "WITH_VENDOR_REPAIR" and current_status not in BILLING_CONFIG["billable_states"]:
        impacts.append({
            "type": "info",
            "icon": "🔧",
            "message": "Asset sent for repair",
            "detail": "No billing impact - asset was not in billable state"
        })

    # Transition FROM paused TO ready for deployment
    elif current_status in BILLING_CONFIG["paused_states"] and new_status == "IN_STOCK_WORKING":
        impacts.append({
            "type": "positive",
            "icon": "✅",
            "message": "Asset available for deployment",
            "detail": "Can be assigned to clients. Billing starts when deployed."
        })

    # Disposed - permanent removal
    elif new_status == "DISPOSED":
        impacts.append({
            "type": "critical",
            "icon": "🗑️",
            "message": "Asset will be PERMANENTLY removed from inventory",
            "detail": "This action cannot be undone"
        })

    return impacts
