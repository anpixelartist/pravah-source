"""Feature engineering — a FIRST-CLASS deliverable (see docs/TRUST.md). The intelligence
lives here. Each feature carries a docstring: WHAT it is + WHY it matters. All functions are
pure (data in -> data out) and cold-start safe (a junction with no history degrades to a
neutral value, never a NaN/inf or a crash).

KEY TASK FE-3 (coverage normalisation): the data is enforcement-generated and lies by
omission. We estimate exposure (how much a place-time was actually watched) and a coverage-
adjusted 'true rate' so blind spots surface instead of being erased. The chronic term of the
Pressure Index can run on this true rate as an OPTION (compute_pressure(chronic_col="cost_adj")),
leaving the default basis (`cost`) unchanged so the validated FACTs still reproduce."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import constants as C

# Commute peaks (IST hours): morning 8–10, evening 17–20. Used by the temporal features.
PEAK_HOURS = frozenset(range(8, 11)) | frozenset(range(17, 21))

# Public-holiday calendar for the data window (2023-11-10 → 2024-04-08). Editable by design:
# a transparent list beats an opaque library so an officer can audit/extend it. Why it matters:
# holidays shift parking demand (markets, temples, malls) away from office corridors.
HOLIDAYS = frozenset({
    "2023-11-12",  # Deepavali
    "2023-11-13",  # Balipadyami (Deepavali)
    "2023-11-27",  # Guru Nanak Jayanti
    "2023-12-25",  # Christmas
    "2024-01-01",  # New Year's Day
    "2024-01-15",  # Makara Sankranti
    "2024-01-26",  # Republic Day
    "2024-03-08",  # Maha Shivaratri
    "2024-03-25",  # Holi
    "2024-03-29",  # Good Friday
})

# Coverage adjustment cap: a sliver of exposure must not let `cost_adj` explode the score.
# 24 active hours = full day; we clip the inflation factor so the smallest watched junction is
# scaled by at most this. Stated openly (glass box).
COVERAGE_MAX_FACTOR = 8.0
NAMED = "junction_name"


def _named(d: pd.DataFrame) -> pd.DataFrame:
    """Rows that carry a real junction tag (drop the 'No Junction' bucket)."""
    return d[d[NAMED] != "No Junction"]


# --------------------------------------------------------------------------- temporal

def add_temporal(d: pd.DataFrame) -> pd.DataFrame:
    """Temporal features per violation row.
    WHAT: day-of-week, weekend flag, commute-peak flag, coarse daypart, the 3–9pm blind-window
    flag, a public-holiday flag, and hours-since-the-previous-ticket-at-this-junction (recency).
    WHY: pressure is not uniform in time; these isolate *when* it happens and, critically, the
    blind evening window the whole project is built around. `first_seen` marks cold-start rows so
    downstream code can treat 'no prior history' explicitly instead of as a zero gap."""
    d = d.copy()
    d["dow"] = d["t"].dt.dayofweek                      # 0 = Monday
    d["is_weekend"] = d["dow"] >= 5
    d["is_peak"] = d["hr"].isin(PEAK_HOURS)
    d["daypart"] = np.select(
        [d["hr"].between(7, 10), d["hr"].between(11, 16),
         d["hr"].between(17, 21), d["hr"].between(22, 23) | d["hr"].between(0, 6)],
        ["morning_peak", "midday", "evening", "night"], default="night",
    )
    d["is_blind_window"] = d["hr"].isin(C.EVENING_HOURS)   # 15..21 IST, the enforcement gap
    d["is_holiday"] = d["t"].dt.strftime("%Y-%m-%d").isin(HOLIDAYS)
    order = d.sort_values("t")
    gap = order.groupby(NAMED)["t"].diff().dt.total_seconds().div(3600.0)
    d["hours_since_prev"] = gap.reindex(d.index)
    d["first_seen"] = d["hours_since_prev"].isna()         # cold-start row: no prior at junction
    return d


# --------------------------------------------------------------------------- vehicle / violation

def add_vehicle_flags(d: pd.DataFrame) -> pd.DataFrame:
    """Vehicle/violation obstruction flags per row.
    WHAT: `heavy_vehicle` (footprint ≥ 2.0 — lorries, buses, tankers, LGVs) and `lane_blocking`
    (severity ≥ 2.5 — double-parking, main-road, traffic-light/zebra obstruction).
    WHY: a lorry double-parked on a main road steals a live lane; a scooter in a no-parking bay
    barely dents flow. These make 'a lorry ≠ a scooter' an explicit, checkable feature."""
    d = d.copy()
    d["heavy_vehicle"] = d["footprint"] >= 2.0
    d["lane_blocking"] = d["severity"] >= 2.5
    return d


def add_recidivism(d: pd.DataFrame) -> pd.DataFrame:
    """Per-vehicle repeat count (total violations by that vehicle in the window, max ~55).
    WHY: habitual violators are a real, targetable signal — a handful of vehicles re-offend
    constantly, and naming them turns enforcement from random into deterrent."""
    d = d.copy()
    d["repeat_count"] = d.groupby("vehicle_number")["vehicle_number"].transform("size")
    return d


# --------------------------------------------------------------------------- spatial

def neighbour_density(cells: pd.DataFrame) -> pd.DataFrame:
    """Spatial-lag: sum of the eight immediate-neighbour cell volumes for each grid cell.
    WHY: pressure clusters — a hot cell ringed by hot cells is a corridor problem, not a point
    problem, and should be weighted up. Standard spatial-lag feature, fully transparent."""
    c = cells.copy()
    idx = {(r.gy, r.gx): r.n for r in c.itertuples()}
    c["neighbour_n"] = [sum(idx.get((gy + dy, gx + dx), 0)
                            for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx))
                        for gy, gx in zip(c.gy, c.gx, strict=False)]
    return c


def coverage_proxy(d: pd.DataFrame) -> pd.DataFrame:
    """BASELINE cell-level exposure proxy (TASK FE-3): distinct active hours per ~270m cell.
    WHAT: `coverage_hours` (how many distinct hours-of-day the cell was ever ticketed in) and a
    coverage-adjusted `true_rate_proxy` ≈ summed cost ÷ exposure (EST).
    WHY: turns observed counts into a coverage-adjusted rate so under-watched cells stop being
    erased. Intentionally simple and clearly labelled EST — refine without overfitting."""
    d = d.copy()
    d["gy"] = (d["lat"] / C.GRID_DEG).round().astype(int)
    d["gx"] = (d["lon"] / C.GRID_DEG).round().astype(int)
    exposure = d.groupby(["gy", "gx"])["hr"].transform("nunique").clip(lower=1)
    d["coverage_hours"] = exposure
    d["true_rate_proxy"] = d.groupby(["gy", "gx"])["cost"].transform("sum") / exposure  # EST
    return d


# --------------------------------------------------------------------------- enforcement context

def validation_rate(d: pd.DataFrame) -> pd.Series:
    """Per-junction ticket rejection rate (data-quality signal), in [0, 1].
    WHY: ~30% of tickets city-wide are rejected (DATA_DICTIONARY). A junction whose tickets are
    often thrown out is noisier evidence — we surface it so a score built on it can be discounted
    or caveated rather than trusted blindly."""
    s = _named(d)
    rejected = s["validation_status"].astype(str).str.contains("reject", case=False, na=False)
    return rejected.groupby(s[NAMED]).mean()


def junction_exposure(d: pd.DataFrame) -> pd.Series:
    """Exposure proxy per junction: distinct active hours-of-day watched (1..24), clipped ≥ 1.
    WHY (FE-3): tickets only exist where/when officers stood. A junction ticketed only in a
    narrow window was barely watched; its true load is under-counted. Exposure is the divisor
    that puts that load back. Cold-start safe (clip ≥ 1 → never divide by zero)."""
    return _named(d).groupby(NAMED)["hr"].nunique().clip(lower=1)


def coverage_adjust(j: pd.DataFrame, d: pd.DataFrame,
                    max_factor: float = COVERAGE_MAX_FACTOR) -> pd.DataFrame:
    """Add the coverage-normalised 'true rate' to an aggregated junction frame (TASK FE-3).
    WHAT: `active_hours` (1..24), `coverage` (active_hours/24 ∈ (0,1]), and `cost_adj` =
    cost ÷ coverage capped at `max_factor`×cost — the chronic load corrected for how little the
    junction was watched.
    WHY: raw counts tell police to keep patrolling where they already do; dividing by exposure
    lifts under-watched blind spots into view. Used by the Pressure Index only on request
    (compute_pressure(chronic_col="cost_adj")), so the default ranking and the validated FACTs
    are unaffected. Glass box: the inflation factor is one number you can read off and challenge.
    Cold-start safe: a junction absent from `d` gets active_hours=1 (max correction, capped)."""
    out = j.copy()
    exp = junction_exposure(d)
    out["active_hours"] = out[NAMED].map(exp).fillna(1).clip(lower=1).astype(int)
    out["coverage"] = (out["active_hours"] / 24.0).clip(lower=1e-9, upper=1.0)
    factor = (1.0 / out["coverage"]).clip(upper=max_factor)
    out["cost_adj"] = (out["cost"] * factor).round(1)
    return out


def build_junction_features(j: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """Enrich an aggregated junction frame with the M1 enforcement-context + FE-3 features.
    WHAT: coverage/`cost_adj` (FE-3), `reject_rate`, and `repeat_share` (fraction of a junction's
    tickets issued to repeat offenders with ≥5 violations).
    WHY: one call attaches the trust-relevant, coverage-corrected signals the Pressure Index and
    the UI can lean on. Pure; cold-start safe (missing junctions fill to neutral 0)."""
    out = coverage_adjust(j, d)
    out["reject_rate"] = out[NAMED].map(validation_rate(d)).fillna(0.0).round(3)
    dd = add_recidivism(_named(d))
    total = dd.groupby(NAMED).size()
    rep = dd[dd["repeat_count"] >= 5].groupby(NAMED).size()
    rep_share = (rep / total).reindex(total.index).fillna(0.0)
    out["repeat_share"] = out[NAMED].map(rep_share).fillna(0.0).round(3)
    return out
