# AGENTS.md
This repo is built for agentic development. The canonical instructions for any AI agent
working here are in **CLAUDE.md** (mission, principles, hard limits, validated ground
truth) and **docs/MILESTONES.md** (the ordered task plan with acceptance tests).

Cursor users: rules are mirrored in `.cursor/rules/pravah.mdc`.
Any agent: read CLAUDE.md first, execute MILESTONES.md in order, keep `make test` green,
and never break the core principles:
- **Glass box, explainable by default** — every score decomposes; every user-facing output
  states WHY, in **plain language** (no jargon in the UI — see CLAUDE.md for the banned list).
- **FACT / EST / AI** labelling is mandatory everywhere.
- **Only the provided parking-violation dataset.** No ASTraM event/incident data, no external
  or live sources. The demo runs fully **offline** (self-hosted fonts, no CDN).
- Interpretable ML only (gradient boosting + SHAP) — never a neural net.
