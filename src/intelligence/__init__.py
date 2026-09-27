"""Transparent illustrative vulnerability scores, not default probabilities."""


def score_entities(entities, exposures):
    largest = dict.fromkeys(entities, 0.0)
    for edge in exposures:
        largest[edge['creditor']] = max(largest[edge['creditor']], edge['amount'])
    results = []
    for identifier, entity in entities.items():
        components = {
            'capital_vulnerability': 1 - min(entity['capital'] / entity['assets'] / 0.15, 1),
            'liquidity_vulnerability': 1 - min(entity['liquidity'] / entity['assets'] / 0.20, 1),
            'counterparty_concentration': min(largest[identifier] / max(entity['capital'], 1e-12), 1),
        }
        score = 0.5 * components['capital_vulnerability'] + 0.3 * components['liquidity_vulnerability'] + 0.2 * components['counterparty_concentration']
        results.append(dict(id=identifier, score=round(score, 6), components=components))
    return sorted(results, key=lambda item: (-item['score'], item['id']))
