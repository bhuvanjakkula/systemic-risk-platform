from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

import numpy as np

from src.common.config import load_settings
from src.common.models import Alert, BankSnapshot, Severity, SystemState


def vendor_concentration(state: SystemState) -> Alert | None:
    cfg = load_settings()["governance"]
    vendors = [b.vendor_ai for b in state.banks.values()]
    if not vendors:
        return None
    counts = Counter(vendors)
    total = max(len(vendors), 1)
    top_vendor, n = counts.most_common(1)[0]
    share = n / total
    if share >= cfg["vendor_concentration_limit"]:
        return Alert(
            title="Third-party AI concentration",
            reason=f"{top_vendor} used by {share:.0%} of monitored banks",
            score=share,
            severity=Severity.WARNING if share < 0.7 else Severity.CRITICAL,
            recommended_actions=[
                "Require model diversity / fallback vendors.",
                "Collect model cards and correlated-output tests.",
            ],
        )
    return None


def reporting_anomalies(history: Dict[str, List[BankSnapshot]]) -> List[Alert]:
    cfg = load_settings()["governance"]
    zcut = cfg["reporting_zscore_flag"]
    alerts = []
    for bid, series in history.items():
        if len(series) < 5:
            continue
        arr = np.array([s.lcr for s in series], dtype=float)
        mu, sd = arr[:-1].mean(), arr[:-1].std() or 1e-6
        z = abs((arr[-1] - mu) / sd)
        if z >= zcut:
            alerts.append(
                Alert(
                    bank_id=bid,
                    title="Reporting anomaly in LCR series",
                    reason=f"latest LCR z-score={z:.2f}",
                    score=min(1.0, z / 6),
                    severity=Severity.WATCH if z < 3.5 else Severity.WARNING,
                    recommended_actions=["Source-data audit", "Reconcile HQLA classification"],
                )
            )
    return alerts


def model_risk_flags(state: SystemState, twin_failed_with_ai: List[str], twin_failed_without_ai: List[str]) -> Alert | None:
    extra = sorted(set(twin_failed_with_ai) - set(twin_failed_without_ai))
    if not extra:
        return None
    return Alert(
        title="AI-herding model-risk amplifier",
        reason=f"Digital twin failures increase when AI agents enabled: +{extra}",
        score=0.72,
        severity=Severity.WARNING,
        recommended_actions=[
            "Limit identical agentic withdrawal/trading policies.",
            "Add kill-switch / desync randomness in liquidity algorithms.",
        ],
    )


def risk_management_deterioration(state: SystemState) -> List[Alert]:
    out = []
    for b in state.banks.values():
        flags = []
        if b.npl_ratio > 0.03 and b.capital_ratio < 0.09:
            flags.append("NPLs rising into thin capital")
        if b.uninsured_deposit_share > 0.5 and b.lcr < 1.1:
            flags.append("runnable funding with weak LCR")
        if flags:
            out.append(
                Alert(
                    bank_id=b.bank_id,
                    title=f"Governance / risk-management deterioration: {b.name}",
                    reason="; ".join(flags),
                    score=0.66,
                    severity=Severity.WARNING,
                    recommended_actions=["Supervisory review of risk appetite and ALCO minutes"],
                )
            )
    return out
