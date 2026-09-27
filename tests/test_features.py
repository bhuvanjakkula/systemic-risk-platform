import math
import unittest

import numpy as np

from src.common.models import NewsItem, SocialBurst
from src.ingestion.synthetic import generate_state
from src.intelligence.features import bank_features, feature_matrix


class FeatureTests(unittest.TestCase):
    def test_matrix_alignment_and_ratios(self):
        state = generate_state()
        ids, keys, matrix, features = feature_matrix(state)
        self.assertEqual(matrix.shape, (5, 10))
        self.assertTrue(np.isfinite(matrix).all())
        self.assertEqual(ids, list(state.banks))
        for row, bid in enumerate(ids):
            bank = state.banks[bid]
            self.assertAlmostEqual(features[bid]['capital_ratio'], bank.capital / bank.assets)
            self.assertAlmostEqual(features[bid]['liquidity_coverage'], bank.liquid_assets / bank.deposits)
            for col, key in enumerate(keys):
                self.assertEqual(matrix[row, col], features[bid][key])

    def test_signal_aggregation_and_unknown_entities(self):
        state = generate_state()
        state.social = [SocialBurst('test', 9, 0.5, ['B01', 'unknown']),
                        SocialBurst('test', 0, 0.9, ['B01']),
                        SocialBurst('test', 99, 0.2, ['B01'])]
        state.news = [NewsItem('test', 'one', -0.3, ['B01', 'unknown']),
                      NewsItem('test', 'two', 0.1, ['B01'])]
        features = bank_features(state)
        self.assertAlmostEqual(features['B01']['social_panic'], 0.5 * math.log(10) + 0.2 * math.log(100))
        self.assertAlmostEqual(features['B01']['news_sentiment'], -0.2)
        self.assertEqual(features['B02']['social_panic'], 0)
        self.assertEqual(features['B02']['news_sentiment'], 0)

    def test_invalid_ratio_denominators(self):
        bank = generate_state().banks['B01']
        bank.assets = 0
        with self.assertRaises(ValueError):
            _ = bank.capital_ratio
        bank.deposits = 0
        with self.assertRaises(ValueError):
            _ = bank.liquidity_coverage


if __name__ == '__main__':
    unittest.main()
