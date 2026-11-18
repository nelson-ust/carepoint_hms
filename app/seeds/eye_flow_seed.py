# app/seeds/eye_flow_seed.py
from __future__ import annotations

"""
Seed a dedicated Eye-Clinic clinical pathway for a tenant.

Creates a reusable ``VisitFlowTemplate`` ("Eye Clinic Pathway") whose steps
follow typical eye-care practice, capturing every service delivery point a
patient passes through — whether the clinic runs standalone or as part of an
integrated hospital:

    Registration -> (Insurance Desk) -> Vision Screening/Pre-test ->
    (Optometry/Refraction) -> Ophthalmology Consultation ->
    (Ophthalmic Imaging) -> (Optical Dispensing) -> (Pharmacy) -> Billing

Steps in parentheses are optional (``is_required = False``). Each stage is
resolved to a concrete service delivery point: first by a preferred code
(the eye-specific points seeded in ``seed_data``), then by the first point of
a fallback ``ServicePointType``. Stages that resolve to nothing (an
eye-specific point a tenant has not configured, with no shared fallback) are
omitted so the template only references real points. Idempotent: re-running
returns the existing template.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ServicePointType
from app.models.all_models import (
    Department,
    ServiceDeliveryPoint,
    VisitFlowTemplate,
    VisitFlowTemplateStep,
)

logger = logging.getLogger(__name__)

EYE_TEMPLATE_CODE = "EYE_CLINIC_PATHWAY"
EYE_TEMPLATE_NAME = "Eye Clinic Pathway"

# Ordered stages. Each: (label, preferred SDP codes, fallback type, required).
# When the fallback type is None and no preferred code exists, the stage is a
# purely eye-specific point and is skipped if the tenant has not configured it.
EYE_PATHWAY: list[tuple[str, list[str], Optional[ServicePointType], bool]] = [
    ("Registration", ["SDP-EYE-REG", "SDP-REG"], ServicePointType.REGISTRATION, True),
    ("Insurance / HMO Desk", ["SDP-INS"], ServicePointType.INSURANCE_CONFIRMATION, False),
    ("Vision Screening & Pre-Test", ["SDP-EYE-SCREEN"], ServicePointType.TRIAGE, True),
    ("Optometry / Refraction", ["SDP-EYE-REFRACT"], None, False),
    ("Ophthalmology Consultation", ["SDP-EYE-CONSULT"], ServicePointType.CLINIC, True),
    ("Ophthalmic Imaging & Diagnostics", ["SDP-EYE-DX"], None, False),
    ("Optical Dispensing", ["SDP-EYE-OPTICAL"], None, False),
    ("Pharmacy", ["SDP-EYE-PHARM", "SDP-PHARM"], ServicePointType.PHARMACY, False),
    ("Billing & Payment", ["SDP-CASH"], ServicePointType.CASHIER, True),
]


# The eye-specific service delivery points the pathway runs on. These are the
# single source of truth: seeded at provisioning (via seed_eye_visit_flow in
# the tenant seed pass) and ensured again on-demand when the pathway is
# activated for an already-provisioned tenant. Shared points (registration,
# insurance, pharmacy, billing) are reused from the tenant's existing points.
#   (name, code, type, preferred department code, queue prefix, location)
EYE_SERVICE_POINTS: list[tuple[str, str, ServicePointType, str, str, str]] = [
    ("Vision Screening & Pre-Test", "SDP-EYE-SCREEN", ServicePointType.TRIAGE, "NURSING", "VST", "Visual acuity, autorefraction and tonometry"),
    ("Optometry / Refraction Room", "SDP-EYE-REFRACT", ServicePointType.CLINIC, "OPD", "REF", "Subjective refraction and optometry"),
    ("Ophthalmology Consultation", "SDP-EYE-CONSULT", ServicePointType.CLINIC, "OPD", "OPH", "Ophthalmologist consulting room"),
    ("Ophthalmic Imaging & Diagnostics", "SDP-EYE-DX", ServicePointType.RADIOLOGY, "OPD", "OCT", "OCT, visual fields and fundus photography"),
    ("Optical Dispensing", "SDP-EYE-OPTICAL", ServicePointType.OTHER, "OPD", "OPT", "Frames, lenses and optical dispensing"),
]


def ensure_eye_service_points(db: Session) -> list[str]:
    """Create the eye-specific service delivery points if missing (idempotent,
    keyed by code). Resolves each point's department by code, falling back to
    any available department. Returns the codes created this call. Caller
    commits; this only flushes."""
    depts = {d.code: d for d in db.query(Department).filter(Department.is_deleted.is_(False)).all()}
    fallback = next(iter(depts.values()), None)
    created: list[str] = []
    for name, code, sp_type, dept_code, prefix, loc in EYE_SERVICE_POINTS:
        existing = _sdp_by_code(db, code)
        if existing is not None:
            continue
        dept = depts.get(dept_code) or fallback
        if dept is None:
            continue  # no departments configured — cannot create a point
        db.add(
            ServiceDeliveryPoint(
                name=name,
                code=code,
                service_point_type=sp_type,
                department_id=dept.id,
                location_description=loc,
                queue_prefix=prefix,
                supports_appointments=sp_type == ServicePointType.CLINIC,
                supports_walk_in=True,
            )
        )
        created.append(code)
    if created:
        db.flush()
    return created


def _sdp_by_code(db: Session, code: str) -> Optional[ServiceDeliveryPoint]:
    stmt = select(ServiceDeliveryPoint).filter(
        ServiceDeliveryPoint.code == code,
        ServiceDeliveryPoint.is_deleted.is_(False),
    )
    return db.execute(stmt).scalars().first()


def _first_sdp_of_type(db: Session, sp_type: ServicePointType) -> Optional[ServiceDeliveryPoint]:
    stmt = (
        select(ServiceDeliveryPoint)
        .filter(
            ServiceDeliveryPoint.service_point_type == sp_type,
            ServiceDeliveryPoint.is_deleted.is_(False),
        )
        .order_by(ServiceDeliveryPoint.id.asc())
    )
    return db.execute(stmt).scalars().first()


def _resolve_stage(
    db: Session, codes: list[str], fallback: Optional[ServicePointType]
) -> Optional[ServiceDeliveryPoint]:
    for code in codes:
        sdp = _sdp_by_code(db, code)
        if sdp is not None:
            return sdp
    if fallback is not None:
        return _first_sdp_of_type(db, fallback)
    return None


def seed_eye_visit_flow(db: Session) -> dict:
    """Ensure the Eye Clinic pathway template exists for this tenant."""
    existing = (
        db.execute(
            select(VisitFlowTemplate).filter(
                VisitFlowTemplate.code == EYE_TEMPLATE_CODE,
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
            "message": "Eye Clinic pathway already exists.",
            "steps": [],
            "skipped_stages": [],
        }

    # Ensure the eye-specific service points exist (covers already-provisioned
    # tenants activating the pathway on demand), then build the template.
    ensure_eye_service_points(db)

    resolved: list[tuple[ServiceDeliveryPoint, bool]] = []
    skipped_stages: list[str] = []
    seen_ids: set[int] = set()
    for label, codes, fallback, required in EYE_PATHWAY:
        sdp = _resolve_stage(db, codes, fallback)
        if sdp is None or sdp.id in seen_ids:
            if sdp is None:
                skipped_stages.append(label)
            continue
        seen_ids.add(sdp.id)
        resolved.append((sdp, required))

    if not resolved:
        return {
            "created": False,
            "template_id": None,
            "template_code": EYE_TEMPLATE_CODE,
            "message": (
                "No service delivery points are configured yet, so the Eye "
                "Clinic pathway could not be seeded. Create service points first."
            ),
            "steps": [],
            "skipped_stages": skipped_stages,
        }

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
        name=EYE_TEMPLATE_NAME,
        code=EYE_TEMPLATE_CODE,
        description=(
            "Dedicated eye-care pathway: Registration -> Insurance -> Vision "
            "Screening -> Optometry/Refraction -> Ophthalmology Consultation -> "
            "Imaging -> Optical Dispensing -> Pharmacy -> Billing."
        ),
        is_default=not has_default,
    )
    db.add(template)
    db.flush()

    steps_summary: list[dict] = []
    for order, (sdp, required) in enumerate(resolved, start=1):
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
                "code": sdp.code,
                "type": sdp.service_point_type.value,
                "is_required": required,
            }
        )

    db.commit()
    db.refresh(template)
    logger.info(
        "Seeded Eye Clinic visit flow template %s with %d steps.",
        template.code,
        len(steps_summary),
    )
    return {
        "created": True,
        "template_id": template.id,
        "template_code": template.code,
        "message": f"Eye Clinic pathway created with {len(steps_summary)} stages.",
        "steps": steps_summary,
        "skipped_stages": skipped_stages,
    }


def describe_eye_flow(db: Session) -> dict:
    """Describe the Eye Clinic pathway for the dedicated flow view.

    The reusable :class:`VisitFlowTemplate` (code ``EYE_CLINIC_PATHWAY``) is the
    single source of truth: when it has been seeded, the stages are read
    straight from its ordered steps, so this reflects any edits made through
    the standard Visit Flow builder. When it has not been seeded yet, the
    proposed stages are returned as a preview (each resolved to a concrete
    service delivery point where one exists) so the page can offer to activate
    the default pathway. Read-only.
    """
    template = (
        db.execute(
            select(VisitFlowTemplate).filter(
                VisitFlowTemplate.code == EYE_TEMPLATE_CODE,
                VisitFlowTemplate.is_deleted.is_(False),
            )
        )
        .scalars()
        .first()
    )

    if template is not None:
        # Source of truth: the actual, editable template steps.
        steps = sorted(
            [s for s in template.steps if not getattr(s, "is_deleted", False)],
            key=lambda s: s.step_order,
        )
        stages: list[dict] = []
        for order, step in enumerate(steps, start=1):
            sdp = step.service_delivery_point
            code = sdp.code if sdp else None
            stages.append(
                {
                    "order": order,
                    "label": sdp.name if sdp else f"Step {order}",
                    "required": bool(step.is_required),
                    "eye_specific": bool(code and code.upper().startswith("SDP-EYE")),
                    "service_delivery_point_id": step.service_delivery_point_id,
                    "service_delivery_point": sdp.name if sdp else None,
                    "code": code,
                    "type": sdp.service_point_type.value if sdp else None,
                    "configured": True,
                }
            )
        return {
            "template_code": EYE_TEMPLATE_CODE,
            "template_name": template.name,
            "template_id": template.id,
            "seeded": True,
            "is_default": bool(template.is_default),
            "from_template": True,
            "stages": stages,
        }

    # Not seeded yet — preview the proposed default pathway.
    stages = []
    for order, (label, codes, fallback, required) in enumerate(EYE_PATHWAY, start=1):
        sdp = _resolve_stage(db, codes, fallback)
        stages.append(
            {
                "order": order,
                "label": label,
                "required": required,
                "eye_specific": fallback is None,
                "service_delivery_point_id": sdp.id if sdp else None,
                "service_delivery_point": sdp.name if sdp else None,
                "code": sdp.code if sdp else None,
                "type": sdp.service_point_type.value if sdp else None,
                "configured": sdp is not None,
            }
        )
    return {
        "template_code": EYE_TEMPLATE_CODE,
        "template_name": EYE_TEMPLATE_NAME,
        "template_id": None,
        "seeded": False,
        "is_default": False,
        "from_template": False,
        "stages": stages,
    }
