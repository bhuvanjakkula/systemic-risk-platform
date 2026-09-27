"""Pedagogical solvency demonstration, not a zero-knowledge solvency proof.

Line items use salted hash commitments and a Merkle tree. Aggregate totals
are disclosed. The transcript is a hash, not a Fiat-Shamir proof of knowledge;
fixed-key HMACs are publicly recomputable checksums. Verification does not
establish that totals match committed line items or independently verify an
inclusion witness. A True result checks consistency of the supplied flags,
including flags that say thresholds are not met; it does not certify solvency.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Dict, List

from src.transparency.merkle import leaf_hash, merkle_proof, merkle_root, verify_proof


def _sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def commit(value: float, blinding: bytes) -> bytes:
    packed = f"{value:.8f}".encode()
    return _sha(b"com:" + packed + blinding)


@dataclass
class LineItem:
    label: str
    value: float
    category: str  # liquid | other_asset | liability | capital


@dataclass
class SolvencyProof:
    bank_id: str
    merkle_root: str
    liquid_commitment: str
    capital_commitment: str
    deposit_commitment: str
    liquid_total: float
    capital_total: float
    deposit_total: float
    meets_lcr: bool
    meets_capital: bool
    transcript: str
    inclusion_ok: bool


def prove_solvency(
    bank_id: str,
    items: List[LineItem],
    lcr_min: float = 1.0,
    cap_ratio_min: float = 0.08,
    assets_total: float = 1.0,
) -> tuple[SolvencyProof, Dict[str, bytes]]:
    blinds: Dict[str, bytes] = {}
    leaves = []
    liquid = capital = deposits = 0.0
    for it in items:
        b = os.urandom(32)
        blinds[it.label] = b
        com = commit(it.value, b)
        leaves.append(leaf_hash(f"{it.label}|{it.category}|{com.hex()}"))
        if it.category == "liquid":
            liquid += it.value
        elif it.category == "capital":
            capital += it.value
        elif it.category == "liability" and it.label.startswith("deposits"):
            deposits += it.value

    root = merkle_root(leaves)
    # Hash public totals with the root; this does not prove their relationship.
    transcript = _sha(
        bank_id.encode()
        + root
        + f"{liquid:.8f}{capital:.8f}{deposits:.8f}".encode()
    ).hex()
    net_outflow_assumption = max(deposits * 0.15, 1e-9)
    lcr = liquid / net_outflow_assumption
    cap_ratio = capital / max(assets_total, 1e-9)

    # Local inclusion self-check; the witness is not exported to the verifier.
    liquid_idxs = [i for i, it in enumerate(items) if it.category == "liquid"]
    inclusion_ok = True
    if liquid_idxs:
        i0 = liquid_idxs[0]
        proof = merkle_proof(leaves, i0)
        inclusion_ok = verify_proof(leaves[i0], proof, root)

    proof = SolvencyProof(
        bank_id=bank_id,
        merkle_root=root.hex(),
        liquid_commitment=hmac.new(b"liq", f"{liquid:.8f}{transcript}".encode(), hashlib.sha256).hexdigest(),
        capital_commitment=hmac.new(b"cap", f"{capital:.8f}{transcript}".encode(), hashlib.sha256).hexdigest(),
        deposit_commitment=hmac.new(b"dep", f"{deposits:.8f}{transcript}".encode(), hashlib.sha256).hexdigest(),
        liquid_total=liquid,
        capital_total=capital,
        deposit_total=deposits,
        meets_lcr=lcr >= lcr_min,
        meets_capital=cap_ratio >= cap_ratio_min,
        transcript=transcript,
        inclusion_ok=inclusion_ok,
    )
    return proof, blinds


def verify_solvency(proof: SolvencyProof, lcr_min: float = 1.0, cap_ratio_min: float = 0.08, assets_total: float = 1.0) -> bool:
    net_outflow_assumption = max(proof.deposit_total * 0.15, 1e-9)
    lcr = proof.liquid_total / net_outflow_assumption
    cap_ratio = proof.capital_total / max(assets_total, 1e-9)
    liq_ok = hmac.compare_digest(
        proof.liquid_commitment,
        hmac.new(b"liq", f"{proof.liquid_total:.8f}{proof.transcript}".encode(), hashlib.sha256).hexdigest(),
    )
    return (
        proof.inclusion_ok
        and liq_ok
        and (lcr >= lcr_min) == proof.meets_lcr
        and (cap_ratio >= cap_ratio_min) == proof.meets_capital
    )
