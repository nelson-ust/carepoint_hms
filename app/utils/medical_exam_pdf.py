# app/utils/medical_exam_pdf.py
"""Branded Medical Examination (fitness assessment) report PDF."""
from __future__ import annotations

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
_AMBER = (217, 119, 6)

_FITNESS_LABEL = {
    "FIT": ("MEDICALLY FIT", _EMERALD),
    "FIT_WITH_RESTRICTIONS": ("MEDICALLY FIT WITH RESTRICTIONS", _AMBER),
    "TEMPORARILY_UNFIT": ("TEMPORARILY UNFIT", _AMBER),
    "PERMANENTLY_UNFIT": ("PERMANENTLY UNFIT", _ROSE),
}


def _a(t: Any) -> str:
    if t is None:
        return ""
    return (str(t).replace("₦", "NGN ").replace("—", "-").replace("–", "-")
            .encode("latin-1", "replace").decode("latin-1"))


def _fmt_dt(v: Any) -> str:
    return v.strftime("%d %b %Y") if isinstance(v, datetime) else (str(v) if v else "-")


def _qr_png(payload: str) -> Optional[str]:
    try:
        import qrcode
        img = qrcode.make(payload)
        fd, path = tempfile.mkstemp(suffix=".png", prefix="mexqr_")
        os.close(fd)
        img.save(path)
        return path
    except Exception:
        return None


def build_medical_exam_report_pdf(*, hospital_name: str, hospital_contact: Optional[str],
                                  logo_path: Optional[str], exam_no: str, exam_type: str,
                                  package_name: str, patient: dict,
                                  visit_number: Optional[str], examined_at: Any,
                                  rows: list[dict], clinical_findings: Optional[str],
                                  recommendations: Optional[str],
                                  restrictions: Optional[str], fitness_status: str,
                                  physician_name: Optional[str],
                                  designation: Optional[str],
                                  license_no: Optional[str], verify_code: str) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()

    # Header
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
    pdf.line(pdf.l_margin, pdf.get_y() + 1, 200, pdf.get_y() + 1)
    pdf.ln(4)

    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 7, _a("MEDICAL EXAMINATION REPORT"), ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 5, _a(f"{exam_type.replace('_', ' ').title()} — {package_name}"), ln=1)
    pdf.ln(2)

    def kv(label, value, w=95):
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(32, 5.5, _a(label))
        pdf.set_text_color(*_INK)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(w - 32, 5.5, _a(value))

    y0 = pdf.get_y()
    kv("Patient", patient.get("name")); pdf.ln(5.5)
    kv("Hospital No.", patient.get("hospital_number")); pdf.ln(5.5)
    kv("DOB / Sex", f"{patient.get('date_of_birth') or '-'} / {patient.get('gender') or '-'}"); pdf.ln(5.5)
    pdf.set_xy(115, y0); kv("Report No.", exam_no, w=85)
    pdf.set_xy(115, y0 + 5.5); kv("Visit No.", visit_number, w=85)
    pdf.set_xy(115, y0 + 11); kv("Examined", _fmt_dt(examined_at), w=85)
    pdf.ln(8)

    # Fitness determination banner
    label, color = _FITNESS_LABEL.get(fitness_status, (fitness_status, _INK))
    pdf.set_fill_color(*[min(255, c + 190) if c < 60 else 235 for c in (0, 0, 0)])
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(*color)
    pdf.cell(0, 10, _a(f"DETERMINATION: {label}"), ln=1, fill=False, border=1)
    pdf.ln(3)

    # Investigations summary
    if rows:
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_text_color(*_EMERALD)
        widths = (70, 45, 20, 55)
        for w, h in zip(widths, ("INVESTIGATION", "RESULT", "UNIT", "REFERENCE RANGE")):
            pdf.cell(w, 6, _a(h))
        pdf.ln(6)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*_INK)
        for r in rows:
            pdf.set_draw_color(*_LINE)
            pdf.line(pdf.l_margin, pdf.get_y(), 200, pdf.get_y())
            for w, v in zip(widths, (r.get("test"), r.get("result"),
                                     r.get("unit"), r.get("reference_range"))):
                pdf.cell(w, 6.5, _a(v)[:int(w / 1.8)])
            pdf.ln(6.5)
        pdf.line(pdf.l_margin, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

    def block(title: str, body: Optional[str]):
        if not body:
            return
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(*_EMERALD)
        pdf.cell(0, 5.5, _a(title.upper()), ln=1)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 5, _a(body))
        pdf.ln(1.5)

    block("Clinical assessment", clinical_findings)
    block("Recommendations", recommendations)
    block("Restrictions / limitations", restrictions)

    # Sign-off
    if pdf.get_y() > 235:
        pdf.add_page()
    pdf.ln(4)
    pdf.set_font("Arial", "B", 9.5)
    pdf.set_text_color(*_INK)
    pdf.cell(0, 5.5, _a(physician_name or "-"), ln=1)
    pdf.set_font("Arial", "", 8.5)
    pdf.set_text_color(*_MUTED)
    meta = " · ".join(x for x in (designation, f"Licence: {license_no}" if license_no else None) if x)
    if meta:
        pdf.cell(0, 4.5, _a(meta), ln=1)
    pdf.set_draw_color(*_INK)
    pdf.line(pdf.l_margin, pdf.get_y() + 9, pdf.l_margin + 70, pdf.get_y() + 9)
    pdf.set_y(pdf.get_y() + 10)
    pdf.set_font("Arial", "", 7.5)
    pdf.cell(0, 4, _a("Reviewing physician (signature)"), ln=1)
    pdf.ln(3)

    qr_path = _qr_png(f"CarePoint HMS Medical Exam | {exam_no} | VERIFY:{verify_code}")
    try:
        if qr_path:
            pdf.image(qr_path, x=175, y=pdf.get_y(), w=22)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 5, _a(f"Verification code: {verify_code}"), ln=1)
        pdf.set_font("Arial", "", 7.5)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(150, 4, _a(
            "Present this code (or scan the QR) to the issuing hospital to "
            "authenticate this report. Generated electronically by CarePoint "
            "HMS; invalid if altered."))
    finally:
        if qr_path:
            try:
                os.remove(qr_path)
            except OSError:
                pass

    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out, str) else bytes(out)
