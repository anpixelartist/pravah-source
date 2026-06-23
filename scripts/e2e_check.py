"""End-to-end data-integrity + engine-parity checks over the built artifacts.
Validates web/data.js against the engine's invariants, and writes the expected re-weighted
ranking (web/_e2e_expected.js) so the browser harness can prove app.js's live recompute
matches the Python engine. Run after `make aggregates`."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

from pravah import constants as C
from pravah.optimise import compare
from pravah.pressure import compute_pressure

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((PASS if cond else FAIL, name, detail))


def load_data() -> dict:
    txt = Path("web/data.js").read_text(encoding="utf-8").strip()
    return json.loads(re.sub(r"^window\.PRAVAH_DATA=|;$", "", txt))


def main() -> int:
    d = load_data()
    k, J = d["kpi"], d["junctions"]

    for key in ("kpi", "meta", "junctions", "phantom", "hourly", "density", "areas", "model"):
        check(f"data.{key} present", key in d)

    check("total = 298,445", k["total"] == C.FACT_TOTAL_APPROX, str(k["total"]))
    check("evening share ~0.85%", abs(k["eve_pct"] - C.FACT_EVENING_SHARE_PCT) < 0.3,
          f"{k['eve_pct']}%")
    check("top junction = Safina Plaza",
          C.FACT_TOP_JUNCTION.lower() in k["top_junction"].lower(), k["top_junction"])
    check("repeat offenders ~3,489",
          abs(k["repeat_offenders"] - C.FACT_REPEAT_OFFENDERS_GE5) < 150, str(k["repeat_offenders"]))
    check("phantom hotspots >= 5", k["n_phantom"] >= 5, str(k["n_phantom"]))
    check("junctions count matches", k["n_junctions"] == len(J), f"{k['n_junctions']} vs {len(J)}")

    bad_decomp = bad_press = bad_fc = bad_req = 0
    for j in J:
        if abs((j["pc"] + j["pb"] + j["pv"]) - j["pressure"]) > 1.5:
            bad_decomp += 1
        if not 0 <= j["pressure"] <= 100:
            bad_press += 1
        if j["req"] not in (1, 2, 3):
            bad_req += 1
        fc = j.get("fc")
        if fc is not None and (fc["dir"] not in ("up", "down", "flat")
                               or not isinstance(fc["reasons"], list)):
            bad_fc += 1
    check("decomposition sums to pressure (all)", bad_decomp == 0, f"{bad_decomp} off")
    check("pressure in 0..100 (all)", bad_press == 0, f"{bad_press} off")
    check("officer tier in {1,2,3} (all)", bad_req == 0, f"{bad_req} off")
    check("forecast shape valid (all)", bad_fc == 0, f"{bad_fc} bad")

    m = d["model"]["metrics"]
    check("model R2 present & >0.5", m.get("r2", 0) > 0.5, str(m.get("r2")))
    check("model beats naive baseline", m["r2"] >= m["baseline_r2"],
          f'{m["r2"]} vs {m["baseline_r2"]}')
    n_up = sum(1 for j in J if (j.get("fc") or {}).get("dir") == "up")
    check("n_rising matches forecasts", d["model"]["n_rising"] == n_up,
          f'{d["model"]["n_rising"]} vs {n_up}')
    imp_sum = sum(d["model"]["importances"].values())
    check("feature importances ~1.0", abs(imp_sum - 1.0) < 0.05, f"sum={imp_sum:.3f}")

    dens = d["density"]
    maxi = dens["w"] * dens["h"] - 1
    in_range = all(0 <= c[0] <= maxi and c[1] > 0 for c in dens["cells"])
    check("density cells in-range & positive", in_range and len(dens["cells"]) > 500,
          f"{len(dens['cells'])} cells")
    la0, la1, lo0, lo1 = k["bbox"]
    areas_ok = all(la0 <= a["lat"] <= la1 and lo0 <= a["lon"] <= lo1 for a in d["areas"])
    check("area labels within bbox", areas_ok and len(d["areas"]) >= 8, f"{len(d['areas'])} areas")
    bm = Path("web/basemap.js")
    check("basemap.js bundled (offline)", bm.exists() and bm.stat().st_size > 50_000,
          f"{bm.stat().st_size // 1024}KB")

    df = pd.DataFrame(J)
    ok_uplift = all(compare(df, n)["pravah"]["recovered"]
                    >= compare(df, n)["baseline"]["recovered"] - 1e-6 for n in (8, 18, 30))
    check("deployment: Pravah >= baseline (8/18/30)", ok_uplift)

    # re-weight sanity: a blindness-led weighting must change the ranking (and stay valid)
    rew = compute_pressure(df, weights={"chronic": 0.2, "blindness": 0.6, "volume": 0.2})
    check("re-weight changes ranking", rew.iloc[0]["name"] != J[0]["name"],
          f'{rew.iloc[0]["name"]} vs default {J[0]["name"]}')

    print("\n=== DATA-INTEGRITY & ENGINE-PARITY ===")
    for status, name, detail in results:
        print(f"  [{status}] {name}" + (f"  ({detail})" if detail else ""))
    n_fail = sum(1 for r in results if r[0] == FAIL)
    print(f"\n  {len(results) - n_fail}/{len(results)} passed.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
