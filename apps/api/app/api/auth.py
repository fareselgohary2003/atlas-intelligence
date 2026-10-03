import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import audit, current_user
from app.core import security
from app.core.config import settings
from app.core.db import get_db
from app.core.ratelimit import account_key
from app.models import User, Workspace, WorkspaceMember
from app.schemas import LoginIn, SignupIn

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("atlas.auth")


def user_out(u: User):
    return {"id": str(u.id), "email": u.email, "name": u.name}


def set_session(response: Response, user_id) -> str:
    token, csrf = security.issue_session(user_id)
    ttl = settings.jwt_expire_minutes * 60
    kw = dict(max_age=ttl, secure=settings.cookie_secure, samesite=settings.cookie_samesite, path="/")
    response.set_cookie(settings.session_cookie, token, httponly=True, **kw)  # not readable by JavaScript
    response.set_cookie(settings.csrf_cookie, csrf, httponly=False, **kw)      # echoed back in X-CSRF-Token
    return token


@router.post("/signup", status_code=201, dependencies=[Depends(security.auth_rate_limit)])
def signup(body: SignupIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, name=body.name, password_hash=security.hash_password(body.password))
    slug = re.sub(r"[^a-z0-9]+", "-", body.workspace_name.lower()).strip("-") or "workspace"
    ws = Workspace(name=body.workspace_name, slug=f"{slug}-{uuid.uuid4().hex[:6]}")
    db.add_all([user, ws])
    db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    audit(db, ws.id, user.id, "USER_CREATED", "user", user.id)
    audit(db, ws.id, user.id, "WORKSPACE_CREATED", "workspace", ws.id)
    db.commit()
    token = set_session(response, user.id)
    return {"user": user_out(user), **({"access_token": token} if body.issue_token else {})}


@router.post("/login", dependencies=[Depends(security.auth_rate_limit)])
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    security.check_account(email)
    user = db.scalar(select(User).where(User.email == email))
    ok = security.verify_password(body.password, user.password_hash if user else security.DUMMY_HASH)
    if not user or not ok:
        log.warning("login failed", extra={"account": account_key(email)[-12:]})  # hashed, never the email or password
        raise HTTPException(401, "Incorrect email or password")
    for m in db.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id).limit(20)):
        audit(db, m.workspace_id, user.id, "USER_LOGIN", "user", user.id)
    db.commit()
    token = set_session(response, user.id)
    return {"user": user_out(user), **({"access_token": token} if body.issue_token else {})}


@router.post("/logout")
def logout(response: Response):
    for name in (settings.session_cookie, settings.csrf_cookie):
        response.delete_cookie(name, path="/")
    return {"ok": True}  # tokens are stateless and short-lived; there is no server-side revocation list (documented limitation)


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Workspace, WorkspaceMember.role).join(WorkspaceMember).where(
        WorkspaceMember.user_id == user.id).order_by(Workspace.created_at)).all()
    return {**user_out(user), "workspaces": [{"id": str(w.id), "name": w.name, "role": r} for w, r in rows]}
