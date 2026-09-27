from __future__ import annotations

from copy import deepcopy
from typing import Dict, List

import numpy as np
from pydantic import BaseModel

from src.common.config import load_settings
from src.common.models import SystemState


class TwinStep(BaseModel):
    t: int
    bank_id: str
    deposits: float
    liquid_assets: float
    capital: float
    run_intensity: float
    failed: bool


class TwinResult(BaseModel):
    steps: List[TwinStep]
    failed_banks: List[str]
    peak_panic: float
    commentary: str


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def run_twin(
    state: SystemState,
    shocked_bank: str,
    rumor_intensity: float = 0.8,
    include_ai_agents: bool = True,
) -> TwinResult:
    cfg = load_settings()["twin"]
    st = deepcopy(state)
    steps: List[TwinStep] = []
    failed = set()
    panic = {b: 0.05 for b in st.banks}
    panic[shocked_bank] = rumor_intensity
    peak = rumor_intensity

    for t in range(int(cfg["steps"])):
        # social amplification + AI herding (agents act on shared signal)
        shared_signal = np.mean(list(panic.values()))
        for bid, bank in st.banks.items():
            social = panic[bid] + cfg["social_amplification"] * shared_signal
            ai = cfg["ai_herding"] * shared_signal if include_ai_agents else 0.0
            fund = (
                2.2 * (0.08 - bank.capital_ratio)
                + 1.6 * (1.0 - bank.lcr)
                + 1.1 * bank.uninsured_deposit_share
                + 0.8 * (st.market.vix / 40.0)
            )
            run_p = _sigmoid(cfg["depositor_sensitivity"] * (social + ai + fund - 0.6))
            if bid in failed:
                run_p = 1.0
            outflow = bank.deposits * run_p * 0.08
            bank.deposits = max(0.0, bank.deposits - outflow)
            bank.liquid_assets = max(0.0, bank.liquid_assets - outflow)
            if bank.liquid_assets < outflow * 0.25:
                fire_sale = outflow * 0.15
                bank.capital = max(0.0, bank.capital - fire_sale)
                bank.assets = max(0.0, bank.assets - fire_sale)
            if bank.liquid_assets <= 1e-6 or bank.capital_ratio < 0.02:
                failed.add(bid)
            panic[bid] = min(1.0, social * 0.85 + run_p * 0.25)
            peak = max(peak, panic[bid])
            steps.append(
                TwinStep(
                    t=t,
                    bank_id=bid,
                    deposits=bank.deposits,
                    liquid_assets=bank.liquid_assets,
                    capital=bank.capital,
                    run_intensity=float(run_p),
                    failed=bid in failed,
                )
            )

        # interbank spillover each step
        for e in st.exposures:
            if e.borrower in failed:
                lender = st.banks[e.lender]
                hit = e.amount * 0.25 / max(cfg["steps"], 1)
                lender.capital = max(0.0, lender.capital - hit)
                panic[e.lender] = min(1.0, panic[e.lender] + 0.08)

    return TwinResult(
        steps=steps,
        failed_banks=sorted(failed),
        peak_panic=float(peak),
        commentary=(
            f"Shock on {shocked_bank} with rumor={rumor_intensity:.2f}, "
            f"AI herding={'on' if include_ai_agents else 'off'}. "
            f"Failed={sorted(failed) or 'none'}."
        ),
    )
