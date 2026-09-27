"""Local hypothesis / scenario / observation notebook; never executes funding."""
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.api.auth import ROOT, database

router = APIRouter(prefix='/inquiry', tags=['Risk experiments'])
class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)
class Scenario(Strict):
    name: str = Field(min_length=1,max_length=60)
    outflow_multiplier: float = Field(default=1,ge=0,le=10)
    facility_available: bool = True
    extra_delay_days: int = Field(default=0,ge=0,le=365)
    cash_shock: float = Field(default=0,ge=0,le=1e15)
    shock_day: int = Field(default=0,ge=0,le=90)
class Experiment(Strict):
    problem: str = Field(min_length=5,max_length=1000)
    hypothesis: str = Field(min_length=5,max_length=1000)
    currency: str = Field(default='USD',pattern=r'^[A-Z]{3}$')
    cash: float = Field(ge=0,le=1e15)
    daily_inflow: float = Field(ge=0,le=1e15)
    daily_outflow: float = Field(ge=0,le=1e15)
    days: int = Field(default=30,ge=1,le=90)
    minimum_cash: float = Field(default=0,ge=0,le=1e15)
    reserve: float = Field(default=0,ge=0,le=1e15)
    reserve_cost: float = Field(default=0,ge=0,le=1e15)
    facility: float = Field(default=0,ge=0,le=1e15)
    facility_delay: int = Field(default=1,ge=0,le=365)
    facility_fee_pct: float = Field(default=0,ge=0,le=100)
    cost_budget: float = Field(default=0,ge=0,le=1e15)
    scenarios: list[Scenario] = Field(min_length=1,max_length=8)
    @model_validator(mode='after')
    def unique_names(self):
        if len({s.name.casefold() for s in self.scenarios}) != len(self.scenarios):
            raise ValueError('Scenario names must be unique')
        if any(s.cash_shock > 0 and s.shock_day > self.days for s in self.scenarios):
            raise ValueError('A cash shock must occur within the experiment horizon')
        return self

def evaluate(e):
    alternatives=[]
    for name, use_reserve, use_facility in [('Baseline',False,False),('Cash buffer',True,False),('Credit facility',False,True),('Combined',True,True)]:
        results=[]
        for s in e.scenarios:
            fee=e.facility*e.facility_fee_pct/100 if use_facility and s.facility_available else 0
            cost=(e.reserve_cost if use_reserve else 0)+fee
            cash=e.cash+(e.reserve if use_reserve else 0)-cost
            arrival=e.facility_delay+s.extra_delay_days
            path=[]
            for day in range(e.days+1):
                if use_facility and s.facility_available and day==arrival:
                    cash+=e.facility
                if day:
                    cash+=e.daily_inflow-e.daily_outflow*s.outflow_multiplier
                if day == s.shock_day:
                    cash -= s.cash_shock
                path.append({'day':day,'cash':cash})
            first=next((r['day'] for r in path if r['cash']<e.minimum_cash),None)
            results.append({'scenario':s.name,'first_breach_day':first,'minimum_cash':min(r['cash'] for r in path),'end_cash':cash,'shortfall':max(0,e.minimum_cash-min(r['cash'] for r in path)),'cost':cost,'cost_within_budget':cost<=e.cost_budget,'path':path})
        alternatives.append({'name':name,'passes_all_supplied_scenarios':all(r['first_breach_day'] is None and r['cost_within_budget'] for r in results),'worst_shortfall':max(r['shortfall'] for r in results),'maximum_cost':max(r['cost'] for r in results),'results':results})
    for alternative in alternatives:
        alternative['funding_plan'] = funding_plan(alternative, e.minimum_cash)
    return {'model_version':'liquidity-inquiry-3','alternatives':alternatives,'scope':'Scenario evidence only. Constant daily cash flows; no intraday timing, interest, facility repayment or behavioral contagion. Reserve is pre-existing accessible cash excluded from opening cash. Costs are charged upfront; facility fee applies when available even if arrival is beyond the horizon. Facilities arrive before end-of-day flows. A supplied one-time cash shock is deducted after those flows on its specified day (including day zero); only closing balances are tested, not intraday payment timing. Negative balances represent unmet funding needs, not permissible borrowing. Passing is not regulatory approval or a causal finding.'}


def funding_plan(alternative, cash_floor):
    """Size a cost-free, immediately available cash top-up for the saved paths."""
    points = [(r['scenario'], p) for r in alternative['results'] for p in r['path']]
    scenario, lowest = min(points, key=lambda pair: pair[1]['cash'])
    required = max(0, cash_floor - lowest['cash'])
    breaches = [p['day'] for _, p in points if p['cash'] < cash_floor]
    budget_ok = all(r['cost_within_budget'] for r in alternative['results'])
    return {
        'additional_cash_required': required,
        'binding_scenario': scenario if required else None,
        'peak_shortfall_day': lowest['day'] if required else None,
        'first_breach_day': min(breaches) if breaches else None,
        'existing_costs_within_budget': budget_ok,
        'review': ('Review response costs as well as funding' if not budget_ok else
                   'Validate cash availability and rerun with actual funding costs' if required else
                   'Monitor assumptions; no extra cash needed in supplied scenarios'),
        'assumptions': 'Extra cash is available at day zero, unrestricted, and adds no cost or repayment. It shifts every modeled balance equally. Funding costs, feasibility and untested scenarios require separate review; this is not a regulatory buffer requirement.',
    }

def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS inquiries (id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS inquiry_observations (id TEXT PRIMARY KEY,inquiry_id TEXT NOT NULL,user_id INTEGER NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL)')

def fetch(db, eid, uid):
    row=db.execute('SELECT payload FROM inquiries WHERE id=? AND user_id=?',(eid,uid)).fetchone()
    if not row: raise HTTPException(404,'Experiment not found')
    return json.loads(row[0])

@router.get('',include_in_schema=False)
def page(): return FileResponse(ROOT/'web'/'inquiry.html')
@router.post('/preview')
def preview(body:Experiment): return {'inputs': body.model_dump(), 'analysis': evaluate(body)}
@router.post('/experiments',status_code=201)
def save(body:Experiment,request:Request):
    record={'id':str(uuid.uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),'inputs':body.model_dump(),'analysis':evaluate(body)}
    with database() as db:
        init(db)
        db.execute('INSERT INTO inquiries VALUES (?,?,?,?)',(record['id'],request.state.user['id'],record['created_at'],json.dumps(record)))
    return record
@router.get('/experiments')
def listing(request:Request):
    with database() as db:
        init(db)
        rows=db.execute('SELECT payload FROM inquiries WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(request.state.user['id'],)).fetchall()
    return [{'id':r['id'],'created_at':r['created_at'],'problem':r['inputs']['problem']} for r in map(lambda r:json.loads(r[0]),rows)]
@router.get('/experiments/{eid}')
def detail(eid:str,request:Request):
    with database() as db:
        init(db); record=fetch(db,eid,request.state.user['id'])
        rows=db.execute('SELECT payload FROM inquiry_observations WHERE inquiry_id=? AND user_id=? ORDER BY created_at',(eid,request.state.user['id'])).fetchall()
    return {**record,'observations':[json.loads(r[0]) for r in rows]}
class Observation(Strict):
    alternative: str = Field(min_length=1,max_length=60)
    scenario: str = Field(min_length=1,max_length=60)
    day: int = Field(ge=0,le=90)
    observed_cash: float = Field(ge=-1e17,le=1e17)
    tolerance: float = Field(ge=0,le=1e15)
    evidence: str = Field(min_length=5,max_length=2000)
    revision: str = Field(min_length=5,max_length=2000)
@router.post('/experiments/{eid}/observations',status_code=201)
def observe(eid:str,body:Observation,request:Request):
    with database() as db:
        init(db); record=fetch(db,eid,request.state.user['id'])
        match=next((r for a in record['analysis']['alternatives'] if a['name']==body.alternative for r in a['results'] if r['scenario']==body.scenario),None)
        if match is None or body.day>record['inputs']['days']: raise HTTPException(422,'Choose a saved alternative, scenario and day within its horizon')
        expected=match['path'][body.day]['cash']; error=body.observed_cash-expected
        result={**body.model_dump(),'id':str(uuid.uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),'projected_cash':expected,'error':error,'review':'Revise assumptions' if abs(error)>body.tolerance else 'Within supplied tolerance; continue observation'}
        db.execute('INSERT INTO inquiry_observations VALUES (?,?,?,?,?)',(result['id'],eid,request.state.user['id'],result['created_at'],json.dumps(result)))
    return result

