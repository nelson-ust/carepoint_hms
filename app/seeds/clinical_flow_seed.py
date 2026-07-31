# app/seeds/clinical_flow_seed.py
from __future__ import annotations

"""
Seed a standard outpatient clinical pathway for a tenant.

Creates a reusable ``VisitFlowTemplate`` ("Standard Outpatient Pathway") whose
steps follow typical hospital practice:

    Registration → Triage/Vitals → Consultation → Laboratory* → Radiology*
    → Pharmacy* → Billing

Steps marked ``*`` are optional (``is_required = False``) — a patient can be
skipped past them when a consultation produced no matching orders. Each step is
mapped to the tenant's first service delivery point of the matching type; types
with no configured service point are omitted so the template only references
real points. The operation is idempotent: re-running returns the existing
template rather than creating a duplicate.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ServicePointType
from app.models.all_models import (
    ServiceDeliveryPoint,
    VisitFlowTemplate,
    VisitFlowTemplateStep,
)

logger = logging.getLogger(__name__)

STANDARD_TEMPLATE_CODE = "STANDARD_OPD"
STANDARD_TEMPLATE_NAME = "Standard Outpatient Pathway"

# Ordered (service-point type, required?) pairs describing the standard flow.
STANDARD_PATHWAY: list[tuple[ServicePointType, bool]] = [
    (ServicePointType.REGISTRATION, True),
    (ServicePointType.TRIAGE, True),
    (ServicePointType.CLINIC, True),
    (ServicePointType.LABORATORY, False),
    (ServicePointType.RADIOLOGY, False),
    (ServicePointType.PHARMACY, False),
    (ServicePointType.CASHIER, True),
]


def _first_sdp_of_type(
    db: Session, sp_type: ServicePointType
) -> Optional[ServiceDeliveryPoint]:
    stmt = (
        select(ServiceDeliveryPoint)
        .filter(
            ServiceDeliveryPoint.service_point_type == sp_type,
            ServiceDeliveryPoint.is_deleted.is_(False),
        )
        .order_by(ServiceDeliveryPoint.id.asc())
    )
    return db.execute(stmt).scalars().first()


def seed_standard_visit_flow(db: Session) -> dict:
    """
    Ensure the standard outpatient pathway template exists for this tenant.

    Returns a summary dict describing what happened. Commits on creation.
    """
    existing = (
        db.execute(
            select(VisitFlowTemplate).filter(
                VisitFlowTemplate.code == STANDARD_TEMPLATE_CODE,
                VisitFlowTemplate.is_deleted.is_(False),
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        return {
            "created": False,
            "template_id": existing.id,
            "template_code": existing.code,
            "message": "Standard pathway already exists.",
            "steps": [],
            "skipped_types": [],
        }

    # Resolve a concrete service point for each stage; drop stages with none.
    resolved: list[tuple[ServiceDeliveryPoint, bool]] = []
    skipped_types: list[str] = []
    for sp_type, required in STANDARD_PATHWAY:
        sdp = _first_sdp_of_type(db, sp_type)
        if sdp is None:
            skipped_types.append(sp_type.value)
            continue
        resolved.append((sdp, required))

    if not resolved:
        return {
            "created": False,
            "template_id": None,
            "template_code": STANDARD_TEMPLATE_CODE,
            "message": (
                "No service delivery points are configured yet, so the standard "
                "pathway could not be seeded. Create service points first."
            ),
            "steps": [],
            "skipped_types": skipped_types,
        }

    template = VisitFlowTemplate(
        name=STANDARD_TEMPLATE_NAME,
        code=STANDARD_TEMPLATE_CODE,
        description=(
            "Default sequential outpatient pathway: Registration → Triage → "
            "Consultation → Laboratory → Radiology → Pharmacy → Billing."
        ),
    )
    db.add(template)
    db.flush()  # assign template.id

    steps_summary: list[dict] = []
    for order, (sdp, required) in enumerate(resolved, start=1):
        step = VisitFlowTemplateStep(
            template_id=template.id,
            service_delivery_point_id=sdp.id,
            step_order=order,
            is_required=required,
            notes=None,
        )
        db.add(step)
        steps_summary.append(
            {
                "step_order": order,
                "service_delivery_point_id": sdp.id,
                "service_delivery_point": sdp.name,
                "type": sdp.service_point_type.value,
                "is_required": required,
            }
        )

    db.commit()
    db.refresh(template)
    logger.info(
        "Seeded standard visit flow template %s with %d steps.",
        template.code,
        len(steps_summary),
    )
    return {
        "created": True,
        "template_id": template.id,
        "template_code": template.code,
        "message": f"Standard pathway created with {len(steps_summary)} stages.",
        "steps": steps_summary,
        "skipped_types": skipped_types,
    }
