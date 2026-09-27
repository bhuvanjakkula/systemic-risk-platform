"""Deterministic, user-supplied exposure scenarios for enterprise research."""
import csv
import io
import math
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from src.api.auth import ROOT
from src.api.plans import selected_plan

router = APIRouter(prefix='/enterprise', tags=['Enterprise'])

def require_enterprise(request):
    user = request.state.user
    plan = selected_plan(user['id'])
    if not user.get('owner_email') and (not plan or plan['id'] != 'enterprise'):
        raise HTTPException(403, 'Financial Enterprises plan or owner access required.')

@router.get('', include_in_schema=False)
def page(request: Request):
    require_enterprise(request)
    return FileResponse(ROOT / 'web' / 'enterprise.html')

class Analysis(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    csv: str = Field(min_length=1, max_length=300000)
    concentration_limit_pct: float = Field(default=25, gt=0, le=100)
    loss_limit_pct: float = Field(default=10, ge=0, le=100)
    shock_pct: float = Field(default=20, ge=0, le=100)

@router.post('/analyze')
def analyze(body: Analysis, request: Request):
    require_enterprise(request)
    reader = csv.DictReader(io.StringIO(body.csv.strip()))
    if reader.fieldnames != ['counterparty', 'sector', 'currency', 'exposure']:
        raise HTTPException(422, 'CSV columns must be counterparty,sector,currency,exposure in that order.')
    rows = []
    for line, row in enumerate(reader, 2):
        try:
            if None in row or any(v is None or not v.strip() for v in row.values()):
                raise ValueError()
            exposure = float(row['exposure'])
            if not math.isfinite(exposure) or exposure <= 0 or exposure > 1e15:
                raise ValueError()
            currency = row['currency'].strip().upper()
            if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
                raise ValueError()
            rows.append(dict(counterparty=row['counterparty'].strip(), sector=row['sector'].strip(), currency=currency, exposure=exposure))
            if len(rows) > 1000:
                raise HTTPException(422, 'Maximum 1,000 exposure rows.')
        except (ValueError, TypeError):
            raise HTTPException(422, f'Invalid row {line}: supply names, a three-letter currency, and a finite positive exposure up to 1e15.')
    if not rows or len({r['currency'] for r in rows}) != 1:
        raise HTTPException(422, 'Supply at least one row, all in one reporting currency. Convert currencies before importing.')
    total = math.fsum(r['exposure'] for r in rows)
    def group(key):
        sums = {}
        for r in rows:
            name = r[key].casefold()
            entry = sums.setdefault(name, {'name': r[key], 'exposure': 0})
            entry['exposure'] += r['exposure']
        return sorted([dict(**r, share_pct=r['exposure']/total*100) for r in sums.values()], key=lambda r: (-r['exposure'], r['name']))
    counterparties, sectors = group('counterparty'), group('sector')
    scenarios = []
    for s in sectors:
        loss = s['exposure'] * body.shock_pct/100
        scenarios.append({'sector': s['name'], 'loss': loss, 'loss_pct': loss/total*100, 'limit_breached': loss/total*100 > body.loss_limit_pct})
    breaches = [{'kind': key, **r} for key, groups in [('counterparty', counterparties), ('sector', sectors)] for r in groups if r['share_pct'] > body.concentration_limit_pct]
    return {'created_at': datetime.now(timezone.utc).isoformat(), 'currency': rows[0]['currency'], 'total_exposure': total,
            'row_count': len(rows), 'counterparties': counterparties, 'sectors': sectors,
            'concentration_hhi': sum((r['share_pct']/100)**2 for r in counterparties),
            'concentration_breaches': breaches, 'sector_shocks': scenarios,
            'limits': body.model_dump(exclude={'csv'}), 'inputs': rows,
            'scope': 'Illustrative exposure haircut scenarios; no probabilities, netting, recoveries, contagion or regulatory certification. Each sector shock is independent. Uploaded data is not retained by this endpoint.'}
