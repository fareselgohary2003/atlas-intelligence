import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, audit, current_user, membership
from app.core.db import get_db
from app.models import AuditLog, User, Workspace, WorkspaceMember
from app.schemas import MemberIn, RolePatch, WorkspaceIn

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", status_code=201)
def create_workspace(body: WorkspaceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-") or "workspace"
    ws = Workspace(name=body.name, slug=f"{slug}-{uuid.uuid4().hex[:6]}")
    db.add(ws)
    db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    audit(db, ws.id, user.id, "WORKSPACE_CREATED", "workspace", ws.id)
    db.commit()
    return {"id": str(ws.id), "name": ws.name, "role": "owner"}


@router.get("/{workspace_id}/members")
def members(workspace_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, workspace_id)
    rows = db.scalars(select(WorkspaceMember).where(WorkspaceMember.workspace_id == uuid.UUID(workspace_id))).all()
    return [{"user_id": str(m.user_id), "name": m.user.name, "email": m.user.email, "role": m.role} for m in rows]


@router.post("/{workspace_id}/members", status_code=201)
def add_member(workspace_id: str, body: MemberIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, workspace_id, ADMIN)
    target = db.scalar(select(User).where(User.email == body.email.lower()))
    if not target:
        raise HTTPException(404, "No account with that email. Ask them to sign up first.")
    wid = uuid.UUID(workspace_id)
    if db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == wid, WorkspaceMember.user_id == target.id)):
        raise HTTPException(409, "Already a member")
    if body.role == "owner":
        raise HTTPException(422, "Ownership transfer is not supported yet")
    db.add(WorkspaceMember(workspace_id=wid, user_id=target.id, role=body.role))
    audit(db, wid, user.id, "MEMBER_ADDED", "user", target.id, {"role": body.role})
    db.commit()
    return {"user_id": str(target.id), "role": body.role}


@router.get("/{workspace_id}/audit")
def audit_log(workspace_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), action: str | None = Query(None, max_length=60),
              research_id: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, workspace_id)
    wid = uuid.UUID(workspace_id)
    q = select(AuditLog).where(AuditLog.workspace_id == wid)
    if action:
        q = q.where(AuditLog.action == action)
    if research_id:
        q = q.where(AuditLog.entity_type == "research", AuditLog.entity_id == research_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditLog.created_at.desc(), AuditLog.id).limit(limit).offset(offset)).all()
    return {"total": total, "items": [{"id": str(a.id), "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
                                       "research_id": a.entity_id if a.entity_type == "research" else None, "actor": a.user.name if a.user else None,
                                       "meta": a.meta, "created_at": a.created_at.isoformat()} for a in rows]}


def _target(db, wid, user_id, caller):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(404, "Member not found")
    m = db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == wid, WorkspaceMember.user_id == uid))
    if not m:
        raise HTTPException(404, "Member not found")
    if m.role == "owner":
        raise HTTPException(403, "Owners cannot be modified or removed here")
    return m


@router.patch("/{workspace_id}/members/{user_id}")
def change_role(workspace_id: str, user_id: str, body: RolePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, workspace_id, ADMIN)
    wid = uuid.UUID(workspace_id)
    m = _target(db, wid, user_id, user)
    if body.role == "owner":
        raise HTTPException(422, "Ownership transfer is not supported yet")
    old, m.role = m.role, body.role
    audit(db, wid, user.id, "ROLE_CHANGED", "user", m.user_id, {"from": old, "to": body.role})
    db.commit()
    return {"user_id": str(m.user_id), "role": m.role}


@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
def remove_member(workspace_id: str, user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    membership(db, user, workspace_id, ADMIN)
    wid = uuid.UUID(workspace_id)
    m = _target(db, wid, user_id, user)
    audit(db, wid, user.id, "MEMBER_REMOVED", "user", m.user_id, {"role": m.role})
    db.delete(m)
    db.commit()
