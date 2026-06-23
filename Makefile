# Pravah config — weights & thresholds live here so they're transparent and adjustable.
# An officer can re-weight the Traffic Pressure Index and watch the ranking move.

[paths]
raw_dir = "data/raw"
violations_glob = "*violation*.csv,violations.csv"
out_json = "web/data/aggregates.json"
# NOTE: only the provided parking-violation dataset is used. The ASTraM event/incident
# dataset is intentionally NOT consumed (competition constraint) — see docs/ADR 0002.

[weights]            # must sum to 1 (auto-normalised if not). See docs/PRESSURE_INDEX.md
chronic = 0.50
blindness = 0.30
volume = 0.20

[model]
recovery_coef = 0.90       # EST: recoverable vehicle-hours/week = cost/weeks * this
min_junction_records = 80
bg_sample = 3500
