# app/dependencies/service_delivery_point.py
from __future__ import annotations

"""
Dependencies that enforce a staff member's assignment to a Service Delivery
Point before they can act on that SDP's queue or workstation.

Policy
------
- Superusers and users carrying the TENANT_ADMIN / ADMIN role pass through
  unconditionally — supervisors and dispatchers must be able to oversee any
  workstation.
- All other authenticated active users must have a StaffProfile whose
  `service_delivery_point_id` matches the SDP they're trying to act on.

Usage
-----
    from typing import Annotated
    from fastapi import Depends, Path
    from app.dependencies.service_delivery_point import require_assigned_to_sdp

    @router.post("/queue/service-points/{service_delivery_point_id}/call-next")
    def call_next(
        service_delivery_point_id: int,
        _: Annotated[
            User,
            Depends(require_assigned_to_sdp(sdp_param_name="service_delivery_point_id")),
        ],
    ): ...

For ticket-scoped actions, use `require_assigned_to_ticket_sdp` which resolves
the SDP from the ticket itself.
"""

from typing import Annotated, Optional

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.dependencies.auth import get_current_active_user
from app.models.all_models import QueueTicket, ServiceDeliveryPoint, User


# Role codes that bypass SDP-assignment checks.
_PRIVILEGED_ROLE_CODES = {"TENANT_ADMIN", "ADMIN"}


def _user_is_privileged(user: User) -> bool:
    """
    Superusers, plus anyone holding TENANT_ADMIN / ADMIN, bypass the SDP-assignment check.
    """
    if user.is_superuser:
        return True
    for link in user.user_roles or []:
        role = getattr(link, "role", None)
        if role is None:
            continue
        code = (getattr(role, "code", None) or getattr(role, "name", None) or "").strip().upper()
        if code in _PRIVILEGED_ROLE_CODES:
            return True
    return False


def _resolve_user_sdp_ids(user: User) -> list[int]:
    """
    Pull the SDP IDs from the user's StaffProfile, if any.
    """
    profile = getattr(user, "staff_profile", None)
    if profile is None:
        return []
    
    # Using the property I added to StaffProfile
    return getattr(profile, "assigned_sdp_ids", [])


def require_assigned_to_sdp(
    *,
    sdp_param_name: str = "service_delivery_point_id",
):
    """
    Build a dependency that enforces caller assignment to the SDP referenced
    by the named path parameter.
    """

    def dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[Session, Depends(get_db)],
        sdp_id: int = Path(..., alias=sdp_param_name),
    ) -> User:
        if _user_is_privileged(current_user):
            return current_user

        sdp = (
            db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.id == sdp_id,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )
        if sdp is None:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": sdp_id},
            )

        user_sdp_ids = _resolve_user_sdp_ids(current_user)
        if not user_sdp_ids:
            raise ForbiddenError(
                message=(
                    "You are not assigned to any service delivery point. "
                    "Ask an administrator to assign you before acting on a queue."
                ),
                detail={"service_delivery_point_id": sdp_id},
            )

        if int(sdp_id) not in user_sdp_ids:
            raise ForbiddenError(
                message=(
                    "You are not assigned to this service delivery point. "
                    "Action denied."
                ),
                detail={
                    "user_assigned_sdp_ids": user_sdp_ids,
                    "target_service_delivery_point_id": int(sdp_id),
                },
            )

        return current_user

    return dependency


def require_assigned_to_ticket_sdp(
    *,
    ticket_param_name: str = "ticket_id",
):
    """
    Build a dependency that enforces caller assignment to the SDP that owns
    the queue ticket referenced by the named path parameter.

    This is the right guard for ticket-scoped actions like /tickets/{id}/call.
    """

    def dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[Session, Depends(get_db)],
        ticket_id: int = Path(..., alias=ticket_param_name),
    ) -> User:
        if _user_is_privileged(current_user):
            return current_user

        ticket = (
            db.query(QueueTicket)
            .filter(QueueTicket.id == ticket_id, QueueTicket.is_deleted.is_(False))
            .first()
        )
        if ticket is None:
            raise NotFoundError(
                message="Queue ticket not found.",
                detail={"ticket_id": ticket_id},
            )

        user_sdp_ids = _resolve_user_sdp_ids(current_user)
        if not user_sdp_ids:
            raise ForbiddenError(
                message=(
                    "You are not assigned to any service delivery point. "
                    "Ask an administrator to assign you before acting on a queue."
                ),
                detail={"ticket_id": ticket_id},
            )

        if int(ticket.service_delivery_point_id) not in user_sdp_ids:
            raise ForbiddenError(
                message="You are not assigned to the service delivery point managing this ticket.",
                detail={
                    "user_assigned_sdp_ids": user_sdp_ids,
                    "ticket_service_delivery_point_id": int(ticket.service_delivery_point_id),
                },
            )

        return current_user

    return dependency
