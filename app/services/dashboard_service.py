"""
Dashboard aggregator services.

Two audiences:

* :class:`SaaSDashboardOverviewService` — broad-spectrum platform
  metrics for SaaS administrators (tenant pipeline, MRR, billing
  AR-ageing, edge connectivity, support access, usage rollups, plan
  adoption, churn snapshot, recent activity feed).
* :class:`TenantDashboardService` — operational metrics for a
  hospital tenant admin (today's visits/appointments, revenue,
  patient counts, queue + bed occupancy, lab/pharmacy backlog,
  inventory alerts, HR overview, medication-adherence alerts).

Both services are read-only aggregators — they emit dictionaries that
the routes return verbatim, never raise on missing optional models
(graceful degrade when a feature isn't installed for the tenant), and
keep query counts low by using ``func.count`` + ``func.sum``.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


def _safe_count(db: Session, model, *filters) -> int:
    """Return a safe ``count(*)`` even when the table or model is absent."""
    try:
        q = db.query(func.count(model.id))
        if filters:
            q = q.filter(*filters)
        return int(q.scalar() or 0)
    except Exception:
        return 0


def _safe_sum(db: Session, column, *filters) -> Decimal:
    try:
        q = db.query(func.coalesce(func.sum(column), 0))
        if filters:
            q = q.filter(*filters)
        return Decimal(str(q.scalar() or 0))
    except Exception:
        return Decimal("0")


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _start_of_today() -> datetime:
    return datetime.combine(_today(), time.min).replace(tzinfo=timezone.utc)


def _start_of_month(day: Optional[date] = None) -> datetime:
    d = day or _today()
    return datetime.combine(d.replace(day=1), time.min).replace(tzinfo=timezone.utc)


def _months_ago(n: int) -> datetime:
    today = _today()
    year = today.year
    month = today.month - n
    while month <= 0:
        month += 12
        year -= 1
    return datetime.combine(date(year, month, 1), time.min).replace(tzinfo=timezone.utc)


# ============================================================
# SaaS overview
# ============================================================


class SaaSDashboardOverviewService:
    """
    Read-only aggregator for the SaaS admin console.

    Uses the **master** database. Always returns a dict so route
    handlers can simply ``return service.method()``.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Top-level overview
    # ------------------------------------------------------------------

    def overview(self) -> dict[str, Any]:
        return {
            "tenants": self.tenant_summary(),
            "billing": self.billing_summary(),
            "edge_nodes": self.edge_node_summary(),
            "support_access": self.support_access_summary(),
            "subscriptions": self.subscription_summary(),
            "onboarding_pipeline": self.onboarding_pipeline(),
        }

    # ------------------------------------------------------------------
    # Tenant population
    # ------------------------------------------------------------------

    def tenant_summary(self) -> dict[str, Any]:
        from app.core.enums import UserStatus
        from app.models.all_models import Tenant

        total = _safe_count(self.db, Tenant, Tenant.is_deleted.is_(False))
        active = _safe_count(self.db, Tenant, Tenant.is_deleted.is_(False), Tenant.status == UserStatus.ACTIVE)
        pending = _safe_count(self.db, Tenant, Tenant.is_deleted.is_(False), Tenant.status == UserStatus.PENDING)
        suspended = _safe_count(self.db, Tenant, Tenant.is_deleted.is_(False), Tenant.status == UserStatus.SUSPENDED)
        provisioned = _safe_count(self.db, Tenant, Tenant.is_deleted.is_(False), Tenant.is_provisioned.is_(True))
        new_this_month = _safe_count(
            self.db,
            Tenant,
            Tenant.is_deleted.is_(False),
            Tenant.date_created >= _start_of_month(),
        )
        return {
            "total": total,
            "active": active,
            "pending_approval": pending,
            "suspended": suspended,
            "provisioned": provisioned,
            "new_this_month": new_this_month,
        }

    def onboarding_pipeline(self) -> dict[str, Any]:
        """Conversion view: applied → approved → active."""
        from app.core.enums import UserStatus
        from app.models.all_models import Tenant

        applied_30d = _safe_count(
            self.db,
            Tenant,
            Tenant.is_deleted.is_(False),
            Tenant.date_created >= datetime.now(timezone.utc) - timedelta(days=30),
        )
        approved_30d = _safe_count(
            self.db,
            Tenant,
            Tenant.is_deleted.is_(False),
            Tenant.is_provisioned.is_(True),
            Tenant.date_updated >= datetime.now(timezone.utc) - timedelta(days=30),
        )
        active_total = _safe_count(
            self.db,
            Tenant,
            Tenant.is_deleted.is_(False),
            Tenant.status == UserStatus.ACTIVE,
        )
        return {
            "applied_last_30d": applied_30d,
            "approved_last_30d": approved_30d,
            "active_total": active_total,
            "approval_conversion_pct": (
                round(100.0 * approved_30d / applied_30d, 1) if applied_30d else 0.0
            ),
        }

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    def subscription_summary(self) -> dict[str, Any]:
        from app.core.enums import SubscriptionStatus
        from app.models.all_models import SubscriptionPlan, TenantSubscription

        try:
            rows = (
                self.db.query(
                    SubscriptionPlan.code,
                    SubscriptionPlan.name,
                    func.count(TenantSubscription.id).label("count"),
                )
                .join(SubscriptionPlan, SubscriptionPlan.id == TenantSubscription.plan_id)
                .filter(
                    TenantSubscription.is_deleted.is_(False),
                    TenantSubscription.status.in_([
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIALING,
                    ]),
                )
                .group_by(SubscriptionPlan.code, SubscriptionPlan.name)
                .all()
            )
        except Exception:
            rows = []

        plan_breakdown = [
            {"code": r.code, "name": r.name, "active_count": int(r.count or 0)}
            for r in rows
        ]
        trialing = _safe_count(
            self.db,
            TenantSubscription,
            TenantSubscription.status == SubscriptionStatus.TRIALING,
            TenantSubscription.is_deleted.is_(False),
        )
        return {"by_plan": plan_breakdown, "trialing_total": trialing}

    # ------------------------------------------------------------------
    # Billing / AR
    # ------------------------------------------------------------------

    def billing_summary(self) -> dict[str, Any]:
        from app.core.enums import (
            SubscriptionInvoiceStatus,
            SubscriptionPaymentStatus,
            SubscriptionStatus,
        )
        from app.models.all_models import (
            SubscriptionInvoice,
            SubscriptionPayment,
            SubscriptionPlan,
            TenantSubscription,
        )

        # MRR — sum of plan prices for ACTIVE subscriptions.
        mrr = Decimal("0")
        try:
            mrr_val = (
                self.db.query(func.coalesce(func.sum(SubscriptionPlan.price), 0))
                .join(TenantSubscription, TenantSubscription.plan_id == SubscriptionPlan.id)
                .filter(
                    TenantSubscription.is_deleted.is_(False),
                    TenantSubscription.status == SubscriptionStatus.ACTIVE,
                )
                .scalar()
            )
            mrr = Decimal(str(mrr_val or 0))
        except Exception:
            pass

        outstanding = _safe_sum(
            self.db,
            SubscriptionInvoice.amount_due,
            SubscriptionInvoice.is_deleted.is_(False),
            SubscriptionInvoice.status.in_([
                SubscriptionInvoiceStatus.ISSUED,
                SubscriptionInvoiceStatus.PARTIALLY_PAID,
                SubscriptionInvoiceStatus.OVERDUE,
            ]),
        )
        overdue_amt = _safe_sum(
            self.db,
            SubscriptionInvoice.amount_due,
            SubscriptionInvoice.is_deleted.is_(False),
            SubscriptionInvoice.status == SubscriptionInvoiceStatus.OVERDUE,
        )
        overdue_count = _safe_count(
            self.db,
            SubscriptionInvoice,
            SubscriptionInvoice.is_deleted.is_(False),
            SubscriptionInvoice.status == SubscriptionInvoiceStatus.OVERDUE,
        )

        paid_this_month = _safe_sum(
            self.db,
            SubscriptionPayment.amount,
            SubscriptionPayment.is_deleted.is_(False),
            SubscriptionPayment.status == SubscriptionPaymentStatus.SUCCEEDED,
            SubscriptionPayment.paid_at >= _start_of_month(),
        )
        paid_last_month = _safe_sum(
            self.db,
            SubscriptionPayment.amount,
            SubscriptionPayment.is_deleted.is_(False),
            SubscriptionPayment.status == SubscriptionPaymentStatus.SUCCEEDED,
            SubscriptionPayment.paid_at >= _months_ago(1),
            SubscriptionPayment.paid_at < _start_of_month(),
        )

        return {
            "mrr": float(mrr),
            "outstanding_total": float(outstanding),
            "overdue_total": float(overdue_amt),
            "overdue_count": overdue_count,
            "collected_this_month": float(paid_this_month),
            "collected_last_month": float(paid_last_month),
        }

    def billing_ageing(self) -> dict[str, Any]:
        """AR ageing buckets: <30, 30-60, 60-90, 90+ days overdue."""
        from app.core.enums import SubscriptionInvoiceStatus
        from app.models.all_models import SubscriptionInvoice

        now = datetime.now(timezone.utc)
        buckets = {"<30": 0, "30-60": 0, "60-90": 0, ">90": 0}
        amounts = {"<30": Decimal("0"), "30-60": Decimal("0"), "60-90": Decimal("0"), ">90": Decimal("0")}
        try:
            rows = (
                self.db.query(SubscriptionInvoice)
                .filter(
                    SubscriptionInvoice.is_deleted.is_(False),
                    SubscriptionInvoice.status.in_([
                        SubscriptionInvoiceStatus.ISSUED,
                        SubscriptionInvoiceStatus.PARTIALLY_PAID,
                        SubscriptionInvoiceStatus.OVERDUE,
                    ]),
                )
                .all()
            )
        except Exception:
            rows = []

        for inv in rows:
            due = inv.due_date
            if due is None:
                continue
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            days_overdue = (now - due).days
            if days_overdue < 30:
                key = "<30"
            elif days_overdue < 60:
                key = "30-60"
            elif days_overdue < 90:
                key = "60-90"
            else:
                key = ">90"
            buckets[key] += 1
            amounts[key] += Decimal(inv.amount_due or 0)

        return {
            "buckets": [
                {"bucket": k, "count": buckets[k], "amount": float(amounts[k])}
                for k in ("<30", "30-60", "60-90", ">90")
            ]
        }

    # ------------------------------------------------------------------
    # Edge connectivity
    # ------------------------------------------------------------------

    def edge_node_summary(self) -> dict[str, Any]:
        from app.core.enums import EdgeNodeStatus
        from app.models.all_models import EdgeNode

        total = _safe_count(self.db, EdgeNode, EdgeNode.is_deleted.is_(False))
        active = _safe_count(self.db, EdgeNode, EdgeNode.is_deleted.is_(False), EdgeNode.status == EdgeNodeStatus.ACTIVE)
        offline = _safe_count(self.db, EdgeNode, EdgeNode.is_deleted.is_(False), EdgeNode.status == EdgeNodeStatus.OFFLINE)
        degraded = _safe_count(self.db, EdgeNode, EdgeNode.is_deleted.is_(False), EdgeNode.status == EdgeNodeStatus.DEGRADED)
        provisioned = _safe_count(self.db, EdgeNode, EdgeNode.is_deleted.is_(False), EdgeNode.status == EdgeNodeStatus.PROVISIONED)
        return {
            "total": total,
            "active": active,
            "offline": offline,
            "degraded": degraded,
            "provisioned": provisioned,
        }

    # ------------------------------------------------------------------
    # Support access
    # ------------------------------------------------------------------

    def support_access_summary(self) -> dict[str, Any]:
        from app.core.enums import SupportAccessStatus
        from app.models.all_models import SupportAccessGrant

        return {
            "requested": _safe_count(self.db, SupportAccessGrant, SupportAccessGrant.status == SupportAccessStatus.REQUESTED),
            "approved": _safe_count(self.db, SupportAccessGrant, SupportAccessGrant.status == SupportAccessStatus.APPROVED),
            "expired": _safe_count(self.db, SupportAccessGrant, SupportAccessGrant.status == SupportAccessStatus.EXPIRED),
            "revoked": _safe_count(self.db, SupportAccessGrant, SupportAccessGrant.status == SupportAccessStatus.REVOKED),
        }

    # ------------------------------------------------------------------
    # Usage rollups (logins / SMS / email / storage)
    # ------------------------------------------------------------------

    def usage_summary(self) -> dict[str, Any]:
        from app.models.all_models import TenantUsage

        login_total = _safe_sum(self.db, TenantUsage.login_count)
        sms_total = _safe_sum(self.db, TenantUsage.sms_count)
        email_total = _safe_sum(self.db, TenantUsage.email_count)
        api_total = _safe_sum(self.db, TenantUsage.api_call_count)
        storage_total_bytes = _safe_sum(self.db, TenantUsage.storage_usage_bytes)
        return {
            "login_count_total": int(login_total),
            "sms_count_total": int(sms_total),
            "email_count_total": int(email_total),
            "api_call_count_total": int(api_total),
            "storage_total_bytes": int(storage_total_bytes),
            "storage_total_gb": round(float(storage_total_bytes) / (1024**3), 2),
        }

    # ------------------------------------------------------------------
    # Top tenants
    # ------------------------------------------------------------------

    def top_tenants_by_usage(self, *, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most-active tenants ranked by login_count."""
        from app.models.all_models import Tenant, TenantUsage

        try:
            rows = (
                self.db.query(
                    Tenant.code,
                    Tenant.name,
                    TenantUsage.login_count,
                    TenantUsage.api_call_count,
                    TenantUsage.storage_usage_bytes,
                )
                .join(TenantUsage, TenantUsage.tenant_id == Tenant.id)
                .filter(Tenant.is_deleted.is_(False))
                .order_by(TenantUsage.login_count.desc())
                .limit(limit)
                .all()
            )
        except Exception:
            rows = []
        return [
            {
                "tenant_code": r.code,
                "tenant_name": r.name,
                "logins": int(r.login_count or 0),
                "api_calls": int(r.api_call_count or 0),
                "storage_bytes": int(r.storage_usage_bytes or 0),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Recent activity feed
    # ------------------------------------------------------------------

    def recent_activity(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Most-recent SaaS-relevant events from the master DB."""
        from app.models.all_models import (
            SaaSNotification,
            SubscriptionInvoice,
            SubscriptionPayment,
            Tenant,
        )

        events: list[dict[str, Any]] = []

        try:
            for n in (
                self.db.query(SaaSNotification)
                .order_by(SaaSNotification.date_created.desc())
                .limit(limit)
                .all()
            ):
                events.append({
                    "type": "notification",
                    "subject": n.subject,
                    "body": n.body,
                    "occurred_at": n.date_created.isoformat() if n.date_created else None,
                })
        except Exception:
            pass

        try:
            for t in (
                self.db.query(Tenant)
                .filter(Tenant.is_deleted.is_(False))
                .order_by(Tenant.date_created.desc())
                .limit(limit)
                .all()
            ):
                events.append({
                    "type": "tenant_registered",
                    "tenant_code": t.code,
                    "tenant_name": t.name,
                    "is_provisioned": t.is_provisioned,
                    "occurred_at": t.date_created.isoformat() if t.date_created else None,
                })
        except Exception:
            pass

        try:
            for p in (
                self.db.query(SubscriptionPayment)
                .order_by(SubscriptionPayment.paid_at.desc())
                .limit(limit)
                .all()
            ):
                events.append({
                    "type": "payment_received",
                    "amount": float(p.amount or 0),
                    "currency": p.currency,
                    "tenant_id": p.tenant_id,
                    "occurred_at": p.paid_at.isoformat() if p.paid_at else None,
                })
        except Exception:
            pass

        events.sort(key=lambda e: e.get("occurred_at") or "", reverse=True)
        return events[:limit]


# ============================================================
# Tenant operational dashboard
# ============================================================


class TenantDashboardService:
    """
    Read-only aggregator for the tenant admin's daily console.

    All queries run against the active tenant database (``get_db()``).
    Each section is wrapped in defensive try/except so one missing
    optional table doesn't take the whole dashboard down.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Top-level overview
    # ------------------------------------------------------------------

    def overview(self) -> dict[str, Any]:
        return {
            "today": self.today_snapshot(),
            "patients": self.patient_summary(),
            "visits": self.visit_summary(),
            "appointments": self.appointment_summary(),
            "inpatient": self.inpatient_summary(),
            "billing": self.billing_summary(),
            "lab_pharmacy_backlog": self.lab_pharmacy_backlog(),
            "inventory_alerts": self.inventory_alerts(),
            "hr": self.hr_summary(),
            "medication_adherence": self.medication_adherence_summary(),
        }

    # ------------------------------------------------------------------
    # Today snapshot — single-call headline numbers
    # ------------------------------------------------------------------

    def today_snapshot(self) -> dict[str, Any]:
        from app.models.all_models import (
            Appointment,
            Invoice,
            Patient,
            Visit,
        )

        today = _today()
        start = _start_of_today()
        end = start + timedelta(days=1)

        return {
            "date": today.isoformat(),
            "new_patients_today": _safe_count(
                self.db,
                Patient,
                Patient.is_deleted.is_(False),
                Patient.date_created >= start,
                Patient.date_created < end,
            ),
            "visits_today": _safe_count(
                self.db,
                Visit,
                Visit.is_deleted.is_(False),
                Visit.date_created >= start,
                Visit.date_created < end,
            ),
            "appointments_today": _safe_count(
                self.db,
                Appointment,
                Appointment.is_deleted.is_(False),
                Appointment.scheduled_start_at >= start,
                Appointment.scheduled_start_at < end,
            ),
            "revenue_today": float(
                _safe_sum(
                    self.db,
                    Invoice.amount_paid,
                    Invoice.is_deleted.is_(False),
                    Invoice.invoice_date >= start,
                    Invoice.invoice_date < end,
                )
            ),
        }

    # ------------------------------------------------------------------
    # Patients
    # ------------------------------------------------------------------

    def patient_summary(self) -> dict[str, Any]:
        from app.models.all_models import Patient

        total = _safe_count(self.db, Patient, Patient.is_deleted.is_(False))
        new_this_month = _safe_count(
            self.db,
            Patient,
            Patient.is_deleted.is_(False),
            Patient.date_created >= _start_of_month(),
        )
        return {"total": total, "new_this_month": new_this_month}

    # ------------------------------------------------------------------
    # Visits + queue
    # ------------------------------------------------------------------

    def visit_summary(self) -> dict[str, Any]:
        from app.core.enums import VisitStatus
        from app.models.all_models import Visit

        return {
            "total_today": _safe_count(
                self.db,
                Visit,
                Visit.is_deleted.is_(False),
                Visit.date_created >= _start_of_today(),
            ),
            "in_progress": _safe_count(
                self.db,
                Visit,
                Visit.is_deleted.is_(False),
                Visit.status == VisitStatus.IN_PROGRESS,
            ),
            "completed_today": _safe_count(
                self.db,
                Visit,
                Visit.is_deleted.is_(False),
                Visit.status == VisitStatus.COMPLETED,
                Visit.date_updated >= _start_of_today(),
            ),
        }

    # ------------------------------------------------------------------
    # Appointments
    # ------------------------------------------------------------------

    def appointment_summary(self) -> dict[str, Any]:
        from app.core.enums import AppointmentStatus
        from app.models.all_models import Appointment

        start = _start_of_today()
        end = start + timedelta(days=1)
        statuses = {
            "scheduled": AppointmentStatus.SCHEDULED if hasattr(AppointmentStatus, "SCHEDULED") else None,
            "completed": AppointmentStatus.COMPLETED if hasattr(AppointmentStatus, "COMPLETED") else None,
            "cancelled": AppointmentStatus.CANCELLED if hasattr(AppointmentStatus, "CANCELLED") else None,
            "no_show": AppointmentStatus.MISSED if hasattr(AppointmentStatus, "MISSED") else None,
        }
        out: dict[str, int] = {}
        for label, status in statuses.items():
            if status is None:
                out[label] = 0
                continue
            out[label] = _safe_count(
                self.db,
                Appointment,
                Appointment.is_deleted.is_(False),
                Appointment.scheduled_start_at >= start,
                Appointment.scheduled_start_at < end,
                Appointment.status == status,
            )
        return out

    # ------------------------------------------------------------------
    # Inpatient + bed occupancy
    # ------------------------------------------------------------------

    def inpatient_summary(self) -> dict[str, Any]:
        try:
            from app.models.all_models import Admission, Bed
        except Exception:
            return {}

        admitted = _safe_count(
            self.db,
            Admission,
            Admission.is_deleted.is_(False),
            getattr(Admission, "admission_status", None).in_(["ADMITTED", "IN_HOUSE"])
            if hasattr(Admission, "admission_status")
            else True,
        ) if hasattr(Admission, "admission_status") else _safe_count(
            self.db, Admission, Admission.is_deleted.is_(False)
        )

        discharged_today = _safe_count(
            self.db,
            Admission,
            Admission.is_deleted.is_(False),
            getattr(Admission, "date_updated") >= _start_of_today()
            if hasattr(Admission, "date_updated")
            else True,
        )

        total_beds = _safe_count(self.db, Bed, Bed.is_deleted.is_(False))
        # Occupied beds — treat anything with a non-null current_admission_id
        # or status == OCCUPIED as occupied. We try whichever attribute the
        # model exposes.
        occupied = 0
        try:
            if hasattr(Bed, "current_admission_id"):
                occupied = _safe_count(
                    self.db,
                    Bed,
                    Bed.is_deleted.is_(False),
                    Bed.current_admission_id.isnot(None),
                )
            elif hasattr(Bed, "status"):
                occupied = _safe_count(
                    self.db,
                    Bed,
                    Bed.is_deleted.is_(False),
                    Bed.status == "OCCUPIED",
                )
        except Exception:
            occupied = 0

        utilisation = round(100.0 * occupied / total_beds, 1) if total_beds else 0.0
        return {
            "admitted": admitted,
            "discharged_today": discharged_today,
            "total_beds": total_beds,
            "occupied_beds": occupied,
            "utilisation_pct": utilisation,
        }

    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------

    def billing_summary(self) -> dict[str, Any]:
        from app.models.all_models import Invoice

        total_billed_mtd = float(
            _safe_sum(
                self.db,
                Invoice.total_amount,
                Invoice.is_deleted.is_(False),
                Invoice.invoice_date >= _start_of_month(),
            )
        )
        total_collected_mtd = float(
            _safe_sum(
                self.db,
                Invoice.amount_paid,
                Invoice.is_deleted.is_(False),
                Invoice.invoice_date >= _start_of_month(),
            )
        )
        outstanding = float(
            _safe_sum(
                self.db,
                Invoice.balance_due,
                Invoice.is_deleted.is_(False),
                Invoice.balance_due > 0,
            )
        )
        unpaid_count = _safe_count(
            self.db,
            Invoice,
            Invoice.is_deleted.is_(False),
            Invoice.balance_due > 0,
        )
        return {
            "billed_this_month": total_billed_mtd,
            "collected_this_month": total_collected_mtd,
            "outstanding_total": outstanding,
            "unpaid_invoice_count": unpaid_count,
        }

    # ------------------------------------------------------------------
    # Lab + pharmacy backlog
    # ------------------------------------------------------------------

    def lab_pharmacy_backlog(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        try:
            from app.core.enums import OrderStatus
            from app.models.all_models import LabOrder

            out["lab_orders_pending"] = _safe_count(
                self.db,
                LabOrder,
                LabOrder.is_deleted.is_(False),
                getattr(LabOrder, "status", None) == OrderStatus.PENDING
                if hasattr(LabOrder, "status")
                else True,
            )
        except Exception:
            out["lab_orders_pending"] = 0

        try:
            from app.core.enums import PrescriptionStatus
            from app.models.all_models import Prescription

            out["prescriptions_pending"] = _safe_count(
                self.db,
                Prescription,
                Prescription.is_deleted.is_(False),
                Prescription.status == PrescriptionStatus.PRESCRIBED,
            )
        except Exception:
            out["prescriptions_pending"] = 0

        try:
            from app.core.enums import DispenseStatus
            from app.models.all_models import Dispense

            out["dispenses_pending"] = _safe_count(
                self.db,
                Dispense,
                Dispense.is_deleted.is_(False),
                Dispense.status == DispenseStatus.PENDING,
            )
        except Exception:
            out["dispenses_pending"] = 0

        return out

    # ------------------------------------------------------------------
    # Inventory alerts
    # ------------------------------------------------------------------

    def inventory_alerts(self) -> dict[str, Any]:
        try:
            from app.models.all_models import InventoryItem
        except Exception:
            return {"low_stock_count": 0, "expiring_soon_count": 0}

        low_stock = 0
        expiring_soon = 0
        try:
            if hasattr(InventoryItem, "quantity_on_hand") and hasattr(InventoryItem, "reorder_level"):
                low_stock = (
                    self.db.query(func.count(InventoryItem.id))
                    .filter(
                        InventoryItem.is_deleted.is_(False),
                        InventoryItem.quantity_on_hand <= InventoryItem.reorder_level,
                    )
                    .scalar()
                    or 0
                )
        except Exception:
            pass

        try:
            if hasattr(InventoryItem, "expiry_date"):
                expiring_soon = _safe_count(
                    self.db,
                    InventoryItem,
                    InventoryItem.is_deleted.is_(False),
                    InventoryItem.expiry_date.isnot(None),
                    InventoryItem.expiry_date <= _today() + timedelta(days=30),
                )
        except Exception:
            pass

        return {"low_stock_count": int(low_stock), "expiring_soon_count": int(expiring_soon)}

    # ------------------------------------------------------------------
    # HR summary
    # ------------------------------------------------------------------

    def hr_summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        try:
            from app.core.enums import EmploymentStatus
            from app.models.all_models import StaffProfile

            out["total_staff"] = _safe_count(
                self.db, StaffProfile, StaffProfile.is_deleted.is_(False)
            )
            out["staff_active"] = _safe_count(
                self.db,
                StaffProfile,
                StaffProfile.is_deleted.is_(False),
                StaffProfile.employment_status == EmploymentStatus.ACTIVE,
            )
            out["staff_on_leave"] = _safe_count(
                self.db,
                StaffProfile,
                StaffProfile.is_deleted.is_(False),
                StaffProfile.employment_status == EmploymentStatus.ON_LEAVE,
            )
        except Exception:
            out.setdefault("total_staff", 0)

        try:
            from app.core.enums import LeaveStatus
            from app.models.all_models import LeaveRequest

            out["leave_requests_pending"] = _safe_count(
                self.db,
                LeaveRequest,
                LeaveRequest.is_deleted.is_(False),
                LeaveRequest.status == LeaveStatus.PENDING,
            )
        except Exception:
            out["leave_requests_pending"] = 0

        try:
            from app.core.enums import LicenseStatus
            from app.models.all_models import StaffLicense

            out["licenses_expiring_soon"] = _safe_count(
                self.db,
                StaffLicense,
                StaffLicense.is_deleted.is_(False),
                StaffLicense.status == LicenseStatus.PENDING_RENEWAL,
            )
            out["licenses_expired"] = _safe_count(
                self.db,
                StaffLicense,
                StaffLicense.is_deleted.is_(False),
                StaffLicense.status == LicenseStatus.EXPIRED,
            )
        except Exception:
            out.setdefault("licenses_expiring_soon", 0)
            out.setdefault("licenses_expired", 0)

        try:
            from app.core.enums import PayrollRunStatus
            from app.models.all_models import PayrollRun

            out["payroll_runs_pending_approval"] = _safe_count(
                self.db,
                PayrollRun,
                PayrollRun.is_deleted.is_(False),
                PayrollRun.status == PayrollRunStatus.CALCULATED,
            )
        except Exception:
            out["payroll_runs_pending_approval"] = 0

        return out

    # ------------------------------------------------------------------
    # Medication adherence
    # ------------------------------------------------------------------

    def medication_adherence_summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        try:
            from app.core.enums import RefillStatus
            from app.models.all_models import (
                AdherenceAlert,
                MedicationSchedule,
                RefillRecord,
            )

            out["active_schedules"] = _safe_count(
                self.db,
                MedicationSchedule,
                MedicationSchedule.is_deleted.is_(False),
            )
            out["unacknowledged_alerts"] = _safe_count(
                self.db,
                AdherenceAlert,
                AdherenceAlert.is_deleted.is_(False),
                AdherenceAlert.is_acknowledged.is_(False),
            )
            out["refills_overdue"] = _safe_count(
                self.db,
                RefillRecord,
                RefillRecord.is_deleted.is_(False),
                RefillRecord.status == RefillStatus.OVERDUE,
            )
        except Exception:
            out.setdefault("active_schedules", 0)
            out.setdefault("unacknowledged_alerts", 0)
            out.setdefault("refills_overdue", 0)
        return out

    # ------------------------------------------------------------------
    # Activity feed
    # ------------------------------------------------------------------

    def recent_activity(self, *, limit: int = 20) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        try:
            from app.models.all_models import Patient

            for p in (
                self.db.query(Patient)
                .filter(Patient.is_deleted.is_(False))
                .order_by(Patient.date_created.desc())
                .limit(limit)
                .all()
            ):
                events.append({
                    "type": "patient_registered",
                    "label": f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip(),
                    "occurred_at": p.date_created.isoformat() if p.date_created else None,
                })
        except Exception:
            pass

        try:
            from app.models.all_models import Visit

            for v in (
                self.db.query(Visit)
                .filter(Visit.is_deleted.is_(False))
                .order_by(Visit.date_created.desc())
                .limit(limit)
                .all()
            ):
                events.append({
                    "type": "visit_started",
                    "patient_id": getattr(v, "patient_id", None),
                    "occurred_at": v.date_created.isoformat() if v.date_created else None,
                })
        except Exception:
            pass

        try:
            from app.models.all_models import Payment

            for p in (
                self.db.query(Payment)
                .filter(Payment.is_deleted.is_(False))
                .order_by(Payment.paid_at.desc())
                .limit(limit)
                .all()
            ):
                events.append({
                    "type": "payment_received",
                    "amount": float(p.amount or 0),
                    "method": p.payment_method,
                    "occurred_at": p.paid_at.isoformat() if p.paid_at else None,
                })
        except Exception:
            pass

        events.sort(key=lambda e: e.get("occurred_at") or "", reverse=True)
        return events[:limit]
