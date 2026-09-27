import math
import unittest
from copy import deepcopy

from src.common.models import Exposure
from src.ingestion.synthetic import generate_state
from src.intelligence.network import cascade_losses, exposure_graph, systemic_scores


class NetworkTests(unittest.TestCase):
    def test_graph_direction(self):
        graph = exposure_graph(generate_state())
        self.assertEqual(graph.number_of_nodes(), 5)
        self.assertEqual(graph.number_of_edges(), 6)
        self.assertEqual(graph['B04']['B01']['amount'], 4200)
        self.assertEqual(graph.nodes['B01']['capital'], 12000)

    def test_each_exposure_charged_once(self):
        state = generate_state()
        state.banks['B05'].capital = 2000
        state.banks['B02'].capital = 500
        before = deepcopy(state)
        losses = cascade_losses(state, ['B01'])
        self.assertEqual(losses['B05'], 2440)
        self.assertEqual(losses['B04'], 3680)
        self.assertEqual(losses['B02'], 360)
        self.assertEqual(state, before)

    def test_cycle_and_empty_seeds(self):
        state = generate_state()
        state.banks['B05'].capital = 2000
        state.exposures.append(Exposure('B01', 'B05', 8000))
        losses = cascade_losses(state, ['B01'])
        self.assertEqual(losses['B01'], 0)
        self.assertEqual(losses['B05'], 2440)
        self.assertTrue(all(value == 0 for value in cascade_losses(state, []).values()))
        self.assertTrue(all(value == 0 for value in cascade_losses(state, ['B01'], 0).values()))

    def test_scores_with_and_without_edges(self):
        state = generate_state()
        scores = systemic_scores(state)
        self.assertEqual(set(scores), set(state.banks))
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1 for value in scores.values()))
        state.exposures = []
        self.assertEqual(systemic_scores(state), dict.fromkeys(state.banks, 0.0))


if __name__ == '__main__':
    unittest.main()
