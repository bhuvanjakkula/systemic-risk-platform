"""Behavior checks for reproducible synthetic scenarios."""
import random
import unittest

from src.ingestion.synthetic import generate_state


class SyntheticTests(unittest.TestCase):
    def test_reproducible_without_global_rng_changes(self):
        before = random.getstate()
        first = generate_state(seed=7)
        self.assertEqual(first, generate_state(seed=7))
        self.assertNotEqual(first.banks['B01'].assets, generate_state(seed=8).banks['B01'].assets)
        self.assertEqual(before, random.getstate())

    def test_network_and_stress(self):
        baseline = generate_state()
        stressed = generate_state(stressed=True)
        self.assertEqual(len(baseline.banks), 5)
        self.assertEqual(len(baseline.exposures), 6)
        for edge in baseline.exposures:
            self.assertIn(edge.lender, baseline.banks)
            self.assertIn(edge.borrower, baseline.banks)
        for key in baseline.banks:
            self.assertLess(stressed.banks[key].assets, baseline.banks[key].assets)
        self.assertLess(stressed.banks['B01'].lcr, baseline.banks['B01'].lcr)
        self.assertGreater(stressed.social[0].panic_score, baseline.social[0].panic_score)
        self.assertGreater(stressed.market.vix, baseline.market.vix)


if __name__ == '__main__':
    unittest.main()
