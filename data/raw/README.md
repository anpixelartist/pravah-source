# data/raw — put the parking-violation CSV here (NOT committed; gitignored)

Pravah uses **only the provided parking-violation dataset** (PS1 — Parking-Induced
Congestion). The ASTraM event/incident dataset is intentionally **not** used (competition
constraint — see `docs/adr/0002-skip-cv-and-festival.md`).

The pipeline auto-detects by filename pattern (see `config/pravah.toml`):
- violations: `*violation*.csv`  (the ~298k-row parking file)

So you can drop the original as-is:
- `jan_to_may_police_violation_anonymized791b166.csv`

or rename it to `violations.csv`. Then:

    make setup
    make aggregates   # regenerates web/data/aggregates.json + prints the FACT & MODEL check

⚠️ This data contains anonymised but sensitive records (incl. vehicle numbers). Never
commit it; never paste it into external tools. See docs/TRUST.md (governance).
