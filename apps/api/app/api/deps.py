import uuid

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import tokens
from app.core.config import settings
from app.core.db import get_db
from app.models import User, WorkspaceMember
from app.observability.logging import bind_context
from app.services.audit import audit  # noqa: F401  (re-exported for routers)

bearer = HTTPBearer(auto_error=False)
WRITE = {"owner", "admin", "researcher"}
ADMIN = {"owner", "admin"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def current_user(request: Request, cred=Depends(bearer), db: Session = Depends(get_db)) -> User:
    """Auth via Bearer token (API clients) or the httpOnly session cookie. Cookie-authenticated unsafe requests also need a valid
    CSRF token (bound to the session) and a trusted Origin."""
    auth_header = request.headers.get("Authorization")
    if auth_header is not None:
        if not cred or not cred.credentials:
            raise HTTPException(401, "Invalid or expired session")
        token = cred.credentials
    else:
        token = request.cookies.get(settings.session_cookie)
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        claims = tokens.decode(token, settings.jwt_secret)
        uid = uuid.UUID(claims["sub"])
    except (tokens.TokenError, ValueError):
        raise HTTPException(401, "Invalid or expired session")
    if not cred and request.method not in SAFE_METHODS:
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origins.split(","):
            raise HTTPException(403, "Untrusted origin")
        if not tokens.verify_csrf(settings.jwt_secret, claims["jti"], request.headers.get("X-CSRF-Token")):
            raise HTTPException(403, "CSRF validation failed")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "Invalid or expired session")
    bind_context(user_id=str(user.id))
    return user


def membership(db: Session, user: User, workspace_id, roles: set | None = None) -> WorkspaceMember:
    """Workspace isolation: non-members get 404, never a hint the workspace exists."""
    try:
        wid = uuid.UUID(str(workspace_id))
    except ValueError:
        raise HTTPException(404, "Workspace not found")
    m = db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == wid, WorkspaceMember.user_id == user.id))
    if not m:
        raise HTTPException(404, "Workspace not found")
    if roles and m.role not in roles:
        raise HTTPException(403, "Your role does not allow this action")
    return m
