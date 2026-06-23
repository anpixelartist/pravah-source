# Pravah · प्रवाह — "flow"

**Stop counting tickets. Start recovering time.**

Pravah turns Bengaluru's parking-violation records into a decision tool for the Traffic
Police. It ranks every junction by a single **pressure score**, exposes the city's evening
enforcement **blind spots** and **phantom hotspots**, **predicts** which junctions get worse
next week (interpretable ML), and recommends **officer deployment** — with a plain-language
reason on every number. Our entry for **PS1 — Parking-Induced Congestion**.

Built on **298,445 real parking-violation records** (2023-11-10 → 2024-04-08). We use **only**
the provided parking dataset — no ASTraM event feed, no external or live data, fully offline.

> Why we win: every other team shows you where the problems *were*. Pravah shows where to put
> your people *next week* — measured in people's time — and explains every recommendation in
> language a constable can act on.

## Quickstart
```bash
make setup                      # install (uv or pip)
# put the parking CSV in data/raw/ (see data/raw/README.md)
make aggregates                 # regenerate web/data/aggregates.json + print FACT & MODEL check
make test                       # pure tests always run; data tests run if the CSV is present
open web/index.html             # the offline command centre (the demo) — no server needed
```

## What's here
- `src/pravah/` — the pure analytics core: `pipeline` → `features` → `pressure` / `optimise` /
  `model` (interpretable next-week forecast + SHAP), wrapped by `explain` / `validate` /
  `equity`. `build_aggregates` is the only I/O. Validated constants in `constants.py`.
- `web/` — the offline, self-contained command centre (the demo). Vanilla HTML/CSS/JS.
- `docs/` — read first: `MILESTONES.md` (build plan), `ARCHITECTURE.md`, `PRESSURE_INDEX.md`,
  `MODEL.md` (the ML model + validation), `TRUST.md` (transparency + feature engineering),
  `DATA_DICTIONARY.md`, `adr/` (key decisions).
- `CLAUDE.md` / `BUILD_PROMPT.md` / `.cursor/rules/` — agentic-dev operating manual.

## How Pravah answers PS1 (Parking-Induced Congestion)
| The problem statement asks for… | Pravah delivers |
|---|---|
| Enforcement is **reactive** | a **forward forecast** of next-week pressure per junction (AI) |
| No **impact heat-map** | a live **pressure map** of 137 junctions, coloured by impact |
| Hard to **prioritise** | a ranked **priority list** + **phantom hotspots** off the radar |
| **Quantify** parking's impact | violations re-expressed as **hours of stuck traffic** |
| Enable **targeted enforcement** | an **explained deployment plan** — a reason on every pick |

## Principles (non-negotiable — see CLAUDE.md)
Glass box, explainable by default · plain language in the UI · the data lies by omission
(coverage-normalise) · FACT / EST / AI always labelled · only the provided dataset · runs
fully offline · human-in-the-loop (recommend, never auto-dispatch) · no CV, no deep learning.

## The 3-minute demo
1. Headline: "298,445 violations analysed — only **0.85%** caught in the 3–9pm window." (FACT)
2. Blind clock: the city goes dark after 3pm — but watched junctions show ~15% evening tickets,
   so it's an **enforcement gap, not reality**. (FACT)
3. Map: toggle phantom hotspots — thousands of violations, off the official radar. (FACT)
4. Forecast: the model calls next week's risers, with a plain reason each. (AI) R²=0.844 on
   held-out weeks it never saw, beating "next week = last week."
5. Deploy slider at your real officer count: same officers, more time recovered, **a reason on
   every pick** — and it covers the blind hours count-based enforcement can't see.
6. Close: "Stop counting tickets. Start recovering time."
