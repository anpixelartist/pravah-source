# ADR 0004 — Coverage-normalised features
**Status:** accepted.
**Context:** The data is enforcement-generated — tickets exist where officers stood. Raw
counts bias any model toward reinforcing current patrol patterns and erasing blind spots.
**Decision:** Engineer an exposure/coverage estimate per place-time and a coverage-adjusted
"true rate" feature. The blindness term in the Pressure Index encodes the same insight.
**Consequences:** Our recommendations can point at under-watched areas, not just where
tickets already pile up. This is the analytical core of the differentiation.
