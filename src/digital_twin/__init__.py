"""Synchronous default contagion with each debtor default applied once."""
from src.common import number


def simulate(entities, exposures, shocks, loss_given_default=0.6):
    lgd = number(loss_given_default, 'loss_given_default', 0, 1)
    if not isinstance(shocks, dict) or any(key not in entities for key in shocks):
        raise ValueError('shocks must map known entity IDs to asset-loss fractions')
    shocks = {key: number(value, 'shock', 0, 1) for key, value in shocks.items()}
    direct = {key: entity['assets'] * shocks.get(key, 0) for key, entity in entities.items()}
    capital = {key: entity['capital'] - direct[key] for key, entity in entities.items()}
    credit_losses = dict.fromkeys(entities, 0.0)
    frontier = {key for key in entities if capital[key] <= 0}
    defaulted = set(frontier)
    rounds = [sorted(frontier)] if frontier else []
    while frontier:
        for edge in exposures:
            if edge['debtor'] in frontier:
                loss = edge['amount'] * lgd
                capital[edge['creditor']] -= loss
                credit_losses[edge['creditor']] += loss
        frontier = {key for key in entities if capital[key] <= 0 and key not in defaulted}
        if frontier:
            rounds.append(sorted(frontier))
            defaulted.update(frontier)
    return dict(defaulted=sorted(defaulted), default_rounds=rounds,
                remaining_capital=capital, direct_losses=direct, credit_losses=credit_losses,
                total_loss=sum(direct.values()) + sum(credit_losses.values()))
