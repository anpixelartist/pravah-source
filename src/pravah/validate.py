"""Validation & trust (M4). No ground-truth congestion exists, so we triangulate validity.
See docs/TRUST.md."""
from __future__ import annotations

import pandas as pd

from . import constants as C


def face_validity(j: pd.DataFrame) -> dict:
    """Do the top junctions match known-bad spots? Implemented check used by sanity tests."""
    top = j.sort_values("pressure", ascending=False).head(5)["name"].tolist()
    hit = any(C.FACT_TOP_JUNCTION.lower() in t.lower() for t in top)
    return {"top5": top, "matches_known_bad": hit}


def natural_experiment(d: pd.DataFrame) -> dict:
    """M4: did enforcement at a junction lower its repeat-violation rate over the window?
    Implement a before/after on per-junction recidivism. Stub returns the contract shape."""
    raise NotImplementedError("M4: before/after recidivism comparison per junction.")


def backtest_ranking(d: pd.DataFrame, weeks_holdout: int = 4) -> dict:
    """M4: precision@k of the hotspot ranking on held-out weeks."""
    raise NotImplementedError("M4: split last N weeks, rank on the rest, score precision@k.")
