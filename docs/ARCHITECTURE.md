# Architecture

```
data/raw/*violation*.csv   (parking dataset ONLY — no ASTraM event/incident feed)
      │  (read, validate against schema)
      ▼
pipeline.py ──> clean (bbox filter, dedup, parse violation lists)
      │         enrich (IST hour, evening flag, severity×footprint cost)
      │         aggregate (junctions ≥80 recs, ~270m grid cells)
      ▼
features.py ──> temporal · spatial (neighbour lag) · vehicle/violation ·
      │         recidivism · validation-rate · COVERAGE-NORMALISED true-rate
      ▼
  ┌───────────────┬──────────────────┬───────────────────┐
pressure.py     optimise.py        model.py
(pressure       (greedy deploy;    (next-week pressure
 score 0–100,   baseline vs        per junction;
 decomposed)    Pravah uplift)     GBR + SHAP reasons,
                                    forward-validated)
  └──────┬────────┴──────────────────┴─────────┘
         │  explain.py (decompose scores, reasons), validate.py, equity.py
         ▼
build_aggregates.py  ──> web/data/aggregates.json  (small, pre-computed)
         ▼
web/index.html  ──> offline command centre: map · blind clock · priority queue ·
                    deployment console (reasons) · forecast · FACT/EST/AI badges
```

## Why this shape
- **Pure core, thin shell.** `pipeline/features/pressure/optimise/model` are pure
  (data in → data out, no I/O). Only `build_aggregates.py` and the CLI write files. This
  makes everything unit-testable and explainable.
- **Pre-computed aggregates.** The browser never touches 298k rows; it loads a ~140KB JSON.
  Instant, and offline-safe (no tiles, no APIs, self-hosted fonts). In production the same JSON
  is produced from the live parking-violation feed instead of a static CSV — that is the only
  seam that changes.
- **Config-driven.** Index weights and thresholds live in `config/pravah.toml`, so an
  officer can re-weight and the ranking moves — transparency you can touch.
- **Trust wrappers, not bolt-ons.** `explain/validate/equity` sit beside the core so every
  number can be traced, tested for validity, and checked for fairness.

## The self-learning loop (M4+)
Each recommendation is logged → next period's data tests whether predicted hotspots held →
weights/feature-importance adjust. This is the answer to the brief's "no post-event learning
system" complaint. Implement as a simple, auditable feedback table — not an opaque online model.
