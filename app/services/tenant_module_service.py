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

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.core.enums import SubscriptionStatus
from app.core.exceptions import BadRequestError, NotFoundError, ServiceError
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
    ("mortuary", "Mortuary & Morgue"),
    ("compliance", "Compliance & Audit"),
    ("dental", "Dental Clinic"),
    ("eye", "Eye Clinic"),
    ("ortho", "Orthopaedics"),
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


# ---------------------------------------------------------------------------
# Facility profiles (verticals). A profile is a one-click preset that narrows a
# tenant to the modules its vertical needs. Integrated hospitals use the full
# "HOSPITAL" profile (no forced gating — every module follows the plan).
#
# ``modules`` lists the SUPPORTED_MODULE_CODES that a vertical keeps ON. When a
# profile is applied, in-profile modules have any override cleared (so they
# follow the subscription plan) and every other module is force-disabled via a
# TenantModuleAccess override. Core pages that carry no module code (patient
# registration, visits, queues, settings, roles…) are always available.
# ---------------------------------------------------------------------------
FACILITY_PROFILES: dict[str, dict] = {
    "HOSPITAL": {
        "label": "Integrated Hospital",
        "workspace_name": "Hospital Workspace",
        "home": "dashboard",
        "description": "Full multi-department hospital — every subscribed module is available.",
        # Sentinel: the full set follows the subscription plan (no forced gating).
        "modules": None,
    },
    "DENTAL": {
        "label": "Dental Clinic",
        "workspace_name": "Dental Clinic",
        "home": "dental",
        "description": "Standalone dental practice: odontogram charting, treatment plans, billing and stock.",
        "modules": {
            "dental", "appointments", "billing", "insurance",
            "inventory", "pharmacy", "reporting", "hr", "compliance", "patient_portal",
        },
    },
    "EYE": {
        "label": "Eye Clinic",
        "workspace_name": "Eye Clinic",
        "home": "eye",
        "description": "Standalone optometry / ophthalmology clinic: refraction, prescriptions, billing and stock.",
        "modules": {
            "eye", "appointments", "billing", "insurance",
            "inventory", "pharmacy", "reporting", "hr", "compliance", "patient_portal",
        },
    },
    "PHARMACY": {
        "label": "Pharmaceutical Store",
        "workspace_name": "Pharmacy",
        "home": "pharmacy",
        "description": "Standalone retail / community pharmacy: dispensing, stock control, billing and claims.",
        "modules": {
            "pharmacy", "inventory", "billing", "insurance", "reporting", "hr", "compliance",
        },
    },
}

DEFAULT_FACILITY_PROFILE = "HOSPITAL"
FACILITY_PROFILE_CODES: set[str] = set(FACILITY_PROFILES.keys())


def normalize_profile(profile: Optional[str]) -> str:
    """Normalise to a known profile code; NULL/blank -> HOSPITAL."""
    code = (profile or "").strip().upper()
    if not code:
        return DEFAULT_FACILITY_PROFILE
    if code not in FACILITY_PROFILE_CODES:
        raise BadRequestError(
            message=f"Unknown facility profile '{profile}'.",
            detail={"supported_profiles": sorted(FACILITY_PROFILE_CODES)},
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

    def _trial_active(self, tenant_id: int) -> bool:
        """True when the tenant's current subscription is a live (unexpired)
        trial. During a trial EVERY module is unlocked, mirroring the API-level
        feature gate, so the tenant can evaluate the whole platform."""
        from app.models.all_models import TenantSubscription  # local import
        sub = (
            self.db.query(TenantSubscription)
            .filter(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.status == SubscriptionStatus.TRIALING,
                TenantSubscription.is_active.is_(True),
            )
            .order_by(TenantSubscription.id.desc())
            .first()
        )
        if not sub:
            return False
        end = sub.trial_end_date
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return end is None or end > datetime.now(timezone.utc)

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
        trial = self._trial_active(tenant_id)
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
            plan_default = True if trial else (bool(getattr(plan, f"has_{code}", False)) if plan else False)
            override = overrides.get(code)
            override_value = override.is_enabled if override is not None else None
            # A SaaS-admin override wins both ways: it can grant a module the
            # plan does not include (loyalty benefit) or disable one it does.
            if override_value is not None:
                effective = override_value and plan is not None
            else:
                effective = plan_default

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

        override = (
            self.db.query(TenantModuleAccess)
            .filter(
                TenantModuleAccess.tenant_id == tenant_id,
                TenantModuleAccess.module_code == code,
                TenantModuleAccess.is_deleted.is_(False),
            )
            .first()
        )
        # An explicit SaaS-admin override wins: grant (loyalty benefit) or disable.
        if override is not None:
            return bool(override.is_enabled)
        # No override -> a live trial unlocks everything, else gate on the plan.
        if self._trial_active(tenant_id):
            return True
        return bool(getattr(plan, f"has_{code}", False))

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def _apply_module(
        self,
        tenant_id: int,
        module_code: str,
        *,
        is_enabled: bool,
        notes: Optional[str] = None,
    ) -> TenantModuleAccess:
        """Create or update a per-tenant module override WITHOUT committing.

        A SaaS-admin override is authoritative: it may enable a module the
        plan does not include (a loyalty benefit) or disable one it does. The
        effective-access computation in :meth:`list_modules_for_tenant` and
        :meth:`is_module_enabled` honours the override, so no plan-membership
        guard is applied on write.
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
        return record

    def _commit(self, message: str) -> None:
        """Commit the session, rolling back and surfacing the real DB error
        (instead of an opaque 500) on failure."""
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            orig = getattr(exc, "orig", None)
            raise ServiceError(
                message=message,
                detail={"error": str(orig) if orig is not None else str(exc)},
            ) from exc

    def set_module(
        self,
        tenant_id: int,
        module_code: str,
        *,
        is_enabled: bool,
        notes: Optional[str] = None,
    ) -> TenantModuleAccess:
        """Create or update a single per-tenant module override."""
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")
        record = self._apply_module(
            tenant_id, module_code, is_enabled=is_enabled, notes=notes
        )
        self._commit("Could not save the module setting.")
        self.db.refresh(record)
        return record

    def bulk_set_modules(
        self,
        tenant_id: int,
        modules: Iterable[dict],
    ) -> list[TenantModuleAccess]:
        """Apply a batch of module overrides atomically (one commit)::

            [{"module_code": "pharmacy", "is_enabled": False, "notes": "..."}]
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")
        out: list[TenantModuleAccess] = []
        for entry in modules or []:
            out.append(
                self._apply_module(
                    tenant_id,
                    entry["module_code"],
                    is_enabled=bool(entry.get("is_enabled", True)),
                    notes=entry.get("notes"),
                )
            )
        self._commit("Could not save the module settings.")
        for record in out:
            self.db.refresh(record)
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

    # ------------------------------------------------------------------
    # Facility profiles (verticals)
    # ------------------------------------------------------------------
    @staticmethod
    def list_profiles() -> list[dict]:
        """Catalog of selectable facility profiles for the UI."""
        out: list[dict] = []
        for code, spec in FACILITY_PROFILES.items():
            modules = spec.get("modules")
            out.append(
                {
                    "code": code,
                    "label": spec["label"],
                    "workspace_name": spec["workspace_name"],
                    "home": spec["home"],
                    "description": spec["description"],
                    # None (HOSPITAL) -> every supported module; else the vertical set.
                    "modules": sorted(SUPPORTED_MODULE_CODES) if modules is None else sorted(modules),
                    "is_default": code == DEFAULT_FACILITY_PROFILE,
                }
            )
        return out

    def get_profile_for_tenant(self, tenant_id: int) -> dict:
        """Return the tenant's current facility profile (defaulting to HOSPITAL)."""
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")
        code = normalize_profile(getattr(tenant, "facility_profile", None))
        spec = FACILITY_PROFILES[code]
        return {
            "code": code,
            "label": spec["label"],
            "workspace_name": spec["workspace_name"],
            "home": spec["home"],
            "description": spec["description"],
        }

    def apply_profile(self, tenant_id: int, profile: str) -> dict:
        """
        Apply a facility profile to a tenant in one transaction.

        * Stores ``tenant.facility_profile``.
        * For every supported module: in-profile modules have their override
          cleared (they follow the subscription plan); out-of-profile modules
          are force-disabled. HOSPITAL clears all overrides (no forced gating).

        Idempotent: re-applying the same profile converges to the same state.
        """
        code = normalize_profile(profile)
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")

        allowed = FACILITY_PROFILES[code]["modules"]  # None for HOSPITAL
        existing = {
            o.module_code: o
            for o in self.db.query(TenantModuleAccess)
            .filter(
                TenantModuleAccess.tenant_id == tenant_id,
                TenantModuleAccess.is_deleted.is_(False),
            )
            .all()
        }

        disabled: list[str] = []
        for mcode, _label in SUPPORTED_MODULES:
            in_profile = allowed is None or mcode in allowed
            override = existing.get(mcode)
            if in_profile:
                # Follow the plan: drop any profile-driven disable override.
                if override is not None and not override.is_enabled:
                    override.soft_delete()
            else:
                # Force the module off for this vertical.
                self._apply_module(
                    tenant_id,
                    mcode,
                    is_enabled=False,
                    notes=f"Disabled by '{code}' facility profile.",
                )
                disabled.append(mcode)

        tenant.facility_profile = code
        self._commit("Could not apply the facility profile.")
        self.db.refresh(tenant)
        return {
            "code": code,
            "label": FACILITY_PROFILES[code]["label"],
            "disabled_modules": disabled,
        }
