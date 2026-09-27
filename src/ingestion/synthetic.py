from __future__ import annotations

import random
from typing import List

from src.common.models import (
    BankSnapshot,
    Exposure,
    MarketTick,
    NewsItem,
    SocialBurst,
    SystemState,
)


BANK_SEED = [
    ("B01", "Northridge Bank", 120_000, 108_000, 18_000, 12_000, 82_000, 0.62, 0.91, 0.041, "MythosAI"),
    ("B02", "Harbor Trust", 90_000, 80_000, 16_000, 10_000, 61_000, 0.28, 1.35, 0.018, "VendorA"),
    ("B03", "Pioneer Credit", 70_000, 64_000, 9_500, 6_000, 48_000, 0.44, 1.05, 0.027, "VendorA"),
    ("B04", "Summit National", 150_000, 132_000, 28_000, 18_000, 97_000, 0.22, 1.48, 0.012, "VendorB"),
    ("B05", "Atlas Wholesale", 200_000, 184_000, 22_000, 16_000, 110_000, 0.51, 0.97, 0.033, "MythosAI"),
]


def generate_state(seed: int = 7, stressed: bool = False) -> SystemState:
    rng = random.Random(seed)
    shock = 1.0 if not stressed else 0.82
    banks = {}
    for bid, name, a, l, liq, cap, dep, unins, lcr, npl, vendor in BANK_SEED:
        banks[bid] = BankSnapshot(
            bank_id=bid,
            name=name,
            assets=a * shock + rng.uniform(-800, 800),
            liabilities=l + rng.uniform(-400, 400),
            liquid_assets=liq * (0.75 if stressed and bid in {"B01", "B05"} else 1.0),
            capital=cap * (0.7 if stressed and bid == "B01" else 1.0),
            deposits=dep,
            uninsured_deposit_share=unins + (0.08 if stressed else 0.0),
            lcr=lcr * (0.72 if stressed and bid == "B01" else 1.0),
            npl_ratio=npl + (0.02 if stressed else 0.0),
            vendor_ai=vendor,
        )

    exposures: List[Exposure] = [
        Exposure(lender="B04", borrower="B01", amount=4200),
        Exposure(lender="B05", borrower="B01", amount=6100),
        Exposure(lender="B02", borrower="B03", amount=1800),
        Exposure(lender="B05", borrower="B03", amount=2500),
        Exposure(lender="B04", borrower="B05", amount=5000),
        Exposure(lender="B02", borrower="B01", amount=900),
    ]

    market = MarketTick(
        vix=18.0 if not stressed else 34.5,
        interbank_spread_bps=12 if not stressed else 48,
        equity_shock=0.0 if not stressed else -0.06,
        rates_shock_bps=0 if not stressed else 75,
    )

    news = [
        NewsItem(source="Wire", text="Regional deposits stable after earnings.", sentiment=0.2, entities=["B02"]),
        NewsItem(source="Wire", text="Concerns over duration losses at Northridge.", sentiment=-0.55 if stressed else -0.1, entities=["B01"]),
    ]
    social = [
        SocialBurst(topic="bank_safety", mentions=120 if not stressed else 8400,
                    panic_score=0.12 if not stressed else 0.78, entities=["B01", "B05"]),
    ]
    return SystemState(banks=banks, exposures=exposures, market=market, news=news, social=social)
