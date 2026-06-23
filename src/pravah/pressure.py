"""Traffic Pressure Index (TPI). A formula, not a verdict — always decomposable.
See docs/PRESSURE_INDEX.md."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import constants as C


def _norm(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 1e-9 else s * 0.0


def compute_pressure(j: pd.DataFrame, weights: dict | None = None,
                     recovery_coef: float = C.RECOVERY_COEF, weeks: float = C.FACT_WEEKS,
                     chronic_col: str = "cost") -> pd.DataFrame:
    """Add pressure + its decomposition (pc/pb/pv in points) + rec + req to a junction frame.

    Expects columns: n, cost, eve_share. Returns a copy with added columns:
      pressure (0-100), pc, pb, pv (point contributions, sum≈pressure),
      rec (recoverable vehicle-hours/week, ESTIMATE), req (officers suggested).

    `chronic_col` selects the basis for the chronic term. Default "cost" (validated FACTs).
    Pass "cost_adj" (from features.coverage_adjust, TASK FE-3) to run the chronic load on the
    coverage-normalised 'true rate' so under-watched blind spots rank up. Falls back to "cost"
    if the requested column is absent, so the call never breaks on a cold-start frame.
    """
    w = weights or C.DEFAULT_WEIGHTS
    d = j.copy()
    max_eve = d["eve_share"].max()
    blindness = 1 - (d["eve_share"] / max_eve if max_eve > 0 else 0)
    chronic_basis = d[chronic_col] if chronic_col in d.columns else d["cost"]
    pc = 100 * w["chronic"] * _norm(np.log1p(chronic_basis))
    pb = 100 * w["blindness"] * blindness
    pv = 100 * w["volume"] * _norm(np.log1p(d["n"]))
    d["pc"], d["pb"], d["pv"] = pc.round(1), pb.round(1), pv.round(1)
    d["pressure"] = (pc + pb + pv).clip(0, 100).round(0).astype(int)
    d["rec"] = (d["cost"] / weeks * recovery_coef).round(0).astype(int)  # EST
    d["req"] = d["pressure"].apply(C.officers_for).astype(int)
    return d.sort_values("pressure", ascending=False).reset_index(drop=True)
