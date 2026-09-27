import unittest
from tests import test_auth
from src.api.inquiry import Experiment, evaluate

class MathTests(unittest.TestCase):
    def body(self,**kw):
        return Experiment(**dict({'problem':'Cash shortfall','hypothesis':'Buffer bridges a funding delay','cash':100,'daily_inflow':0,'daily_outflow':40,'days':3,'minimum_cash':0,'reserve':50,'reserve_cost':0,'facility':100,'facility_delay':2,'facility_fee_pct':0,'cost_budget':0,'scenarios':[{'name':'Stress'}]},**kw))
    def test_baseline_buffer_and_facility(self):
        a=evaluate(self.body())['alternatives']
        self.assertEqual(a[0]['results'][0]['first_breach_day'],3)
        self.assertEqual(a[0]['worst_shortfall'],20)
        self.assertEqual(a[1]['results'][0]['end_cash'],30)
        self.assertEqual(a[2]['results'][0]['end_cash'],80)
        self.assertTrue(a[3]['passes_all_supplied_scenarios'])
    def test_delayed_recovery_does_not_hide_early_breach(self):
        d=evaluate(self.body(cash=10,facility_delay=2))['alternatives'][2]
        self.assertEqual(d['results'][0]['first_breach_day'],1)
        self.assertFalse(d['passes_all_supplied_scenarios'])
    def test_day_zero_cost_budget_and_unavailable_funding(self):
        a=evaluate(self.body(cash=0,reserve=10,reserve_cost=11,facility_delay=0,facility_fee_pct=1,scenarios=[{'name':'Unavailable','facility_available':False}]))['alternatives']
        self.assertEqual(a[1]['results'][0]['first_breach_day'],0)
        self.assertFalse(a[1]['passes_all_supplied_scenarios'])
        self.assertEqual(a[2]['results'][0]['cost'],0)
        self.assertEqual(a[2]['results'][0]['end_cash'],-120)
        a=evaluate(self.body(facility_delay=0))['alternatives'][2]
        self.assertEqual(a['results'][0]['path'][0]['cash'],200)

class FundingPlanTests(unittest.TestCase):
    body = MathTests.body
    def test_top_up_is_sufficient_and_minimal_across_scenarios(self):
        body = self.body(cash=10, scenarios=[{'name':'Normal'}, {'name':'Run','outflow_multiplier':2,'facility_available':False}])
        for alternative in evaluate(body)['alternatives']:
            plan = alternative['funding_plan']
            extra = plan['additional_cash_required']
            balances = [p['cash'] for r in alternative['results'] for p in r['path']]
            self.assertGreater(extra, 0)
            self.assertGreaterEqual(min(balances) + extra, body.minimum_cash)
            self.assertLess(min(balances) + extra - 0.01, body.minimum_cash)
            self.assertEqual(plan['binding_scenario'], 'Run')

    def test_early_gap_before_facility_recovery(self):
        plan = evaluate(self.body(cash=10, facility=200))['alternatives'][2]['funding_plan']
        self.assertEqual(plan['additional_cash_required'], 30)
        self.assertEqual(plan['first_breach_day'], 1)
        self.assertEqual(plan['peak_shortfall_day'], 1)

    def test_no_gap_does_not_hide_cost_breach(self):
        result = evaluate(self.body(cash=1000, reserve_cost=10))['alternatives'][1]
        plan = result['funding_plan']
        self.assertEqual(plan['additional_cash_required'], 0)
        self.assertIsNone(plan['binding_scenario'])
        self.assertIsNone(plan['peak_shortfall_day'])
        self.assertFalse(plan['existing_costs_within_budget'])
        self.assertFalse(result['passes_all_supplied_scenarios'])

    def test_day_zero_gap_and_positive_floor(self):
        plan = evaluate(self.body(cash=0, daily_outflow=0, minimum_cash=50))['alternatives'][0]['funding_plan']
        self.assertEqual(plan['additional_cash_required'], 50)
        self.assertEqual(plan['first_breach_day'], 0)
        self.assertEqual(plan['peak_shortfall_day'], 0)


class ApiTests(unittest.TestCase):
    setUp=test_auth.AuthTests.setUp
    tearDown=test_auth.AuthTests.tearDown
    def enable(self):
        self.client.post('/auth/signup',json=self.creds)
        self.client.post('/plans/select',json={'plan_id':'professional'})
    def test_save_observe_isolation_and_export(self):
        body=MathTests().body().model_dump()
        self.assertEqual(self.client.post('/inquiry/preview',json=body).status_code,401)
        self.enable()
        self.assertEqual(self.client.get('/inquiry').status_code,200)
        self.assertEqual(self.client.post('/inquiry/preview',json=body).status_code,200)
        self.assertEqual(self.client.get('/inquiry/experiments').json(),[])
        r=self.client.post('/inquiry/experiments',json=body)
        self.assertEqual(r.status_code,201); eid=r.json()['id']
        self.assertEqual(r.json()['analysis']['model_version'], 'liquidity-inquiry-2')
        self.assertEqual(r.json()['analysis']['alternatives'][0]['funding_plan']['additional_cash_required'],20)
        observation={'alternative':'Baseline','scenario':'Stress','day':1,'observed_cash':50,'tolerance':5,'evidence':'Ledger sample dated today','revision':'Recheck the assumed daily outflow'}
        r=self.client.post(f'/inquiry/experiments/{eid}/observations',json=observation)
        self.assertEqual(r.status_code,201)
        self.assertEqual(r.json()['projected_cash'],60)
        self.assertEqual(r.json()['error'],-10)
        self.assertEqual(r.json()['review'],'Revise assumptions')
        for changes in [{'day':4},{'scenario':'unknown'},{'alternative':'not real'}]:
            self.assertEqual(self.client.post(f'/inquiry/experiments/{eid}/observations',json={**observation,**changes}).status_code,422)
        self.client.post('/auth/signout')
        self.client.post('/auth/signin',json=self.creds)
        self.assertEqual(len(self.client.get(f'/inquiry/experiments/{eid}').json()['observations']),1)
        self.client.post('/auth/signup',json={**self.creds,'mobile':'+15555550129'})
        self.client.post('/plans/select',json={'plan_id':'bank'})
        self.assertEqual(self.client.get('/inquiry/experiments').json(),[])
        self.assertEqual(self.client.get(f'/inquiry/experiments/{eid}').status_code,404)
        self.assertEqual(self.client.post(f'/inquiry/experiments/{eid}/observations',json=observation).status_code,404)
    def test_validation(self):
        self.enable();body=MathTests().body().model_dump()
        for change in [{'days':0},{'cash':-1},{'facility_delay':1.5},{'cash':'NaN'},{'scenarios':[{'name':'A'},{'name':'a'}]},{'scenarios':[]}]:
            self.assertEqual(self.client.post('/inquiry/preview',json={**body,**change}).status_code,422)
