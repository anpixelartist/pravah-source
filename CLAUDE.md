# CLAUDE.md — operating manual for the Pravah build agent

You are the lead engineer building **Pravah** (प्रवाह, "flow"), our entry for the
Bengaluru Traffic Police / ASTraM hackathon. Read this file fully before touching code.
It is the source of truth. When in doubt, follow it over your own assumptions.

## Mission (the one idea everything serves)
Police measure enforcement in the wrong currency: they count *violations* and deploy by
*gut*. The real goal is **flow** — commuter time lost. 500 helmet tickets can cause zero
congestion; one truck at a chokepoint costs thousands of vehicle-hours. Pravah re-expresses
violations as **vehicle-hours of delay**, ranks junctions by a single **Traffic Pressure
Index**, exposes the city's enforcement **blind spots**, and outputs an **officer-deployment
plan** that recovers the most time per officer. Tagline: *"Stop counting tickets. Start
recovering time."* We are the decision brain on top of ASTraM, not a competitor to it.

## Non-negotiable principles
1. **Glass box, never black box. Explainable by default.** Every output a user sees — each
   deployment, each score, each forecast — states WHY in plain language. Every score
   decomposes into named parts. No number a 55-year-old IPS officer can't have explained in
   one sentence. Where we use ML, it is interpretable (gradient boosting + SHAP), never a
   neural net.
2. **Plain language in the UI.** Anything a non-technical officer or judge reads is plain.
   BANNED in user-facing UI text: "TPI", "vehicle-hours", "knapsack", "chronic / blindness /
   volume", "budget", "coverage-normalised", "queueing". Use instead: "pressure score",
   "hours of stuck traffic cleared", "barely checked in the evening", "officers available",
   etc. Technical terms live ONLY in docs/spec/code — never in the interface.
3. **The solution is only as good as its inputs.** Feature engineering is a first-class
   deliverable, not glue code. See `docs/TRUST.md`. This is where we win — focus here.
4. **The data lies by omission.** Tickets exist where officers stood. "No tickets after
   3pm" means "nobody looked," not "no violations." Never feed raw counts to a model that
   will then tell police to keep doing what they already do. Use coverage-normalised
   features (TASK FE-3).
5. **Facts, estimates, and AI output are visually + textually distinct** everywhere — UI,
   docs, speech. FACT = measured from data; EST = modelled/derived; AI = the interpretable
   ML model's prediction. Keep the small FACT / EST / AI badges in the UI, mandatory.
6. **Only the provided dataset for analysis.** Every number, score, ranking and forecast comes
   from the provided **parking-violation** data alone. No external/live data feeds the analysis;
   the ASTraM event/incident dataset is **not** used. The one exception is purely cartographic:
   a **street basemap** (OpenStreetMap road/water geometry) is fetched **once at build time** by
   `scripts/build_basemap.py` and **bundled locally** (`web/basemap.js`) as a visual backdrop —
   never a live call, never an analysis input. If the competition forbids any third-party
   cartography, delete `basemap.js` and the map falls back to the data-only density base.
7. **Offline-first.** The demo runs by opening `web/index.html` — no server, no internet, no
   live tiles/APIs at demo time. Real lat/long on our own canvas projection; self-host fonts and
   the basemap; no CDN. The only network use anywhere is build-time asset prep (fonts, basemap).
8. **Human-in-the-loop.** Pravah *recommends*; the officer *decides*. Never auto-dispatch.

## Hard "do not build" list (these lose, or have no data — confirmed against the files)
- ❌ Computer vision / helmet detection. No dataset; ~80% of teams do it. Red ocean.
- ❌ Anything on the **ASTraM event/incident dataset**. Competition constraint — we use only
     the parking-violation file. (No breakdown/incident forecaster, no festival/rally predictor.)
- ❌ Real-time ASTraM / CCTV integration. Out of scope for the hackathon; mock the seam.
- ❌ External / live data (map tiles, geocoders, traffic APIs). Offline-only.
- ❌ Deep learning anything. Violates principle 1.

## One theme (submission framing)
Submit as a clean **PS1 — Parking-Induced Congestion** solution. One coherent story:
find the chronic + blind-spot pressure, predict where it heads next week, deploy against it
with a reason on every pick. No second theme competing for the judge's attention.

## Validated ground truth (already computed from the real 298,445 records — do NOT re-guess)
- Window: 2023-11-10 → 2024-04-08 (~21.4 weeks). 100% of rows geocoded.
- ~93% of violations are parking. 137 ranked junctions (≥80 records), 55 police stations.
- City-wide share of violations in the 3–9pm window: **0.85%** (the blind spot). FACT.
- The junctions that DO get evening enforcement show ~12–15% evening share — proof the gap
  is enforcement, not reality. FACT.
- Top junction by pressure: **Safina Plaza**. FACT. 12 phantom hotspots off the radar. FACT.
- Repeat offenders: ~3,489 vehicles with ≥5 violations; max ~55. FACT.
- **corr(ticket-count, impact) = 0.98** → re-ranking deployment by impact instead of raw
  count gains only **~3–5%** more time recovered. Do NOT inflate this. The real advantages
  are the **blind spot + phantom coverage** (places count-based enforcement never sees) and
  the **forward forecast** — not the optimiser delta.
- **Interpretable model (DELIVERED, required):** a `GradientBoostingRegressor` predicts each
  junction's next-week parking pressure from its recent trajectory. Forward-validated on the
  held-out last 5 weeks (16–20; the partial final week is dropped): **R² = 0.844** (naive
  "next week = last week" baseline R² = 0.827), MAE 25.2 vs 26.9 → **+6.2% better on MAE**.
  SHAP gives per-prediction reasons. Trees + SHAP only — never a neural net (ADR 0001). All
  model output is labelled **AI/EST**; the trajectory it learns from is FACT. See `docs/MODEL.md`.
- "~16k uncaught evening violations" and all vehicle-hour figures are EST (modelled).
All constants (severity, footprint, bbox, weights, thresholds) live in
`src/pravah/constants.py`. Treat them as authoritative.

## How to work
- Execute `docs/MILESTONES.md` in order. Each milestone has a deliverable + an acceptance
  test. Do not start the next milestone until the current one's tests pass.
- Before writing a module, read its docstring contract — interfaces are already defined.
- Run `make test` and `make lint` before declaring any milestone done.
- Reproduce the validated numbers. `tests/test_sanity.py` checks them against the real
  data; if your pipeline output drifts from the FACTs above, you broke something.
- Keep functions pure where possible (data in → data out). Side effects (file writes,
  fetches) live only in `build_aggregates.py` and the CLI layer.
- Commit per milestone with a message `Mx: <what>`.

## Architecture (see docs/ARCHITECTURE.md)
raw parking CSV → `pipeline` (clean·enrich·aggregate) → `features` → `pressure` + `optimise` +
`model` (interpretable next-week forecast + SHAP) → `build_aggregates` writes
`web/data/aggregates.json` → self-contained, offline web command centre renders it.
`explain`, `validate`, `equity` wrap the core for trust.

## Definition of done for the whole product
See `docs/MILESTONES.md` → "Acceptance: demo-ready". If every box is checked and
`make demo` shows a working offline command centre with decomposed scores, the live
deployment uplift, and a labelled forecast, we ship.
