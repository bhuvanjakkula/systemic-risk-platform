"""Illustrative decision support. No authority to execute interventions."""
from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Nonnegative = Annotated[float, Field(ge=0, le=1e12, allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Costs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    false_positive: Nonnegative = 10
    false_negative: Nonnegative = 100
    true_positive: Nonnegative = 5
    true_negative: Nonnegative = 0
    fiscal_cost: Nonnegative = 0
    moral_hazard_cost: Nonnegative = 0

    def losses(self, p):
        overhead = self.fiscal_cost + self.moral_hazard_cost
        return ((1-p)*self.false_positive + p*self.true_positive + overhead,
                (1-p)*self.true_negative + p*self.false_negative)


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', protected_namespaces=('model_dump',))
    probability: Probability = 0.35
    uncertainty: Probability = 0.1
    costs: Costs = Field(default_factory=Costs)
    evidence_verified: bool = False
    commitment: bool = False
    model_validated: bool = False
    data_fresh: bool = True
    collateral_eligible: bool = False
    audit_cost: Nonnegative = 2


def evaluate(req: PolicyRequest):
    c = req.costs
    numerator = c.false_positive - c.true_negative + c.fiscal_cost + c.moral_hazard_cost
    denominator = c.false_positive - c.true_negative + c.false_negative - c.true_positive
    crossing = numerator / denominator if denominator else None
    threshold = crossing if crossing is not None and 0 <= crossing <= 1 else None
    action_loss, wait_loss = c.losses(req.probability)
    low = max(0, req.probability-req.uncertainty)
    high = min(1, req.probability+req.uncertainty)
    margins = [c.losses(p)[0]-c.losses(p)[1] for p in (low, high)]
    ambiguous = min(margins) <= 0 <= max(margins)
    blockers = []
    for field, reason in [('evidence_verified', 'Verify independent evidence'),
                          ('commitment', 'Approve and commit the policy before use'),
                          ('model_validated', 'Validate probability calibration on held-out outcomes'),
                          ('data_fresh', 'Refresh stale observations'),
                          ('collateral_eligible', 'Review collateral and facility eligibility')]:
        if not getattr(req, field):
            blockers.append(reason)
    # Perfect-information value is an upper bound, not an audit efficacy claim.
    p = req.probability
    perfect_loss = ((1-p)*min(c.losses(0)) + p*min(c.losses(1)))
    information_bound = max(0, min(action_loss, wait_loss)-perfect_loss)
    protocol = 'human_review' if blockers or ambiguous or action_loss <= wait_loss else 'monitor'
    payload = req.model_dump()
    return {'protocol': protocol, 'economic_preference': 'review_intervention' if action_loss < wait_loss else 'wait',
            'threshold': threshold, 'threshold_direction': 'above' if denominator > 0 else 'below' if denominator < 0 else 'constant',
            'intervention_loss': action_loss, 'inaction_loss': wait_loss,
            'uncertainty_interval': [low, high], 'ambiguous': ambiguous,
            'blockers': blockers, 'audit_value_upper_bound': information_bound,
            'audit_potentially_worthwhile': req.audit_cost < information_bound,
            'execution_authorized': False, 'policy_sha256': sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            'curve': [{'probability': i/100, 'intervention': c.losses(i/100)[0], 'inaction': c.losses(i/100)[1]} for i in range(101)],
            'scope': 'Illustrative cost model; user-supplied probability, not the heuristic scan score. Human decision support only.'}


class CalibrationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    probabilities: list[Probability] = Field(min_length=2, max_length=2000)
    outcomes: list[Literal[0, 1]] = Field(min_length=2, max_length=2000)
    costs: Costs = Field(default_factory=Costs)

    @model_validator(mode='after')
    def lengths(self):
        if len(self.probabilities) != len(self.outcomes):
            raise ValueError('probabilities and outcomes must have equal lengths')
        if set(self.outcomes) != {0, 1}:
            raise ValueError('both outcome classes are required')
        return self


def calibrate(req: CalibrationRequest):
    pairs = list(zip(req.probabilities, req.outcomes))
    # Include never-alert explicitly, even if a probability equals one.
    candidates = sorted(set([0.0] + req.probabilities)) + [None]
    rows = []
    for cutoff in candidates:
        counts = dict(tp=0, fp=0, tn=0, fn=0)
        loss = 0
        for p, y in pairs:
            alert = cutoff is not None and p >= cutoff
            counts[('t' if alert == bool(y) else 'f') + ('p' if alert else 'n')] += 1
            loss += req.costs.losses(y)[0 if alert else 1]
        rows.append({'threshold': cutoff, 'mean_loss': loss/len(pairs), **counts})
    best = min(rows, key=lambda r: r['mean_loss'])
    bins = []
    for i in range(10):
        values = [(p,y) for p,y in pairs if min(int(p*10),9) == i]
        if values:
            bins.append({'lower': i/10, 'count': len(values), 'mean_probability': sum(p for p,y in values)/len(values), 'event_rate': sum(y for p,y in values)/len(values)})
    return {'best': best, 'curve': rows, 'reliability': bins,
            'brier_score': sum((p-y)**2 for p,y in pairs)/len(pairs),
            'scope': 'Threshold selected on supplied validation outcomes. Evaluate on a separate test set before use; this does not certify or fit probability calibration.'}

