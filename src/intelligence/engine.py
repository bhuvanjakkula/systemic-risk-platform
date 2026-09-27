from __future__ import annotations

from typing import List

import numpy as np
from sklearn.ensemble import IsolationForest

from src.common.config import load_settings
from src.common.models import Alert, Severity, SystemState
from src.intelligence.features import bank_features
from src.intelligence.network import cascade_losses, systemic_scores


def _severity(score: float) -> Severity:
    if score >= 0.85:
        return Severity.CRITICAL
    if score >= 0.70:
        return Severity.WARNING
    if score >= 0.55:
        return Severity.WATCH
    return Severity.INFO


def score_bank(f: dict, sys_imp: float) -> float:
    capital_gap = max(0.0, 0.10 - f["capital_ratio"]) / 0.10
    lcr_gap = max(0.0, 1.0 - f["lcr"])
    panic = min(1.0, f["social_panic"] / 8.0)
    unins = f["uninsured"]
    market = min(1.0, (f["vix"] / 40.0) * 0.5 + f["spread"] / 80.0)
    news = max(0.0, -f["news_sentiment"])
    raw = (
        0.28 * capital_gap
        + 0.18 * lcr_gap
        + 0.16 * panic
        + 0.12 * unins
        + 0.10 * market
        + 0.08 * news
        + 0.08 * min(1.0, sys_imp * 8)
    )
    return float(np.clip(raw, 0, 1))


def recommend(f: dict, score: float) -> List[str]:
    acts = []
    if f["lcr"] < 1.05 or f["liquidity_coverage"] < 1.2:
        acts.append("Pre-position discount-window collateral and raise HQLA.")
    if f["uninsured"] > 0.4 and f["social_panic"] > 1.0:
        acts.append("Activate run-playbook: communication, insured-deposit messaging, outflow caps review.")
    if f["capital_ratio"] < 0.09:
        acts.append("Supervisor review of capital plan; restrict distributions.")
    if score > 0.7:
        acts.append("Open real-time liquidity dashboard to resolution authority.")
        acts.append("Run digital-twin shock with AI-herding and social amplification.")
    if not acts:
        acts.append("Continue enhanced monitoring.")
    return acts


def analyze(state: SystemState) -> List[Alert]:
    cfg = load_settings()
    thresh = cfg["platform"]["alert_threshold"]
    lgd = cfg["platform"]["contagion_loss_rate"]
    feats = bank_features(state)
    sys_imp = systemic_scores(state)

    ids = list(feats)
    X = np.array([[v for v in feats[i].values()] for i in ids], dtype=float)
    iso = IsolationForest(contamination=0.25, random_state=42)
    iso.fit(X)
    anomaly = dict(zip(ids, iso.decision_function(X)))

    alerts: List[Alert] = []
    for bid, f in feats.items():
        s = score_bank(f, sys_imp.get(bid, 0.0))
        s = min(1.0, s + max(0.0, -anomaly[bid]) * 0.15)
        if s < thresh and f["lcr"] >= 1.0 and f["capital_ratio"] >= 0.08:
            continue
        losses = cascade_losses(state, [bid], lgd=lgd)
        contagion = sum(1 for k, v in losses.items() if k != bid and v > 0)
        reason = (
            f"score={s:.2f} cap={f['capital_ratio']:.3f} lcr={f['lcr']:.2f} "
            f"uninsured={f['uninsured']:.2f} panic={f['social_panic']:.2f} "
            f"cascade_touched={contagion}"
        )
        alerts.append(
            Alert(
                bank_id=bid,
                title=f"Systemic risk signal: {state.banks[bid].name}",
                reason=reason,
                score=s,
                severity=_severity(s),
                recommended_actions=recommend(f, s),
            )
        )
    alerts.sort(key=lambda a: a.score, reverse=True)
    return alerts
