from app.models import AuditLog


def audit(db, workspace_id, user_id, action, entity_type=None, entity_id=None, meta=None):
    """Adds an audit row to the caller's session so it commits in the same transaction as the action."""
    db.add(AuditLog(workspace_id=workspace_id, user_id=user_id, action=action, entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id else None, meta=meta or {}))
