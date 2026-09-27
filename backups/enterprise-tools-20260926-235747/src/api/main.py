from __future__ import annotations

from dataclasses import asdict
from threading import Lock

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.digital_twin.simulator import run_twin
from src.governance.monitors import (
    model_risk_flags,
    risk_management_deterioration,
    vendor_concentration,
)
from src.ingestion.mock_feeds import generate_state
from src.intelligence.engine import analyze
from src.transparency.ledger import PermissionedLedger
from src.transparency.zk_lite import LineItem, prove_solvency, verify_solvency

app = FastAPI(title="Systemic Risk Platform", version="0.1.0")
from src.api.workbench import router
app.include_router(router)
from src.api.auth import router as auth_router, protect
from starlette.middleware.trustedhost import TrustedHostMiddleware
app.include_router(auth_router)
from src.api.plans import router as plans_router
app.include_router(plans_router)
from src.api.owner import router as owner_router
app.include_router(owner_router)
app.middleware('http')(protect)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]', 'testserver'])
LEDGER = PermissionedLedger()
LEDGER_LOCK = Lock()


class TwinRequest(BaseModel):
    seed: int = 7
    stressed: bool = True
    shocked_bank: str = "B01"
    rumor: float = Field(default=0.85, ge=0, le=1)
    ai_agents: bool = True


@app.get("/health")
def health():
    with LEDGER_LOCK:
        return {"ok": True, "ledger_height": len(LEDGER.chain)}


@app.get("/scan")
def scan(stressed: bool = True, seed: int = 7):
    state = generate_state(seed=seed, stressed=stressed)
    alerts = analyze(state)
    gov = [a for a in [vendor_concentration(state)] if a] + risk_management_deterioration(state)
    return {
        "banks": {k: asdict(v) for k, v in state.banks.items()},
        "risk_alerts": [asdict(a) for a in alerts],
        "governance_alerts": [asdict(a) for a in gov],
    }


@app.post("/twin")
def twin(req: TwinRequest):
    state = generate_state(seed=req.seed, stressed=req.stressed)
    if req.shocked_bank not in state.banks:
        raise HTTPException(status_code=404, detail="unknown bank")
    with_ai = run_twin(state, req.shocked_bank, req.rumor, True)
    without = run_twin(state, req.shocked_bank, req.rumor, False)
    flag = model_risk_flags(state, with_ai.failed_banks, without.failed_banks)
    return {
        "with_ai": with_ai.model_dump(),
        "without_ai": without.model_dump(),
        "selected_scenario": "with_ai" if req.ai_agents else "without_ai",
        "governance": asdict(flag) if flag else None,
    }


@app.post("/solvency/{bank_id}")
def solvency(bank_id: str, stressed: bool = True):
    state = generate_state(stressed=stressed)
    if bank_id not in state.banks:
        raise HTTPException(status_code=404, detail="unknown bank")
    b = state.banks[bank_id]
    items = [
        LineItem("hqla_tsy", b.liquid_assets * 0.7, "liquid"),
        LineItem("hqla_reserves", b.liquid_assets * 0.3, "liquid"),
        LineItem("loans", max(b.assets - b.liquid_assets, 0), "other_asset"),
        LineItem("deposits_retail", b.deposits, "liability"),
        LineItem("equity", b.capital, "capital"),
    ]
    proof, _ = prove_solvency(bank_id, items, assets_total=b.assets)
    ok = verify_solvency(proof, assets_total=b.assets)
    with LEDGER_LOCK:
        blk = LEDGER.append_proof(proof)
        chain_valid = LEDGER.verify_chain()
    return {
        "verified": ok,
        "verification_scope": "Demonstration consistency check; not a cryptographic solvency proof.",
        "proof": asdict(proof),
        "block": blk.model_dump(),
        "chain_valid": chain_valid,
    }
