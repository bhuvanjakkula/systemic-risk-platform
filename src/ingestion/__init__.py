"""Validate entity balance sheets and directed credit exposures."""
from src.common import number


def ingest(payload, max_entities=500):
    if not isinstance(payload, dict):
        raise ValueError('Input must be an object')
    entities = payload.get('entities')
    exposures = payload.get('exposures', [])
    if not isinstance(entities, list) or not 1 <= len(entities) <= max_entities:
        raise ValueError(f'entities must contain 1 to {max_entities} entries')
    if not isinstance(exposures, list):
        raise ValueError('exposures must be a list')
    records = {}
    for entity in entities:
        if not isinstance(entity, dict):
            raise ValueError('Each entity must be an object')
        identifier = entity.get('id')
        if not isinstance(identifier, str) or not identifier.strip() or identifier in records:
            raise ValueError('Entity IDs must be unique nonempty strings')
        assets = number(entity.get('assets'), 'assets')
        if assets == 0:
            raise ValueError('assets must be positive')
        capital = number(entity.get('capital'), 'capital', 0, assets)
        liquidity = number(entity.get('liquidity'), 'liquidity', 0, assets)
        records[identifier] = dict(id=identifier, assets=assets, capital=capital, liquidity=liquidity)
    edges, seen, totals = [], set(), dict.fromkeys(records, 0.0)
    for exposure in exposures:
        if not isinstance(exposure, dict):
            raise ValueError('Each exposure must be an object')
        creditor, debtor = exposure.get('creditor'), exposure.get('debtor')
        if not isinstance(creditor, str) or not isinstance(debtor, str):
            raise ValueError('Exposure endpoints must be entity IDs')
        if creditor not in records or debtor not in records or creditor == debtor:
            raise ValueError('Exposure endpoints must be distinct known entities')
        if (creditor, debtor) in seen:
            raise ValueError('Duplicate exposure; aggregate each creditor/debtor pair first')
        seen.add((creditor, debtor))
        amount = number(exposure.get('amount'), 'amount')
        totals[creditor] += amount
        if totals[creditor] > records[creditor]['assets']:
            raise ValueError('Total credit exposures cannot exceed creditor assets')
        edges.append(dict(creditor=creditor, debtor=debtor, amount=amount))
    return records, edges
