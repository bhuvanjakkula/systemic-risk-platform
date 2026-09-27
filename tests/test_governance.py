import unittest
from dataclasses import replace

from src.common.models import Severity
from src.governance.checks import (
    vendor_concentration, reporting_anomalies,
    model_risk_flags, risk_management_deterioration,
)
from src.ingestion.synthetic import generate_state


class GovernanceTests(unittest.TestCase):
    def test_vendor_threshold_and_empty_state(self):
        state = generate_state()
        self.assertIsNone(vendor_concentration(state))
        state.banks['B02'].vendor_ai = 'MythosAI'
        alert = vendor_concentration(state)
        self.assertEqual(alert.score, 0.6)
        self.assertEqual(alert.severity, Severity.WARNING)
        self.assertIsNone(alert.bank_id)
        state.banks['B03'].vendor_ai = 'MythosAI'
        self.assertEqual(vendor_concentration(state).severity, Severity.CRITICAL)
        state.banks.clear()
        self.assertIsNone(vendor_concentration(state))

    def test_reporting_history(self):
        bank = generate_state().banks['B01']
        stable = [replace(bank, lcr=1.0) for _ in range(5)]
        self.assertEqual(reporting_anomalies({'B01': stable[:4]}), [])
        self.assertEqual(reporting_anomalies({'B01': stable}), [])
        stable[-1] = replace(bank, lcr=1.5)
        alerts = reporting_anomalies({'B01': stable})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].bank_id, 'B01')
        self.assertEqual(alerts[0].severity, Severity.WARNING)
        self.assertEqual(alerts[0].score, 1.0)

    def test_ai_failure_difference(self):
        state = generate_state()
        self.assertIsNone(model_risk_flags(state, ['B01'], ['B01', 'B02']))
        alert = model_risk_flags(state, ['B03', 'B02', 'B02'], ['B03'])
        self.assertIsNone(alert.bank_id)
        self.assertIn("+['B02']", alert.reason)

    def test_deterioration_flags(self):
        state = generate_state()
        state.banks = {'B01': replace(state.banks['B01'], assets=100, capital=8,
                                     npl_ratio=0.04, uninsured_deposit_share=0.6, lcr=0.9)}
        alerts = risk_management_deterioration(state)
        self.assertEqual(len(alerts), 1)
        self.assertIn('NPLs rising into thin capital', alerts[0].reason)
        self.assertIn('runnable funding with weak LCR', alerts[0].reason)
        state.banks['B01'] = replace(state.banks['B01'], capital=20, lcr=1.5)
        self.assertEqual(risk_management_deterioration(state), [])


if __name__ == '__main__':
    unittest.main()
