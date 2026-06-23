from pravah.optimise import compare, knapsack
from pravah.pressure import compute_pressure


def test_pravah_beats_or_matches_ticket_baseline(toy_junctions):
    out = compute_pressure(toy_junctions)
    res = compare(out, n_officers=4)
    assert res["pravah"]["recovered"] >= res["baseline"]["recovered"]


def test_allocate_respects_officer_budget(toy_junctions):
    out = compute_pressure(toy_junctions)
    rows = out.to_dict("records")
    res = knapsack(rows, 3)
    assert res["officers_used"] <= 3
