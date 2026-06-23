# Data dictionary (real columns we rely on)

Place the parking-violation CSV in `data/raw/`. The pipeline auto-detects it by pattern (see
`config/pravah.toml`); or rename to `violations.csv`. **Only the parking-violation dataset is
used** — the ASTraM event/incident dataset is intentionally not consumed (see ADR 0002).

## violations  (~298,445 rows · 2023-11-10→2024-04-08 · 100% geocoded)
| column | use |
|---|---|
| latitude, longitude | mapping, grid cells, phantom detection (FACT: all non-zero) |
| created_datetime | UTC → convert to Asia/Kolkata; hour, evening flag |
| violation_type | stringified list e.g. `"['WRONG PARKING']"` → explode → severity |
| vehicle_type | → footprint weight |
| junction_name | `"No Junction"` when untagged; named-junction aggregation |
| police_station | zone-level rollups, equity |
| vehicle_number | recidivism feature (PERSONAL DATA — see governance) |
| validation_status | data-quality / rejection-rate feature (~30% rejected) |
| closed_datetime, action_taken_timestamp | response timing (optional) |

~93% of rows are parking violations. Severity & footprint maps: `src/pravah/constants.py`.

The next-week forecast (`model.py`) is built from a **weekly trajectory of this same parking
data** — no second dataset. See `docs/MODEL.md`.

> The ASTraM event/incident dataset is **not used** (competition constraint — ADR 0002). No CV,
> no breakdown/festival forecaster, no external/live sources.
