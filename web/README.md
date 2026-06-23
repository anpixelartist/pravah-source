# web — the glass-box command centre (M5, delivered)

Three files: `index.html` (structure) · `styles.css` (identity + design tokens) · `app.js`
(logic). Data loads from `data.js` (inlined `window.PRAVAH_DATA`) and fonts are **self-hosted**
in `web/fonts/`, so the demo runs **fully offline** — just open `index.html` (double-click).
No map tiles, no APIs, no CDN, no CORS.

Regenerate `data.js` + `data/aggregates.json` from the parking CSV with `make aggregates`.
For live-data development (fetching `data/aggregates.json`) run `make web` and open localhost.

## Design — map-first, modern, light
The **city map is the home**; everything else lives in **one slide-in panel, one task at a
time** (Overview · a tapped junction · Priorities · Deploy · Forecast · Adjust), so the screen
is never crowded. Light, airy surface with one confident accent and the **teal → amber → coral
heat scale = pressure** (colour always means something). Display type Space Grotesk, body Inter,
numbers in JetBrains Mono — all self-hosted. Three provenance badges, always: **FACT** (measured),
**EST** (modelled), **AI** (model prediction). Progressive disclosure: tap a dot for detail;
nothing dumps everything at once.

### The map
A real **street basemap of Bengaluru** (OpenStreetMap roads + water) sits under a subtle
violation-density heat and the pressure dots, with area labels and a km scale bar. **Zoom**
(scroll, pinch, the +/−/⌖ buttons, or double-click) and **pan** (drag) to inspect any spot.
The basemap is fetched once at build time by `scripts/build_basemap.py` and bundled into
`web/basemap.js` — so the demo still runs **fully offline** (no tiles, no API, no live calls).
Delete `basemap.js` to fall back to a data-only density base if third-party cartography is
disallowed.

## Plain language (a rule, not a nicety)
No jargon in the interface. The UI never says "TPI", "vehicle-hours", "knapsack", "chronic /
blindness / volume", "coverage-normalised". It says "pressure score", "hours of stuck traffic
cleared", "officers available", "how bad the parking is", "evening blind spot", "number of
cases". Technical terms live only in `docs/` and code. See CLAUDE.md for the banned list.

## What's in it (glass box)
- **City pressure map (home)** — real coordinates on a self-contained projection; dots
  coloured/sized by the pressure score; hover for a plain tooltip; phantom hotspots as dashed
  rings. **Tap any dot** to open that junction.
- **Junction panel** — the pressure score broken into its three plain parts (FACT), the
  **next-week forecast** (AI) with its drivers, the raw recent tickets behind it, the suggested
  officers, and the cost of ignoring it.
- **Overview** — the headline numbers + the **blind clock** (the 0.85% evening collapse, with the
  proof caption). Opens first as the hook; close it for a clean map.
- **Priorities** — the ranked worst-first list; tap a row to jump to that junction.
- **Deploy** — places officers to clear the most stuck-traffic hours, a reason on every pick, an
  equity check across police-station areas, and an honest comparison vs today's ticket-led way.
- **Forecast** — the interpretable model's accuracy (R² on held-out weeks), what it leans on, and
  the junctions predicted to worsen — each with plain reasons. All badged AI.
- **Adjust (⚙)** — drag "how bad the parking is" / "evening blind spot" / "number of cases" and the
  whole city re-ranks instantly (mirrors `pressure.py`; recommended weights = exact Python output).
  Tucked away, not on the main screen.
- **FACT / EST / AI badges** everywhere; human-in-the-loop framing; keyboard-accessible (Esc
  closes, dots/rows are focusable); reduced-motion aware; bottom-sheet layout on mobile.

> Note on the deployment comparison: ticket-count and impact correlate ~0.98 in this dataset, so
> the *re-ranking* gain is honestly modest (~3–5%). Pravah's decisive advantages are structural —
> the evening blind spot (~0% caught), the phantom hotspots, and the forward forecast. We say so
> rather than inflate the optimiser delta.
