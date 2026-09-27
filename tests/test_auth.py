import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.api.main import app
from src.api.auth import COOKIE, database

class AuthTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=str(Path(self.folder.name)/'accounts.sqlite3')
        self.env=patch.dict(os.environ,{'SRP_AUTH_DB':self.path})
        self.env.start()
        self.client=TestClient(app,headers={'X-SRP-Request':'1'})
        self.creds={'mobile':'+15555550123','password':'Test-only long password!'}
    def tearDown(self):
        self.client.close();self.env.stop();self.folder.cleanup()
    def signup(self):
        return self.client.post('/auth/signup',json=self.creds)
    def test_first_page_and_all_protected_routes(self):
        self.assertIn('Welcome back',self.client.get('/').text)
        self.assertEqual(self.client.get('/dashboard',follow_redirects=False).status_code,303)
        for path in ['/scan','/openapi.json','/auth/me']:
            self.assertEqual(self.client.get(path).status_code,401)
        for path in ['/twin','/policy/evaluate','/policy/calibrate','/reports/import','/solvency/B01']:
            self.assertEqual(self.client.post(path,json={}).status_code,401)
    def test_signup_login_logout_and_cookie_replay(self):
        r=self.signup();self.assertEqual(r.status_code,201)
        self.assertIn('HttpOnly',r.headers['set-cookie']);self.assertIn('SameSite=strict',r.headers['set-cookie'])
        self.assertEqual(self.client.get('/auth/me').json(),{'mobile':self.creds['mobile'],'mobile_verified':False})
        self.assertEqual(self.client.post('/plans/select',json={'plan_id':'professional'}).status_code,200)
        self.assertIn('See stress',self.client.get('/dashboard').text)
        token=self.client.cookies.get(COOKIE)
        self.assertEqual(self.client.post('/auth/signout').status_code,200)
        self.client.cookies.set(COOKIE,token)
        self.assertEqual(self.client.get('/scan').status_code,401)
        self.client.cookies.clear()
        self.assertEqual(self.client.post('/auth/signin',json=self.creds).status_code,200)
        self.assertNotEqual(self.client.cookies.get(COOKIE),token)
        self.assertEqual(self.client.get('/docs').status_code,200)
    def test_persistent_hashes_and_sessions(self):
        self.signup()
        with database() as db:
            stored=db.execute('SELECT password_hash FROM users').fetchone()[0]
            session=db.execute('SELECT token_hash FROM sessions').fetchone()[0]
        self.assertTrue(stored.startswith('scrypt$'))
        self.assertNotIn(self.creds['password'],stored)
        self.assertNotEqual(session,self.client.cookies.get(COOKIE))
        with TestClient(app,headers={'X-SRP-Request':'1'}) as other:
            self.assertEqual(other.post('/auth/signin',json=self.creds).status_code,200)
    def test_duplicate_normalization_invalid_inputs_and_wrong_password(self):
        self.signup()
        normalized={**self.creds,'mobile':'+1 (555) 555-0123'}
        self.assertEqual(self.client.post('/auth/signup',json=normalized).status_code,409)
        self.assertEqual(self.client.post('/auth/signin',json=normalized).status_code,200)
        for fields in [{'mobile':'12345'}, {'password':'short'}, {'password':'x'*129}]:
            self.assertEqual(self.client.post('/auth/signup',json={**self.creds,**fields}).status_code,422)
        wrong=self.client.post('/auth/signin',json={**self.creds,'password':'An incorrect password!'})
        unknown=self.client.post('/auth/signin',json={**self.creds,'mobile':'+15555550124'})
        self.assertEqual(wrong.status_code,401);self.assertEqual(wrong.json(),unknown.json())
    def test_expiry(self):
        self.signup()
        with database() as db:db.execute('UPDATE sessions SET expires_at=?',(int(time.time())-1,))
        self.assertEqual(self.client.get('/auth/me').status_code,401)
    def test_csrf_and_host_rejection(self):
        with TestClient(app) as other:
            self.assertEqual(other.post('/auth/signup',json=self.creds).status_code,403)
        self.assertEqual(self.client.post('/auth/signup',json=self.creds,headers={'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.get('/',headers={'Host':'attacker.example'}).status_code,400)
    def test_rate_limit(self):
        # Fill persistent buckets directly to avoid spending the test on password hashing.
        self.signup()
        with database() as db:db.execute('UPDATE attempts SET count=40')
        r=self.client.post('/auth/signin',json=self.creds)
        self.assertEqual(r.status_code,429);self.assertEqual(r.headers['retry-after'],'900')

