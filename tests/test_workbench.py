import unittest
from tests.auth_support import authenticated_client
from src.api.main import app
from src.governance.policy import Costs, PolicyRequest, evaluate, CalibrationRequest, calibrate
from src.ingestion.report_csv import parse_reports
CSV = 'bank_id,as_of,currency,liquid_assets,stressed_outflows,capital,rwa\nA,2026-09-24,USD,120,100,15,100\n'
class WorkbenchTests(unittest.TestCase):
    def test_cost_crossing(self):
        d=evaluate(PolicyRequest())
        self.assertAlmostEqual(d['threshold'],10/105)
        self.assertGreater(evaluate(PolicyRequest(costs=Costs(fiscal_cost=20)))['threshold'],d['threshold'])
        self.assertFalse(d['execution_authorized'])
    def test_dominance_and_reverse(self):
        self.assertIsNone(evaluate(PolicyRequest(costs=Costs(false_positive=200,true_positive=200)))['threshold'])
        d=evaluate(PolicyRequest(costs=Costs(false_positive=0,true_negative=10,true_positive=100,false_negative=0)))
        self.assertEqual(d['threshold_direction'],'below')
        self.assertAlmostEqual(d['threshold'],10/110)
    def test_gate_and_ambiguity(self):
        params=dict(evidence_verified=True,commitment=True,model_validated=True,data_fresh=True,collateral_eligible=True)
        self.assertEqual(evaluate(PolicyRequest(probability=0,uncertainty=0,**params))['protocol'],'monitor')
        d=evaluate(PolicyRequest(probability=0.1,uncertainty=0.1,**params))
        self.assertTrue(d['ambiguous'])
        self.assertFalse(d['execution_authorized'])
        self.assertEqual(d['protocol'],'human_review')
    def test_calibration_and_never_alert(self):
        d=calibrate(CalibrationRequest(probabilities=[0.1,0.9],outcomes=[0,1]))
        self.assertAlmostEqual(d['brier_score'],0.01)
        self.assertEqual(d['best']['threshold'],0.9)
        self.assertEqual(d['best']['tp'],1)
        d=calibrate(CalibrationRequest(probabilities=[1,1],outcomes=[0,1],costs=Costs(false_positive=1000,false_negative=1)))
        self.assertIsNone(d['best']['threshold'])
        self.assertEqual(d['best']['fn'],1)
    def test_csv(self):
        d=parse_reports(CSV)
        self.assertEqual(d['rows'][0]['lcr'],1.2)
        for value in [CSV.replace('120,100','120,0'),CSV.replace('2026-09-24','bad'),CSV+CSV.splitlines()[1],CSV.replace('120','NaN')]:
            with self.subTest(value=value),self.assertRaises(ValueError):parse_reports(value)
    def test_endpoints(self):
        with authenticated_client(app) as c:
            self.assertIn('See stress',c.get('/').text)
            self.assertEqual(c.post('/policy/evaluate',json={}).status_code,200)
            self.assertEqual(c.post('/policy/evaluate',json={'probability':1.1}).status_code,422)
            self.assertEqual(c.post('/policy/calibrate',json={'probabilities':[0,1],'outcomes':[0]}).status_code,422)
            self.assertEqual(c.post('/reports/import',json={'csv':CSV}).status_code,200)
            self.assertEqual(c.post('/reports/import',json={'csv':'bad'}).status_code,422)
