"""Explainable review flags; no automated trading or regulatory decisions."""


def review(scores, simulation, threshold):
    flags = [dict(entity=row['id'], reason='Vulnerability score exceeds review threshold')
             for row in scores if row['score'] >= threshold]
    flags += [dict(entity=identifier, reason='Simulated capital exhaustion')
              for identifier in simulation['defaulted']]
    return dict(review_required=bool(flags), flags=flags)
