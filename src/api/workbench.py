from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, ValidationError
from src.governance.policy import PolicyRequest, CalibrationRequest, evaluate, calibrate
from src.ingestion.report_csv import parse_reports

router = APIRouter()
WEB = Path(__file__).resolve().parents[2] / 'web'

@router.get('/', include_in_schema=False)
def entry(request: Request):
    if not request.state.user:
        return FileResponse(WEB / 'signin.html')
    from src.api.plans import selected_plan
    return RedirectResponse('/dashboard' if request.state.user.get('owner_email') or selected_plan(request.state.user['id']) else '/plans', status_code=303)

@router.get('/signin', include_in_schema=False)
def signin_page(request: Request):
    if request.state.user:
        return RedirectResponse('/dashboard' if request.state.user.get('owner_email') else '/plans', status_code=303)
    return FileResponse(WEB / 'signin.html')

@router.get('/dashboard', include_in_schema=False)
def dashboard():
    return FileResponse(WEB / 'index.html')

@router.post('/policy/evaluate')
def policy(req: PolicyRequest):
    return evaluate(req)

@router.post('/policy/calibrate')
def calibration(req: CalibrationRequest):
    return calibrate(req)

class CSVRequest(BaseModel):
    csv: str = Field(min_length=1, max_length=500000)

@router.post('/reports/import')
def reports(req: CSVRequest):
    try:
        return parse_reports(req.csv)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
