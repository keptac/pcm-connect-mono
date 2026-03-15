from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...services.alumni_transition import run_transition
from ...services.audit_log import log_action
from ..deps import require_role
from ...models import AuditLog
from ...schemas import AuditLogRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/alumni-transition")
def alumni_transition(db: Session = Depends(get_db), user=Depends(require_role(["super_admin"]))):
    updated = run_transition(db, user.id)
    log_action(db, user.id, "alumni_transition", "member", None, {"updated": updated})
    return {"updated": updated}


@router.get("/audit-logs", response_model=list[AuditLogRead])
def audit_logs(db: Session = Depends(get_db), user=Depends(require_role(["super_admin"]))):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    results = []
    import json
    for log in logs:
        results.append(AuditLogRead(
            id=log.id,
            actor_user_id=log.actor_user_id,
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            meta=json.loads(log.meta_json or "{}"),
            created_at=log.created_at,
        ))
    return results
