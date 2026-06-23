"""Canonical column names and the raw->canonical contract. See docs/DATA_DICTIONARY.md."""
from __future__ import annotations

VIOLATION_COLS = [
    "latitude", "longitude", "created_datetime", "violation_type", "vehicle_type",
    "junction_name", "police_station", "vehicle_number", "validation_status",
]


def require(df, cols, name):
    """Fail loudly if expected columns are missing — never silently produce wrong numbers."""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing required columns {missing}. "
                         f"Check the raw file matches docs/DATA_DICTIONARY.md.")
