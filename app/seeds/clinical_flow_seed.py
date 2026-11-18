# app/seeds/clinical_flow_seed.py
from __future__ import annotations

"""
Seed a standard outpatient clinical pathway for a tenant.

Creates a reusable ``VisitFlowTemplate`` ("Standard Outpatient Pathway") whose
steps follow typical hospital practice:

    Registration → HMO desk* → Payment → Triage/Vitals → Consultation →
    Laboratory* → Radiology* → Pharmacy* → Checkout

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
    # Canonical Nigerian tertiary-hospital outpatient pathway:
    #   Records → HMO desk* → pay card/consult fee → Vitals & Triage →
    #   Consultation → Lab* → Radiology* → Pharmacy* → Checkout.
    # Steps marked * (is_required=False) are skipped when not applicable:
    # the HMO desk is for insured patients, and lab/radiology/pharmacy only
    # apply when the consultation produced matching orders.
    (ServicePointType.REGISTRATION, True),          # Health Records — folder/number
    (ServicePointType.INSURANCE_CONFIRMATION, False),  # HMO desk — insured only
    (ServicePointType.CASHIER, True),               # card / consultation fee
    (ServicePointType.TRIAGE, True),                # vitals & triage
    (ServicePointType.CLINIC, True),                # consultation (GOPD)
    (ServicePointType.LABORATORY, False),
    (ServicePointType.RADIOLOGY, False),
    (ServicePointType.PHARMACY, False),
    (ServicePointType.CASHIER, True),               # checkout / final billing
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

    # Flag this as the tenant default only if no other template already is.
    has_default = (
        db.execute(
            select(VisitFlowTemplate).filter(
                VisitFlowTemplate.is_default.is_(True),
                VisitFlowTemplate.is_deleted.is_(False),
            )
        )
        .scalars()
        .first()
        is not None
    )

    template = VisitFlowTemplate(
        name=STANDARD_TEMPLATE_NAME,
        code=STANDARD_TEMPLATE_CODE,
        description=(
            "Default outpatient pathway: Registration → HMO desk → "
            "Payment (card/consult fee) → Triage → Consultation → Laboratory "
            "→ Radiology → Pharmacy → Checkout."
        ),
        is_default=not has_default,
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


# The previous auto-seeded sequence. Used to tell an un-customized (pristine)
# standard template apart from one an admin has edited, so a retroactive
# re-alignment only rewrites templates that were never touched.
LEGACY_PATHWAY_TYPES: list[ServicePointType] = [
    ServicePointType.REGISTRATION,
    ServicePointType.TRIAGE,
    ServicePointType.CLINIC,
    ServicePointType.LABORATORY,
    ServicePointType.RADIOLOGY,
    ServicePointType.PHARMACY,
    ServicePointType.CASHIER,
]


def _resolve_pathway(
    db: Session, pathway: list[tuple[ServicePointType, bool]]
) -> tuple[list[tuple[ServiceDeliveryPoint, bool]], list[str]]:
    """Map a (type, required) pathway onto concrete SDPs, dropping missing types."""
    resolved: list[tuple[ServiceDeliveryPoint, bool]] = []
    skipped: list[str] = []
    for sp_type, required in pathway:
        sdp = _first_sdp_of_type(db, sp_type)
        if sdp is None:
            skipped.append(sp_type.value)
            continue
        resolved.append((sdp, required))
    return resolved, skipped


def reconcile_standard_visit_flow(db: Session, *, force: bool = False) -> dict:
    """
    Bring an existing tenant's Standard Outpatient Pathway into line with the
    current canonical sequence (see ``STANDARD_PATHWAY``).

    - No template yet  → delegate to :func:`seed_standard_visit_flow` (create).
    - Already aligned  → no-op.
    - Pristine legacy  → rewrite its steps to the new sequence.
    - Customized       → left untouched unless ``force=True`` (so an admin's
      hand-edited pathway is never silently clobbered).

    Idempotent and safe to re-run. Commits only when it changes something.
    """
    template = (
        db.execute(
            select(VisitFlowTemplate).filter(
                VisitFlowTemplate.code == STANDARD_TEMPLATE_CODE,
                VisitFlowTemplate.is_deleted.is_(False),
            )
        )
        .scalars()
        .first()
    )
    if template is None:
        return seed_standard_visit_flow(db)

    desired, skipped_types = _resolve_pathway(db, STANDARD_PATHWAY)
    desired_types = [sdp.service_point_type for sdp, _ in desired]

    current_steps = sorted(
        [st for st in template.steps if not getattr(st, "is_deleted", False)],
        key=lambda st: st.step_order,
    )
    current_types: list[Optional[ServicePointType]] = []
    for st in current_steps:
        sdp = (
            db.execute(
                select(ServiceDeliveryPoint).filter(
                    ServiceDeliveryPoint.id == st.service_delivery_point_id
                )
            )
            .scalars()
            .first()
        )
        current_types.append(sdp.service_point_type if sdp else None)

    if current_types == desired_types:
        return {
            "updated": False,
            "template_id": template.id,
            "template_code": template.code,
            "message": "Standard pathway is already aligned.",
            "steps": [],
            "skipped_types": skipped_types,
        }

    legacy_resolved, _ = _resolve_pathway(
        db, [(t, True) for t in LEGACY_PATHWAY_TYPES]
    )
    legacy_types = [sdp.service_point_type for sdp, _ in legacy_resolved]
    is_pristine_legacy = current_types == legacy_types

    if not is_pristine_legacy and not force:
        return {
            "updated": False,
            "customized": True,
            "template_id": template.id,
            "template_code": template.code,
            "message": (
                "The standard pathway has been customized for this tenant and "
                "was left unchanged. Re-run with force=true to overwrite it "
                "with the canonical sequence."
            ),
            "steps": [],
            "skipped_types": skipped_types,
        }

    # Rewrite the steps. Template steps are pure config (no runtime rows point
    # at them), and the (template_id, step_order) unique constraint counts
    # soft-deleted rows, so we hard-delete the old steps before recreating.
    for st in list(template.steps):
        db.delete(st)
    db.flush()

    steps_summary: list[dict] = []
    for order, (sdp, required) in enumerate(desired, start=1):
        db.add(
            VisitFlowTemplateStep(
                template_id=template.id,
                service_delivery_point_id=sdp.id,
                step_order=order,
                is_required=required,
                notes=None,
            )
        )
        steps_summary.append(
            {
                "step_order": order,
                "service_delivery_point_id": sdp.id,
                "service_delivery_point": sdp.name,
                "type": sdp.service_point_type.value,
                "is_required": required,
            }
        )

    template.description = (
        "Default outpatient pathway: Registration → HMO desk → Payment "
        "(card/consult fee) → Triage → Consultation → Laboratory → Radiology "
        "→ Pharmacy → Checkout."
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    logger.info(
        "Reconciled standard visit flow template %s to %d steps.",
        template.code,
        len(steps_summary),
    )
    return {
        "updated": True,
        "forced": bool(force and not is_pristine_legacy),
        "template_id": template.id,
        "template_code": template.code,
        "message": f"Standard pathway re-aligned to {len(steps_summary)} stages.",
        "steps": steps_summary,
        "skipped_types": skipped_types,
    }
