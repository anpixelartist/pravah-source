from pravah.explain import decompose
from pravah.pressure import compute_pressure


def test_pressure_in_range_and_sorted(toy_junctions):
    out = compute_pressure(toy_junctions)
    assert out["pressure"].between(0, 100).all()
    assert out["pressure"].is_monotonic_decreasing  # sorted worst-first


def test_decomposition_sums_to_pressure(toy_junctions):
    out = compute_pressure(toy_junctions)
    for _, r in out.iterrows():
        assert abs((r["pc"] + r["pb"] + r["pv"]) - r["pressure"]) <= 1.0


def test_glass_box_label(toy_junctions):
    out = compute_pressure(toy_junctions)
    d = decompose(out.iloc[0].to_dict())
    assert "TPI" in d["label"] and len(d["parts"]) == 3
