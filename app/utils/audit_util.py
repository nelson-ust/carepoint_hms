from typing import Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone, date
import json

from app.models.all_models import AuditLog
from app.core.multitenancy import get_current_tenant_id

def log_entity_change(
    db: Session,
    actor_user_id: Optional[int],
    action: str,
    entity_name: str,
    entity_id: Any,
    before_data: Optional[dict] = None,
    after_data: Optional[dict] = None,
    extra_metadata: Optional[dict] = None,
    request_id: Optional[str] = None
) -> AuditLog:
    """
    Record a detailed audit log entry for an entity change.
    
    Args:
        db: Tenant database session.
        actor_user_id: ID of the user performing the action.
        action: The action performed (e.g., 'CREATE', 'UPDATE', 'DELETE').
        entity_name: Name of the entity (e.g., 'PATIENT', 'INVOICE').
        entity_id: ID of the entity being modified.
        before_data: Dictionary of entity state BEFORE the change.
        after_data: Dictionary of entity state AFTER the change.
        extra_metadata: Additional context.
        request_id: Optional tracking ID.
    """
    audit_log = AuditLog(
        actor_user_id=actor_user_id,
        action=action.upper(),
        entity_name=entity_name.upper(),
        entity_id=str(entity_id) if entity_id else None,
        request_id=request_id,
        before_data=before_data,
        after_data=after_data,
        extra_metadata=extra_metadata or {},
    )
    db.add(audit_log)
    db.flush() # Ensure it's part of the transaction
    return audit_log

def build_audit_payload(obj: Any, exclude: Optional[set] = None) -> dict:
    """
    Helper to convert a SQLAlchemy model instance to a dict for auditing.
    """
    if not obj:
        return {}
    
    exclude = exclude or {"password_hash", "created_at", "updated_at", "tenant_id", "is_deleted"}
    
    payload = {}
    for column in obj.__table__.columns:
        if column.name in exclude:
            continue
        value = getattr(obj, column.name)
        if isinstance(value, (datetime, date)):
            payload[column.name] = value.isoformat()
        else:
            payload[column.name] = value
            
    return payload





