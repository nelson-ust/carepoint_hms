# app/services/approval_notifications.py
"""
Submission emails for the approval engine.

When a request is submitted into a flow, two branded emails go out
(best-effort — a mail failure never breaks the submission):

* to the hand-picked first-step approver — "this request needs your action";
* to the requester — "your request is now with <approver> for approval".

Both use the tenant-branded HTML template in ``app.utils.email_utils`` and
carry a CTA that deep-links to the request's progress page.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

if TYPE_CHECKING:  # pragma: no cover
    from app.models.all_models import ApprovalRequest, ApprovalStep, User

logger = logging.getLogger(__name__)


def _display_name(user: Optional["User"]) -> str:
    if user is None:
        return "your approver"
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.username or user.email


def _type_label(code: str) -> str:
    return (code or "").replace("_", " ").title()


def _request_url(request_id: int) -> Optional[str]:
    try:
        from app.core.config import settings
        base = (getattr(settings, "FRONTEND_URL", None) or "").rstrip("/")
        return f"{base}/approvals/requests/{request_id}" if base else None
    except Exception:  # pragma: no cover - defensive
        return None


def _brand_name() -> Optional[str]:
    try:
        from app.core.multitenancy import get_current_tenant
        tenant = get_current_tenant()
        return tenant.name if tenant else None
    except Exception:  # pragma: no cover - defensive
        return None


def _fmt_dt(value) -> str:
    try:
        return value.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return str(value or "—")


def send_submission_emails(db: Session, req: "ApprovalRequest", *, first_step: "ApprovalStep") -> None:
    """Send the approver + requester submission emails for ``req``."""
    from app.models.all_models import User
    from app.schemas.notification_schema import NotificationAdHocDispatchSchema
    from app.services.notification_service import NotificationService
    from app.utils.email_utils import render_branded_email

    requester = db.query(User).filter(User.id == req.requester_user_id).first()
    approver = (
        db.query(User).filter(User.id == req.assigned_approver_user_id).first()
        if req.assigned_approver_user_id else None
    )

    brand = _brand_name()
    url = _request_url(req.id)
    type_label = _type_label(req.request_type_code)
    requester_name = _display_name(requester)
    approver_name = _display_name(approver)
    flow_name = getattr(req.flow, "name", None) or "Approval flow"

    details = [
        ("Request", f"#{req.id} — {req.title}"),
        ("Type", type_label),
        ("Requested by", requester_name),
        ("Submitted", _fmt_dt(req.submitted_at)),
        ("Approval flow", flow_name),
        ("Current step", f"Step {first_step.step_order} — {first_step.name}"),
    ]
    # Append the subject snapshot (what is actually being approved).
    if isinstance(req.payload, dict):
        for key, value in list(req.payload.items())[:8]:
            if value is None or str(value).strip() == "":
                continue
            label = str(key).replace("_", " ").strip().title()
            details.append((label, str(value)))

    notifier = NotificationService(db)

    # ── 1) Approver: "you need to action this" ──────────────────────
    if approver is not None:
        subject = f"Action needed: {type_label} request from {requester_name}"
        text = (
            f"Hello {approver_name},\n\n"
            f"{requester_name} has submitted a {type_label} request "
            f"(\"{req.title}\") and selected you to review it.\n\n"
            f"It is now waiting at step {first_step.step_order} "
            f"({first_step.name}) of the {flow_name}.\n\n"
            f"Please sign in and either Approve it, Return it for correction, "
            f"or Reject it." + (f"\n\nReview it here: {url}" if url else "")
        )
        html = render_branded_email(
            title="A request needs your action",
            intro=(
                f"Hello {approver_name}, {requester_name} has submitted a "
                f"{type_label} request and selected you as the approver."
            ),
            body_paragraphs=[
                "The request is now sitting in your approval queue and will not "
                "progress until you act on it.",
                "From the request page you can approve it, return it to "
                f"{requester_name} for correction with a note, or reject it.",
            ],
            details=details,
            details_heading="Request summary",
            highlight_label="Status",
            highlight_value="Awaiting your action",
            highlight_caption=f"Step {first_step.step_order} · {first_step.name}",
            cta_label="Review & Take Action",
            cta_url=url,
            footer_note=(
                "You are receiving this email because you were selected as the "
                "approver for this request."
            ),
            preheader=f"{requester_name} needs your approval on a {type_label} request.",
            brand_name=brand,
        )
        try:
            notifier.dispatch_ad_hoc(
                NotificationAdHocDispatchSchema(
                    channel="EMAIL", subject=subject, body=text, body_html=html,
                    user_id=approver.id,
                ),
                actor_user_id=req.requester_user_id,
                raise_on_failure=False,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Approver email failed for request %s: %s", req.id, exc)

    # ── 2) Requester: "your request is with the approver" ───────────
    if requester is not None:
        with_whom = (
            f"It is now with {approver_name} for approval."
            if approver is not None
            else f"It is now awaiting the '{first_step.name}' approvers."
        )
        subject = f"Your {type_label} request has been submitted"
        text = (
            f"Hi {requester_name},\n\n"
            f"Your {type_label} request (\"{req.title}\") was submitted "
            f"successfully. {with_whom}\n\n"
            f"You will be notified as it progresses through the {flow_name}."
            + (f"\n\nTrack it here: {url}" if url else "")
        )
        html = render_branded_email(
            title="Your request is on its way",
            intro=(
                f"Hi {requester_name}, your {type_label} request was submitted "
                f"successfully. {with_whom}"
            ),
            body_paragraphs=[
                "No further action is needed from you right now. If the approver "
                "returns it for correction, you can amend it and resubmit.",
                "You can follow its progress step by step from the request page.",
            ],
            details=details,
            details_heading="Request summary",
            highlight_label="Status",
            highlight_value="In progress",
            highlight_caption=(
                f"With {approver_name}" if approver is not None
                else f"Awaiting {first_step.name}"
            ),
            cta_label="Track My Request",
            cta_url=url,
            footer_note="You are receiving this email because you submitted this request.",
            preheader=f"Your {type_label} request is now awaiting approval.",
            brand_name=brand,
        )
        try:
            notifier.dispatch_ad_hoc(
                NotificationAdHocDispatchSchema(
                    channel="EMAIL", subject=subject, body=text, body_html=html,
                    user_id=requester.id,
                ),
                actor_user_id=req.requester_user_id,
                raise_on_failure=False,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Requester email failed for request %s: %s", req.id, exc)
