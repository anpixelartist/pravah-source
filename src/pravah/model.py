"""Interpretable next-week pressure forecast (PS1, parking data ONLY — no ASTraM event feed).

WHAT: for each junction we build a weekly trajectory of chronic load (Σ severity×footprint) and
train a GradientBoostingRegressor to predict NEXT week's load from recent history (lags, rolling
mean, week-over-week trend, long-run typical level, recent evening activity). It is validated
FORWARD in time — trained on the early weeks, scored on held-out later weeks — and benchmarked
against the naive "next week = last week" persistence baseline. SHAP gives every prediction a
per-feature reason in plain language.

WHY interpretable trees + SHAP and NEVER a neural net: a 55-year-old IPS officer (and an RTI
request) must be able to read WHY a junction is predicted to get worse. See ADR 0001.

All model output is an ESTIMATE (badge: AI). The trajectory it learns from is FACT."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

NAMED = "junction_name"

# Trajectory features (all derived only from a junction's PAST weeks -> no leakage) and the
# plain-language phrase each maps to in the UI ("why this prediction").
FEATURES: dict[str, str] = {
    "lag1": "last week's load",
    "lag2": "load two weeks ago",
    "lag3": "load three weeks ago",
    "roll3": "its recent 3-week average",
    "trend": "the week-over-week trend",
    "cummean": "its long-run typical load",
    "weeks_seen": "how long it has been tracked",
    "eve_lag1": "recent evening activity",
}
FEATURE_COLS = list(FEATURES)


def weekly_panel(d: pd.DataFrame) -> pd.DataFrame:
    """Per-junction × per-week chronic load (FACT trajectory the model learns from).
    WHY: pressure is a time series, not a snapshot; the weekly panel is what makes a forward
    forecast possible. Weeks with no tickets are real zeros (kept) so gaps don't break the lags.
    A trailing **partial** week (the data window rarely ends on a week boundary) is dropped — a
    half-week of tickets would otherwise read as a city-wide collapse and make the model 'predict'
    a rebound everywhere. Detected relative to the median week's day-count, so it never misfires."""
    s = d[d[NAMED] != "No Junction"].copy()
    s["week"] = ((s["t"] - s["t"].min()).dt.days // 7).astype(int)
    s["_day"] = s["t"].dt.normalize()
    day_counts = s.groupby("week")["_day"].nunique()
    med = float(day_counts.median())
    wk_max = int(s["week"].max())
    while wk_max > 0 and day_counts.get(wk_max, 0) < 0.6 * med:   # drop trailing partial week(s)
        wk_max -= 1
    s = s[s["week"] <= wk_max].drop(columns="_day")
    g = s.groupby([NAMED, "week"]).agg(cost=("cost", "sum"), eve=("evening", "mean")).reset_index()
    wk_max = int(g["week"].max())
    out = []
    for name, grp in g.groupby(NAMED):
        full = (grp.set_index("week").reindex(range(wk_max + 1))
                .assign(**{NAMED: name}))
        full["cost"] = full["cost"].fillna(0.0)
        full["eve"] = full["eve"].fillna(0.0)
        out.append(full.reset_index().rename(columns={"index": "week"}))
    return pd.concat(out, ignore_index=True).sort_values([NAMED, "week"]).reset_index(drop=True)


def make_supervised(panel: pd.DataFrame) -> pd.DataFrame:
    """Turn the weekly panel into one supervised row per (junction, week): trajectory features
    from the PAST → target = that week's load. Cold-start safe (missing lags fill to 0 and
    `weeks_seen` lets the model down-weight thin histories)."""
    rows = panel.copy()
    grp = rows.groupby(NAMED)
    rows["lag1"] = grp["cost"].shift(1)
    rows["lag2"] = grp["cost"].shift(2)
    rows["lag3"] = grp["cost"].shift(3)
    rows["roll3"] = grp["cost"].shift(1).rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    cummean = grp["cost"].apply(lambda s: s.shift(1).expanding().mean())
    rows["cummean"] = cummean.reset_index(level=0, drop=True)
    rows["eve_lag1"] = grp["eve"].shift(1)
    rows["weeks_seen"] = grp.cumcount()
    rows["trend"] = rows["lag1"] - rows["lag2"]
    rows = rows[rows["weeks_seen"] >= 1].copy()              # need ≥1 prior week to predict
    rows[FEATURE_COLS] = rows[FEATURE_COLS].fillna(0.0)
    rows["target"] = rows["cost"]
    return rows


def time_split(sup: pd.DataFrame, holdout_weeks: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Forward (out-of-time) split: the last `holdout_weeks` weeks are the held-out test set.
    WHY: a traffic forecast that only proves itself on shuffled data proves nothing — the honest
    test is 'trained on the past, did it call the future'."""
    cut = int(sup["week"].max()) - holdout_weeks + 1
    return sup[sup["week"] < cut].copy(), sup[sup["week"] >= cut].copy()


def fit(train: pd.DataFrame) -> GradientBoostingRegressor:
    """Train the interpretable gradient-boosted model (shallow trees, fixed seed)."""
    m = GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.05,
                                  subsample=0.9, random_state=0)
    m.fit(train[FEATURE_COLS], train["target"])
    return m


def evaluate(model: GradientBoostingRegressor, test: pd.DataFrame) -> dict:
    """Score the model on the held-out weeks vs the naive persistence baseline (pred = last week).
    Returns REAL metrics — nothing here is hardcoded."""
    pred = model.predict(test[FEATURE_COLS])
    base = test["lag1"].to_numpy()                          # 'next week = last week'
    y = test["target"].to_numpy()
    mae = float(mean_absolute_error(y, pred))
    base_mae = float(mean_absolute_error(y, base))
    return {
        "r2": round(float(r2_score(y, pred)), 3),
        "baseline_r2": round(float(r2_score(y, base)), 3),
        "mae": round(mae, 1),
        "baseline_mae": round(base_mae, 1),
        "improvement_pct": round(100 * (base_mae - mae) / base_mae, 1) if base_mae else 0.0,
        "n_train": 0, "n_test": int(len(test)),
        "test_weeks": sorted(int(w) for w in test["week"].unique()),
    }


def _shap_values(model: GradientBoostingRegressor, X: pd.DataFrame) -> np.ndarray | None:
    """Per-prediction SHAP contributions (interpretable attribution). Falls back to None if the
    optional shap dependency misbehaves, so a build never breaks on explanation tooling."""
    try:
        import shap
        return shap.TreeExplainer(model).shap_values(X)
    except Exception:
        return None


def _reasons(shap_row: np.ndarray | None, importances: np.ndarray, k: int = 2) -> list[str]:
    """Top-k plain-language drivers of a single prediction, ranked by SHAP influence (or global
    importance as a fallback). We rank by |SHAP| but phrase the drivers neutrally and let the
    headline (forecast vs this week) carry the up/down direction — because a SHAP sign is
    'vs the average junction-week', which would read backwards next to a 'rising/easing' headline.
    Honest and non-contradictory: these are the factors the forecast leaned on most."""
    if shap_row is not None:
        order = np.argsort(-np.abs(shap_row))[:k]
    else:
        order = np.argsort(-importances)[:k]
    return [FEATURES[FEATURE_COLS[i]] for i in order]


# A junction whose recent weekly load is below this is too small to forecast a credible
# trend for — a one-violation wobble would read as a huge % swing. We mark it "steady".
MIN_REF_LOAD = 15.0


def predict_next(panel: pd.DataFrame, model: GradientBoostingRegressor) -> pd.DataFrame:
    """Forecast the week AFTER the data ends for every junction, with reasons + direction.

    Direction/percent are measured against the junction's **recent typical level** (mean of its
    last 3 weeks), not a single last week — a near-zero last week would otherwise produce absurd
    swings (+1900%). The change is clipped to a sane range and small junctions (recent load below
    MIN_REF_LOAD) are reported 'steady' rather than guessed. Cold-start junctions (no prior week)
    are skipped, not invented."""
    feat_rows, names, refs, lasts = [], [], [], []
    for name, grp in panel.groupby(NAMED):
        g = grp.sort_values("week")
        costs = g["cost"].to_numpy()
        if len(costs) < 1:
            continue
        lag1 = costs[-1]
        lag2 = costs[-2] if len(costs) >= 2 else 0.0
        lag3 = costs[-3] if len(costs) >= 3 else 0.0
        feat_rows.append({
            "lag1": lag1, "lag2": lag2, "lag3": lag3,
            "roll3": float(np.mean(costs[-3:])), "trend": lag1 - lag2,
            "cummean": float(np.mean(costs)), "weeks_seen": int(len(costs)),
            "eve_lag1": float(g["eve"].to_numpy()[-1]),
        })
        names.append(name)
        refs.append(float(np.mean(costs[-3:])))     # recent typical level (stable baseline)
        lasts.append(float(lag1))
    X = pd.DataFrame(feat_rows, columns=FEATURE_COLS)
    preds = model.predict(X).clip(min=0)
    shap_vals = _shap_values(model, X)
    imp = model.feature_importances_
    out = []
    for i, name in enumerate(names):
        ref, pred = refs[i], float(preds[i])
        delta = max(-95.0, min(200.0, round(100 * (pred - ref) / ref))) if ref > 1e-9 else 0.0
        if ref < MIN_REF_LOAD:                       # too small to call a trend honestly
            direction = "flat"
        else:
            direction = "up" if delta > 10 else "down" if delta < -10 else "flat"
        row = shap_vals[i] if shap_vals is not None else None
        out.append({NAMED: name, "pred": round(pred, 1), "last": round(lasts[i], 1),
                    "ref": round(ref, 1), "delta_pct": delta, "dir": direction,
                    "reasons": _reasons(row, imp)})
    return pd.DataFrame(out)


def build_report(d: pd.DataFrame, holdout_weeks: int = 5) -> dict:
    """End-to-end: panel → supervised → forward-validate → forecast next week for every junction.
    Returns the model card (REAL metrics) + per-junction predictions. Used by build_aggregates
    and the tests. All output is an ESTIMATE (AI); the trajectory it learns from is FACT."""
    panel = weekly_panel(d)
    sup = make_supervised(panel)
    train, test = time_split(sup, holdout_weeks)
    model = fit(train)
    metrics = evaluate(model, test)
    metrics["n_train"] = int(len(train))
    preds = predict_next(panel, model)
    importances = {FEATURES[c]: round(float(v), 3)
                   for c, v in zip(FEATURE_COLS, model.feature_importances_, strict=False)}
    return {
        "target": "next-week chronic parking load (severity × vehicle footprint)",
        "model": "GradientBoostingRegressor (shallow trees) + SHAP — interpretable, no neural net",
        "metrics": metrics,
        "importances": dict(sorted(importances.items(), key=lambda kv: -kv[1])),
        "predictions": {r[NAMED]: {"pred": r["pred"], "last": r["last"], "delta_pct": r["delta_pct"],
                                   "dir": r["dir"], "reasons": r["reasons"]}
                        for _, r in preds.iterrows()},
        "estimate": True,
    }
