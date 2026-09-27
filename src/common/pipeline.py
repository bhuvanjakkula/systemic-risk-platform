"""Compose ingestion, analysis, simulation, governance and evidence."""
from src.common import load_settings
from src.ingestion import ingest
from src.intelligence import score_entities
from src.digital_twin import simulate
from src.governance import review
from src.transparency import audit_record


def analyze(payload):
    settings = load_settings()
    entities, exposures = ingest(payload, 500)
    scores = score_entities(entities, exposures)
    simulation = simulate(entities, exposures, payload.get('shocks', {}), settings['platform']['contagion_loss_rate'])
    result = dict(scores=scores, simulation=simulation,
                  governance=review(scores, simulation, settings['platform']['alert_threshold']))
    result['audit'] = audit_record(payload, result, settings)
    return result
