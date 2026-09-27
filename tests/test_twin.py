import json
import unittest
from copy import deepcopy

from src.common.config import load_settings
from src.digital_twin.simulator import run_twin
from src.ingestion.synthetic import generate_state


class TwinTests(unittest.TestCase):
    def test_trace_and_serialization(self):
        state = generate_state(stressed=True)
        before = deepcopy(state)
        result = run_twin(state, 'B01')
        self.assertEqual(state, before)
        self.assertEqual(result, run_twin(state, 'B01'))
        self.assertEqual(len(result.steps), load_settings()['twin']['steps'] * len(state.banks))
        self.assertEqual(len(json.loads(result.model_dump_json())['steps']), len(result.steps))
        self.assertTrue(0 <= result.peak_panic <= 1)
        last = {}
        for step in result.steps:
            self.assertGreaterEqual(step.deposits, 0)
            self.assertGreaterEqual(step.liquid_assets, 0)
            self.assertGreaterEqual(step.capital, 0)
            self.assertTrue(0 <= step.run_intensity <= 1)
            if step.bank_id in last:
                self.assertLessEqual(step.deposits, last[step.bank_id].deposits)
                if last[step.bank_id].failed:
                    self.assertTrue(step.failed)
            last[step.bank_id] = step
        self.assertEqual(result.failed_banks, sorted(bid for bid, step in last.items() if step.failed))

    def test_ai_toggle_changes_first_step(self):
        state = generate_state()
        enabled = run_twin(state, 'B01', include_ai_agents=True)
        disabled = run_twin(state, 'B01', include_ai_agents=False)
        self.assertGreater(enabled.steps[0].run_intensity, disabled.steps[0].run_intensity)
        self.assertLess(enabled.steps[0].deposits, disabled.steps[0].deposits)
        self.assertIn('AI herding=off', disabled.commentary)


if __name__ == '__main__':
    unittest.main()
