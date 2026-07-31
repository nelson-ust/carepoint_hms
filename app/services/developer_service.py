# app/services/developer_service.py
from __future__ import annotations

"""
Self-service developer platform.

Third-party developers register (email-verified), then create *apps* that each
carry one API key. An API key by itself grants nothing against real data: a
holding **tenant must approve a data grant** before the app can read that
hospital's patient history or baseline diagnostics. Effective access for any
call is::

    requested_scope  in  app.scopes  ∩  grant.approved_scopes   (grant APPROVED)

All developer/app/grant rows live in the master database; patient data is read
from the holding tenant's own database.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.api_key import (
    extract_scheme_prefix,
    generate_prefixed_key,
    hash_api_key,
    verify_api_key,
)
from app.core.database import get_master_db_context, get_tenant_db_context
from app.core.enums import (
    DeveloperAccountStatus,
    DeveloperAppEnvironment,
    DeveloperAppStatus,
    DeveloperGrantStatus,
)
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.utils.patient_export import (
    build_patient_baseline_diagnostics,
    build_patient_medical_history,
)

# ---------------------------------------------------------------------------
# Scope catalog — the *only* capabilities a developer key can be granted.
# Deliberately narrow and read-only: this is data-exchange, not full control.
# ---------------------------------------------------------------------------
DEVELOPER_SCOPES: dict[str, str] = {
    "patient:search": "Search patients by name or identifier (minimal demographics).",
    "patient:history:read": "Read a patient's medical history — diagnoses, consultations, medications, procedures, admissions.",
    "diagnostics:read": "Read a patient's baseline diagnostics — vital signs, laboratory results and radiology.",
}

_VERIFICATION_TTL_HOURS = 48
_DATA_KEY_SCHEME = "cpk"      # CarePoint developer data key
_DASHBOARD_SCHEME = "cpm"     # CarePoint developer management/dashboard token
_VERIFY_SCHEME = "cpv"        # CarePoint email-verification token


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _csv(scopes) -> str:
    if isinstance(scopes, str):
        items = [s.strip() for s in scopes.split(",")]
    else:
        items = [str(s).strip() for s in (scopes or [])]
    seen, out = set(), []
    for s in items:
        if s and s in DEVELOPER_SCOPES and s not in seen:
            seen.add(s)
            out.append(s)
    return ",".join(out)


def _scope_set(csv: Optional[str]) -> set[str]:
    return {s.strip() for s in (csv or "").split(",") if s.strip()}


# ===========================================================================
# Serializers
# ===========================================================================

def _account_read(a) -> dict:
    return {
        "id": a.id,
        "organization_name": a.organization_name,
        "contact_name": a.contact_name,
        "email": a.email,
        "website": a.website,
        "description": a.description,
        "status": a.status.value if hasattr(a.status, "value") else a.status,
        "email_verified": a.email_verified,
        "created_at": _as_utc(a.created_at).isoformat() if getattr(a, "created_at", None) else None,
    }


def _app_read(app) -> dict:
    return {
        "id": app.id,
        "developer_account_id": app.developer_account_id,
        "name": app.name,
        "environment": app.environment.value if hasattr(app.environment, "value") else app.environment,
        "status": app.status.value if hasattr(app.status, "value") else app.status,
        "key_prefix": app.key_prefix,
        "scopes": sorted(_scope_set(app.scopes)),
        "expires_at": _as_utc(app.expires_at).isoformat() if app.expires_at else None,
        "last_used_at": _as_utc(app.last_used_at).isoformat() if app.last_used_at else None,
        "created_at": _as_utc(app.created_at).isoformat() if getattr(app, "created_at", None) else None,
    }


def _grant_read(g, *, tenant_name: Optional[str] = None) -> dict:
    return {
        "id": g.id,
        "developer_app_id": g.developer_app_id,
        "developer_account_id": g.developer_account_id,
        "tenant_id": g.tenant_id,
        "tenant_name": tenant_name,
        "status": g.status.value if hasattr(g.status, "value") else g.status,
        "requested_scopes": sorted(_scope_set(g.requested_scopes)),
        "approved_scopes": sorted(_scope_set(g.approved_scopes)),
        "justification": g.justification,
        "requested_at": _as_utc(g.requested_at).isoformat() if g.requested_at else None,
        "decided_at": _as_utc(g.decided_at).isoformat() if g.decided_at else None,
        "decision_note": g.decision_note,
    }


class DeveloperService:
    # -------------------------------------------------------------------
    # Registration + email verification (public, unauthenticated)
    # -------------------------------------------------------------------
    def register(self, *, organization_name: str, contact_name: str, email: str,
                 website: Optional[str] = None, description: Optional[str] = None) -> dict:
        from app.models.all_models import DeveloperAccount

        email = (email or "").strip().lower()
        if not email or "@" not in email:
            raise BadRequestError(message="A valid email address is required.")
        if not (organization_name or "").strip():
            raise BadRequestError(message="Organization name is required.")

        full_token, _prefix, token_hash = generate_prefixed_key(_VERIFY_SCHEME)

        with get_master_db_context() as mdb:
            existing = mdb.query(DeveloperAccount).filter(
                DeveloperAccount.email == email,
                DeveloperAccount.is_deleted.is_(False),
            ).first()
            if existing is not None:
                if existing.email_verified:
                    raise BadRequestError(message="An account with this email already exists.")
                # Re-registration before verification: refresh the token.
                existing.organization_name = organization_name.strip()
                existing.contact_name = (contact_name or existing.contact_name or "").strip()
                existing.website = website
                existing.description = description
                existing.verification_token_hash = token_hash
                existing.verification_expires_at = _now() + timedelta(hours=_VERIFICATION_TTL_HOURS)
                mdb.add(existing)
                mdb.commit()
                account_id = existing.id
            else:
                acct = DeveloperAccount(
                    organization_name=organization_name.strip(),
                    contact_name=(contact_name or "").strip() or organization_name.strip(),
                    email=email,
                    website=website,
                    description=description,
                    status=DeveloperAccountStatus.PENDING,
                    email_verified=False,
                    verification_token_hash=token_hash,
                    verification_expires_at=_now() + timedelta(hours=_VERIFICATION_TTL_HOURS),
                )
                mdb.add(acct)
                mdb.commit()
                mdb.refresh(acct)
                account_id = acct.id

        # Send the verification email (best-effort — never block registration on
        # email transport). The token is also returned so the flow is completable
        # in environments without outbound email configured.
        email_sent = self._send_verification_email(
            email=email, contact_name=contact_name,
            organization_name=organization_name, token=full_token,
        )
        return {
            "account_id": account_id,
            "email": email,
            "verification_token": full_token,
            "expires_in_hours": _VERIFICATION_TTL_HOURS,
            "email_sent": email_sent,
        }

    def _send_verification_email(self, *, email: str, contact_name: Optional[str],
                                 organization_name: Optional[str], token: str) -> bool:
        """Dispatch the verification email. Returns True on success, False if
        email is unconfigured or delivery fails - never raises."""
        try:
            from urllib.parse import urlencode
            from app.core.config import settings
            from app.utils.email_utils import send_developer_verification_email

            base = (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
            verify_url = (
                f"{base}/developers?{urlencode({'email': email, 'token': token})}"
                if base else None
            )
            result = send_developer_verification_email(
                email=email,
                contact_name=contact_name or "",
                organization_name=organization_name or "",
                token=token,
                expires_hours=_VERIFICATION_TTL_HOURS,
                verify_url=verify_url,
            )
            return bool(result.get("success"))
        except Exception:
            return False

    def verify_email(self, *, email: str, token: str) -> dict:
        from app.models.all_models import DeveloperAccount

        email = (email or "").strip().lower()
        with get_master_db_context() as mdb:
            acct = mdb.query(DeveloperAccount).filter(
                DeveloperAccount.email == email,
                DeveloperAccount.is_deleted.is_(False),
            ).first()
            if acct is None:
                raise NotFoundError(message="No developer account for that email.")
            if acct.email_verified:
                raise BadRequestError(message="This account is already verified.")
            if not acct.verification_token_hash or not verify_api_key(token, acct.verification_token_hash):
                raise BadRequestError(message="Invalid verification token.")
            if acct.verification_expires_at and _now() > _as_utc(acct.verification_expires_at):
                raise BadRequestError(message="Verification token has expired. Please request a new one.")

            full_token, prefix, token_hash = generate_prefixed_key(_DASHBOARD_SCHEME)
            acct.email_verified = True
            acct.status = DeveloperAccountStatus.ACTIVE
            acct.verified_at = _now()
            acct.verification_token_hash = None
            acct.verification_expires_at = None
            acct.dashboard_token_prefix = prefix
            acct.dashboard_token_hash = token_hash
            mdb.add(acct)
            mdb.commit()
            mdb.refresh(acct)
            data = _account_read(acct)

        data["dashboard_token"] = full_token
        return data

    def resend_verification(self, *, email: str) -> dict:
        from app.models.all_models import DeveloperAccount

        email = (email or "").strip().lower()
        full_token, _prefix, token_hash = generate_prefixed_key(_VERIFY_SCHEME)
        with get_master_db_context() as mdb:
            acct = mdb.query(DeveloperAccount).filter(
                DeveloperAccount.email == email,
                DeveloperAccount.is_deleted.is_(False),
            ).first()
            if acct is None:
                raise NotFoundError(message="No developer account for that email.")
            if acct.email_verified:
                raise BadRequestError(message="This account is already verified.")
            acct.verification_token_hash = token_hash
            acct.verification_expires_at = _now() + timedelta(hours=_VERIFICATION_TTL_HOURS)
            mdb.add(acct)
            mdb.commit()
            contact_name = acct.contact_name
            organization_name = acct.organization_name
        email_sent = self._send_verification_email(
            email=email, contact_name=contact_name,
            organization_name=organization_name, token=full_token,
        )
        return {"email": email, "verification_token": full_token,
                "expires_in_hours": _VERIFICATION_TTL_HOURS, "email_sent": email_sent}

    # -------------------------------------------------------------------
    # Dashboard-token auth + app management (developer self-service)
    # -------------------------------------------------------------------
    def resolve_account_by_dashboard_token(self, token: str):
        """Return the ACTIVE DeveloperAccount ORM row for a mgmt token, or None.
        Caller must be inside a master-db context (returns detached-safe dict via
        callers); here we return the id for re-query within the same context."""
        from app.models.all_models import DeveloperAccount

        prefix = extract_scheme_prefix(token or "")
        if not prefix:
            return None
        with get_master_db_context() as mdb:
            acct = mdb.query(DeveloperAccount).filter(
                DeveloperAccount.dashboard_token_prefix == prefix,
                DeveloperAccount.is_deleted.is_(False),
            ).first()
            if acct is None or not acct.dashboard_token_hash:
                return None
            if not verify_api_key(token, acct.dashboard_token_hash):
                return None
            if acct.status != DeveloperAccountStatus.ACTIVE:
                return None
            return {"id": acct.id, "email": acct.email, "organization_name": acct.organization_name,
                    "contact_name": acct.contact_name}

    def me(self, *, account_id: int) -> dict:
        from app.models.all_models import DeveloperAccount, DeveloperApp

        with get_master_db_context() as mdb:
            acct = mdb.query(DeveloperAccount).filter(DeveloperAccount.id == account_id).first()
            if acct is None:
                raise NotFoundError(message="Account not found.")
            data = _account_read(acct)
            apps = mdb.query(DeveloperApp).filter(
                DeveloperApp.developer_account_id == account_id,
                DeveloperApp.is_deleted.is_(False),
            ).order_by(DeveloperApp.id.desc()).all()
            data["apps"] = [_app_read(a) for a in apps]
            return data

    def create_app(self, *, account_id: int, name: str,
                   environment: str = "SANDBOX", scopes=None) -> dict:
        from app.models.all_models import DeveloperApp

        clean_scopes = _csv(scopes)
        if not clean_scopes:
            raise BadRequestError(message="Select at least one valid scope for the app.")
        try:
            env = DeveloperAppEnvironment(str(environment).strip().upper())
        except Exception:
            env = DeveloperAppEnvironment.SANDBOX

        full_key, prefix, key_hash = generate_prefixed_key(_DATA_KEY_SCHEME)
        with get_master_db_context() as mdb:
            app = DeveloperApp(
                developer_account_id=account_id,
                name=(name or "").strip() or "Untitled app",
                environment=env,
                status=DeveloperAppStatus.ACTIVE,
                key_prefix=prefix,
                key_hash=key_hash,
                scopes=clean_scopes,
            )
            mdb.add(app)
            mdb.commit()
            mdb.refresh(app)
            data = _app_read(app)
        data["api_key"] = full_key
        return data

    def list_apps(self, *, account_id: int) -> list[dict]:
        from app.models.all_models import DeveloperApp

        with get_master_db_context() as mdb:
            rows = mdb.query(DeveloperApp).filter(
                DeveloperApp.developer_account_id == account_id,
                DeveloperApp.is_deleted.is_(False),
            ).order_by(DeveloperApp.id.desc()).all()
            return [_app_read(a) for a in rows]

    def _owned_app(self, mdb, app_id: int, account_id: int):
        from app.models.all_models import DeveloperApp

        app = mdb.query(DeveloperApp).filter(
            DeveloperApp.id == app_id,
            DeveloperApp.developer_account_id == account_id,
            DeveloperApp.is_deleted.is_(False),
        ).first()
        if app is None:
            raise NotFoundError(message="App not found.")
        return app

    def revoke_app(self, *, app_id: int, account_id: int) -> dict:
        with get_master_db_context() as mdb:
            app = self._owned_app(mdb, app_id, account_id)
            app.status = DeveloperAppStatus.REVOKED
            mdb.add(app)
            mdb.commit()
            mdb.refresh(app)
            return _app_read(app)

    def rotate_key(self, *, app_id: int, account_id: int) -> dict:
        full_key, prefix, key_hash = generate_prefixed_key(_DATA_KEY_SCHEME)
        with get_master_db_context() as mdb:
            app = self._owned_app(mdb, app_id, account_id)
            app.key_prefix = prefix
            app.key_hash = key_hash
            app.status = DeveloperAppStatus.ACTIVE
            mdb.add(app)
            mdb.commit()
            mdb.refresh(app)
            data = _app_read(app)
        data["api_key"] = full_key
        return data

    def update_app_scopes(self, *, app_id: int, account_id: int, scopes) -> dict:
        clean = _csv(scopes)
        if not clean:
            raise BadRequestError(message="Select at least one valid scope.")
        with get_master_db_context() as mdb:
            app = self._owned_app(mdb, app_id, account_id)
            app.scopes = clean
            mdb.add(app)
            mdb.commit()
            mdb.refresh(app)
            return _app_read(app)

    # -------------------------------------------------------------------
    # Data grants — developer requests a tenant's data; tenant approves.
    # -------------------------------------------------------------------
    def request_grant(self, *, account_id: int, app_id: int, tenant_code: str,
                      requested_scopes=None, justification: Optional[str] = None) -> dict:
        from app.models.all_models import DeveloperDataGrant, Tenant

        with get_master_db_context() as mdb:
            app = self._owned_app(mdb, app_id, account_id)
            tenant = mdb.query(Tenant).filter(
                Tenant.code == (tenant_code or "").strip(),
                Tenant.is_deleted.is_(False),
            ).first()
            if tenant is None:
                raise NotFoundError(message="No hospital/tenant with that code.")

            req = _csv(requested_scopes) or app.scopes
            # Cannot request more than the app itself carries.
            req = ",".join(sorted(_scope_set(req) & _scope_set(app.scopes)))
            if not req:
                raise BadRequestError(message="Requested scopes must be a subset of the app's scopes.")

            existing = mdb.query(DeveloperDataGrant).filter(
                DeveloperDataGrant.developer_app_id == app_id,
                DeveloperDataGrant.tenant_id == tenant.id,
                DeveloperDataGrant.is_deleted.is_(False),
                DeveloperDataGrant.status.in_([DeveloperGrantStatus.PENDING, DeveloperGrantStatus.APPROVED]),
            ).first()
            if existing is not None:
                raise BadRequestError(message="A pending or active grant already exists for this hospital.")

            grant = DeveloperDataGrant(
                developer_app_id=app_id,
                developer_account_id=account_id,
                tenant_id=tenant.id,
                status=DeveloperGrantStatus.PENDING,
                requested_scopes=req,
                approved_scopes="",
                justification=justification,
                requested_at=_now(),
            )
            mdb.add(grant)
            mdb.commit()
            mdb.refresh(grant)
            return _grant_read(grant, tenant_name=tenant.name)

    def list_grants(self, *, account_id: int) -> list[dict]:
        from app.models.all_models import DeveloperDataGrant, Tenant

        with get_master_db_context() as mdb:
            rows = mdb.query(DeveloperDataGrant).filter(
                DeveloperDataGrant.developer_account_id == account_id,
                DeveloperDataGrant.is_deleted.is_(False),
            ).order_by(DeveloperDataGrant.id.desc()).all()
            names = {t.id: t.name for t in mdb.query(Tenant).all()}
            return [_grant_read(g, tenant_name=names.get(g.tenant_id)) for g in rows]

    # -------------------------------------------------------------------
    # Tenant-side grant review (JWT admin)
    # -------------------------------------------------------------------
    def list_grants_for_tenant(self, *, tenant_id: int, status: Optional[str] = None) -> list[dict]:
        from app.models.all_models import DeveloperAccount, DeveloperApp, DeveloperDataGrant, Tenant

        with get_master_db_context() as mdb:
            q = mdb.query(DeveloperDataGrant).filter(
                DeveloperDataGrant.tenant_id == tenant_id,
                DeveloperDataGrant.is_deleted.is_(False),
            )
            if status:
                try:
                    q = q.filter(DeveloperDataGrant.status == DeveloperGrantStatus(status.strip().upper()))
                except Exception:
                    pass
            rows = q.order_by(DeveloperDataGrant.id.desc()).all()
            tname = {t.id: t.name for t in mdb.query(Tenant).all()}
            accts = {a.id: a for a in mdb.query(DeveloperAccount).all()}
            apps = {a.id: a for a in mdb.query(DeveloperApp).all()}
            out = []
            for g in rows:
                d = _grant_read(g, tenant_name=tname.get(g.tenant_id))
                acct = accts.get(g.developer_account_id)
                app = apps.get(g.developer_app_id)
                d["developer"] = _account_read(acct) if acct else None
                d["app_name"] = app.name if app else None
                d["app_environment"] = (app.environment.value if app and hasattr(app.environment, "value") else None)
                out.append(d)
            return out

    def decide_grant(self, *, grant_id: int, tenant_id: int, approve: bool,
                     approved_scopes=None, note: Optional[str] = None,
                     user_id: Optional[int] = None) -> dict:
        from app.models.all_models import DeveloperApp, DeveloperDataGrant, Tenant

        with get_master_db_context() as mdb:
            grant = mdb.query(DeveloperDataGrant).filter(
                DeveloperDataGrant.id == grant_id,
                DeveloperDataGrant.tenant_id == tenant_id,
                DeveloperDataGrant.is_deleted.is_(False),
            ).first()
            if grant is None:
                raise NotFoundError(message="Grant not found for this hospital.")

            if approve:
                app = mdb.query(DeveloperApp).filter(DeveloperApp.id == grant.developer_app_id).first()
                app_scopes = _scope_set(app.scopes) if app else set()
                req = _scope_set(grant.requested_scopes)
                chosen = _scope_set(_csv(approved_scopes)) if approved_scopes else req
                # never approve beyond what was requested AND what the app carries
                effective = ",".join(sorted(chosen & req & app_scopes))
                if not effective:
                    raise BadRequestError(message="No valid scopes to approve.")
                grant.status = DeveloperGrantStatus.APPROVED
                grant.approved_scopes = effective
            else:
                grant.status = DeveloperGrantStatus.DENIED
                grant.approved_scopes = ""

            grant.decided_by_user_id = user_id
            grant.decided_at = _now()
            grant.decision_note = note
            mdb.add(grant)
            mdb.commit()
            mdb.refresh(grant)
            tenant = mdb.query(Tenant).filter(Tenant.id == tenant_id).first()
            return _grant_read(grant, tenant_name=tenant.name if tenant else None)

    def revoke_grant(self, *, grant_id: int, tenant_id: int, user_id: Optional[int] = None,
                     note: Optional[str] = None) -> dict:
        from app.models.all_models import DeveloperDataGrant, Tenant

        with get_master_db_context() as mdb:
            grant = mdb.query(DeveloperDataGrant).filter(
                DeveloperDataGrant.id == grant_id,
                DeveloperDataGrant.tenant_id == tenant_id,
                DeveloperDataGrant.is_deleted.is_(False),
            ).first()
            if grant is None:
                raise NotFoundError(message="Grant not found for this hospital.")
            grant.status = DeveloperGrantStatus.REVOKED
            grant.decided_by_user_id = user_id
            grant.decided_at = _now()
            grant.decision_note = note
            mdb.add(grant)
            mdb.commit()
            mdb.refresh(grant)
            tenant = mdb.query(Tenant).filter(Tenant.id == tenant_id).first()
            return _grant_read(grant, tenant_name=tenant.name if tenant else None)

    # -------------------------------------------------------------------
    # Platform-admin oversight of developer accounts
    # -------------------------------------------------------------------
    def list_accounts(self, *, status: Optional[str] = None) -> list[dict]:
        from app.models.all_models import DeveloperAccount

        with get_master_db_context() as mdb:
            q = mdb.query(DeveloperAccount).filter(DeveloperAccount.is_deleted.is_(False))
            if status:
                try:
                    q = q.filter(DeveloperAccount.status == DeveloperAccountStatus(status.strip().upper()))
                except Exception:
                    pass
            return [_account_read(a) for a in q.order_by(DeveloperAccount.id.desc()).all()]

    def set_account_status(self, *, account_id: int, active: bool,
                           reason: Optional[str] = None, user_id: Optional[int] = None) -> dict:
        from app.models.all_models import DeveloperAccount

        with get_master_db_context() as mdb:
            acct = mdb.query(DeveloperAccount).filter(DeveloperAccount.id == account_id).first()
            if acct is None:
                raise NotFoundError(message="Developer account not found.")
            acct.status = DeveloperAccountStatus.ACTIVE if active else DeveloperAccountStatus.SUSPENDED
            acct.suspended_reason = None if active else reason
            acct.reviewed_by_user_id = user_id
            acct.reviewed_at = _now()
            mdb.add(acct)
            mdb.commit()
            mdb.refresh(acct)
            return _account_read(acct)

    # -------------------------------------------------------------------
    # Data-plane: authenticate an app key + enforce scope ∩ grant, then read
    # from the holding tenant's database.
    # -------------------------------------------------------------------
    def authenticate_app(self, *, key: str):
        """Return a lightweight principal dict for a presented data API key, or
        raise 401. Updates last_used.*"""
        from app.models.all_models import DeveloperAccount, DeveloperApp

        prefix = extract_scheme_prefix(key or "")
        if not prefix:
            raise BadRequestError(message="Malformed API key.")
        with get_master_db_context() as mdb:
            app = mdb.query(DeveloperApp).filter(
                DeveloperApp.key_prefix == prefix,
                DeveloperApp.is_deleted.is_(False),
            ).first()
            if app is None or not verify_api_key(key, app.key_hash):
                raise ForbiddenError(message="Invalid API key.")
            if app.status != DeveloperAppStatus.ACTIVE:
                raise ForbiddenError(message="This API key has been revoked.")
            if app.expires_at and _now() > _as_utc(app.expires_at):
                raise ForbiddenError(message="This API key has expired.")
            acct = mdb.query(DeveloperAccount).filter(DeveloperAccount.id == app.developer_account_id).first()
            if acct is None or acct.status != DeveloperAccountStatus.ACTIVE:
                raise ForbiddenError(message="Developer account is not active.")
            try:
                app.last_used_at = _now()
                mdb.add(app)
                mdb.commit()
            except Exception:
                mdb.rollback()
            return {
                "app_id": app.id,
                "account_id": acct.id,
                "app_name": app.name,
                "organization_name": acct.organization_name,
                "email": acct.email,
                "environment": app.environment.value if hasattr(app.environment, "value") else app.environment,
                "scopes": _scope_set(app.scopes),
            }

    def _resolve_grant(self, *, app_id: int, tenant_code: str, scope: str):
        """Return (tenant_id, tenant_name) if an APPROVED grant covers ``scope``
        for this app+tenant, else raise 403/404."""
        from app.models.all_models import DeveloperDataGrant, Tenant

        with get_master_db_context() as mdb:
            tenant = mdb.query(Tenant).filter(
                Tenant.code == (tenant_code or "").strip(),
                Tenant.is_deleted.is_(False),
            ).first()
            if tenant is None:
                raise NotFoundError(message="No hospital/tenant with that code.")
            grant = mdb.query(DeveloperDataGrant).filter(
                DeveloperDataGrant.developer_app_id == app_id,
                DeveloperDataGrant.tenant_id == tenant.id,
                DeveloperDataGrant.status == DeveloperGrantStatus.APPROVED,
                DeveloperDataGrant.is_deleted.is_(False),
            ).first()
            if grant is None:
                raise ForbiddenError(message="This hospital has not approved data access for your app.")
            if scope not in _scope_set(grant.approved_scopes):
                raise ForbiddenError(message=f"Your grant for this hospital does not include the '{scope}' scope.")
            return tenant.id, tenant.name

    def data_search_patients(self, *, principal: dict, tenant_code: str,
                             search: Optional[str], limit: int = 25) -> dict:
        if "patient:search" not in principal["scopes"]:
            raise ForbiddenError(message="Your API key lacks the 'patient:search' scope.")
        tenant_id, tenant_name = self._resolve_grant(
            app_id=principal["app_id"], tenant_code=tenant_code, scope="patient:search")
        from app.services.integration_service import IntegrationService
        with get_tenant_db_context(tenant_id) as tdb:
            items = IntegrationService(tdb).search_patients(query=search, limit=limit)
        return {"tenant": tenant_name, "count": len(items), "items": items}

    def data_medical_history(self, *, principal: dict, tenant_code: str, global_patient_id: str) -> dict:
        if "patient:history:read" not in principal["scopes"]:
            raise ForbiddenError(message="Your API key lacks the 'patient:history:read' scope.")
        tenant_id, tenant_name = self._resolve_grant(
            app_id=principal["app_id"], tenant_code=tenant_code, scope="patient:history:read")
        with get_tenant_db_context(tenant_id) as tdb:
            record = build_patient_medical_history(tdb, global_patient_id)
        if record is None:
            raise NotFoundError(message="Patient not found at this hospital.")
        record["tenant"] = tenant_name
        return record

    def data_baseline_diagnostics(self, *, principal: dict, tenant_code: str, global_patient_id: str) -> dict:
        if "diagnostics:read" not in principal["scopes"]:
            raise ForbiddenError(message="Your API key lacks the 'diagnostics:read' scope.")
        tenant_id, tenant_name = self._resolve_grant(
            app_id=principal["app_id"], tenant_code=tenant_code, scope="diagnostics:read")
        with get_tenant_db_context(tenant_id) as tdb:
            record = build_patient_baseline_diagnostics(tdb, global_patient_id)
        if record is None:
            raise NotFoundError(message="Patient not found at this hospital.")
        record["tenant"] = tenant_name
        return record
