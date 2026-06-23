# BUILD_PROMPT.md — paste this to kick off the agent

> Use this as your first message to the coding agent (Claude Code / Cursor) after opening
> the repo. `CLAUDE.md` is loaded automatically as project context; this prompt sets the
> first task. Keep it short on purpose — the depth lives in CLAUDE.md and docs/.

---

You are the lead engineer on **Pravah** (PS1 — Parking-Induced Congestion). Read `CLAUDE.md`,
`docs/MILESTONES.md`, `docs/ARCHITECTURE.md`, `docs/PRESSURE_INDEX.md`, `docs/MODEL.md`, and
`docs/TRUST.md` before writing code. Then:

1. Confirm your understanding back to me in 6 bullets: the mission, the glass-box +
   plain-language rule, the "data lies by omission" rule, the do-not-build list (incl. the
   only-provided-dataset / no-ASTraM-event-data constraint), where the validated constants
   live, and the milestone you're starting.
2. Place the parking CSV in `data/raw/` (see `data/raw/README.md` for the exact filename), then
   run `make setup && make aggregates`. Confirm the output reproduces the validated FACTs
   (evening share ≈ 0.85%, Safina Plaza top, ~3,489 repeat offenders) and the MODEL line
   (R² ≈ 0.84 on held-out weeks). If it doesn't, stop and tell me what drifted — do not "fix"
   by changing the constants.
3. Begin at the **first unfinished milestone** in `docs/MILESTONES.md`. For each milestone:
   read the module contracts, implement, make `make test` and `make lint` pass, then show
   me a one-paragraph summary + the acceptance evidence before moving on.

Rules that override anything else you might infer:
- Glass box, explainable by default. Every score decomposes; every output a user sees states
  its reason — in **plain language** (no jargon in the UI; see CLAUDE.md for the banned list).
- Label FACT (from data), EST (modelled), and AI (the ML model's prediction) distinctly.
- Use **only the provided parking-violation dataset**. No ASTraM event/incident data, no
  external or live sources. Nothing in the demo path may require the internet (self-host fonts).
- Do not build CV, ASTraM event/incident analytics, a festival forecaster, deep learning, or
  live ASTraM/CCTV integration.
- Human-in-the-loop: recommend, never auto-dispatch.
- Reproduce validated numbers; never silently change `src/pravah/constants.py` to make a
  test pass — if a constant is wrong, raise it with me explicitly.

Optimise for a jaw-dropping, trustworthy 3-minute demo, not feature count. Move fast, but
leave every decision explainable. Start by confirming understanding, then go.
