"""
SLA calculation logic — extracted from app.py.
Handles SLA status, counts, and role-based asset filtering.
"""

from datetime import datetime, date

import pandas as pd

from config.constants import SLA_CONFIG, USER_ROLES


def calculate_sla_status(status, days_in_status):
    """Calculate SLA status based on asset state and days"""
    if status not in SLA_CONFIG:
        return "ok", 0

    config = SLA_CONFIG[status]
    if days_in_status >= config["critical"]:
        return "critical", config["critical"]
    elif days_in_status >= config["warning"]:
        return "warning", config["warning"]
    return "ok", config["warning"]


def get_sla_counts(assets_df):
    """Get count of assets in each SLA category"""
    sla_counts = {"ok": 0, "warning": 0, "critical": 0}

    if assets_df.empty or "Current Status" not in assets_df.columns:
        return sla_counts

    today = date.today()

    for _, asset in assets_df.iterrows():
        status = asset.get("Current Status", "")
        if status in SLA_CONFIG:
            # Try to get status change date
            status_date = None
            if "Status Changed Date" in asset and pd.notna(asset.get("Status Changed Date")):
                try:
                    status_date = datetime.strptime(str(asset["Status Changed Date"])[:10], "%Y-%m-%d").date()
                except:
                    pass
            elif "Returned Date" in asset and pd.notna(asset.get("Returned Date")) and status == "RETURNED_FROM_CLIENT":
                try:
                    status_date = datetime.strptime(str(asset["Returned Date"])[:10], "%Y-%m-%d").date()
                except:
                    pass

            if status_date:
                days = (today - status_date).days
            else:
                days = 0

            sla_status, _ = calculate_sla_status(status, days)
            sla_counts[sla_status] += 1

    return sla_counts


def get_sla_breached_assets(assets_df):
    """Return detailed list of assets in warning or critical SLA status."""
    breached = []

    if assets_df.empty or "Current Status" not in assets_df.columns:
        return breached

    today = date.today()

    for _, asset in assets_df.iterrows():
        status = asset.get("Current Status", "")
        if status not in SLA_CONFIG:
            continue

        status_date = None
        if "Status Changed Date" in asset and pd.notna(asset.get("Status Changed Date")):
            try:
                status_date = datetime.strptime(str(asset["Status Changed Date"])[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        elif "Returned Date" in asset and pd.notna(asset.get("Returned Date")) and status == "RETURNED_FROM_CLIENT":
            try:
                status_date = datetime.strptime(str(asset["Returned Date"])[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        if not status_date:
            continue

        days = (today - status_date).days
        sla_level, threshold = calculate_sla_status(status, days)

        if sla_level in ("warning", "critical"):
            breached.append({
                "serial": asset.get("Serial Number", "N/A"),
                "status": status,
                "days": days,
                "sla_level": sla_level,
                "client": asset.get("Current Location", "—"),
                "threshold": threshold,
            })

    breached.sort(key=lambda x: (0 if x["sla_level"] == "critical" else 1, -x["days"]))
    return breached


def filter_assets_by_role(assets_df, role):
    """Filter assets based on user role focus states"""
    role_config = USER_ROLES.get(role, USER_ROLES["admin"])
    focus_states = role_config.get("focus_states")

    if focus_states is None or assets_df.empty:
        return assets_df

    if "Current Status" not in assets_df.columns:
        return assets_df

    return assets_df[assets_df["Current Status"].isin(focus_states)]
