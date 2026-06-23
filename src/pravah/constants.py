"""Authoritative, VALIDATED constants. Computed from the real 298,445-record dataset.
Do NOT re-guess these. If one looks wrong, raise it with the team (see BUILD_PROMPT.md)."""
from __future__ import annotations

TIMEZONE = "Asia/Kolkata"

# Bengaluru bounding box (lat_min, lat_max, lon_min, lon_max)
BBOX = (12.7, 13.35, 77.3, 77.85)

# Evening "blind window" — hours (IST), inclusive 15..21 (3pm–9pm)
EVENING_HOURS = tuple(range(15, 22))

# Violation severity (lane-obstruction weight). Higher = worse for flow.
SEVERITY: dict[str, float] = {
    "DOUBLE PARKING": 3.0,
    "PARKING IN A MAIN ROAD": 3.0,
    "PARKING NEAR TRAFFIC LIGHT OR ZEBRA CROSS": 3.0,
    "PARKING NEAR ROAD CROSSING": 2.5,
    "PARKING ON FOOTPATH": 2.0,
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC": 2.0,
    "WRONG PARKING": 1.5,
    "NO PARKING": 1.0,
}
SEVERITY_DEFAULT = 1.0

# Vehicle physical footprint (road space / obstruction multiplier).
FOOTPRINT: dict[str, float] = {
    "LORRY/GOODS VEHICLE": 3.0, "HGV": 3.0, "TANKER": 3.0,
    "BUS (BMTC/KSRTC)": 3.0, "PRIVATE BUS": 3.0, "LGV": 2.0,
    "MAXI-CAB": 1.6, "TEMPO": 1.6, "VAN": 1.6, "GOODS AUTO": 1.4,
    "CAR": 1.5, "JEEP": 1.5, "PASSENGER AUTO": 1.2,
    "SCOOTER": 0.5, "MOTOR CYCLE": 0.5, "MOPED": 0.4,
}
FOOTPRINT_DEFAULT = 1.0

# Traffic Pressure Index default weights (override in config/pravah.toml).
DEFAULT_WEIGHTS = {"chronic": 0.50, "blindness": 0.30, "volume": 0.20}

# Recoverable vehicle-hours/week (ESTIMATE) = cost/weeks * RECOVERY_COEF
RECOVERY_COEF = 0.90

# Aggregation / detection thresholds
MIN_JUNCTION_RECORDS = 80      # min violations for a junction to be ranked
GRID_DEG = 0.0025              # ~270 m cells for phantom-hotspot detection
PHANTOM_MIN_N = 400            # min violations in a cell to be a phantom candidate
PHANTOM_MAX_NAMED_FRAC = 0.35  # cell is "off radar" if <35% rows carry a named junction

# Officer staffing tiers by pressure
def officers_for(pressure: float) -> int:
    return 3 if pressure >= 85 else 2 if pressure >= 60 else 1

# ---- VALIDATED FACTS (for sanity tests; tolerances generous) ----
FACT_WINDOW = ("2023-11-10", "2024-04-08")
FACT_WEEKS = 21.4
FACT_TOTAL_APPROX = 298_445
FACT_EVENING_SHARE_PCT = 0.85          # ± 0.3
FACT_TOP_JUNCTION = "Safina Plaza"     # substring match
FACT_REPEAT_OFFENDERS_GE5 = 3_489      # ± 100
FACT_COVERED_EVENING_PCT = 14.7        # UCO Bank Jn — proof evenings are catchable
