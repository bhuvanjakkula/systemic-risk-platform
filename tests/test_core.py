from src.ingestion.mock_feeds import generate_state
from src.intelligence.engine import analyze
from src.intelligence.network import cascade_losses
from src.digital_twin.simulator import run_twin
from src.transparency.merkle import leaf_hash, merkle_proof, merkle_root, verify_proof
from src.transparency.zk_lite import LineItem, prove_solvency, verify_solvency
from src.transparency.ledger import PermissionedLedger


def test_alerts_rise_under_stress():
    calm = analyze(generate_state(stressed=False))
    hot = analyze(generate_state(stressed=True))
    assert max([a.score for a in hot] or [0]) >= max([a.score for a in calm] or [0])


def test_cascade():
    st = generate_state(stressed=True)
    losses = cascade_losses(st, ["B01"])
    assert losses["B04"] > 0 or losses["B05"] > 0


def test_twin_runs():
    r = run_twin(generate_state(stressed=True), "B01")
    assert len(r.steps) > 0


def test_merkle_and_proof():
    leaves = [leaf_hash(x) for x in ["a", "b", "c", "d"]]
    root = merkle_root(leaves)
    proof = merkle_proof(leaves, 2)
    assert verify_proof(leaves[2], proof, root)


def test_solvency_ledger():
    b = generate_state(stressed=True).banks["B02"]
    items = [
        LineItem("hqla", b.liquid_assets, "liquid"),
        LineItem("deposits_retail", b.deposits, "liability"),
        LineItem("equity", b.capital, "capital"),
    ]
    proof, _ = prove_solvency("B02", items, assets_total=b.assets)
    assert verify_solvency(proof, assets_total=b.assets)
    led = PermissionedLedger()
    led.append_proof(proof)
    assert led.verify_chain()


def load_tests(loader, tests, pattern):
    """Include function-style tests in the existing unittest discovery command."""
    import unittest

    tests.addTests(unittest.FunctionTestCase(test) for test in (
        test_alerts_rise_under_stress,
        test_cascade,
        test_twin_runs,
        test_merkle_and_proof,
        test_solvency_ledger,
    ))
    return tests
