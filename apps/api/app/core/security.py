import os

import bcrypt
from fastapi import HTTPException, Request

from app.core import tokens
from app.core.config import settings
from app.core.ratelimit import MemoryLimiter, SafeLimiter, account_key, create_limiter

_limiter = None
DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode()  # equalises timing for unknown accounts


def get_limiter():
    global _limiter
    if _limiter is None:
        _limiter = create_limiter(os.environ)
    return _limiter


def reset_limits():
    global _limiter
    _limiter = SafeLimiter(MemoryLimiter())


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    return bcrypt.checkpw(p.encode(), h.encode())


def issue_session(user_id):
    """-> (session JWT for the httpOnly cookie, CSRF token readable by the frontend)"""
    token, jti = tokens.issue(user_id, settings.jwt_secret, settings.jwt_expire_minutes * 60)
    return token, tokens.csrf_token(settings.jwt_secret, jti)


def _block(retry):
    raise HTTPException(429, "Too many attempts. Try again later.", headers={"Retry-After": str(retry)})


def auth_rate_limit(request: Request):
    ok, retry = get_limiter().hit("ip:" + (request.client.host if request.client else "?"), 20, 60)
    if not ok:
        _block(retry)


def check_account(email: str):
    ok, retry = get_limiter().hit(account_key(email), 10, 900)  # per-account attempt cap, independent of IP rotation
    if not ok:
        _block(retry)
