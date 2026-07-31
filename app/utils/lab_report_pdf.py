# app/utils/lab_report_pdf.py
"""
Branded laboratory report PDF.

Renders a released lab order as a professional report: hospital identity
(logo, name, contact), laboratory name, patient block, visit + order
numbers, a results table (test / result / unit / reference range), specimen
and date details, interpretation, the reporting scientist's name with a
signature line, approval details and a QR verification code so the document
can be authenticated.
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


def _a(t: Any) -> str:
    if t is None:
        return ""
    return (str(t).replace("₦", "NGN ").replace("—", "-").replace("–", "-")
            .encode("latin-1", "replace").decode("latin-1"))


def _fmt_dt(v: Any) -> str:
    if isinstance(v, datetime):
        return v.strftime("%d %b %Y %H:%M")
    return str(v) if v else "-"


def verification_code(order_no: str, salt: str = "") -> str:
    """Deterministic 10-char verification code for a released report."""
    return hashlib.sha256(f"CPHMS-LAB|{order_no}|{salt}".encode()).hexdigest()[:10].upper()


def _qr_png(payload: str) -> Optional[str]:
    try:
        import qrcode
        img = qrcode.make(payload)
        fd, path = tempfile.mkstemp(suffix=".png", prefix="labqr_")
        os.close(fd)
        img.save(path)
        return path
    except Exception:
        return None


def build_lab_report_pdf(*, hospital_name: str, hospital_contact: Optional[str],
                         lab_name: str, logo_path: Optional[str],
                         patient: dict, visit_number: Optional[str],
                         order_no: str, ordered_at: Any, reported_at: Any,
                         rows: list[dict], interpretation: Optional[str],
                         scientist_name: Optional[str],
                         approved_by: Optional[str],
                         verify_code: str) -> bytes:
    """``rows``: {test, result, unit, reference_range, specimen, collected_at,
    flag} per released test."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()

    # ----- Header: logo + hospital identity --------------------------------
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
    pdf.set_x(text_x)
    pdf.set_text_color(*_EMERALD)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, _a(lab_name.upper()), ln=1)
    if pdf.get_y() < 30:
        pdf.set_y(30)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y() + 1, 200, pdf.get_y() + 1)
    pdf.ln(4)

    # ----- Title -----------------------------------------------------------
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 7, _a("LABORATORY REPORT"), ln=1)
    pdf.ln(1)

    # ----- Patient / order block ------------------------------------------
    pdf.set_font("Arial", "", 9)
    def kv(label: str, value: Any, w: float = 95) -> None:
        pdf.set_text_color(*_MUTED)
        pdf.cell(30, 5.5, _a(label))
        pdf.set_text_color(*_INK)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(w - 30, 5.5, _a(value))
        pdf.set_font("Arial", "", 9)

    y0 = pdf.get_y()
    kv("Patient", patient.get("name")); pdf.ln(5.5)
    kv("Hospital No.", patient.get("hospital_number")); pdf.ln(5.5)
    kv("DOB / Sex", f"{patient.get('date_of_birth') or '-'} / {patient.get('gender') or '-'}"); pdf.ln(5.5)
    kv("Blood group", f"{patient.get('blood_group') or '-'}  Genotype: {patient.get('genotype') or '-'}"); pdf.ln(5.5)
    pdf.set_xy(115, y0)
    kv("Visit No.", visit_number, w=85); pdf.set_xy(115, y0 + 5.5)
    kv("Request No.", order_no, w=85); pdf.set_xy(115, y0 + 11)
    kv("Requested", _fmt_dt(ordered_at), w=85); pdf.set_xy(115, y0 + 16.5)
    kv("Reported", _fmt_dt(reported_at), w=85)
    pdf.ln(8)
    pdf.line(pdf.l_margin, pdf.get_y() + 1, 200, pdf.get_y() + 1)
    pdf.ln(4)

    # ----- Results table ---------------------------------------------------
    pdf.set_font("Arial", "B", 8.5)
    pdf.set_text_color(*_EMERALD)
    widths = (62, 38, 20, 40, 30)
    for w, h in zip(widths, ("TEST", "RESULT", "UNIT", "REFERENCE RANGE", "SPECIMEN")):
        pdf.cell(w, 6, _a(h))
    pdf.ln(6)
    pdf.set_text_color(*_INK)
    pdf.set_font("Arial", "", 9)
    for r in rows:
        pdf.set_draw_color(*_LINE)
        pdf.line(pdf.l_margin, pdf.get_y(), 200, pdf.get_y())
        vals = (r.get("test"), r.get("result"), r.get("unit"),
                r.get("reference_range"), r.get("specimen"))
        for w, v in zip(widths, vals):
            pdf.cell(w, 6.5, _a(v)[:int(w / 1.8)])
        pdf.ln(6.5)
        if r.get("collected_at"):
            pdf.set_font("Arial", "", 7.5)
            pdf.set_text_color(*_MUTED)
            pdf.cell(0, 4, _a(f"   Collected: {_fmt_dt(r['collected_at'])}"), ln=1)
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(*_INK)
    pdf.line(pdf.l_margin, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # ----- Interpretation --------------------------------------------------
    if interpretation:
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(*_EMERALD)
        pdf.cell(0, 5.5, _a("INTERPRETATION"), ln=1)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 5, _a(interpretation))
        pdf.ln(2)

    # ----- Sign-off + verification ----------------------------------------
    y = pdf.get_y() + 6
    if y > 240:
        pdf.add_page()
        y = pdf.get_y() + 6
    pdf.set_y(y)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*_INK)
    pdf.cell(95, 5.5, _a(scientist_name or "-"), ln=0)
    if approved_by:
        pdf.cell(0, 5.5, _a(approved_by), ln=1)
    else:
        pdf.ln(5.5)
    pdf.set_draw_color(*_INK)
    pdf.line(pdf.l_margin, pdf.get_y() + 8, pdf.l_margin + 70, pdf.get_y() + 8)
    if approved_by:
        pdf.line(115, pdf.get_y() + 8, 185, pdf.get_y() + 8)
    pdf.set_y(pdf.get_y() + 9)
    pdf.set_font("Arial", "", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.cell(95, 4, _a("Reporting laboratory scientist (signature)"))
    if approved_by:
        pdf.cell(0, 4, _a("Approved by (signature)"), ln=1)
    else:
        pdf.ln(4)
    pdf.ln(4)

    qr_payload = f"CarePoint HMS Lab Report | {order_no} | VERIFY:{verify_code}"
    qr_path = _qr_png(qr_payload)
    try:
        if qr_path:
            pdf.image(qr_path, x=175, y=pdf.get_y(), w=22)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 5, _a(f"Verification code: {verify_code}"), ln=1)
        pdf.set_font("Arial", "", 7.5)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(150, 4, _a(
            "Present this code (or scan the QR) to the issuing laboratory to "
            "authenticate this report. This document was generated "
            "electronically by CarePoint HMS and is invalid if altered."))
    finally:
        if qr_path:
            try:
                os.remove(qr_path)
            except OSError:
                pass

    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out, str) else bytes(out)
