import unittest
from dataclasses import replace

from src.transparency.merkle import leaf_hash, merkle_root
from src.transparency.solvency import LineItem, commit, prove_solvency, verify_solvency


class SolvencyTests(unittest.TestCase):
    def setUp(self):
        self.items = [LineItem('cash', 20, 'liquid'),
                      LineItem('equity', 10, 'capital'),
                      LineItem('deposits_retail', 80, 'liability')]

    def test_commitment_openings_and_thresholds(self):
        proof, blinds = prove_solvency('B01', self.items, assets_total=100)
        leaves = [leaf_hash(f'{item.label}|{item.category}|{commit(item.value, blinds[item.label]).hex()}')
                  for item in self.items]
        self.assertEqual(proof.merkle_root, merkle_root(leaves).hex())
        self.assertTrue(all(len(blind) == 32 for blind in blinds.values()))
        self.assertEqual((proof.liquid_total, proof.capital_total, proof.deposit_total), (20, 10, 80))
        self.assertTrue(proof.meets_lcr and proof.meets_capital)
        self.assertTrue(verify_solvency(proof, assets_total=100))

    def test_changed_liquid_total_rejected(self):
        proof, _ = prove_solvency('B01', self.items, assets_total=100)
        self.assertFalse(verify_solvency(replace(proof, liquid_total=21), assets_total=100))

    def test_consistent_failed_thresholds_are_not_solvency(self):
        proof, _ = prove_solvency('B01', self.items, lcr_min=2, cap_ratio_min=0.2, assets_total=100)
        self.assertFalse(proof.meets_lcr)
        self.assertFalse(proof.meets_capital)
        self.assertTrue(verify_solvency(proof, lcr_min=2, cap_ratio_min=0.2, assets_total=100))

    def test_documented_unchecked_fields(self):
        proof, _ = prove_solvency('B01', self.items, assets_total=100)
        altered = replace(proof, bank_id='different', merkle_root='00' * 32,
                          capital_commitment='00' * 32, deposit_commitment='00' * 32)
        self.assertTrue(verify_solvency(altered, assets_total=100))


if __name__ == '__main__':
    unittest.main()
