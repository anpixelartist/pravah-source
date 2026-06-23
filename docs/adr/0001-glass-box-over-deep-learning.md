# ADR 0001 — Glass box over deep learning
**Status:** accepted.
**Context:** Buyers are police; decisions face senior-officer review, RTI, press. An
unexplainable recommendation cannot be acted on or defended.
**Decision:** Use transparent, decomposable scoring (the Traffic Pressure Index) and
interpretable ML only (gradient boosting + SHAP). No neural nets. Every score decomposes;
every recommendation states its reason.
**Consequences:** We trade a little predictive ceiling for trust, auditability, and
adoption — the things that actually win this hackathon and survive deployment.
