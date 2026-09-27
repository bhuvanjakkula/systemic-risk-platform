import unittest
from concurrent.futures import ThreadPoolExecutor

from tests.auth_support import authenticated_client
from src.api import main
from src.transparency.ledger import PermissionedLedger


class FastAPITests(unittest.TestCase):
    def setUp(self):
        main.LEDGER = PermissionedLedger()
        self.auth_context = authenticated_client(main.app)
        self.client = self.auth_context.__enter__()

    def tearDown(self):
        self.auth_context.__exit__(None, None, None)

    def test_health_and_scan(self):
        self.assertEqual(self.client.get('/health').json(), {'ok': True, 'ledger_height': 1})
        response = self.client.get('/scan?stressed=true&seed=7')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['banks']), 5)
        self.assertTrue(response.json()['risk_alerts'])
        self.assertEqual(response.json(), self.client.get('/scan?stressed=true&seed=7').json())

    def test_twin_and_validation(self):
        response = self.client.post('/twin', json={'ai_agents': False})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body['with_ai']['steps']), 120)
        self.assertEqual(len(body['without_ai']['steps']), 120)
        self.assertEqual(body['selected_scenario'], 'without_ai')
        self.assertEqual(self.client.post('/twin', json={'shocked_bank': 'unknown'}).status_code, 404)
        for rumor in (-0.1, 1.1):
            self.assertEqual(self.client.post('/twin', json={'rumor': rumor}).status_code, 422)

    def test_solvency_and_unknown_bank(self):
        self.assertEqual(self.client.post('/solvency/unknown').status_code, 404)
        self.assertEqual(len(main.LEDGER.chain), 1)
        response = self.client.post('/solvency/B01')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['verified'])
        self.assertTrue(body['chain_valid'])
        self.assertEqual(body['block']['index'], 1)
        self.assertEqual(body['proof']['bank_id'], 'B01')
        self.assertIn('not a cryptographic solvency proof', body['verification_scope'])

    def test_concurrent_append(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: main.solvency('B01'), range(8)))
        self.assertEqual(sorted(result['block']['index'] for result in results), list(range(1, 9)))
        self.assertTrue(main.LEDGER.verify_chain())


if __name__ == '__main__':
    unittest.main()
