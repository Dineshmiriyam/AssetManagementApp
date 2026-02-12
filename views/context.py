"""Shared context object passed to all page renderers."""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class AppContext:
    """Bundles shared state that page renderers need from app.py."""

    # Connection state
    api: Any = None  # True for MySQL, Api object for Airtable, None if disconnected
    data_source: str = "mysql"
    mysql_available: bool = False
    auth_available: bool = False

    # DataFrames
    assets_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    clients_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    issues_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    repairs_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    assignments_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Credential info (needed by Settings page)
    airtable_base_id: str = ""
    airtable_api_key: str = ""
