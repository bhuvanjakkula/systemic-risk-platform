import unittest
from tests import test_auth
from src.api.auth import database, fingerprint
from src.api.owner import provision_owner, OWNER_EMAIL

class OwnerTests(unittest.TestCase):
    setUp=test_auth.AuthTests.setUp
    tearDown=test_auth.AuthTests.tearDown
    def activate(self):
        token=provision_owner()
        response=self.client.post('/auth/owner/setup',json={'token':token,'password':self.creds['password']})
        self.assertEqual(response.status_code,200)
        return token,response
    def test_setup_login_and_free_access(self):
        token,response=self.activate()
        self.assertEqual(response.json()['redirect'],'/dashboard')
        self.assertEqual(self.client.get('/auth/me').json()['role'],'owner')
        self.assertEqual(self.client.get('/scan').status_code,200)
        self.assertEqual(self.client.get('/dashboard',follow_redirects=False).status_code,200)
        self.assertEqual(self.client.get('/plans/current').json()['billing_status'],'owner_exempt')
        self.client.post('/auth/signout')
        response=self.client.post('/auth/signin',json={'mobile':OWNER_EMAIL.upper(),'password':self.creds['password']})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['redirect'],'/dashboard')
        self.assertIsNone(provision_owner())
    def test_no_public_owner_signup_or_claim(self):
        response=self.client.post('/auth/signup',json={'mobile':OWNER_EMAIL,'password':self.creds['password']})
        self.assertEqual(response.status_code,422)
        response=self.client.post('/auth/signup',json={**self.creds,'owner_email':OWNER_EMAIL})
        self.assertEqual(response.status_code,422)
        provision_owner()
        response=self.client.post('/auth/signin',json={'mobile':OWNER_EMAIL,'password':self.creds['password']})
        self.assertEqual(response.status_code,401)
        self.assertEqual(self.client.get('/scan').status_code,401)
    def test_token_single_use_and_not_stored_plaintext(self):
        token=provision_owner()
        with database() as db:
            self.assertEqual(db.execute('SELECT setup_hash FROM owner_access').fetchone()[0],fingerprint(token))
        body={'token':token,'password':self.creds['password']}
        self.assertEqual(self.client.post('/auth/owner/setup',json=body).status_code,200)
        self.assertEqual(self.client.post('/auth/owner/setup',json=body).status_code,400)
    def test_invalid_expired_tokens_and_normal_customer(self):
        token=provision_owner()
        with database() as db:db.execute('UPDATE owner_access SET setup_expires=0')
        self.assertEqual(self.client.post('/auth/owner/setup',json={'token':token,'password':self.creds['password']}).status_code,400)
        self.assertEqual(self.client.post('/auth/owner/setup',json={'token':'x'*43,'password':self.creds['password']}).status_code,400)
        self.client.post('/auth/signup',json=self.creds)
        self.assertEqual(self.client.get('/scan').status_code,403)
