from __future__ import annotations

from typing import Dict, List

import networkx as nx

from src.common.models import SystemState


def exposure_graph(state: SystemState) -> nx.DiGraph:
    g = nx.DiGraph()
    for b in state.banks:
        g.add_node(b, capital=state.banks[b].capital, assets=state.banks[b].assets)
    for e in state.exposures:
        g.add_edge(e.lender, e.borrower, amount=e.amount)
    return g


def cascade_losses(state: SystemState, initial_failed: List[str], lgd: float = 0.4) -> Dict[str, float]:
    """Simple default cascade: failed borrower inflicts LGD * exposure on lender.

    Each exposure is charged once; lenders already failed are not charged further.
    """
    g = exposure_graph(state)
    failed = set(initial_failed)
    losses = {n: 0.0 for n in g.nodes}
    applied = set()
    changed = True
    while changed:
        changed = False
        for lender, borrower, data in list(g.edges(data=True)):
            edge = (lender, borrower)
            if borrower in failed and lender not in failed and edge not in applied:
                applied.add(edge)
                hit = data["amount"] * lgd
                losses[lender] += hit
                cap = state.banks[lender].capital - losses[lender]
                if cap <= 0:
                    failed.add(lender)
                    changed = True
    return losses


def systemic_scores(state: SystemState) -> Dict[str, float]:
    g = exposure_graph(state)
    if g.number_of_edges() == 0:
        return {n: 0.0 for n in g.nodes}
    # Reversed edges pass PageRank importance from borrowers to lenders.
    pr = nx.pagerank(g.reverse(), weight="amount")
    # NetworkX treats these weights as path distances, not exposure strength.
    deg = nx.betweenness_centrality(g, weight="amount")
    return {n: 0.6 * pr.get(n, 0) + 0.4 * deg.get(n, 0) for n in g.nodes}
