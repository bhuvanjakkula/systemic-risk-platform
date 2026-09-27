"""Explicitly provisioned local owner; never granted through public signup."""
import secrets
import time
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from src.api.auth import ROOT, database, fingerprint, password_hash, issue_session, throttle

router=APIRouter(tags=['Owner account'])
OWNER_EMAIL='bhuvanjakkula@gmail.com'

def provision_owner():
    """Local administrator operation only. Does not reset an activated password."""
    token=secrets.token_urlsafe(32)
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT u.id,u.password_hash FROM users u JOIN owner_access o ON o.user_id=u.id WHERE o.email=?',(OWNER_EMAIL,)).fetchone()
        if row and row['password_hash']:
            return None
        if row:
            uid=row['id']
        else:
            existing=db.execute('SELECT id FROM users WHERE mobile=?',(OWNER_EMAIL,)).fetchone()
            if existing:
                raise RuntimeError('Existing identifier requires explicit administrator review; owner was not granted.')
            uid=db.execute('INSERT INTO users(mobile,password_hash,created_at) VALUES (?,?,?)',(OWNER_EMAIL,'',int(time.time()))).lastrowid
            db.execute('INSERT INTO owner_access(user_id,email) VALUES (?,?)',(uid,OWNER_EMAIL))
        db.execute('UPDATE owner_access SET setup_hash=?,setup_expires=? WHERE user_id=?',(fingerprint(token),int(time.time())+86400,uid))
    return token

@router.get('/owner/setup',include_in_schema=False)
def setup_page():
    return FileResponse(ROOT/'web'/'owner-setup.html')

class Setup(BaseModel):
    model_config=ConfigDict(extra='forbid')
    token: SecretStr=Field(min_length=32,max_length=128)
    password: SecretStr=Field(min_length=12,max_length=128)

@router.post('/auth/owner/setup')
def complete_setup(body: Setup,request: Request,response: Response):
    throttle(request,'owner-setup')
    checksum=fingerprint(body.token.get_secret_value())
    with database() as db:
        row=db.execute('SELECT user_id FROM owner_access WHERE setup_hash=? AND setup_expires>?',(checksum,int(time.time()))).fetchone()
    if not row:
        raise HTTPException(400,'This setup link is invalid, expired, or already used.')
    encoded=password_hash(body.password.get_secret_value())
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        consumed=db.execute('UPDATE owner_access SET setup_hash=NULL,setup_expires=NULL WHERE user_id=? AND setup_hash=? AND setup_expires>?',(row['user_id'],checksum,int(time.time())))
        if consumed.rowcount != 1:
            raise HTTPException(400,'This setup link is invalid, expired, or already used.')
        db.execute('UPDATE users SET password_hash=? WHERE id=?',(encoded,row['user_id']))
        db.execute('DELETE FROM sessions WHERE user_id=?',(row['user_id'],))
    return issue_session(request,response,row['user_id'])
