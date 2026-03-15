import json
from sqlalchemy.orm import Session
from ..models import AuditLog


def log_action(db: Session, actor_user_id: int | None, action: str, entity: str, entity_id: str | None, meta: dict | None = None) -> None:
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        meta_json=json.dumps(meta or {}),
    )
    db.add(log)
    db.commit()
