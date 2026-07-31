# app/utils/invoice_pdf.py
"""Branded visit invoice / billing statement PDF: charges grouped by service
category, payments received, and the outstanding balance — with hospital
identity and a QR verification code."""
from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fpdf import FPDF

_INK = (15, 23, 42)
_MUTED = (110, 120, 135)
_LINE = (215, 220, 228)
_EMERALD = (5, 150, 105)
_ROSE = (225, 29, 72)


def _a(t: Any) -> str:
    if t is None:
        return ""
    return (str(t).replace("₦", "NGN ").replace("—", "-").replace("–", "-")
            .encode("latin-1", "replace").decode("latin-1"))


def _money(v: Any) -> str:
    try:
        return f"{Decimal(str(v or 0)):,.2f}"
    except Exception:
        return "0.00"


def _fmt_dt(v: Any) -> str:
    return v.strftime("%d %b %Y %H:%M") if isinstance(v, datetime) else (str(v) if v else "-")


def invoice_verify_code(billing_no: str, total: Any) -> str:
    return hashlib.sha256(f"CPHMS-INV|{billing_no}|{total}".encode()).hexdigest()[:10].upper()


def _qr_png(payload: str) -> Optional[str]:
    try:
        import qrcode
        img = qrcode.make(payload)
        fd, path = tempfile.mkstemp(suffix=".png", prefix="invqr_")
        os.close(fd)
        img.save(path)
        return path
    except Exception:
        return None


def build_invoice_pdf(*, hospital_name: str, hospital_contact: Optional[str],
                      logo_path: Optional[str], patient: dict,
                      visit_number: Optional[str], billing_no: str,
                      generated_at: Any, grouped_items: list[tuple[str, list[dict]]],
                      gross: Any, discount: Any, total: Any, paid: Any,
                      outstanding: Any, payments: list[dict],
                      verify_code: str) -> bytes:
    """``grouped_items``: [(category, [{name, code, qty, unit_price, line_total,
    rendered_at}])]; ``payments``: [{amount, method, paid_at, reference}]."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()

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
    pdf.cell(120, 7, _a("VISIT INVOICE"))
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 7, _a(billing_no), ln=1, align="R")

    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(120, 5, _a(f"Patient: {patient.get('name')}  ({patient.get('hospital_number') or '-'})"))
    pdf.cell(0, 5, _a(f"Visit: {visit_number or '-'}"), ln=1, align="R")
    pdf.cell(120, 5, "")
    pdf.cell(0, 5, _a(f"Generated: {_fmt_dt(generated_at)}"), ln=1, align="R")
    pdf.ln(3)

    # Charges by category
    for category, rows in grouped_items:
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_text_color(*_EMERALD)
        pdf.cell(0, 6, _a(category.upper()), ln=1)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*_INK)
        for r in rows:
            pdf.set_draw_color(*_LINE)
            pdf.line(pdf.l_margin, pdf.get_y(), 200, pdf.get_y())
            pdf.cell(92, 6.5, _a(r.get("name"))[:52])
            pdf.cell(18, 6.5, _a(f"x{_money(r.get('qty'))}"), align="R")
            pdf.cell(35, 6.5, _a(_money(r.get("unit_price"))), align="R")
            pdf.cell(0, 6.5, _a(_money(r.get("line_total"))), ln=1, align="R")
        pdf.ln(1)

    pdf.line(pdf.l_margin, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)

    def totals_row(label: str, value: Any, *, bold=False, color=_INK):
        pdf.set_font("Arial", "B" if bold else "", 9.5 if bold else 9)
        pdf.set_text_color(*color)
        pdf.cell(145, 6, _a(label), align="R")
        pdf.cell(0, 6, _a(_money(value)), ln=1, align="R")

    totals_row("Gross", gross)
    if Decimal(str(discount or 0)) > 0:
        totals_row("Discount", f"-{_money(discount)}")
    totals_row("TOTAL", total, bold=True)
    totals_row("Paid", paid, color=_EMERALD)
    totals_row("OUTSTANDING", outstanding, bold=True,
               color=_ROSE if Decimal(str(outstanding or 0)) > 0 else _EMERALD)
    pdf.ln(3)

    if payments:
        pdf.set_font("Arial", "B", 8.5)
        pdf.set_text_color(*_EMERALD)
        pdf.cell(0, 6, _a("PAYMENTS RECEIVED"), ln=1)
        pdf.set_font("Arial", "", 8.5)
        pdf.set_text_color(*_INK)
        for p in payments:
            pdf.cell(60, 5.5, _a(_fmt_dt(p.get("paid_at"))))
            pdf.cell(50, 5.5, _a(p.get("method")))
            pdf.cell(45, 5.5, _a(p.get("reference") or ""))
            pdf.cell(0, 5.5, _a(_money(p.get("amount"))), ln=1, align="R")
        pdf.ln(2)

    qr_path = _qr_png(f"CarePoint HMS Invoice | {billing_no} | VERIFY:{verify_code}")
    try:
        if qr_path:
            pdf.image(qr_path, x=175, y=pdf.get_y(), w=22)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 5, _a(f"Verification code: {verify_code}"), ln=1)
        pdf.set_font("Arial", "", 7.5)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(150, 4, _a(
            "System-generated invoice. Present the code or scan the QR at the "
            "issuing hospital to authenticate. Amounts in NGN."))
    finally:
        if qr_path:
            try:
                os.remove(qr_path)
            except OSError:
                pass

    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out, str) else bytes(out)
