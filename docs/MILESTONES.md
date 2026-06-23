# MILESTONES — the agent executes these in order

Each milestone: **deliverable → files → acceptance test**. Do not advance until the
acceptance test passes (`make test` + `make lint` green, plus the stated check).

Status legend: [x] done in scaffold · [ ] for the agent.

## M0 — Repo runs end-to-end (scaffold)            [x] (verify on your machine)
- Deliverable: `make setup && make aggregates` regenerates `web/data/aggregates.json`
  from the raw CSVs; `make demo` opens the command centre.
- Acceptance: `tests/test_sanity.py` passes against real data (evening share ≈ 0.85% ±0.3,
  top junction = Safina Plaza, repeat offenders ≥5 ≈ 3,489 ±100). Pure tests
  (`test_pressure`, `test_optimise`, `test_constants`) pass with no data present.

## M1 — Feature engineering layer                  [x] DONE
- Deliverable: `features.py` complete — temporal, spatial (incl. neighbour spatial-lag),
  violation/vehicle, recidivism, validation-rate, and the **coverage / exposure** features.
- Files: `src/pravah/features.py`, `tests/test_features.py`, update `docs/TRUST.md` table.
- Acceptance: each feature has a docstring stating what it is and why it matters; the
  coverage-normalised "true rate" feature exists and is used by pressure as an option;
  unit tests cover edge cases (cold-start junction with no history degrades gracefully).

## M2 — Glass-box explanations                      [x] DONE
- Deliverable: `explain.py` complete — `decompose(junction)` returns the point
  contributions (chronic / blindness / volume) that sum to the pressure score; 
  `deployment_reason(pick, alternative)` returns a one-sentence plain-language reason;
  forecast predictions return SHAP-style per-feature attributions.
- Files: `src/pravah/explain.py`, `tests/test_explain.py`.
- Acceptance: for any junction, contributions sum to pressure (±1). Every deployment pick
  in the optimiser output carries a non-empty reason string.

## M3 — Interpretable next-week pressure forecast    [x] DONE
- Deliverable: `model.py` — a `GradientBoostingRegressor` predicting each junction's next-week
  parking pressure (chronic load) from its recent trajectory (lags, rolling mean, trend,
  long-run level, recent evening activity). Forward-validated out-of-time; SHAP per-prediction
  reasons; per-junction forecast wired into the aggregates + UI. **Parking data ONLY** — the
  ASTraM event/incident dataset is not used (see ADR 0002). Interpretable trees + SHAP, never
  a neural net.
- Files: `src/pravah/model.py`, `tests/test_model.py`.
- Acceptance (met): trained on early weeks, scored on the held-out last 5 weeks (16–20) —
  **R² = 0.844** vs the naive persistence baseline R² = 0.827 (MAE 25.2 vs 26.9, **+6.2%**).
  Every prediction carries plain-language reasons. All output labelled AI/EST. Numbers are
  reproduced by `make aggregates` (the MODEL line) — never hardcoded.

## M4 — Validation & trust                          [ ]
- Deliverable: `validate.py` (backtest, face-validity, mini natural-experiment: did
  enforcement at a junction lower its repeat-violation rate?) and `equity.py` (zone-coverage
  fairness flag: warn when deployment starves whole zones).
- Files: `src/pravah/validate.py`, `src/pravah/equity.py`, tests for both.
- Acceptance: a `make report` produces a short metrics+fairness summary; equity flag fires
  on a deliberately skewed allocation in tests.

## M5 — Glass-box command centre                    [x] DONE (in scaffold)
- Deliverable: evolve `web/index.html` into the trust UI — click a junction to see its
  score decomposition and raw evidence; adjustable index weights (live re-rank); deployment
  console with baseline-vs-Pravah uplift AND per-pick reasons; FACT/EST badges; forecast view.
- Files: `web/index.html` (+ optional `web/app.js`, `web/styles.css`), `web/README.md`.
- Acceptance: works offline; weights slider re-ranks live; every number is FACT- or
  EST-badged; keyboard focus + reduced-motion respected; responsive to mobile.

## M6 — Submission package                           [ ]
- Deliverable: 6–8 slide deck, the 3-minute demo script in `README`, methods note on
  estimates, and an offline `dist/` build of the web app with data inlined.
- Acceptance: `make build-web` emits a single self-contained file that runs by double-click.

---

## Acceptance: demo-ready (the whole-product checklist)
- [x] One command regenerates all aggregates from the parking CSV (only dataset used).
- [x] Map renders 130+ real junctions offline; hover/click work; phantom layer toggles.
- [x] Click a junction → score decomposition + raw evidence shown (glass box).
- [x] Blind clock shows the 0.85% evening collapse with the proof caption.
- [x] Deploy slider shows a positive % uplift of Pravah over the ticket-count baseline,
      with a reason on every pick.
- [x] Next-week forecast view lists predicted risers with plain-language reasons (AI/EST).
- [x] Equity flag present; human-in-the-loop framing explicit.
- [x] Every fact is labelled FACT, every modelled number EST, every ML prediction AI.
- [x] All user-facing text is plain language (no jargon — see CLAUDE.md banned list).
- [x] Nothing in the demo path requires the internet (self-hosted fonts; no CDN/tiles/APIs).
