"""Glass-box explanations. Turn numbers into reasons a human can check and defend.
decompose() + deployment_reason() are implemented (pure arithmetic + templates).
Per-prediction forecast reasons (SHAP) live in `model.predict_next` (M3)."""
from __future__ import annotations


def decompose(j: dict) -> dict:
    """Return the Pressure Index broken into named, summing parts (points)."""
    return {
        "pressure": j["pressure"],
        "parts": [
            {"name": "chronic load", "points": j["pc"],
             "why": "severity x vehicle footprint of illegal parking here"},
            {"name": "blindness", "points": j["pb"],
             "why": "how little this spot is watched in the evening (hidden risk)"},
            {"name": "volume", "points": j["pv"], "why": "raw violation count, log-scaled"},
        ],
        "label": f"TPI {j['pressure']} = {round(j['pc'])} chronic + "
                 f"{round(j['pb'])} blindness + {round(j['pv'])} volume",
    }


def deployment_reason(pick: dict, rank: int) -> str:
    """One-sentence, plain-language justification that travels with every recommendation."""
    blind = " — and it's an evening blind spot" if pick.get("eve_share", 100) < 2 else ""
    return (f"Send {pick['req']} officer(s) to {pick['name']}: pressure {pick['pressure']}/100, "
            f"~{pick['rec']} vehicle-hours/week recoverable (EST){blind}.")


def counterfactual(pick: dict) -> str:
    return f"Skip {pick['name']} and you forgo ~{pick['rec']} vehicle-hours/week of recovery (EST)."
