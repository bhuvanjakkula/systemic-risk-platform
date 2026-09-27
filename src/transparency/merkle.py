from __future__ import annotations

import hashlib
from typing import List, Tuple


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(payload: str) -> bytes:
    return _h(b"leaf:" + payload.encode())


def merkle_root(leaves: List[bytes]) -> bytes:
    if not leaves:
        return _h(b"empty")
    layer = leaves[:]
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        nxt = []
        for i in range(0, len(layer), 2):
            nxt.append(_h(b"node:" + layer[i] + layer[i + 1]))
        layer = nxt
    return layer[0]


def merkle_proof(leaves: List[bytes], index: int) -> List[Tuple[bytes, str]]:
    proof = []
    layer = leaves[:]
    idx = index
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        pair = idx ^ 1
        side = "right" if idx % 2 == 0 else "left"
        proof.append((layer[pair], side))
        nxt = []
        for i in range(0, len(layer), 2):
            nxt.append(_h(b"node:" + layer[i] + layer[i + 1]))
        layer = nxt
        idx //= 2
    return proof


def verify_proof(leaf: bytes, proof: List[Tuple[bytes, str]], root: bytes) -> bool:
    cur = leaf
    for sib, side in proof:
        cur = _h(b"node:" + (cur + sib if side == "right" else sib + cur))
    return cur == root
