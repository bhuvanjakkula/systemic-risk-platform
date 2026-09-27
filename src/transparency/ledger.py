"""In-memory hash chain; no access control, signatures, or consensus."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel

from src.transparency.zk_lite import SolvencyProof


class Block(BaseModel):
    index: int
    ts: str
    prev_hash: str
    payload: dict
    hash: str


class PermissionedLedger:
    def __init__(self) -> None:
        genesis = self._make(0, "0" * 64, {"type": "genesis"})
        self.chain: List[Block] = [genesis]

    def _make(self, index: int, prev: str, payload: dict) -> Block:
        ts = datetime.now(timezone.utc).isoformat()
        raw = json.dumps({"index": index, "ts": ts, "prev": prev, "payload": payload}, sort_keys=True)
        h = hashlib.sha256(raw.encode()).hexdigest()
        return Block(index=index, ts=ts, prev_hash=prev, payload=payload, hash=h)

    def append_proof(self, proof: SolvencyProof, attestor: str = "supervisor") -> Block:
        payload = {
            "type": "solvency_attestation",
            "attestor": attestor,
            "proof": asdict(proof),
        }
        blk = self._make(len(self.chain), self.chain[-1].hash, payload)
        self.chain.append(blk)
        return blk

    def verify_chain(self) -> bool:
        if not self.chain:
            return False
        for i, block in enumerate(self.chain):
            expected_prev = "0" * 64 if i == 0 else self.chain[i - 1].hash
            if block.index != i or block.prev_hash != expected_prev:
                return False
            if i == 0 and block.payload != {"type": "genesis"}:
                return False
            raw = json.dumps(
                {
                    "index": block.index,
                    "ts": block.ts,
                    "prev": block.prev_hash,
                    "payload": block.payload,
                },
                sort_keys=True,
            )
            if hashlib.sha256(raw.encode()).hexdigest() != block.hash:
                return False
        return True
