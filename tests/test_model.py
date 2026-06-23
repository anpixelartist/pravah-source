"""M3 — interpretable next-week forecast tests. Pure (synthetic weekly trajectories, no CSVs).
Cover the supervised construction (no leakage / no NaN), the forward-in-time split, and the
end-to-end report shape incl. plain-language reasons and graceful cold-start behaviour."""
import warnings

import numpy as np
import pandas as pd
import pytest

from pravah import model as M

warnings.filterwarnings("ignore")  # silence shap/sklearn chatter in CI


@pytest.fixture
def weekly_d():
    """3 junctions × 12 weekly rows through the columns model.py consumes (junction_name, t,
    cost, evening). Rising / steady / noisy so the trajectory features have something to learn."""
    start = pd.Timestamp("2024-01-01", tz="Asia/Kolkata")
    rows = []
    for w in range(12):
        t = start + pd.Timedelta(weeks=w)
        rows.append({"junction_name": "BTP1 - Rising", "t": t, "cost": 100 + 12 * w, "evening": 0})
        rows.append({"junction_name": "BTP2 - Steady", "t": t, "cost": 50.0, "evening": 1})
        rows.append({"junction_name": "BTP3 - Noisy", "t": t, "cost": 30 + (w % 3) * 9, "evening": 0})
    return pd.DataFrame(rows)


def test_weekly_panel_is_complete(weekly_d):
    panel = M.weekly_panel(weekly_d)
    assert set(panel["junction_name"].unique()) == {"BTP1 - Rising", "BTP2 - Steady", "BTP3 - Noisy"}
    assert (panel.groupby("junction_name").size() == 12).all()   # reindexed to a full week grid


def test_supervised_has_no_leakage_or_nans(weekly_d):
    sup = M.make_supervised(M.weekly_panel(weekly_d))
    assert sup[M.FEATURE_COLS].notna().all().all()             # lags filled, never NaN
    assert (sup["weeks_seen"] >= 1).all()                       # never predict with zero history
    # lag1 at week w must equal the actual cost at week w-1 (true past, no peeking)
    r = sup[(sup["junction_name"] == "BTP1 - Rising") & (sup["week"] == 5)].iloc[0]
    assert r["lag1"] == pytest.approx(100 + 12 * 4)


def test_time_split_holds_out_last_weeks(weekly_d):
    sup = M.make_supervised(M.weekly_panel(weekly_d))
    train, test = M.time_split(sup, holdout_weeks=3)
    assert sorted(test["week"].unique().tolist()) == [9, 10, 11]
    assert train["week"].max() < test["week"].min()           # strictly forward in time


def test_build_report_shape_and_reasons(weekly_d):
    rep = M.build_report(weekly_d, holdout_weeks=3)
    m = rep["metrics"]
    for key in ("r2", "baseline_r2", "mae", "baseline_mae", "improvement_pct", "n_test", "test_weeks"):
        assert key in m
    assert rep["estimate"] is True
    preds = rep["predictions"]
    assert set(preds) == {"BTP1 - Rising", "BTP2 - Steady", "BTP3 - Noisy"}
    vocab = set(M.FEATURES.values())
    for p in preds.values():
        assert p["pred"] >= 0 and p["dir"] in ("up", "down", "flat")
        assert 1 <= len(p["reasons"]) <= 2
        assert all(r in vocab for r in p["reasons"])           # plain-language, from the known set


def test_steady_junction_forecasts_flat(weekly_d):
    rep = M.build_report(weekly_d, holdout_weeks=3)
    steady = rep["predictions"]["BTP2 - Steady"]
    assert steady["dir"] == "flat"                             # constant history -> ~no change
    assert abs(steady["pred"] - 50.0) < 12


def test_predictions_are_finite(weekly_d):
    rep = M.build_report(weekly_d, holdout_weeks=3)
    assert all(np.isfinite(p["pred"]) and np.isfinite(p["last"]) for p in rep["predictions"].values())
