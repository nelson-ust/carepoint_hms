"""
app.services.tenant_module_service

Manage per-tenant module access overrides on top of subscription-plan
defaults.

Effective access for module ``M`` for tenant ``T``:

    plan.has_<M>  AND  (TenantModuleAccess(T, M).is_enabled if exists else True)

Modules are addressed by short codes that match the ``has_<code>`` flag on
:class:`SubscriptionPlan` (``clinical``, ``laboratory``, ``pharmacy``, etc.).
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.core.enums import SubscriptionStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    SubscriptionPlan,
    Tenant,
    TenantModuleAccess,
    TenantSubscription,
)


# ---------------------------------------------------------------------------
# Module catalog. Adding a module here makes it available to every tenant.
# ---------------------------------------------------------------------------
SUPPORTED_MODULES: tuple[tuple[str, str], ...] = (
    ("clinical", "Clinical / Consultations"),
    ("inpatient", "Inpatient & Admissions"),
    ("laboratory", "Laboratory"),
    ("pharmacy", "Pharmacy"),
    ("inventory", "Inventory & Stock"),
    ("billing", "Billing & Invoicing"),
    ("reporting", "Reports & Analytics"),
    ("appointments", "Appointments"),
    ("patient_portal", "Patient Portal"),
    ("insurance", "Insurance Claims"),
    ("radiology", "Radiology"),
    ("surgical", "Surgical / Theatre"),
    ("hr", "Human Resources"),
    ("dietary", "Dietary & Meal Management"),
    ("ambulance", "Ambulance & Fleet"),
    ("compliance", "Compliance & Audit"),
)


SUPPORTED_MODULE_CODES: set[str] = {code for code, _ in SUPPORTED_MODULES}


def _normalize(module_code: str) -> str:
    code = (module_code or "").strip().lower()
    if not code:
        raise BadRequestError(message="Module code is required.")
    if code not in SUPPORTED_MODULE_CODES:
        raise BadRequestError(
            message=f"Unsupported module '{code}'.",
            detail={"supported_modules": sorted(SUPPORTED_MODULE_CODES)},
        )
    return code


class TenantModuleService:
    """
    Service for managing per-tenant module access.

    All methods operate on the **master** database.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_active_plan(self, tenant_id: int) -> Optional[SubscriptionPlan]:
        sub = (
            self.db.query(TenantSubscription)
            .join(SubscriptionPlan)
            .filter(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.status.in_(
                    [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
                ),
                TenantSubscription.is_active.is_(True),
            )
            .first()
        )
        return sub.plan if sub else None

    def list_modules_for_tenant(self, tenant_id: int) -> list[dict]:
        """
        Return a complete view of module access for a tenant.

        Each entry contains ``code``, ``label``, ``plan_default``,
        ``override``, and ``effective`` (boolean).
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")

        plan = self.get_active_plan(tenant_id)
        overrides = {
            override.module_code: override
            for override in self.db.query(TenantModuleAccess)
            .filter(
                TenantModuleAccess.tenant_id == tenant_id,
                TenantModuleAccess.is_deleted.is_(False),
            )
            .all()
        }

        result: list[dict] = []
        for code, label in SUPPORTED_MODULES:
            plan_default = bool(getattr(plan, f"has_{code}", False)) if plan else False
            override = overrides.get(code)
            override_value = override.is_enabled if override is not None else None
            effective = plan_default and (override_value if override_value is not None else True)

            result.append(
                {
                    "code": code,
                    "label": label,
                    "plan_default": plan_default,
                    "override": override_value,
                    "effective": effective,
                    "notes": override.notes if override else None,
                }
            )
        return result

    def is_module_enabled(self, tenant_id: int, module_code: str) -> bool:
        """
        Compute the effective access for a single module.
        """
        code = _normalize(module_code)
        plan = self.get_active_plan(tenant_id)
        if plan is None:
            return False
        if not getattr(plan, f"has_{code}", False):
            return False

        override = (
            self.db.query(TenantModuleAccess)
            .filter(
                TenantModuleAccess.tenant_id == tenant_id,
                TenantModuleAccess.module_code == code,
                TenantModuleAccess.is_deleted.is_(False),
            )
            .first()
        )
        if override is None:
            return True
        return bool(override.is_enabled)

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def set_module(
        self,
        tenant_id: int,
        module_code: str,
        *,
        is_enabled: bool,
        notes: Optional[str] = None,
    ) -> TenantModuleAccess:
        """
        Create or update a per-tenant module override.
        """
        code = _normalize(module_code)
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")

        # Refuse to enable a module the active plan does not include.
        if is_enabled:
            plan = self.get_active_plan(tenant_id)
            if plan is None or not getattr(plan, f"has_{code}", False):
                raise BadRequestError(
                    message=(
                        f"Module '{code}' is not part of the tenant's active "
                        f"subscription plan and cannot be enabled."
                    ),
                    detail={"module": code},
                )

        record = (
            self.db.query(TenantModuleAccess)
            .filter(
                TenantModuleAccess.tenant_id == tenant_id,
                TenantModuleAccess.module_code == code,
            )
            .first()
        )
        if record is None:
            record = TenantModuleAccess(
                tenant_id=tenant_id,
                module_code=code,
                is_enabled=is_enabled,
                notes=notes,
            )
            self.db.add(record)
        else:
            record.is_enabled = is_enabled
            record.is_deleted = False
            if notes is not None:
                record.notes = notes

        self.db.commit()
        return record

    def bulk_set_modules(
        self,
        tenant_id: int,
        modules: Iterable[dict],
    ) -> list[TenantModuleAccess]:
        """
        Apply a batch of module overrides::

            [{"module_code": "pharmacy", "is_enabled": False, "notes": "..."}]
        """
        out: list[TenantModuleAccess] = []
        for entry in modules or []:
            out.append(
                self.set_module(
                    tenant_id,
                    entry["module_code"],
                    is_enabled=bool(entry.get("is_enabled", True)),
                    notes=entry.get("notes"),
                )
            )
        return out

    def reset_module(self, tenant_id: int, module_code: str) -> None:
        """
        Drop the per-tenant override and fall back to the plan default.
        """
        code = _normalize(module_code)
        record = (
            self.db.query(TenantModuleAccess)
            .filter(
                TenantModuleAccess.tenant_id == tenant_id,
                TenantModuleAccess.module_code == code,
            )
            .first()
        )
        if record is None:
            return
        # Soft-delete via the BaseTable pattern.
        record.soft_delete()
        self.db.commit()
