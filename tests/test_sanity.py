"""Data-gated: reproduce the VALIDATED FACTs from the real CSVs. Run with the files in
data/raw/. Skipped automatically if absent (so CI stays green without private data)."""

import pytest

from pravah import constants as C
from pravah.build_aggregates import _find, build
from pravah.config import Config

pytestmark = pytest.mark.data
cfg = Config.load()
_has_data = cfg.raw_dir.exists() and _find(cfg.raw_dir, cfg.violations_glob) is not None


@pytest.fixture(scope="module")
def agg():
    if not _has_data:
        pytest.skip("no violations CSV in data/raw — see data/raw/README.md")
    return build(cfg, quick=True)


def test_evening_blind_spot(agg):
    assert abs(agg["kpi"]["eve_pct"] - C.FACT_EVENING_SHARE_PCT) < 0.3


def test_top_junction_is_known_bad(agg):
    assert C.FACT_TOP_JUNCTION.lower() in agg["kpi"]["top_junction"].lower()


def test_repeat_offenders_count(agg):
    assert abs(agg["kpi"]["repeat_offenders"] - C.FACT_REPEAT_OFFENDERS_GE5) < 150


def test_has_phantom_hotspots(agg):
    assert agg["kpi"]["n_phantom"] >= 5
