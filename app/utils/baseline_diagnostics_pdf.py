# app/utils/baseline_diagnostics_pdf.py
"""Branded **Baseline Diagnostic Profile** report PDF.

The patient's lifelong, visit-independent clinical characteristics — blood
group, genotype, rhesus factor, G6PD, infectious-disease screening, metabolic
baselines, clinical alerts and immunisation status — laid out as verifiable
diagnostic records with a QR/verification code, hospital branding and a
confidentiality notice. Suitable for digital sharing and high-quality print.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime
from typing import Any, Optional

from fpdf import FPDF

_INK = (15, 23, 42)
_MUTED = (110, 120, 135)
_LINE = (215, 220, 228)
_EMERALD = (5, 150, 105)
_ROSE = (225, 29, 72)
_AMBER = (180, 120, 10)
_SOFT = (247, 249, 251)


def _a(t: Any) -> str:
    """Latin-1 safe text for the core PDF fonts."""
    if t is None:
        return ""
    return (str(t).replace("₦", "NGN ").replace("—", "-").replace("–", "-")
            .replace("’", "'").replace("“", '"').replace("”", '"')
            .encode("latin-1", "replace").decode("latin-1"))


def _fmt_dt(v: Any) -> str:
    if isinstance(v, datetime):
        return v.strftime("%d %b %Y %H:%M")
    return str(v) if v else "-"


def _fmt_date(v: Any) -> str:
    if isinstance(v, datetime):
        return v.strftime("%d %b %Y")
    return str(v) if v else "-"


def baseline_verify_code(reference: str, version: Any) -> str:
    """Deterministic verification code for a baseline profile snapshot."""
    return hashlib.sha256(
        f"CPHMS-BDP|{reference}|{version}".encode()
    ).hexdigest()[:10].upper()


def _qr_png(payload: str) -> Optional[str]:
    try:
        import qrcode
        img = qrcode.make(payload)
        fd, path = tempfile.mkstemp(suffix=".png", prefix="bdpqr_")
        os.close(fd)
        img.save(path)
        return path
    except Exception:
        return None


def _status_color(status: Optional[str]) -> tuple:
    s = (status or "").upper()
    if s == "VERIFIED":
        return _EMERALD
    if s == "NOT_RECORDED":
        return _MUTED
    return _AMBER  # RECORDED / on file, not clinician-verified


def _status_label(status: Optional[str]) -> str:
    s = (status or "").upper()
    return {
        "VERIFIED": "Verified",
        "RECORDED": "On record",
        "NOT_RECORDED": "Not recorded",
    }.get(s, s.title() or "-")


def build_baseline_diagnostics_pdf(
    *,
    hospital_name: str,
    hospital_contact: Optional[str],
    logo_path: Optional[str],
    patient: dict,
    generated_at: Any,
    version: Any,
    recorded_at: Any,
    updated_at: Any,
    primary_physician_name: Optional[str],
    categories: list[dict],
    verify_code: str,
) -> bytes:
    """``categories``: [{"name": str, "records": [{"label", "value",
    "interpretation", "verification_status", "verified_by", "updated_at"}]}].
    Only records with a value are rendered."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=22)
    pdf.add_page()
    right = 200.0

    # ---- Header: logo + hospital identity ----
    text_x = pdf.l_margin
    if logo_path:
        try:
            pdf.image(logo_path, x=pdf.l_margin, y=10, h=16)
            text_x = pdf.l_margin + 20
        except Exception:
            text_x = pdf.l_margin
    pdf.set_xy(text_x, 10)
    pdf.set_font("Arial", "B", 15)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 7, _a(hospital_name), ln=1)
    pdf.set_x(text_x)
    pdf.set_font("Arial", "", 8.5)
    pdf.set_text_color(*_MUTED)
    if hospital_contact:
        pdf.cell(0, 4.5, _a(hospital_contact), ln=1)
    if pdf.get_y() < 28:
        pdf.set_y(28)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y() + 1, right, pdf.get_y() + 1)
    pdf.ln(4)

    # ---- Title ----
    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(*_INK)
    pdf.cell(120, 7, _a("BASELINE DIAGNOSTIC PROFILE"))
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 7, _a(f"Version {version}"), ln=1, align="R")

    # ---- Patient identity block ----
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*_MUTED)
    name = patient.get("name") or "-"
    hosp_no = patient.get("hospital_number") or "-"
    gid = patient.get("global_patient_id") or "-"
    dob = _fmt_date(patient.get("date_of_birth"))
    gender = patient.get("gender") or "-"
    pdf.cell(120, 5, _a(f"Patient: {name}"))
    pdf.cell(0, 5, _a(f"Hospital No: {hosp_no}"), ln=1, align="R")
    pdf.cell(120, 5, _a(f"Patient ID: {gid}"))
    pdf.cell(0, 5, _a(f"Date of birth: {dob}"), ln=1, align="R")
    pdf.cell(120, 5, _a(f"Gender: {gender}"))
    pdf.cell(0, 5, _a(f"Generated: {_fmt_dt(generated_at)}"), ln=1, align="R")
    if primary_physician_name:
        pdf.cell(0, 5, _a(f"Primary physician: {primary_physician_name}"), ln=1)
    pdf.ln(2)

    # ---- Column layout ----
    col_label = 55.0
    col_value = 63.0
    col_status = 28.0
    col_updated = right - pdf.l_margin - col_label - col_value - col_status

    def category_header(title: str) -> None:
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_text_color(*_EMERALD)
        pdf.set_fill_color(*_SOFT)
        pdf.cell(0, 6.5, _a(title.upper()), ln=1, fill=True)
        pdf.set_font("Arial", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(col_label, 5, _a("DIAGNOSTIC"))
        pdf.cell(col_value, 5, _a("VALUE"))
        pdf.cell(col_status, 5, _a("STATUS"))
        pdf.cell(col_updated, 5, _a("UPDATED"), ln=1)

    rendered_any = False
    for cat in categories:
        records = [r for r in (cat.get("records") or []) if r.get("value")]
        if not records:
            continue
        rendered_any = True
        # Keep header with at least one row.
        if pdf.get_y() > 250:
            pdf.add_page()
        category_header(cat.get("name") or "Records")
        for r in records:
            pdf.set_draw_color(*_LINE)
            y0 = pdf.get_y()
            pdf.line(pdf.l_margin, y0, right, y0)

            label = _a(r.get("label"))
            value = _a(r.get("value"))
            interp = r.get("interpretation")
            status = r.get("verification_status")
            updated = _fmt_date(r.get("updated_at"))

            # Compute wrapped height for the value cell (+ interpretation line).
            pdf.set_font("Arial", "", 8.5)
            value_lines = pdf.multi_cell(col_value, 5, value, split_only=True) or [value]
            n_lines = max(1, len(value_lines))
            row_h = 5 * n_lines + 2
            if interp:
                pdf.set_font("Arial", "I", 7)
                interp_lines = pdf.multi_cell(col_value, 4, _a(interp),
                                              split_only=True) or [interp]
                row_h += 4 * max(1, len(interp_lines))

            x0 = pdf.l_margin
            # Label
            pdf.set_xy(x0, y0 + 1)
            pdf.set_font("Arial", "B", 8.5)
            pdf.set_text_color(*_INK)
            pdf.multi_cell(col_label, 5, label[:60])
            # Value (+ interpretation)
            pdf.set_xy(x0 + col_label, y0 + 1)
            pdf.set_font("Arial", "", 8.5)
            pdf.set_text_color(*_INK)
            pdf.multi_cell(col_value, 5, value)
            if interp:
                pdf.set_x(x0 + col_label)
                pdf.set_font("Arial", "I", 7)
                pdf.set_text_color(*_MUTED)
                pdf.multi_cell(col_value, 4, _a(interp))
            # Status
            pdf.set_xy(x0 + col_label + col_value, y0 + 1)
            pdf.set_font("Arial", "B", 7.5)
            pdf.set_text_color(*_status_color(status))
            pdf.cell(col_status, 5, _a(_status_label(status)))
            # Updated
            pdf.set_font("Arial", "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(col_updated, 5, _a(updated))

            pdf.set_xy(x0, y0 + row_h)
        pdf.ln(2)

    if not rendered_any:
        pdf.set_font("Arial", "I", 9.5)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(0, 6, _a(
            "No baseline diagnostic records have been captured yet. Your "
            "hospital will populate this profile as your baseline clinical "
            "information is confirmed."))

    # ---- Footer: verification + confidentiality ----
    if pdf.get_y() > 240:
        pdf.add_page()
    else:
        pdf.ln(3)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), right, pdf.get_y())
    pdf.ln(3)

    qr_path = _qr_png(
        f"CarePoint HMS Baseline Diagnostic Profile | {patient.get('global_patient_id') or ''} "
        f"| v{version} | VERIFY:{verify_code}"
    )
    try:
        if qr_path:
            pdf.image(qr_path, x=right - 24, y=pdf.get_y(), w=22)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 5, _a(f"Verification code: {verify_code}"), ln=1)
        pdf.set_font("Arial", "", 7.5)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(150, 4, _a(
            "This Baseline Diagnostic Profile is a system-generated summary of "
            "the patient's enduring clinical information, maintained "
            "independently of visit-specific investigations. Present the code "
            "or scan the QR at the issuing hospital to authenticate."))
        pdf.ln(1)
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(*_ROSE)
        pdf.multi_cell(150, 4, _a(
            "CONFIDENTIAL MEDICAL RECORD. This document contains protected "
            "health information intended solely for the patient and authorised "
            "healthcare providers. Unauthorised access, use or disclosure is "
            "prohibited."))
    finally:
        if qr_path:
            try:
                os.remove(qr_path)
            except OSError:
                pass

    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out, str) else bytes(out)
