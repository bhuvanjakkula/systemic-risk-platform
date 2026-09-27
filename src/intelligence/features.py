from __future__ import annotations

from typing import Dict

import numpy as np

from src.common.models import SystemState


def bank_features(state: SystemState) -> Dict[str, Dict[str, float]]:
    social_panic = {b: 0.0 for b in state.banks}
    news_sent = {b: 0.0 for b in state.banks}
    for s in state.social:
        for e in s.entities:
            if e in social_panic:
                social_panic[e] += s.panic_score * np.log1p(s.mentions)
    for n in state.news:
        for e in n.entities:
            if e in news_sent:
                news_sent[e] += n.sentiment

    out: Dict[str, Dict[str, float]] = {}
    for bid, b in state.banks.items():
        out[bid] = {
            "capital_ratio": b.capital_ratio,
            "lcr": b.lcr,
            "liquidity_coverage": b.liquidity_coverage,
            "uninsured": b.uninsured_deposit_share,
            "npl": b.npl_ratio,
            "social_panic": float(social_panic[bid]),
            "news_sentiment": float(news_sent[bid]),
            "vix": state.market.vix,
            "spread": state.market.interbank_spread_bps,
            "rates_shock": state.market.rates_shock_bps,
        }
    return out


def feature_matrix(state: SystemState):
    feats = bank_features(state)
    keys = [
        "capital_ratio", "lcr", "liquidity_coverage", "uninsured", "npl",
        "social_panic", "news_sentiment", "vix", "spread", "rates_shock",
    ]
    ids = list(feats)
    X = np.array([[feats[i][k] for k in keys] for i in ids], dtype=float)
    return ids, keys, X, feats
