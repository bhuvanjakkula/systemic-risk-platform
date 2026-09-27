import copy
import json
import threading
import tempfile
from pathlib import Path

import yaml
from src.common import load_settings
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from tests.fixtures import SAMPLE
from src.api import Handler
from src.common.pipeline import analyze
from src.ingestion import ingest
from src.digital_twin import simulate
from src.transparency import digest


class CoreTests(unittest.TestCase):
    def test_settings(self):
        settings = load_settings()
        self.assertEqual(settings['platform']['alert_threshold'], 0.62)
        self.assertEqual(settings['platform']['contagion_loss_rate'], 0.4)
        self.assertEqual(settings['twin']['steps'], 24)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.yaml'
            defaults = load_settings(path)
            for section, values in defaults.items():
                for key, value in values.items():
                    self.assertEqual(settings[section][key], value)
            defaults['twin']['steps'] = 99
            self.assertEqual(load_settings(path)['twin']['steps'], 24)
            custom = {'platform': {'alert_threshold': 0.9}}
            path.write_text(yaml.safe_dump(custom), encoding='utf-8')
            self.assertEqual(load_settings(path), custom)

    def test_cascade(self):
        result = analyze(SAMPLE)
        self.assertEqual(result['simulation']['default_rounds'], [['Bank-A'], ['Bank-B'], ['Bank-C']])
        self.assertEqual(result['simulation']['total_loss'], 26)
        self.assertTrue(result['governance']['review_required'])

    def test_no_shock(self):
        data = copy.deepcopy(SAMPLE)
        data['shocks'] = {}
        self.assertEqual(analyze(data)['simulation']['total_loss'], 0)
        self.assertEqual(analyze(data)['simulation']['defaulted'], [])

    def test_cycle_counts_each_default_once(self):
        data = copy.deepcopy(SAMPLE)
        data['exposures'].append(dict(creditor='Bank-A', debtor='Bank-C', amount=20))
        result = analyze(data)['simulation']
        self.assertEqual(result['total_loss'], 34)
        self.assertEqual(len(result['default_rounds']), 3)

    def test_invalid_inputs(self):
        for value in (float('nan'), float('inf'), -1, True, '100'):
            data = copy.deepcopy(SAMPLE)
            data['entities'][0]['assets'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze(data)
        for shocks in ({'missing': 0.1}, {'Bank-A': 1.1}, []):
            data = dict(SAMPLE, shocks=shocks)
            with self.subTest(shocks=shocks), self.assertRaises(ValueError):
                analyze(data)

    def test_invalid_networks(self):
        for edge in (dict(creditor='missing', debtor='Bank-A', amount=1),
                     dict(creditor='Bank-A', debtor='Bank-A', amount=1),
                     dict(creditor='Bank-B', debtor='Bank-A', amount=1),
                     dict(creditor='Bank-B', debtor='Bank-C', amount=90)):
            data = copy.deepcopy(SAMPLE)
            data['exposures'].append(edge)
            with self.subTest(edge=edge), self.assertRaises(ValueError):
                analyze(data)

    def test_zero_capital_and_zero_lgd(self):
        data = copy.deepcopy(SAMPLE)
        data['entities'][0]['capital'] = 0
        entities, edges = ingest(data)
        result = simulate(entities, edges, {}, 0)
        self.assertEqual(result['defaulted'], ['Bank-A'])
        self.assertEqual(result['total_loss'], 0)

    def test_scores_and_evidence(self):
        result = analyze(SAMPLE)
        self.assertTrue(all(0 <= row['score'] <= 1 for row in result['scores']))
        audit = result.pop('audit')
        self.assertEqual(audit['output_sha256'], digest(result))
        self.assertEqual(audit['input_sha256'], digest(SAMPLE))
        checksum = audit.pop('record_sha256')
        self.assertEqual(checksum, digest(audit))
        result['simulation']['total_loss'] += 1
        self.assertNotEqual(audit['output_sha256'], digest(result))

    def test_api(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        try:
            for method, path, body, expected in (
                ('GET', '/health', None, 200),
                ('GET', '/missing', None, 404),
                ('POST', '/analyze', json.dumps(SAMPLE), 200),
                ('POST', '/analyze', '{bad', 400),
                ('POST', '/analyze', '[]', 400),
            ):
                conn.request(method, path, body, {'Content-Type': 'application/json'})
                response = conn.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, expected)
                if method == 'POST' and expected == 200:
                    self.assertEqual(payload['simulation']['total_loss'], 26)
        finally:
            conn.close()
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
