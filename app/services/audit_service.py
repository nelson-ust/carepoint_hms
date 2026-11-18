# app/services/audit_service.py
from __future__ import annotations

"""
Audit logging service.

Central place to (a) write audit entries and (b) query them, for both
tenant-scoped operations (``AuditLog`` in the tenant DB) and platform /
SaaS-admin operations (``SaaSAuditLog`` in the master DB).

Writes are best-effort and fully guarded: auditing must never break the
operation being audited. Each writer opens/uses the appropriate session and
swallows (logs) any failure.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.all_models import AuditLog, SaaSAuditLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Writers (best-effort)
# ---------------------------------------------------------------------------


def write_tenant_audit(
    db: Session,
    *,
    action: str,
    entity_name: str,
    actor_user_id: Optional[int] = None,
    actor_label: Optional[str] = None,
    actor_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    http_method: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = None,
    before_data: Optional[dict] = None,
    after_data: Optional[dict] = None,
    extra_metadata: Optional[dict] = None,
    commit: bool = True,
) -> None:
    """Write a tenant-scoped audit row. Never raises."""
    try:
        row = AuditLog(
            actor_user_id=actor_user_id,
            actor_label=actor_label,
            actor_type=actor_type,
            action=action,
            entity_name=entity_name,
            entity_id=entity_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            http_method=http_method,
            path=path,
            status_code=status_code,
            before_data=before_data,
            after_data=after_data,
            extra_metadata=extra_metadata,
        )
        db.add(row)
        if commit:
            db.commit()
    except Exception as exc:  # pragma: no cover - auditing must not break callers
        logger.warning("write_tenant_audit failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass


def write_saas_audit(
    master_db: Session,
    *,
    action: str,
    entity_name: str,
    actor_admin_id: Optional[int] = None,
    actor_label: Optional[str] = None,
    actor_type: Optional[str] = "SAAS_ADMIN",
    entity_id: Optional[int] = None,
    target_tenant_id: Optional[int] = None,
    target_tenant_code: Optional[str] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    http_method: Optional[str] = None,
    path: Optional[str] = None,
    status_code: Optional[int] = None,
    before_data: Optional[dict] = None,
    after_data: Optional[dict] = None,
    extra_metadata: Optional[dict] = None,
    commit: bool = True,
) -> None:
    """Write a platform/SaaS audit row to the master DB. Never raises."""
    try:
        row = SaaSAuditLog(
            actor_admin_id=actor_admin_id,
            actor_label=actor_label,
            actor_type=actor_type,
            action=action,
            entity_name=entity_name,
            entity_id=entity_id,
            target_tenant_id=target_tenant_id,
            target_tenant_code=target_tenant_code,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            http_method=http_method,
            path=path,
            status_code=status_code,
            before_data=before_data,
            after_data=after_data,
            extra_metadata=extra_metadata,
        )
        master_db.add(row)
        if commit:
            master_db.commit()
    except Exception as exc:  # pragma: no cover
        logger.warning("write_saas_audit failed: %s", exc)
        try:
            master_db.rollback()
        except Exception:
            pass


def write_saas_audit_autocommit(**kwargs: Any) -> None:
    """Open a short master session and write a SaaS audit row. Never raises."""
    try:
        from app.core.database import get_master_db_context

        with get_master_db_context() as master_db:
            write_saas_audit(master_db, **kwargs)
    except Exception as exc:  # pragma: no cover
        logger.warning("write_saas_audit_autocommit failed: %s", exc)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def _apply_common_filters(query, model, *, action, entity_name, q, date_from, date_to):
    if action:
        query = query.filter(model.action == action.strip().upper())
    if entity_name:
        query = query.filter(model.entity_name == entity_name.strip().upper())
    if date_from:
        query = query.filter(model.date_created >= date_from)
    if date_to:
        query = query.filter(model.date_created <= date_to)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                model.entity_name.ilike(like),
                model.action.ilike(like),
                model.actor_label.ilike(like),
                model.ip_address.ilike(like),
                model.path.ilike(like),
            )
        )
    return query


def list_tenant_audit_logs(
    db: Session,
    *,
    action: Optional[str] = None,
    entity_name: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    q: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    query = db.query(AuditLog).filter(AuditLog.is_deleted.is_(False))
    query = _apply_common_filters(
        query, AuditLog, action=action, entity_name=entity_name, q=q,
        date_from=date_from, date_to=date_to,
    )
    if actor_user_id is not None:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    total = query.count()
    rows = (
        query.order_by(AuditLog.date_created.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 200))
        .all()
    )
    return rows, total


def list_saas_audit_logs(
    master_db: Session,
    *,
    action: Optional[str] = None,
    entity_name: Optional[str] = None,
    actor_admin_id: Optional[int] = None,
    target_tenant_code: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SaaSAuditLog], int]:
    query = master_db.query(SaaSAuditLog).filter(SaaSAuditLog.is_deleted.is_(False))
    query = _apply_common_filters(
        query, SaaSAuditLog, action=action, entity_name=entity_name, q=q,
        date_from=date_from, date_to=date_to,
    )
    if actor_admin_id is not None:
        query = query.filter(SaaSAuditLog.actor_admin_id == actor_admin_id)
    if target_tenant_code:
        query = query.filter(SaaSAuditLog.target_tenant_code == target_tenant_code.strip().lower())
    total = query.count()
    rows = (
        query.order_by(SaaSAuditLog.date_created.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 200))
        .all()
    )
    return rows, total
