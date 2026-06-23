"""Config loader. Weights/thresholds are config so an officer can re-weight and watch the
ranking move (transparency you can touch)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import constants as C


@dataclass
class Config:
    raw_dir: Path = Path("data/raw")
    violations_glob: str = "*violation*.csv,violations.csv"
    out_json: Path = Path("web/data/aggregates.json")
    weights: dict = field(default_factory=lambda: dict(C.DEFAULT_WEIGHTS))
    recovery_coef: float = C.RECOVERY_COEF
    min_junction_records: int = C.MIN_JUNCTION_RECORDS
    bg_sample: int = 3500

    @classmethod
    def load(cls, path: str | Path = "config/pravah.toml") -> Config:
        cfg = cls()
        p = Path(path)
        if p.exists():
            d = tomllib.loads(p.read_text())
            paths = d.get("paths", {})
            cfg.raw_dir = Path(paths.get("raw_dir", cfg.raw_dir))
            cfg.violations_glob = paths.get("violations_glob", cfg.violations_glob)
            cfg.out_json = Path(paths.get("out_json", cfg.out_json))
            cfg.weights = {**cfg.weights, **d.get("weights", {})}
            model = d.get("model", {})
            cfg.recovery_coef = model.get("recovery_coef", cfg.recovery_coef)
            cfg.min_junction_records = model.get("min_junction_records", cfg.min_junction_records)
            cfg.bg_sample = model.get("bg_sample", cfg.bg_sample)
        s = sum(cfg.weights.values())
        if abs(s - 1.0) > 1e-6:  # normalise; weights must sum to 1
            cfg.weights = {k: v / s for k, v in cfg.weights.items()}
        return cfg
