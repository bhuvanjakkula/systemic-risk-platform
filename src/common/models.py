"""Typed containers for synthetic observations; no accounting reconciliation implied."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


@dataclass
class BankSnapshot:
    bank_id: str
    name: str
    assets: float
    liabilities: float
    liquid_assets: float
    capital: float
    deposits: float
    uninsured_deposit_share: float
    lcr: float
    npl_ratio: float
    vendor_ai: str

    @property
    def capital_ratio(self) -> float:
        """Capital divided by total assets; requires positive assets."""
        if self.assets <= 0:
            raise ValueError('capital_ratio requires positive assets')
        return self.capital / self.assets

    @property
    def liquidity_coverage(self) -> float:
        """Liquid assets divided by deposits, distinct from regulatory LCR."""
        if self.deposits <= 0:
            raise ValueError('liquidity_coverage requires positive deposits')
        return self.liquid_assets / self.deposits


@dataclass
class Exposure:
    lender: str
    borrower: str
    amount: float


@dataclass
class MarketTick:
    vix: float
    interbank_spread_bps: float
    equity_shock: float
    rates_shock_bps: float


@dataclass
class NewsItem:
    source: str
    text: str
    sentiment: float
    entities: List[str]


@dataclass
class SocialBurst:
    topic: str
    mentions: int
    panic_score: float
    entities: List[str]


@dataclass
class SystemState:
    banks: Dict[str, BankSnapshot]
    exposures: List[Exposure]
    market: MarketTick
    news: List[NewsItem]
    social: List[SocialBurst]


class Severity(str, Enum):
    INFO = "info"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    title: str
    reason: str
    score: float
    severity: Severity
    recommended_actions: List[str]
    bank_id: str | None = None
