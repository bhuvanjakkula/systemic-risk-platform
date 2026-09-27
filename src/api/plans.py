"""Local plan preferences. No payment or subscription is created."""
from typing import Literal
import time
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from src.api.auth import database, ROOT

router = APIRouter(tags=['Customer plans'])
PLANS = {
    'professional': {'id':'professional', 'name':'Professional', 'monthly_price_usd':999, 'currency':'USD', 'interval':'month', 'stripe_payment_link':'https://buy.stripe.com/test_dRmbIT7ds5hPbTheIK2oE0l'},
    'bank': {'id':'bank', 'name':'Bank', 'monthly_price_usd':4999, 'currency':'USD', 'interval':'month', 'stripe_payment_link':'https://buy.stripe.com/test_bJe4grdBQ6lT7D18km2oE0j'},
    'enterprise': {'id':'enterprise', 'name':'Financial Enterprises', 'monthly_price_usd':9999, 'currency':'USD', 'interval':'month', 'stripe_payment_link':'https://buy.stripe.com/test_6oUaEPfJYh0xaPd8km2oE0k'},
}

def selected_plan(user_id):
    with database() as db:
        row=db.execute('SELECT plan_id FROM plan_preferences WHERE user_id=?', (user_id,)).fetchone()
    return PLANS.get(row['plan_id']) if row else None

@router.get('/plans', include_in_schema=False)
def plans_page():
    return FileResponse(ROOT/'web'/'plans.html')

@router.get('/plans/catalog')
def catalog():
    return {'plans':list(PLANS.values()), 'payment_collection_enabled':False}

@router.get('/plans/current')
def current(request: Request):
    if request.state.user.get('owner_email'):
        return {'plan':None, 'billing_status':'owner_exempt', 'subscription_active':False, 'owner_access':True, 'monthly_price_usd':0}
    return {'plan':selected_plan(request.state.user['id']), 'billing_status':'not_connected', 'subscription_active':False}

class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan_id: Literal['professional','bank','enterprise']

@router.post('/plans/select')
def select(body: Selection, request: Request):
    if request.state.user.get('owner_email'):
        return {'billing_status':'owner_exempt', 'subscription_active':False, 'redirect':'/dashboard'}
    with database() as db:
        db.execute('INSERT INTO plan_preferences(user_id,plan_id,selected_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET plan_id=excluded.plan_id,selected_at=excluded.selected_at', (request.state.user['id'],body.plan_id,int(time.time())))
    return {'plan':PLANS[body.plan_id], 'billing_status':'not_connected', 'subscription_active':False, 'redirect':'/dashboard'}

