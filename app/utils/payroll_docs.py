# app/utils/payroll_docs.py
from __future__ import annotations

"""
Payroll document builders: payslip PDF (PyFPDF) and remittance CSVs
(bank transfer schedule, PAYE, pension incl. employer share, NHF).
"""

import csv
import io
from decimal import Decimal
from typing import Iterable, Optional

from fpdf import FPDF

_INK = (15, 23, 42)
_MUTED = (110, 120, 135)
_LINE = (215, 220, 228)
_EMERALD = (5, 150, 105)


def _a(t) -> str:
    if t is None:
        return ""
    return (str(t).replace("₦", "NGN ").replace("—", "-").replace("–", "-")
            .encode("latin-1", "replace").decode("latin-1"))


def _money(v) -> str:
    try:
        return f"{Decimal(str(v or 0)):,.2f}"
    except Exception:
        return "0.00"


def build_payslip_pdf(*, hospital_name: str, staff_name: str, staff_number: Optional[str],
                      department: Optional[str], period_label: str, line: dict,
                      logo_path: Optional[str] = None) -> bytes:
    """Render a single payslip. ``line`` mirrors PayrollLine fields + breakdown.
    ``logo_path`` is an optional pre-normalised PNG of the hospital logo."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    # Header (logo left, titles beside it when present)
    text_x = pdf.l_margin
    if logo_path:
        try:
            pdf.image(logo_path, x=pdf.l_margin, y=10, h=16)
            text_x = pdf.l_margin + 20
        except Exception:
            text_x = pdf.l_margin
    pdf.set_xy(text_x, 10)
    pdf.set_text_color(*_EMERALD)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, _a("PAYSLIP"), ln=1)
    pdf.set_x(text_x)
    pdf.set_text_color(*_INK)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, _a(hospital_name), ln=1)
    if logo_path:
        pdf.set_x(text_x)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 6, _a(f"Pay period: {period_label}"), ln=1)
    if logo_path and pdf.get_y() < 28:
        pdf.set_y(28)
    pdf.ln(2)

    # Staff block
    pdf.set_text_color(*_INK)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, _a(staff_name), ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(*_MUTED)
    meta = " · ".join(x for x in [staff_number, department] if x)
    if meta:
        pdf.cell(0, 5, _a(meta), ln=1)
    pdf.ln(3)

    def section(title: str, rows: Iterable[tuple[str, str]], total_label: str, total_val: str):
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(*_EMERALD)
        pdf.cell(0, 6, _a(title.upper()), ln=1)
        pdf.set_text_color(*_INK)
        pdf.set_font("Arial", "", 9.5)
        for label, val in rows:
            pdf.cell(120, 6, _a(label))
            pdf.cell(0, 6, _a(val), ln=1, align="R")
        pdf.set_draw_color(*_LINE)
        pdf.line(pdf.get_x(), pdf.get_y() + 1, 200, pdf.get_y() + 1)
        pdf.ln(2)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(120, 6, _a(total_label))
        pdf.cell(0, 6, _a(total_val), ln=1, align="R")
        pdf.ln(3)

    bd = line.get("breakdown_json") or {}
    earn_rows = [("Basic salary", _money(line.get("base_salary")))]
    for a in (bd.get("allowances") or []):
        earn_rows.append((a.get("type_code") or "Allowance",
                          _money(a.get("amount")) if a.get("amount") is not None else f"{a.get('percent')}% of basic"))
    if Decimal(str(line.get("overtime_amount") or 0)) > 0:
        earn_rows.append(("Overtime", _money(line.get("overtime_amount"))))
    for oo in (bd.get("one_offs") or []):
        if oo.get("kind") != "OTHER_DEDUCTION":
            earn_rows.append((f"{oo.get('kind', 'BONUS').replace('_', ' ').title()}"
                              + (f" — {oo.get('note')}" if oo.get("note") else ""),
                              _money(oo.get("amount"))))
    section("Earnings", earn_rows, "Gross pay", _money(line.get("gross_pay")))

    ded_rows = [
        ("PAYE (income tax)", _money(line.get("paye_amount"))),
        ("Pension (employee)", _money(line.get("pension_amount"))),
        ("NHF", _money(line.get("nhf_amount"))),
    ]
    _adv = Decimal(str(bd.get("advance_recovery") or 0))
    _loan_total = Decimal(str(line.get("loan_repayment_amount") or 0))
    _loan_only = Decimal(str(bd.get("loan_repayment"))) if bd.get("loan_repayment") is not None else (_loan_total - _adv)
    if _loan_only > 0:
        ded_rows.append(("Loan repayment", _money(_loan_only)))
    if _adv > 0:
        ded_rows.append(("Salary advance recovery", _money(_adv)))
    if _loan_only <= 0 and _adv <= 0 and _loan_total > 0:
        ded_rows.append(("Loan / advance recovery", _money(_loan_total)))
    if Decimal(str(line.get("other_deductions") or 0)) > 0:
        ded_rows.append(("Other deductions", _money(line.get("other_deductions"))))
    section("Deductions", ded_rows, "Total deductions", _money(line.get("total_deductions")))

    pdf.set_fill_color(236, 253, 245)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(*_EMERALD)
    pdf.cell(120, 10, _a("NET PAY"), fill=True)
    pdf.cell(0, 10, _a(f"NGN {_money(line.get('net_pay'))}"), ln=1, align="R", fill=True)

    pdf.ln(4)
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(*_MUTED)
    if bd.get("pension_employer"):
        pdf.cell(0, 5, _a(f"Employer pension contribution (not deducted): NGN {_money(bd['pension_employer'])}"), ln=1)
    if bd.get("nsitf_employer") and Decimal(str(bd.get("nsitf_employer") or 0)) > 0:
        pdf.cell(0, 5, _a(f"NSITF employer contribution (not deducted): NGN {_money(bd['nsitf_employer'])}"), ln=1)
    if bd.get("proration"):
        pr = bd["proration"]
        pdf.cell(0, 5, _a(f"Prorated: {pr.get('payable_days')}/{pr.get('period_days')} days"
                          + (f", {pr.get('unpaid_leave_days')} unpaid-leave day(s)" if pr.get("unpaid_leave_days") else "")), ln=1)
    pdf.cell(0, 5, _a("This is a system-generated payslip and requires no signature."), ln=1)

    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out, str) else bytes(out)


def _csv_bytes(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def bank_schedule_csv(rows: list[dict]) -> bytes:
    return _csv_bytes(
        ["Staff Number", "Staff Name", "Bank", "Account Number", "Account Name", "Net Pay"],
        [[r.get("staff_number"), r.get("staff_name"), r.get("bank_name"),
          r.get("bank_account_no"), r.get("bank_account_name"), _money(r.get("net_pay"))] for r in rows])


def paye_schedule_csv(rows: list[dict]) -> bytes:
    return _csv_bytes(
        ["Staff Number", "Staff Name", "Tax ID", "Taxable Gross", "PAYE"],
        [[r.get("staff_number"), r.get("staff_name"), r.get("tax_id"),
          _money(r.get("taxable_gross")), _money(r.get("paye_amount"))] for r in rows])


def pension_schedule_csv(rows: list[dict]) -> bytes:
    """Pension remittance schedule grouped by Pension Fund Administrator.

    Rows are ordered per provider with a subtotal after each PFA block and a
    grand total at the end, so each PFA's remittance amount reads directly
    off the schedule. Staff without a provider fall under 'Unassigned PFA'.
    """
    def _tot(r: dict) -> Decimal:
        return (Decimal(str(r.get("pension_amount") or 0))
                + Decimal(str(r.get("pension_employer") or 0)))

    groups: dict[str, list[dict]] = {}
    for r in rows:
        key = r.get("pension_provider") or "Unassigned PFA"
        groups.setdefault(key, []).append(r)

    out_rows: list[list] = []
    grand_emp = grand_er = Decimal("0")
    for provider in sorted(groups):
        members = groups[provider]
        license_no = next((m.get("pfa_license_no") for m in members
                           if m.get("pfa_license_no")), None)
        header = provider + (f" (PFA licence: {license_no})" if license_no else "")
        out_rows.append([f"— {header} —", "", "", "", "", ""])
        sub_emp = sub_er = Decimal("0")
        for r in members:
            emp = Decimal(str(r.get("pension_amount") or 0))
            er = Decimal(str(r.get("pension_employer") or 0))
            sub_emp += emp
            sub_er += er
            out_rows.append([r.get("staff_number"), r.get("staff_name"),
                             r.get("pension_pin"), _money(emp), _money(er),
                             _money(_tot(r))])
        out_rows.append(["", f"Subtotal — {provider}", "",
                         _money(sub_emp), _money(sub_er), _money(sub_emp + sub_er)])
        grand_emp += sub_emp
        grand_er += sub_er
    out_rows.append(["", "GRAND TOTAL", "", _money(grand_emp), _money(grand_er),
                     _money(grand_emp + grand_er)])

    return _csv_bytes(
        ["Staff Number", "Staff Name", "Pension PIN", "Employee 8%", "Employer 10%", "Total"],
        out_rows)


def nsitf_schedule_csv(rows: list[dict]) -> bytes:
    """NSITF remittance: 1% of gross emoluments, employer-borne."""
    body = [[r.get("staff_number"), r.get("staff_name"),
             _money(r.get("gross_pay")), _money(r.get("nsitf_employer"))]
            for r in rows]
    total = sum(Decimal(str(r.get("nsitf_employer") or 0)) for r in rows)
    body.append(["", "GRAND TOTAL", "", _money(total)])
    return _csv_bytes(
        ["Staff Number", "Staff Name", "Gross Emoluments", "NSITF (Employer 1%)"],
        body)


def nhf_schedule_csv(rows: list[dict]) -> bytes:
    return _csv_bytes(
        ["Staff Number", "Staff Name", "NHF Number", "Basic Salary", "NHF 2.5%"],
        [[r.get("staff_number"), r.get("staff_name"), r.get("nhf_number"),
          _money(r.get("base_salary")), _money(r.get("nhf_amount"))] for r in rows])
