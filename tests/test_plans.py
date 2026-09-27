import unittest
from tests import test_auth
from src.api.auth import database

class PlanTests(unittest.TestCase):
    setUp = test_auth.AuthTests.setUp
    tearDown = test_auth.AuthTests.tearDown
    signup = test_auth.AuthTests.signup
    def test_prices_and_auth_required(self):
        data=self.client.get('/plans/catalog').json()
        self.assertEqual([(p['id'],p['monthly_price_usd'],p['currency'],p['interval']) for p in data['plans']], [('professional',999,'USD','month'),('bank',4999,'USD','month'),('enterprise',9999,'USD','month')])
        self.assertFalse(data['payment_collection_enabled'])
        self.assertEqual(self.client.post('/plans/select',json={'plan_id':'bank'}).status_code,401)
    def test_onboarding_selection_and_persistence(self):
        self.assertEqual(self.signup().json()['redirect'],'/plans')
        self.assertEqual(self.client.get('/dashboard',follow_redirects=False).headers['location'],'/plans')
        self.assertEqual(self.client.get('/scan').json()['code'],'plan_required')
        for name,price in [('professional',999),('bank',4999),('enterprise',9999)]:
            r=self.client.post('/plans/select',json={'plan_id':name})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['plan']['monthly_price_usd'],price)
            self.assertFalse(r.json()['subscription_active'])
            self.assertIn('See stress',self.client.get('/dashboard').text)
        self.client.post('/auth/signout')
        self.assertEqual(self.client.post('/auth/signin',json=self.creds).json()['redirect'],'/plans')
        self.assertEqual(self.client.get('/plans/current').json()['plan']['id'],'enterprise')
    def test_price_tampering_and_invalid_plan(self):
        self.signup()
        for body in [{'plan_id':'free'},{'plan_id':'bank','monthly_price_usd':1}]:
            self.assertEqual(self.client.post('/plans/select',json=body).status_code,422)
        self.assertIsNone(self.client.get('/plans/current').json()['plan'])
    def test_choices_are_per_account(self):
        self.signup()
        self.client.post('/plans/select',json={'plan_id':'bank'})
        other={**self.creds,'mobile':'+15555550125'}
        self.client.post('/auth/signup',json=other)
        self.assertIsNone(self.client.get('/plans/current').json()['plan'])
        self.assertEqual(self.client.get('/scan').status_code,403)



    def test_existing_plan_database_migrates_without_losing_selection(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TABLE plan_preferences (user_id INTEGER PRIMARY KEY, plan_id TEXT NOT NULL CHECK(plan_id IN ('professional','bank')), selected_at INTEGER NOT NULL)")
            db.execute("INSERT INTO plan_preferences VALUES (123,'bank',456)")
            db.commit()
        with database() as db:
            self.assertEqual(tuple(db.execute('SELECT * FROM plan_preferences').fetchone()), (123, 'bank', 456))
            db.execute("UPDATE plan_preferences SET plan_id='enterprise' WHERE user_id=123")
        with database() as db:
            self.assertEqual(db.execute('SELECT plan_id FROM plan_preferences').fetchone()[0], 'enterprise')

