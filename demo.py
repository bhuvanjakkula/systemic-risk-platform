from __future__ import annotations

import json
from dataclasses import asdict

from src.digital_twin.simulator import run_twin
from src.governance.monitors import (
    model_risk_flags,
    reporting_anomalies,
    risk_management_deterioration,
    vendor_concentration,
)
from src.ingestion.mock_feeds import generate_state
from src.intelligence.engine import analyze
from src.transparency.ledger import PermissionedLedger
from src.transparency.zk_lite import LineItem, prove_solvency, verify_solvency


def main() -> None:
    calm = generate_state(seed=7, stressed=False)
    stress = generate_state(seed=7, stressed=True)

    print("=== RISK INTELLIGENCE (stressed) ===")
    for a in analyze(stress):
        print(f"[{a.severity}] {a.title} score={a.score:.2f}")
        print("   ", a.reason)
        for act in a.recommended_actions:
            print("    -", act)

    print("\n=== DIGITAL TWIN ===")
    with_ai = run_twin(stress, "B01", rumor_intensity=0.9, include_ai_agents=True)
    without = run_twin(stress, "B01", rumor_intensity=0.9, include_ai_agents=False)
    print(with_ai.commentary)
    print("Failed with AI agents   :", with_ai.failed_banks)
    print("Failed without AI agents:", without.failed_banks)

    print("\n=== TRANSPARENCY / SOLVENCY PROOF ===")
    ledger = PermissionedLedger()
    b = stress.banks["B01"]
    items = [
        LineItem("hqla_tsy", b.liquid_assets * 0.7, "liquid"),
        LineItem("hqla_reserves", b.liquid_assets * 0.3, "liquid"),
        LineItem("loans", max(b.assets - b.liquid_assets, 0), "other_asset"),
        LineItem("deposits_retail", b.deposits, "liability"),
        LineItem("equity", b.capital, "capital"),
    ]
    proof, _ = prove_solvency("B01", items, assets_total=b.assets)
    print("verified (demo consistency only, not a cryptographic solvency proof):", verify_solvency(proof, assets_total=b.assets))
    print("meets_lcr / meets_capital:", proof.meets_lcr, proof.meets_capital)
    print("root:", proof.merkle_root[:16], "...")
    blk = ledger.append_proof(proof)
    print("ledger block", blk.index, "chain_ok", ledger.verify_chain())

    print("\n=== GOVERNANCE ===")
    history = {
        bid: [generate_state(seed=s, stressed=False).banks[bid] for s in range(6)]
        + [stress.banks[bid]]
        for bid in stress.banks
    }
    gov = []
    vc = vendor_concentration(stress)
    if vc:
        gov.append(vc)
    mf = model_risk_flags(stress, with_ai.failed_banks, without.failed_banks)
    if mf:
        gov.append(mf)
    gov.extend(risk_management_deterioration(stress))
    gov.extend(reporting_anomalies(history))
    for a in gov:
        print(f"[{a.severity}] {a.title} :: {a.reason}")

    print("\nJSON sample alert:")
    print(json.dumps(asdict(analyze(stress)[0]), default=str, indent=2))


if __name__ == "__main__":
    main()
