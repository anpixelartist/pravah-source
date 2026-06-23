"""Pure data pipeline: load -> clean -> enrich -> aggregate. No file writes here.
Reproduces the validated numbers (see constants.FACT_*)."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd

from . import constants as C
from .schema import VIOLATION_COLS, require


def _parse_list(x: str) -> list[str]:
    try:
        return ast.literal_eval(x) if isinstance(x, str) and x.startswith("[") else [x]
    except Exception:
        return [x]


def clean_name(j: str) -> str:
    """Strip 'BTP135 - ' style prefixes for display."""
    return re.sub(r"^BTP\d+\s*-\s*", "", str(j)).strip()


def load_violations(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    require(df, VIOLATION_COLS, "violations")
    return df


def clean_enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to Bengaluru, parse times to IST, compute per-violation cost + evening flag."""
    d = df.copy()
    d["lat"] = pd.to_numeric(d["latitude"], errors="coerce")
    d["lon"] = pd.to_numeric(d["longitude"], errors="coerce")
    d["t"] = pd.to_datetime(d["created_datetime"], errors="coerce", utc=True).dt.tz_convert(C.TIMEZONE)
    d = d.dropna(subset=["lat", "lon", "t"])
    la0, la1, lo0, lo1 = C.BBOX
    d = d[d.lat.between(la0, la1) & d.lon.between(lo0, lo1)].copy()
    d["hr"] = d["t"].dt.hour
    d["evening"] = d["hr"].isin(C.EVENING_HOURS).astype(int)
    vt = d["violation_type"].apply(_parse_list)
    d["severity"] = vt.apply(
        lambda L: max((C.SEVERITY.get(t, C.SEVERITY_DEFAULT) for t in L), default=C.SEVERITY_DEFAULT)
    )
    d["footprint"] = d["vehicle_type"].map(C.FOOTPRINT).fillna(C.FOOTPRINT_DEFAULT)
    d["cost"] = d["severity"] * d["footprint"]
    d["topvt"] = vt.apply(lambda L: L[0] if L else "—")
    return d


def weeks_span(d: pd.DataFrame) -> float:
    return max((d["t"].max() - d["t"].min()).days / 7.0, 1.0)


def aggregate_junctions(d: pd.DataFrame, min_records: int = C.MIN_JUNCTION_RECORDS) -> pd.DataFrame:
    """Junction-level rollup with the inputs the Pressure Index needs."""
    named = d[d["junction_name"] != "No Junction"]
    g = named.groupby("junction_name").agg(
        lat=("lat", "median"), lon=("lon", "median"), n=("cost", "size"),
        cost=("cost", "sum"), eve=("evening", "sum"), veh=("vehicle_number", "nunique"),
        ps=("police_station", lambda s: s.mode().iat[0] if not s.mode().empty else ""),
    ).reset_index()
    g["eve_share"] = 100 * g["eve"] / g["n"]
    top = (named.groupby(["junction_name", "topvt"]).size().reset_index(name="c")
           .sort_values("c", ascending=False).drop_duplicates("junction_name")
           .set_index("junction_name")["topvt"])
    g["top_violation"] = g["junction_name"].map(top).fillna("—")
    g["name"] = g["junction_name"].apply(clean_name)
    return g[g["n"] >= min_records].reset_index(drop=True)


def grid_cells(d: pd.DataFrame) -> pd.DataFrame:
    g = d.copy()
    g["gy"] = (g["lat"] / C.GRID_DEG).round().astype(int)
    g["gx"] = (g["lon"] / C.GRID_DEG).round().astype(int)
    c = g.groupby(["gy", "gx"]).agg(
        n=("cost", "size"), eve=("evening", "sum"),
        named=("junction_name", lambda s: (s != "No Junction").mean()),
        lat=("lat", "mean"), lon=("lon", "mean"),
    ).reset_index()
    c["eve_share"] = 100 * c["eve"] / c["n"]
    return c


def phantom_hotspots(cells: pd.DataFrame, top: int = 12) -> pd.DataFrame:
    """High-volume cells that are off the named-junction radar."""
    ph = cells[(cells["named"] < C.PHANTOM_MAX_NAMED_FRAC) & (cells["n"] >= C.PHANTOM_MIN_N)]
    return ph.sort_values("n", ascending=False).head(top).reset_index(drop=True)


def hourly_histogram(d: pd.DataFrame) -> list[int]:
    return d.groupby("hr").size().reindex(range(24), fill_value=0).astype(int).tolist()


def repeat_offenders(d: pd.DataFrame, threshold: int = 5) -> int:
    vc = d["vehicle_number"].value_counts()
    return int((vc >= threshold).sum())
