import unittest
from tests import test_auth
from src.api.owner import provision_owner

class EnterpriseTests(unittest.TestCase):
    setUp = test_auth.AuthTests.setUp
    tearDown = test_auth.AuthTests.tearDown
    sample = 'counterparty,sector,currency,exposure\nA,Bank,USD,30\na,Bank,USD,20\nB,Insurance,USD,50'
    def enable(self):
        self.client.post('/auth/signup', json=self.creds)
        self.client.post('/plans/select', json={'plan_id':'enterprise'})
    def test_calculation_grouping_and_boundaries(self):
        self.enable()
        r=self.client.post('/enterprise/analyze',json={'csv':self.sample,'concentration_limit_pct':50,'loss_limit_pct':10,'shock_pct':20})
        self.assertEqual(r.status_code,200)
        d=r.json()
        self.assertEqual(d['total_exposure'],100)
        self.assertEqual(len(d['counterparties']),2)
        self.assertEqual(d['counterparties'][0]['exposure'],50)
        self.assertEqual(d['concentration_hhi'],0.5)
        self.assertEqual(d['concentration_breaches'],[])
        self.assertTrue(all(s['loss']==10 and not s['limit_breached'] for s in d['sector_shocks']))
        d=self.client.post('/enterprise/analyze',json={'csv':self.sample,'concentration_limit_pct':49,'loss_limit_pct':9}).json()
        self.assertEqual(len(d['concentration_breaches']),4)
        self.assertTrue(all(s['limit_breached'] for s in d['sector_shocks']))
    def test_access_and_owner_exemption(self):
        self.assertEqual(self.client.post('/enterprise/analyze',json={'csv':self.sample}).status_code,401)
        self.client.post('/auth/signup',json=self.creds)
        self.client.post('/plans/select',json={'plan_id':'bank'})
        self.assertEqual(self.client.get('/enterprise').status_code,403)
        self.assertEqual(self.client.post('/enterprise/analyze',json={'csv':self.sample}).status_code,403)
        token=provision_owner()
        self.client.post('/auth/owner/setup',json={'token':token,'password':self.creds['password']})
        self.assertEqual(self.client.get('/enterprise').status_code,200)
        self.assertEqual(self.client.post('/enterprise/analyze',json={'csv':self.sample}).status_code,200)
    def test_invalid_and_mixed_currency_rows(self):
        self.enable()
        for csv in ['', 'bad,columns\n1,2', self.sample.replace('30','nan'),self.sample.replace('30','-1'),self.sample.replace('30','inf'),self.sample.replace('30','0'),self.sample.replace('30','1e16'),self.sample.replace('Insurance,USD','Insurance,EUR'),'counterparty,sector,currency,exposure\nA,Bank,USD,']:
            self.assertEqual(self.client.post('/enterprise/analyze',json={'csv':csv}).status_code,422)
        for overrides in [{'shock_pct':101},{'loss_limit_pct':-1},{'concentration_limit_pct':0}]:
            self.assertEqual(self.client.post('/enterprise/analyze',json={'csv':self.sample,**overrides}).status_code,422)
