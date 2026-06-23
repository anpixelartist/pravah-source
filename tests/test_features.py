"""M1 — feature-engineering tests. Pure (synthetic data, no CSVs needed). Cover each feature
group and the edge cases that matter: the coverage-normalised 'true rate' (FE-3), its use as a
Pressure-Index option, and cold-start junctions degrading gracefully (no NaN/inf, no crash)."""
import numpy as np
import pandas as pd
import pytest

from pravah import features as F
from pravah import pipeline as P
from pravah.pressure import compute_pressure


def _utc(ist: str) -> str:
    """IST wall-clock -> the UTC string the raw CSV would carry (clean_enrich converts back)."""
    return pd.Timestamp(ist, tz="Asia/Kolkata").tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(jn, hr, vt, ov, veh, status, day="2024-01-16"):
    # 2024-01-16 is a Tuesday (non-holiday); callers override for holiday/weekend cases.
    return {
        "latitude": "12.9750", "longitude": "77.5900",
        "created_datetime": _utc(f"{day} {hr:02d}:00:00"),
        "violation_type": f"['{ov}']", "vehicle_type": vt,
        "junction_name": jn, "police_station": "PS1",
        "vehicle_number": veh, "validation_status": status,
    }


@pytest.fixture
def enriched():
    """Three contrasting junctions through the real clean_enrich path:
    Wide   — watched 07..18 (broad exposure), heavy lorries, lane-blocking, all accepted;
    Narrow — all tickets at 10:00 (sliver of exposure), one repeat offender, some rejected;
    Cold   — a single record (cold-start)."""
    rows = []
    rows += [_row("BTP1 - Wide", h, "LORRY/GOODS VEHICLE", "DOUBLE PARKING",
                  f"KA01W{h}", "Accepted") for h in range(7, 19)]
    rows += [_row("BTP2 - Narrow", 10, "SCOOTER", "NO PARKING",
                  "KA02REPEAT", "Rejected" if i % 2 else "Accepted") for i in range(8)]
    rows += [_row("BTP3 - Cold", 11, "CAR", "WRONG PARKING", "KA03COLD", "Accepted")]
    raw = pd.DataFrame(rows)
    return P.clean_enrich(raw)


@pytest.fixture
def junctions(enriched):
    return P.aggregate_junctions(enriched, min_records=1)


# ----------------------------------------------------------------- temporal

def test_temporal_columns_and_flags(enriched):
    t = F.add_temporal(enriched)
    for col in ("dow", "is_weekend", "is_peak", "daypart", "is_blind_window",
                "is_holiday", "hours_since_prev", "first_seen"):
        assert col in t.columns
    assert not t["is_weekend"].any()              # all rows are a Tuesday
    assert not t["is_holiday"].any()              # 2024-01-16 is not in HOLIDAYS
    assert t.loc[t["hr"] == 18, "is_blind_window"].all()   # 6pm is inside 15..21
    assert not t.loc[t["hr"] == 7, "is_blind_window"].any()


def test_holiday_flag_fires_on_known_holiday():
    raw = pd.DataFrame([_row("BTP1 - X", 12, "CAR", "NO PARKING", "V1", "Accepted",
                             day="2024-01-15")])   # Makara Sankranti
    t = F.add_temporal(P.clean_enrich(raw))
    assert t["is_holiday"].all()


def test_time_since_prev_one_first_seen_per_junction(enriched):
    t = F.add_temporal(enriched)
    firsts = t.groupby("junction_name")["first_seen"].sum()
    assert (firsts == 1).all()                    # exactly one cold-start row per junction
    gaps = t.loc[~t["first_seen"], "hours_since_prev"]
    assert (gaps >= 0).all() and gaps.notna().all()


# ----------------------------------------------------------------- vehicle / violation

def test_vehicle_flags(enriched):
    f = F.add_vehicle_flags(enriched)
    assert f.loc[f["junction_name"] == "BTP1 - Wide", "heavy_vehicle"].all()      # lorries
    assert not f.loc[f["junction_name"] == "BTP2 - Narrow", "heavy_vehicle"].any()  # scooters
    assert f.loc[f["junction_name"] == "BTP1 - Wide", "lane_blocking"].all()      # double parking
    assert not f.loc[f["junction_name"] == "BTP2 - Narrow", "lane_blocking"].any()  # no parking


def test_recidivism(enriched):
    r = F.add_recidivism(enriched)
    assert r.loc[r["vehicle_number"] == "KA02REPEAT", "repeat_count"].iloc[0] == 8
    assert r.loc[r["vehicle_number"] == "KA03COLD", "repeat_count"].iloc[0] == 1


# ----------------------------------------------------------------- spatial

def test_spatial_lag_and_cell_coverage(enriched):
    cells = P.grid_cells(enriched)
    nb = F.neighbour_density(cells)
    assert "neighbour_n" in nb.columns and (nb["neighbour_n"] >= 0).all()
    cov = F.coverage_proxy(enriched)
    assert (cov["coverage_hours"] >= 1).all()
    assert cov["true_rate_proxy"].notna().all()


# ----------------------------------------------------------------- enforcement context / FE-3

def test_validation_rate_in_unit_interval(enriched):
    vr = F.validation_rate(enriched)
    assert vr.between(0, 1).all()
    assert vr["BTP2 - Narrow"] > 0                # half of Narrow's tickets are rejected
    assert vr["BTP1 - Wide"] == 0


def test_coverage_adjust_lifts_underwatched_junction(junctions, enriched):
    adj = F.coverage_adjust(junctions, enriched).set_index("junction_name")
    # Wide watched 12 hours, Narrow only 1 -> Narrow has far lower coverage...
    assert adj.loc["BTP1 - Wide", "coverage"] > adj.loc["BTP2 - Narrow", "coverage"]
    # ...so its coverage-adjusted cost is inflated relative to raw cost (blind-spot correction).
    assert adj.loc["BTP2 - Narrow", "cost_adj"] > adj.loc["BTP2 - Narrow", "cost"]
    assert adj["coverage"].between(0, 1).all()


def test_coverage_adjust_is_finite_and_capped(junctions, enriched):
    adj = F.coverage_adjust(junctions, enriched)
    assert np.isfinite(adj["cost_adj"]).all()     # no NaN/inf anywhere, incl. the cold junction
    factor = adj["cost_adj"] / adj["cost"]
    assert (factor <= F.COVERAGE_MAX_FACTOR + 1e-6).all()


def test_cold_start_junction_degrades_gracefully(enriched):
    """A junction present in the frame but with NO matching rows in `d` must not crash or NaN."""
    j = P.aggregate_junctions(enriched, min_records=1)
    ghost = j.iloc[[0]].copy()
    ghost["junction_name"] = "BTP9 - Ghost"        # exists in frame, absent from `d`
    j2 = pd.concat([j, ghost], ignore_index=True)
    out = F.build_junction_features(j2, enriched)
    g = out[out["junction_name"] == "BTP9 - Ghost"].iloc[0]
    assert g["active_hours"] == 1 and 0 < g["coverage"] <= 1
    assert np.isfinite(g["cost_adj"])
    assert g["reject_rate"] == 0.0 and g["repeat_share"] == 0.0


def test_build_junction_features_columns(junctions, enriched):
    out = F.build_junction_features(junctions, enriched)
    for col in ("coverage", "cost_adj", "reject_rate", "repeat_share"):
        assert col in out.columns
    narrow = out[out["junction_name"] == "BTP2 - Narrow"].iloc[0]
    assert narrow["repeat_share"] == 1.0           # all 8 rows are the same repeat offender


# ----------------------------------------------------------------- FE-3 used by the index

def test_pressure_accepts_coverage_option(junctions, enriched):
    adj = F.build_junction_features(junctions, enriched)
    out = compute_pressure(adj, chronic_col="cost_adj")
    assert out["pressure"].between(0, 100).all()
    for _, r in out.iterrows():                    # decomposition still sums to the score
        assert abs((r["pc"] + r["pb"] + r["pv"]) - r["pressure"]) <= 1.0


def test_pressure_default_basis_unchanged(junctions, enriched):
    """Default chronic_col='cost' must be identical to passing the raw cost explicitly —
    proves the FE-3 option is additive and cannot drift the validated default ranking."""
    adj = F.build_junction_features(junctions, enriched)
    base = compute_pressure(adj)
    same = compute_pressure(adj, chronic_col="cost")
    assert base["pressure"].tolist() == same["pressure"].tolist()


def test_pressure_missing_column_falls_back_to_cost(junctions):
    out = compute_pressure(junctions, chronic_col="does_not_exist")
    assert out["pressure"].between(0, 100).all()   # graceful fallback, no KeyError
