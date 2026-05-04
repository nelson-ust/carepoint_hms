# app/api/v1/endpoints/saas_notification_routes.py
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin
from app.models.all_models import SaaSNotification

router = APIRouter(prefix="/saas/notifications", tags=["SaaS - Notifications"])

@router.get(
    "",
    response_model=dict,
    summary="List in-app notifications for the current SaaS Admin",
)
def list_saas_notifications(
    admin: CurrentSaaSAdmin,
    db: Annotated[Session, Depends(get_master_db)],
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
):
    query = db.query(SaaSNotification).filter(SaaSNotification.saas_admin_id == admin.id)
    
    if unread_only:
        query = query.filter(SaaSNotification.is_read == False)
        
    total = query.count()
    notifications = query.order_by(SaaSNotification.id.desc()).offset(skip).limit(limit).all()
    
    results = []
    for n in notifications:
        results.append({
            "id": n.id,
            "subject": n.subject,
            "body": n.body,
            "status": n.status.value if n.status else None,
            "is_read": n.is_read,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "date_created": n.date_created.isoformat() if n.date_created else None
        })

    return {
        "success": True,
        "total": total,
        "data": results,
    }

@router.patch(
    "/{notification_id}/read",
    response_model=dict,
    summary="Mark a SaaS notification as read",
)
def mark_notification_read(
    notification_id: int,
    admin: CurrentSaaSAdmin,
    db: Annotated[Session, Depends(get_master_db)],
):
    notification = db.query(SaaSNotification).filter(
        SaaSNotification.id == notification_id,
        SaaSNotification.saas_admin_id == admin.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Notification not found."
        )
        
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    
    return {
        "success": True,
        "message": "Notification marked as read."
    }
