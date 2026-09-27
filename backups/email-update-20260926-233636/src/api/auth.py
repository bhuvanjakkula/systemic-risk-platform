"""Local mobile/password accounts and revocable, opaque sessions."""
from contextlib import contextmanager
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix='/auth', tags=['Accounts'])
COOKIE = 'srp_session'
SESSION_SECONDS = 8 * 60 * 60
ROOT = Path(__file__).resolve().parents[2]

@contextmanager
def database():
    path = Path(os.environ.get('SRP_AUTH_DB', str(ROOT / 'data' / 'accounts.sqlite3')))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, mobile TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS owner_access (
          user_id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
          setup_hash TEXT, setup_expires INTEGER);
        CREATE TABLE IF NOT EXISTS plan_preferences (
          user_id INTEGER PRIMARY KEY, plan_id TEXT NOT NULL CHECK(plan_id IN ('professional','bank')),
          selected_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts (
          bucket TEXT PRIMARY KEY, started_at INTEGER NOT NULL, count INTEGER NOT NULL);
        ''')
        yield db
        db.commit()
    finally:
        db.close()


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=5, dklen=32)
    return 'scrypt$16384$8$5$' + salt.hex() + '$' + digest.hex()


def password_matches(password, encoded):
    salt = bytes.fromhex(encoded.split('$')[4])
    return hmac.compare_digest(password_hash(password, salt), encoded)


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mobile: str = Field(min_length=8, max_length=32)
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator('mobile')
    @classmethod
    def normalize_mobile(cls, value):
        value = re.sub(r'[\s()-]', '', value)
        if not re.fullmatch(r'\+[1-9][0-9]{7,14}', value):
            raise ValueError('Use your country code, for example +919876543210')
        return value


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()


def throttle(request, mobile):
    now = int(time.time())
    ip = request.client.host if request.client else 'local'
    blocked = False
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM attempts WHERE started_at < ?', (now-900,))
        for key, limit in [('ip:'+ip, 40), ('mobile:'+mobile, 10)]:
            bucket = fingerprint(key)
            row = db.execute('SELECT count FROM attempts WHERE bucket=?', (bucket,)).fetchone()
            if row and row['count'] >= limit:
                blocked = True
            db.execute('INSERT INTO attempts VALUES (?, ?, 1) ON CONFLICT(bucket) DO UPDATE SET count=count+1', (bucket, now))
    if blocked:
        raise HTTPException(429, 'Too many attempts. Please try again in 15 minutes.', headers={'Retry-After': '900'})


def current_user(request):
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 128:
        return None
    with database() as db:
        row = db.execute('SELECT u.id, u.mobile, o.email AS owner_email FROM sessions s JOIN users u ON u.id=s.user_id LEFT JOIN owner_access o ON o.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?', (fingerprint(token), int(time.time()))).fetchone()
    return dict(row) if row else None


def issue_session(request, response, user_id):
    token = secrets.token_urlsafe(32)
    with database() as db:
        db.execute('DELETE FROM sessions WHERE expires_at <= ?', (int(time.time()),))
        old = request.cookies.get(COOKIE)
        if old:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (fingerprint(old),))
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (fingerprint(token), user_id, int(time.time())+SESSION_SECONDS))
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=request.url.scheme=='https', samesite='strict', path='/')
    with database() as db:
        owner = db.execute('SELECT 1 FROM owner_access WHERE user_id=?', (user_id,)).fetchone()
    return {'ok': True, 'redirect': '/dashboard' if owner else '/plans'}


@router.post('/signup', status_code=201)
def signup(body: Credentials, request: Request, response: Response):
    throttle(request, body.mobile)
    encoded = password_hash(body.password.get_secret_value())
    try:
        with database() as db:
            cursor = db.execute('INSERT INTO users(mobile,password_hash,created_at) VALUES (?,?,?)', (body.mobile, encoded, int(time.time())))
            uid = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Unable to create this account. Try signing in or use another mobile number.')
    return issue_session(request, response, uid)


class LoginCredentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mobile: str = Field(min_length=8, max_length=254)
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator('mobile')
    @classmethod
    def normalize_identifier(cls, value):
        value = value.strip().lower()
        if '@' in value:
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
                raise ValueError('Enter a mobile number or owner email')
            return value
        return Credentials.normalize_mobile(value)


@router.post('/signin')
def signin(body: LoginCredentials, request: Request, response: Response):
    throttle(request, body.mobile)
    with database() as db:
        row = db.execute('SELECT id,password_hash FROM users WHERE mobile=?', (body.mobile,)).fetchone()
    # Equal-cost hash work for unknown numbers and wrong passwords.
    encoded = row['password_hash'] if row and row['password_hash'] else 'scrypt$16384$8$5$' + ('00'*16) + '$' + ('00'*32)
    valid = password_matches(body.password.get_secret_value(), encoded)
    if not row or not valid:
        raise HTTPException(401, 'Mobile number or password is incorrect.')
    return issue_session(request, response, row['id'])


@router.post('/signout')
def signout(request: Request, response: Response):
    token = request.cookies.get(COOKIE, '')
    with database() as db:
        db.execute('DELETE FROM sessions WHERE token_hash=?', (fingerprint(token),))
    response.delete_cookie(COOKIE, path='/', httponly=True, samesite='strict')
    return {'ok': True}


@router.get('/me')
def me(request: Request):
    if request.state.user.get('owner_email'):
        return {'email':request.state.user['owner_email'], 'role':'owner', 'billing_exempt':True}
    return {'mobile': request.state.user['mobile'], 'mobile_verified': False}


async def protect(request: Request, call_next):
    path = request.url.path
    # Non-simple custom header blocks browser cross-site form requests; no CORS is enabled.
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        expected = f'{request.url.scheme}://{request.url.netloc}'
        if request.headers.get('x-srp-request') != '1' or (origin and origin != expected) or request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Request origin could not be verified.'}, status_code=403)
    public = path in ('/', '/signin', '/health', '/auth/signup', '/auth/signin', '/favicon.ico', '/plans', '/plans/catalog', '/owner/setup', '/auth/owner/setup')
    request.state.user = await run_in_threadpool(current_user, request)
    if not public and not request.state.user:
        if path in ('/dashboard', '/docs', '/redoc'):
            return RedirectResponse('/signin', status_code=303)
        return JSONResponse({'detail': 'Please sign in to continue.'}, status_code=401, headers={'Cache-Control':'no-store'})
    if request.state.user and not request.state.user.get('owner_email') and not public and path not in ('/auth/me', '/auth/signout', '/plans/current', '/plans/select'):
        from src.api.plans import selected_plan
        if not await run_in_threadpool(selected_plan, request.state.user['id']):
            if path in ('/dashboard', '/docs', '/redoc'):
                return RedirectResponse('/plans', status_code=303)
            return JSONResponse({'detail':'Choose a customer plan to continue.', 'code':'plan_required', 'redirect':'/plans'}, status_code=403, headers={'Cache-Control':'no-store'})
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
    if path in ('/docs', '/redoc'):
        response.headers['Content-Security-Policy'] = response.headers['Content-Security-Policy'].replace("script-src 'self'", "script-src https://cdn.jsdelivr.net 'self'").replace("style-src 'self'", "style-src https://cdn.jsdelivr.net 'self'")
    return response
