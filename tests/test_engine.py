import unittest
from copy import deepcopy
from unittest.mock import patch

from src.common.config import load_settings
from src.common.models import Severity
from src.ingestion.synthetic import generate_state
from src.intelligence.engine import _severity, analyze, recommend, score_bank
from src.intelligence.features import bank_features


class EngineTests(unittest.TestCase):
    def test_severity_boundaries(self):
        for score, expected in [(0, Severity.INFO), (0.549, Severity.INFO),
                                (0.55, Severity.WATCH), (0.70, Severity.WARNING),
                                (0.85, Severity.CRITICAL), (1, Severity.CRITICAL)]:
            self.assertEqual(_severity(score), expected)

    def test_score_bounds_and_stress_direction(self):
        baseline = bank_features(generate_state())['B01']
        stressed = bank_features(generate_state(stressed=True))['B01']
        self.assertGreater(score_bank(stressed, 0.1), score_bank(baseline, 0.1))
        extreme = dict(stressed, capital_ratio=-10, news_sentiment=-100)
        self.assertEqual(score_bank(extreme, 1), 1.0)
        healthy = dict(baseline, lcr=2, liquidity_coverage=2, capital_ratio=0.2,
                       uninsured=0, social_panic=0, news_sentiment=0, vix=0, spread=0)
        self.assertEqual(score_bank(healthy, 0), 0)
        self.assertEqual(recommend(healthy, 0), ['Continue enhanced monitoring.'])

    def test_reproducible_alerts_and_no_state_mutation(self):
        state = generate_state(stressed=True)
        before = deepcopy(state)
        alerts = analyze(state)
        self.assertEqual(alerts, analyze(state))
        self.assertEqual(state, before)
        self.assertIn('B01', [alert.bank_id for alert in alerts])
        self.assertEqual([a.score for a in alerts], sorted([a.score for a in alerts], reverse=True))
        for alert in alerts:
            self.assertTrue(0 <= alert.score <= 1)
            self.assertIsInstance(alert.severity, Severity)
            self.assertTrue(alert.recommended_actions)
            self.assertIn('cascade_touched=', alert.reason)

    def test_threshold_and_buffer_overrides(self):
        state = generate_state()
        cfg = load_settings()
        cfg['platform']['alert_threshold'] = 0
        with patch('src.intelligence.engine.load_settings', return_value=cfg):
            self.assertEqual(len(analyze(state)), len(state.banks))
        cfg['platform']['alert_threshold'] = 1
        with patch('src.intelligence.engine.load_settings', return_value=cfg):
            actual = {alert.bank_id for alert in analyze(state)}
        expected = {bid for bid, bank in state.banks.items() if bank.lcr < 1 or bank.capital_ratio < 0.08}
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
