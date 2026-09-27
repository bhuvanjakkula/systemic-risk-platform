from pathlib import Path
from typing import Any, Dict

import yaml


def load_settings(path: str | Path | None = None) -> Dict[str, Any]:
    p = Path(path or Path(__file__).resolve().parents[2] / "config" / "settings.yaml")
    if not p.exists():
        return {
            "platform": {"alert_threshold": 0.62, "contagion_loss_rate": 0.4,
                         "capital_ratio_min": 0.08, "lcr_min": 1.0},
            "twin": {"steps": 24, "depositor_sensitivity": 1.35,
                     "social_amplification": 0.22, "ai_herding": 0.18},
            "governance": {"vendor_concentration_limit": 0.45, "reporting_zscore_flag": 2.5},
        }
    with p.open() as f:
        return yaml.safe_load(f)
