import unittest
from tests import test_auth
from src.api.owner import OWNER_EMAIL


class EmailTests(unittest.TestCase):
    setUp = test_auth.AuthTests.setUp
    tearDown = test_auth.AuthTests.tearDown

    def test_email_signup_persistence_login_and_plan_gate(self):
        body = {'email': ' Analyst@Example.com ', 'password': self.creds['password']}
        response = self.client.post('/auth/signup', json=body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['redirect'], '/plans')
        self.assertEqual(self.client.get('/auth/me').json(), {'email': 'analyst@example.com', 'email_verified': False})
        self.assertEqual(self.client.get('/scan').status_code, 403)
        self.client.post('/plans/select', json={'plan_id': 'professional'})
        self.client.post('/auth/signout')
        self.assertEqual(self.client.post('/auth/signin', json=body).status_code, 200)
        self.assertEqual(self.client.get('/scan').status_code, 200)
        self.assertEqual(self.client.post('/auth/signup', json={**body, 'email': 'analyst@example.com'}).status_code, 409)

    def test_email_validation_and_owner_cannot_be_claimed(self):
        for email in ['a@@example.com', 'a@-example.com', 'a@exam ple.com', OWNER_EMAIL.upper()]:
            self.assertEqual(self.client.post('/auth/signup', json={'email': email, 'password': self.creds['password']}).status_code, 422)
        self.assertEqual(self.client.post('/auth/signup', json={**self.creds, 'email': 'a@example.com'}).status_code, 422)

    def test_email_in_legacy_identifier_and_wrong_password(self):
        body = {**self.creds, 'mobile': 'customer@example.com'}
        self.assertEqual(self.client.post('/auth/signup', json=body).status_code, 201)
        self.client.post('/auth/signout')
        self.assertEqual(self.client.post('/auth/signin', json={**body, 'password': 'Wrong password long!'}).status_code, 401)
        self.assertEqual(self.client.post('/auth/signin', json=body).status_code, 200)

