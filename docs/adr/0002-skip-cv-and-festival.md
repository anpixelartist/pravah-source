# ADR 0002 — One theme: parking-induced congestion; skip CV and the event dataset
**Status:** accepted (revised).
**Context:** CV has no dataset and ~80% of teams will submit near-identical YOLO demos. The
provided ASTraM **event/incident** dataset is also off the table for this entry — we treat it
as out of scope per the competition constraint (use only the provided parking-violation data).
A split focus (parking + incidents) also dilutes one clear story for the judges.
**Decision:** Anchor entirely on **PS1 — Parking-Induced Congestion**, using **only the
parking-violation dataset**. One coherent narrative: chronic + blind-spot pressure → forward
forecast → explained deployment. Do **not** build CV, a festival/rally forecaster, or any
incident/breakdown analytics on the event dataset.
**Consequences:** We avoid the red ocean and the data-less trap, stay clearly inside the
competition's data rules, and tell one sharp story instead of two half-stories. The forward
forecast (`model.py`) is built on the parking trajectory itself, not on the event feed.
