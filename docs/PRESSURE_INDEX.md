# The Traffic Pressure Index (TPI)

One number per junction, 0–100 — like an air-quality index, but for congestion.
It is a **formula, not a verdict**. It must always be shown decomposed.

```
TPI = 100 × ( w_chronic · norm(log1p(cost))
            + w_blind   · blindness
            + w_volume  · norm(log1p(n)) )

cost      = Σ (severity × vehicle_footprint) over the junction's violations
blindness = 1 − (junction_evening_share ÷ max_evening_share_across_junctions)
n         = raw violation count
norm(x)   = (x − min) / (max − min)   across all junctions
weights   = config/pravah.toml  (default 0.50 / 0.30 / 0.20)
```

## Why each term (say this to judges)
- **chronic cost** — a tanker double-parked on a main road must outweigh a scooter in a
  no-parking bay. Severity × footprint encodes that. (`constants.SEVERITY`, `constants.FOOTPRINT`)
- **blindness** — junctions never watched in the evening carry hidden, uncounted risk;
  this term stops the index from simply echoing where officers already patrol.
- **volume** — raw load still matters, but only at 20% weight, log-scaled so a few giant
  junctions don't dominate everything.

## Decomposition (glass box)
`explain.decompose(j)` returns the three contributions in points (they sum to TPI ±1):
`pc = 100·w_chronic·norm(...)`, `pb = 100·w_blind·blindness`, `pv = 100·w_volume·norm(...)`.
The UI shows e.g. **TPI 98 = 51 chronic + 28 blindness + 19 volume**.

## Derived, transparent outputs
- `rec` = recoverable vehicle-hours/week (EST) = cost / weeks × `RECOVERY_COEF` (0.90).
  This is a queueing-style approximation; the coefficient is config and stated openly.
- `req` = officers suggested: TPI ≥ 85 → 3, ≥ 60 → 2, else 1 (`constants.OFFICER_TIERS`).

> All `rec`/vehicle-hour figures are ESTIMATES. The ranking, counts, evening share and
> blindness inputs are FACTS computed from the data.

## Plain-language names (UI vs spec)
This document is the spec, so it uses the precise terms. The **UI must not** — see CLAUDE.md.
The mapping the interface uses:

| spec term | what the officer sees |
|---|---|
| TPI / Traffic Pressure Index | **pressure score** (0–100) |
| chronic load | **how bad the illegal parking is** (big vehicles, main roads) |
| blindness | **barely checked in the evening** |
| volume | **sheer number of cases** |
| recoverable vehicle-hours | **hours of stuck traffic cleared** |
| officers (knapsack budget) | **officers available** |
