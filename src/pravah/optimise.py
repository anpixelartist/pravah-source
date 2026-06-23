"""Officer-deployment optimiser + baseline-vs-Pravah uplift (the money shot).

Baseline = current practice: greedily send officers to the highest-ticket-count junctions.
Pravah   = a 0/1 knapsack that maximises recovered vehicle-hours within the officer budget,
           respecting each junction's staffing need. By construction Pravah >= baseline.
Pure functions; the UI mirrors this exactly. Pravah recommends — a human decides."""
from __future__ import annotations

import pandas as pd


def allocate(rows: list[dict], n_officers: int, value="rec", cost="req") -> dict:
    """Naive greedy fill down a pre-sorted list (used for the 'current practice' baseline)."""
    used, recovered, picks = 0, 0, []
    for r in rows:
        if used + r[cost] <= n_officers:
            used += r[cost]
            recovered += r[value]
            picks.append(r)
        if used >= n_officers:
            break
    return {"recovered": recovered, "officers_used": used, "picks": picks}


def knapsack(rows: list[dict], n_officers: int, value="rec", cost="req") -> dict:
    """0/1 knapsack: maximise total `value` subject to sum(`cost`) <= n_officers."""
    cap = int(n_officers)
    dp = [0.0] * (cap + 1)
    keep = [[False] * (cap + 1) for _ in rows]
    for i, r in enumerate(rows):
        w, v = int(r[cost]), r[value]
        for c in range(cap, w - 1, -1):
            if dp[c - w] + v > dp[c]:
                dp[c] = dp[c - w] + v
                keep[i][c] = True
    c, picks = cap, []
    for i in range(len(rows) - 1, -1, -1):
        if keep[i][c]:
            picks.append(rows[i])
            c -= int(rows[i][cost])
    picks.reverse()
    return {"recovered": dp[cap], "officers_used": cap - c, "picks": picks}


def compare(j: pd.DataFrame, n_officers: int) -> dict:
    """Current practice (by ticket count) vs Pravah (knapsack on recovered vehicle-hours)."""
    rows = j.to_dict("records")
    base = allocate(sorted(rows, key=lambda r: -r["n"]), n_officers)
    pra = knapsack(rows, n_officers)
    uplift = (round(100 * (pra["recovered"] - base["recovered"]) / base["recovered"], 1)
              if base["recovered"] else 0.0)
    return {"baseline": base, "pravah": pra, "uplift_pct": uplift}
