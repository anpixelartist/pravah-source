"""Data-gated: reproduce the VALIDATED FACTs from the real CSVs. Run with the files in
data/raw/. Skipped automatically if absent (so CI stays green without private data)."""

import pytest

from pravah import constants as C
from pravah import pipeline as P
from pravah.build_aggregates import _find, build
from pravah.config import Config
from pravah.pressure import compute_pressure

pytestmark = pytest.mark.data
cfg = Config.load()
_has_data = cfg.raw_dir.exists() and _find(cfg.raw_dir, cfg.violations_glob) is not None


@pytest.fixture(scope="module")
def agg():
    if not _has_data:
        pytest.skip("no violations CSV in data/raw — see data/raw/README.md")
    return build(cfg, quick=True)


@pytest.fixture(scope="module")
def clean():
    if not _has_data:
        pytest.skip("no violations CSV in data/raw — see data/raw/README.md")
    return P.clean_enrich(P.load_violations(_find(cfg.raw_dir, cfg.violations_glob)))


def test_evening_blind_spot(agg):
    assert abs(agg["kpi"]["eve_pct"] - C.FACT_EVENING_SHARE_PCT) < 0.3


def test_top_junction_is_known_bad(agg):
    assert C.FACT_TOP_JUNCTION.lower() in agg["kpi"]["top_junction"].lower()


def test_repeat_offenders_count(agg):
    assert abs(agg["kpi"]["repeat_offenders"] - C.FACT_REPEAT_OFFENDERS_GE5) < 150


def test_has_phantom_hotspots(agg):
    assert agg["kpi"]["n_phantom"] >= 5


def _top(dd, k=10):
    j = P.aggregate_junctions(dd, cfg.min_junction_records)
    j = compute_pressure(j, cfg.weights, cfg.recovery_coef, P.weeks_span(dd))
    return j.head(k)["name"].tolist()


def test_ranking_robust_to_rejected_tickets(clean):
    """Limit: ~30% of decided tickets are rejected. Show the ranking isn't an artifact of them —
    drop every rejected ticket and the top-10 barely moves, top junction unchanged."""
    rej = clean["validation_status"].astype(str).str.contains("reject", case=False, na=False)
    full, val = _top(clean), _top(clean[~rej])
    assert len(set(full) & set(val)) >= 8
    assert C.FACT_TOP_JUNCTION.lower() in val[0].lower()


def test_evening_blindspot_robust_to_rejected_tickets(clean):
    """The 0.85% evening blind spot survives removing all rejected tickets (it's not noise)."""
    rej = clean["validation_status"].astype(str).str.contains("reject", case=False, na=False)
    assert abs(100 * clean["evening"].mean() - 100 * clean[~rej]["evening"].mean()) < 0.3
