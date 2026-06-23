"""Equity guardrail (M4). Deploying purely by time-recovered over-polices rich commercial
corridors and starves residential zones. Flag it — police buyers and the public will notice."""
from __future__ import annotations


def zone_coverage_flag(picks: list[dict], all_zones: set[str], key: str = "police_station") -> dict:
    """Warn when a deployment plan ignores whole zones. Simple, auditable, defensible."""
    covered = {p.get(key) for p in picks if p.get(key)}
    neglected = sorted(all_zones - covered)
    share = len(covered) / len(all_zones) if all_zones else 1.0
    return {
        "zones_covered": len(covered), "zones_total": len(all_zones),
        "coverage_share": round(share, 2), "neglected_zones": neglected,
        "flag": share < 0.5,
        "note": "Deployment concentrates in few zones — review for equity." if share < 0.5 else "",
    }
