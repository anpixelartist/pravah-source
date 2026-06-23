# Trust, transparency & feature engineering

Our differentiation is not a fancier model — it is a solution the police can **trust and
defend** (to a senior officer, an RTI request, the press). The trust architecture:

**good inputs (feature engineering) → transparent reasoning (glass box) → proven & honest
(validation + limits) → human decides (in the loop).**

## 1. Feature engineering (the intelligence lives here)
The raw columns are weak; the derived features are the product. The "implemented in" column
names the pure, unit-tested function in `src/pravah/features.py` (M1 — see `tests/test_features.py`).

| Group | Features | Why it matters | Implemented in |
|---|---|---|---|
| Temporal | hour, day-of-week, weekend, peak/off-peak, evening-blind flag, holiday join, time-since-last (per junction) | when pressure happens; isolates the blind window | `add_temporal` (`pipeline.clean_enrich` sets hour/evening) |
| Spatial | junction, ~270m cell, neighbour density (spatial lag), police-station zone, commercial-intensity proxy | pressure clusters; proxy stands in for missing land-use data | `neighbour_density`, `coverage_proxy` (`pipeline.grid_cells`) |
| Vehicle / violation | severity weight, footprint, lane-blocking flag, heavy-vehicle flag | a lorry ≠ a scooter; encodes real obstruction | `add_vehicle_flags` (severity/footprint in `pipeline`) |
| Recidivism | per-vehicle repeat count (max ~55), per-junction repeat share | habitual violators are a real, targetable signal | `add_recidivism`, `build_junction_features` |
| Enforcement context | local validation/rejection rate, **coverage / exposure → true rate** | data-quality + the bias correction below | `validation_rate`, `junction_exposure`, `coverage_adjust` |

### The key feature: coverage normalisation (TASK FE-3)
The data is **enforcement-generated**: tickets exist where officers stood. Raw counts, fed
to a model, will confidently tell police to keep patrolling exactly where they already do —
and ignore the blind spots forever. So we estimate **exposure** (how much each place was
actually watched, e.g. distinct enforcement hours/officers per cell) and compute a
coverage-adjusted **true rate** ≈ observed ÷ exposure. This turns the blind-spot finding
from a chart into a corrected map. Start with a documented baseline; refine, don't overfit.

**Implemented (M1):** `features.junction_exposure` estimates exposure as the distinct active
hours a junction was ever watched (1..24); `features.coverage_adjust` divides chronic cost by
that coverage to produce `cost_adj` (the true rate), capped at `COVERAGE_MAX_FACTOR` so a sliver
of exposure can't explode a score. The Pressure Index consumes it on request —
`compute_pressure(chronic_col="cost_adj")` — while the **default basis stays `cost`** so the
validated FACTs reproduce unchanged. The same insight also drives the index's blindness term.

## 2. Transparent reasoning (glass box) — and plain language
- Scores decompose (`explain.decompose`) — the pressure score = chronic + blindness + volume,
  in points. (Those internal terms appear in docs/code; in the UI they read as plain English.)
- Every recommendation carries a one-sentence reason (`explain.deployment_reason`).
- Weights are config and adjustable live — transparency you can touch.
- Click-through to the raw violation records behind any score.
- Counterfactuals: "ignore this junction → lose X hours of stuck traffic cleared."
- The forecast (`model.py`) is interpretable: gradient boosting + SHAP, never a neural net.
  Each prediction shows its plain-language drivers.
- **Plain language is a rule, not a nicety.** Anything an officer/judge reads avoids jargon
  ("TPI", "vehicle-hours", "knapsack", "coverage-normalised"…). See CLAUDE.md for the banned
  list. Three badges keep provenance honest: **FACT** (data), **EST** (modelled), **AI** (model).

## 3. Proven & honest
- **Validity** (no ground-truth congestion exists, so we triangulate): a **forward, out-of-time
  forecast** — trained on early weeks, scored on the held-out last 5 weeks (16–20): **R² = 0.844**
  vs the naive persistence baseline 0.827 (+6.2% MAE), reproduced by `make aggregates`, never
  hardcoded (see `docs/MODEL.md`); face-validity (top junctions match known-bad spots — they do);
  a mini natural experiment (did enforcement lower a junction's repeat-violation rate?).
- **Honest about the optimiser:** corr(ticket-count, impact) = 0.98, so re-ranking deployment by
  impact instead of raw count only adds **~3–5%** more time recovered. We say so — the real wins
  are the blind-spot + phantom coverage and the forward forecast, not the optimiser delta.
- **Robust to the rejected-ticket bias:** drop every rejected ticket and re-run — the top-10
  junctions stay **9/10** unchanged (top junction still Safina Plaza) and the evening share moves
  only **0.85% → 0.79%**. The findings aren't artifacts of disputed tickets. Reproduced by
  `tests/test_sanity.py`.
- **Equity guardrail** (`equity.py`): deploying purely by time-recovered over-polices rich
  commercial corridors and starves residential zones — flag it.

## 3a. Known limits & how we handle them
The data is enforcement-generated; some bias is **structural and cannot be fully removed** from a
dataset that never recorded the absences. We don't hide that — we bound it, mitigate it, and show
the residual. (This is also surfaced in the UI: the Overview "Honest about the data" note and a
per-junction **data-confidence** flag.)

| Limit | Why it matters | What Pravah does | Residual risk |
|---|---|---|---|
| **Enforcement-generated** — tickets only exist where officers stood | Un-patrolled junctions read as "clean" when they're just unseen; a naive model would entrench current patrols | Coverage-normalised features (`features.coverage_adjust`, FE-3) + the **blindness** term; we treat the blind spot as *the finding*, not noise (ADR 0004) | Places with **zero** history can't be scored from absence — surfaced as cold-start, never invented |
| **Timestamps are filing-time, not occurrence-time** | A 3–9pm crackdown clusters at filing time; the 0.85% evening figure partly reflects *when officers file* | We don't rest the claim on the raw clock alone — we use a **control**: junctions that *are* watched in the evening still write ~12–15% of tickets then, so the gap is enforcement, not reality | Exact occurrence times are unknowable; the evening finding is directional, not a precise count |
| **~30% of *decided* tickets rejected** (≈17% of all; ~40% are never adjudicated) | Scores leaning on rejected tickets are less reliable | Rejection rate (among decided tickets) is exported **per junction** and shown as a **confidence flag** (high/medium/low) in the UI; the ranking is verified robust to dropping rejected tickets (above) | Can't tell officer-error vs contested-but-real vs data-entry; we flag, we don't adjudicate |
| Geocoding noise · cold-start junctions | Minor placement error; thin-history junctions | ~270m grid tolerance; cold-start junctions degrade gracefully (no guessed scores) | Small positional jitter remains |

> The honest stance: Pravah makes a biased dataset **safer to act on** — it cannot make it unbiased.

## 4. Human-in-the-loop
Pravah recommends; the officer decides. Never auto-dispatch. Say this explicitly — it is
how adoption happens instead of resistance.

## Privacy / governance
`vehicle_number` is personal data; the recidivism feature needs handling rules (hashing,
access control, retention). One line on governance signals we are deployment-ready.
