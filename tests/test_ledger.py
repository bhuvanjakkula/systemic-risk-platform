import unittest

from src.transparency.ledger import PermissionedLedger
from src.transparency.zk_lite import LineItem, prove_solvency


class LedgerTests(unittest.TestCase):
    def test_append_and_serialization(self):
        ledger = PermissionedLedger()
        self.assertTrue(ledger.verify_chain())
        proof, _ = prove_solvency('B01', [LineItem('cash', 20, 'liquid')])
        block = ledger.append_proof(proof)
        self.assertEqual(block.index, 1)
        self.assertEqual(block.prev_hash, ledger.chain[0].hash)
        self.assertEqual(block.payload['proof']['bank_id'], 'B01')
        self.assertEqual(block.payload['attestor'], 'supervisor')
        self.assertTrue(block.model_dump_json())
        proof.bank_id = 'changed'
        self.assertEqual(block.payload['proof']['bank_id'], 'B01')
        ledger.append_proof(proof, 'auditor')
        self.assertTrue(ledger.verify_chain())

    def test_tampered_payload_and_link(self):
        proof, _ = prove_solvency('B01', [])
        for field, value in [('prev_hash', 'bad'), ('hash', 'bad'), ('index', 7), ('ts', 'bad')]:
            ledger = PermissionedLedger()
            block = ledger.append_proof(proof)
            setattr(block, field, value)
            with self.subTest(field=field):
                self.assertFalse(ledger.verify_chain())
        ledger = PermissionedLedger()
        ledger.append_proof(proof).payload['proof']['liquid_total'] = 999
        self.assertFalse(ledger.verify_chain())

    def test_genesis_and_empty_chain(self):
        ledger = PermissionedLedger()
        ledger.chain[0].ts = 'tampered'
        self.assertFalse(ledger.verify_chain())
        ledger.chain.clear()
        self.assertFalse(ledger.verify_chain())


if __name__ == '__main__':
    unittest.main()
