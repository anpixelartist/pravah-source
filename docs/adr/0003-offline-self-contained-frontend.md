# ADR 0003 — Offline, self-contained frontend
**Status:** accepted.
**Context:** Live demos die on conference Wi-Fi and external tile servers.
**Decision:** Plot real lat/long on our own canvas/SVG projection. No map tiles, no APIs at
demo time. Aggregates are pre-computed to a small JSON; `make build-web` inlines them for a
double-click offline build.
**Consequences:** The demo never breaks. Slightly more frontend work; worth it.
