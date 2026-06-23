# The forecast model (interpretable, parking data only)

Pravah ships one ML model. It is **delivered and required**, not optional — and it is
**interpretable on purpose** (gradient-boosted trees + SHAP, never a neural net; see ADR 0001).
It uses **only the provided parking-violation dataset** — no ASTraM event/incident feed.

> All model output is labelled **AI/EST** in the UI. The trajectory it learns from is FACT.

## What it predicts
For every junction, **next week's parking pressure** — operationalised as next week's *chronic
load* `Σ(severity × vehicle_footprint)` — from that junction's own recent history. This turns a
reactive map ("where it was bad") into a forward one ("where to be next week").

## Features (all from a junction's PAST weeks → no leakage)
| feature | plain-language name (UI) |
|---|---|
| `lag1` / `lag2` / `lag3` | last week's load / two / three weeks ago |
| `roll3` | its recent 3-week average |
| `trend` | the week-over-week trend |
| `cummean` | its long-run typical load |
| `weeks_seen` | how long it has been tracked (cold-start guard) |
| `eve_lag1` | recent evening activity |

Built in `model.weekly_panel` → `model.make_supervised`. Missing weeks are real zeros; thin
histories are handled by `weeks_seen` rather than dropped (cold-start safe).

## How it's validated (honestly)
**Forward, out-of-time.** We train on the early weeks and score on the **held-out last 5 weeks
(16–20)** — the real test is "trained on the past, did it call the future," not a shuffled split.
The trailing **partial** week is dropped (the data window ends mid-week; a half-week would read
as a city-wide collapse). Benchmarked against the naive **persistence baseline** ("next week =
last week").

Reproduced every build by `make aggregates` (the `MODEL` line) — **never hardcoded**:

| metric | Pravah model | naive baseline |
|---|---|---|
| R² (held-out weeks 16–20) | **0.844** | 0.827 |
| MAE | **25.2** | 26.9 |
| improvement on MAE | **+6.2%** | — |
| train / test rows | 2,520 | 840 |

The gain over persistence is modest and we say so — parking pressure is highly persistent.
The value is a *calibrated, explained* forward call (which junctions are **rising**), not a
flashy headline number.

## Why each prediction is explainable
`model.predict_next` attaches, per junction: the predicted load, the change vs this week
(**rising / easing / steady**), and the **top drivers** of that prediction via
`shap.TreeExplainer`. We rank drivers by SHAP magnitude but phrase them neutrally and let the
headline carry direction — a SHAP sign is "vs the average junction-week," which would read
backwards next to a "rising/easing" headline. Global feature importance is in the model card.

## Limits (put them on a slide)
- Selection bias: the data is enforcement-generated (see `docs/TRUST.md`, FE-3) — the model
  learns the *observed* trajectory, not ground-truth demand.
- Short horizon: ~21 weeks of history; one-week-ahead only.
- Persistence-dominated: long-run level + last week explain most variance (see importances).
- It informs, it does not dispatch. Human-in-the-loop, always.
