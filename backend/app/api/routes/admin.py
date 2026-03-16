from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...services.alumni_transition import run_transition
from ...services.audit_log import log_action
from ..deps import require_role
from ...models import AuditLog, User
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
    actor_ids = sorted({log.actor_user_id for log in logs if log.actor_user_id})
    actor_lookup = {
        actor.id: actor
        for actor in (
            db.query(User)
            .filter(User.id.in_(actor_ids))
            .all()
            if actor_ids
            else []
        )
    }
    results = []
    import json
    for log in logs:
        actor = actor_lookup.get(log.actor_user_id)
        results.append(AuditLogRead(
            id=log.id,
            actor_user_id=log.actor_user_id,
            actor_name=(actor.name or actor.email) if actor else None,
            actor_number=(actor.member.member_id if actor and actor.member and actor.member.member_id else str(actor.id) if actor else None),
            action=log.action,
            entity=log.entity,
            entity_id=log.entity_id,
            meta=json.loads(log.meta_json or "{}"),
            created_at=log.created_at,
        ))
    return results
