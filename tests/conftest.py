import pandas as pd
import pytest


@pytest.fixture
def toy_junctions():
    """Small synthetic junction frame for pure-logic tests (no data files needed)."""
    return pd.DataFrame([
        {"name": "A", "n": 15000, "cost": 20000, "eve_share": 1.0},
        {"name": "B", "n": 11000, "cost": 15000, "eve_share": 0.1},
        {"name": "C", "n": 5000,  "cost": 8000,  "eve_share": 15.0},
        {"name": "D", "n": 200,   "cost": 300,   "eve_share": 0.0},
    ])
