"""CLI: regenerate web data from the raw CSVs. The ONLY place that does I/O.

    python -m pravah.build_aggregates            # writes web/data/aggregates.json + web/data.js
    python -m pravah.build_aggregates --quick     # skip background scatter

Exports everything the glass-box UI needs: per-junction raw inputs (so the weight sliders
recompute the Pressure Index live), sample raw evidence behind each score, police_station
for the equity check, and the interpretable next-week-pressure forecast (model.py) with
per-junction plain-language reasons. Uses ONLY the provided parking-violation dataset.
Reproduces the validated FACTs; if output drifts, the pipeline changed (see CLAUDE.md)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from . import model as M
from . import pipeline as P
from .config import Config
from .pressure import compute_pressure


def _find(raw_dir: Path, globs: str) -> Path | None:
    """globs may be a comma-separated list of patterns; first match wins."""
    for pat in [g.strip() for g in globs.split(",")]:
        hits = sorted(raw_dir.glob(pat))
        if hits:
            return hits[0]
    return None


def hidden_evening_estimate(j: pd.DataFrame) -> int:
    """EST: extrapolate uncaught evening violations at blind junctions from the few that
    ARE covered. Clearly an estimate (small benchmark) — labelled EST everywhere."""
    g = j[j["n"] >= 200]
    covered = g[g["eve_share"] >= 8]
    if covered.empty:
        return 0
    bench = covered["eve_share"].median() / 100.0
    blind = g[g["eve_share"] < 2]
    implied = (blind["n"] / (1 - bench) * bench - blind["n"] * blind["eve_share"] / 100.0).clip(lower=0).sum()
    return int(implied)


def build_density(d: pd.DataFrame, w: int = 128, h: int = 150) -> dict:
    """Bin all violations into a fine grid over the data's bounding box. Blurred in the browser
    this renders as the city's actual activity footprint — a real, offline map base (violations
    trace the road network), not floating dots. Emitted sparse (only non-empty cells)."""
    la0, la1 = float(d.lat.min()), float(d.lat.max())
    lo0, lo1 = float(d.lon.min()), float(d.lon.max())
    ix = ((d["lon"] - lo0) / (lo1 - lo0) * (w - 1)).round().clip(0, w - 1).astype(int)
    iy = ((la1 - d["lat"]) / (la1 - la0) * (h - 1)).round().clip(0, h - 1).astype(int)
    vc = (iy * w + ix).value_counts()
    cells = [[int(i), int(c)] for i, c in vc.items()]
    return {"w": w, "h": h, "max": int(vc.max()), "bbox": [la0, la1, lo0, lo1], "cells": cells}


def build_areas(d: pd.DataFrame, top: int = 12) -> list[dict]:
    """Top police-station zones placed at their centroid — area labels so the map can be read
    ('Jayanagar', 'Malleshwaram', …). Data-driven and offline; no external geocoder."""
    g = (d[d["police_station"].astype(str).str.strip() != ""]
         .groupby("police_station").agg(lat=("lat", "median"), lon=("lon", "median"),
                                        n=("lat", "size")).reset_index()
         .sort_values("n", ascending=False).head(top))
    return [{"name": str(r["police_station"]).strip(), "lat": round(float(r["lat"]), 5),
             "lon": round(float(r["lon"]), 5)} for _, r in g.iterrows()]


def _evidence(d: pd.DataFrame, k: int = 5) -> dict:
    """Up to k sample raw rows per junction — the click-through evidence behind a score."""
    named = d[d["junction_name"] != "No Junction"].sort_values("t", ascending=False)
    out: dict[str, list] = {}
    for jn, grp in named.groupby("junction_name"):
        rows = grp.head(k)
        out[jn] = [{
            "t": r.t.strftime("%d %b %H:%M"), "v": str(r.vehicle_type)[:22],
            "o": str(r.topvt).title()[:34], "s": str(r.validation_status or "—")[:10],
        } for r in rows.itertuples()]
    return out


def build(cfg: Config, quick: bool = False) -> dict:
    vpath = _find(cfg.raw_dir, cfg.violations_glob)
    if not vpath:
        raise FileNotFoundError(f"No violations file matching {cfg.violations_glob} in {cfg.raw_dir}. "
                                f"See data/raw/README.md.")
    raw = P.load_violations(vpath)
    d = P.clean_enrich(raw)
    weeks = P.weeks_span(d)
    j = P.aggregate_junctions(d, cfg.min_junction_records)
    j = compute_pressure(j, cfg.weights, cfg.recovery_coef, weeks)
    cells = P.grid_cells(d)
    ph = P.phantom_hotspots(cells)
    hourly = P.hourly_histogram(d)
    evidence = _evidence(d)
    report = M.build_report(d)            # interpretable next-week forecast (AI/EST), parking data only
    preds = report["predictions"]

    junctions = [{
        "name": r["name"], "lat": round(r["lat"], 5), "lon": round(r["lon"], 5),
        "n": int(r["n"]), "cost": round(float(r["cost"]), 1),  # raw input -> live re-rank
        "pressure": int(r["pressure"]), "eve_share": round(r["eve_share"], 1),
        "pc": r["pc"], "pb": r["pb"], "pv": r["pv"],           # glass-box decomposition
        "top": str(r["top_violation"]).title(), "veh": int(r["veh"]),
        "rec": int(r["rec"]), "req": int(r["req"]),
        "ps": str(r.get("ps", "")),                            # police station -> equity
        "evidence": evidence.get(r["junction_name"], []),
        "fc": preds.get(r["junction_name"]),                   # next-week forecast (AI), or None
    } for _, r in j.iterrows()]
    phantom = [{"lat": round(r["lat"], 5), "lon": round(r["lon"], 5),
                "n": int(r["n"]), "eve_share": round(r["eve_share"], 1)} for _, r in ph.iterrows()]
    density = build_density(d)
    areas = build_areas(d)

    covered = j[(j["n"] >= 200) & (j["eve_share"] >= 8)]
    kpi = {
        "total": int(len(d)), "eve_pct": round(100 * d["evening"].mean(), 2),
        "n_junctions": len(junctions), "n_phantom": len(phantom),
        "top_junction": junctions[0]["name"] if junctions else "",
        "top_pressure": junctions[0]["pressure"] if junctions else 0,
        "weeks": round(weeks, 1), "date_min": str(d["t"].min().date()), "date_max": str(d["t"].max().date()),
        "covered_eve": (round(float(covered["eve_share"].max()), 1) if not covered.empty else 0),
        "hidden_est": hidden_evening_estimate(j),   # EST
        "repeat_offenders": P.repeat_offenders(d),
        "bbox": [float(d.lat.min()), float(d.lat.max()), float(d.lon.min()), float(d.lon.max())],
    }
    meta = {"weights": cfg.weights, "weeks": round(weeks, 1), "recovery_coef": cfg.recovery_coef}
    model_card = {k: report[k] for k in ("target", "model", "metrics", "importances", "estimate")}
    n_rising = sum(1 for jn in junctions if (jn["fc"] or {}).get("dir") == "up")
    model_card["n_forecast"] = sum(1 for jn in junctions if jn["fc"])
    model_card["n_rising"] = n_rising
    return {"kpi": kpi, "meta": meta, "junctions": junctions, "phantom": phantom,
            "hourly": hourly, "density": density, "areas": areas, "model": model_card}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build Pravah web data from raw CSVs.")
    ap.add_argument("--config", default="config/pravah.toml")
    ap.add_argument("--quick", action="store_true", help="skip background scatter")
    args = ap.parse_args(argv)
    cfg = Config.load(args.config)
    out = build(cfg, quick=args.quick)
    payload = json.dumps(out, separators=(",", ":"))
    cfg.out_json.parent.mkdir(parents=True, exist_ok=True)
    cfg.out_json.write_text(payload)
    # inlined copy so the demo runs offline by double-click (no fetch / CORS)
    Path("web/data.js").write_text("window.PRAVAH_DATA=" + payload + ";")
    k, mc = out["kpi"], out["model"]["metrics"]
    print(f"[pravah] wrote {cfg.out_json} and web/data.js")
    print(f"[pravah] FACT check -> total={k['total']:,}  evening={k['eve_pct']}%  "
          f"top={k['top_junction']}  junctions={k['n_junctions']}  phantom={k['n_phantom']}  "
          f"repeat>=5={k['repeat_offenders']:,}")
    print(f"[pravah] MODEL (AI/EST) -> R2={mc['r2']} vs baseline {mc['baseline_r2']} on held-out "
          f"weeks {mc['test_weeks']}; MAE {mc['mae']} vs {mc['baseline_mae']} "
          f"(+{mc['improvement_pct']}% better)")
    return out


if __name__ == "__main__":
    main()
