# app/utils/card_statement_pdf.py
from __future__ import annotations

"""
Render a patient membership-card usage statement (credits & debits) to PDF.

Uses FPDF core fonts (latin-1), so all text is passed through ``_ascii`` and
money is prefixed with the currency code rather than a symbol. The statement
shows the hospital, the patient/card identity, a summary (period, totals,
closing balance) and a dated ledger table where every debit states the service
it paid for.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Sequence

from fpdf import FPDF

_PRIMARY = (14, 116, 144)      # teal-700
_HEAD_BG = (14, 116, 144)
_STRIPE = (243, 247, 249)
_TEXT = (30, 41, 59)
_MUTED = (100, 116, 139)
_CREDIT = (22, 163, 74)
_DEBIT = (220, 38, 38)


def _ascii(text) -> str:
    if text is None:
        return ""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def _money(value, currency: str = "NGN") -> str:
    try:
        d = Decimal(str(value or 0))
    except Exception:
        d = Decimal("0")
    return f"{currency} {d:,.2f}"


def _fmt_dt(value) -> str:
    if not value:
        return "-"
    if isinstance(value, (datetime, date)):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return _ascii(value)
    return dt.strftime("%d %b %Y %H:%M") if isinstance(dt, datetime) else dt.strftime("%d %b %Y")


def _fmt_day(value) -> str:
    if not value:
        return "-"
    if isinstance(value, (datetime, date)):
        return value.strftime("%d %b %Y")
    return _ascii(value)


def _fit(pdf: FPDF, text: str, max_w: float) -> str:
    text = _ascii(text)
    if pdf.get_string_width(text) <= max_w:
        return text
    ell = "..."
    while text and pdf.get_string_width(text + ell) > max_w:
        text = text[:-1]
    return (text + ell) if text else ell


# Column widths (A4 usable width = 190mm with 10mm margins)
_COLS = [
    ("Date", 30.0, "L"),
    ("Purpose / Service", 64.0, "L"),
    ("Credit", 30.0, "R"),
    ("Debit", 30.0, "R"),
    ("Balance", 36.0, "R"),
]


class _StatementPDF(FPDF):
    def __init__(self, hospital_name: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.hospital_name = hospital_name
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(10, 10, 10)

    def header(self) -> None:
        self.set_fill_color(*_HEAD_BG)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 14)
        self.set_xy(10, 10)
        self.cell(0, 9, _fit(self, self.hospital_name, 150), ln=1, align="L", fill=True)
        self.set_font("Arial", "B", 10)
        self.set_x(10)
        self.cell(0, 7, "CARD USAGE STATEMENT", ln=1, align="L", fill=True)
        self.set_text_color(*_TEXT)
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Arial", "I", 7)
        self.set_text_color(*_MUTED)
        self.cell(
            0,
            6,
            _ascii(f"Generated {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC    |    Page {self.page_no()}/{{nb}}"),
            align="C",
        )

    def table_head(self) -> None:
        self.set_font("Arial", "B", 8)
        self.set_fill_color(*_PRIMARY)
        self.set_text_color(255, 255, 255)
        for title, w, align in _COLS:
            self.cell(w, 7, _ascii(title), border=0, align=align, fill=True)
        self.ln(7)
        self.set_text_color(*_TEXT)


def build_card_statement_pdf(
    *,
    hospital_name: str,
    patient_name: str,
    patient_mrn: Optional[str],
    card_number: str,
    card_status: Optional[str],
    balance,
    transactions: Sequence[dict],
    period_from=None,
    period_to=None,
    currency: str = "NGN",
) -> bytes:
    """
    ``transactions`` is an ordered (oldest-first) sequence of dicts with keys:
    ``date``, ``is_credit`` (bool), ``amount``, ``purpose``, ``balance_after``.
    """
    pdf = _StatementPDF(_ascii(hospital_name or "Hospital"))
    pdf.alias_nb_pages()
    pdf.add_page()

    total_credit = Decimal("0")
    total_debit = Decimal("0")
    for t in transactions:
        amt = Decimal(str(t.get("amount") or 0))
        if t.get("is_credit"):
            total_credit += amt
        else:
            total_debit += amt

    # ----- Identity + summary block -----
    def _row(label: str, value: str) -> None:
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(32, 6, _ascii(label))
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*_TEXT)
        pdf.cell(63, 6, _fit(pdf, value, 62), ln=1)

    y0 = pdf.get_y()
    # left column
    _row("Patient", patient_name or "-")
    _row("Hospital No.", patient_mrn or "-")
    _row("Card number", card_number or "-")
    _row("Card status", (card_status or "-"))
    left_bottom = pdf.get_y()

    # right column (summary) — drawn alongside
    pdf.set_xy(110, y0)
    period = "All time"
    if period_from or period_to:
        period = f"{_fmt_day(period_from) if period_from else 'start'}  to  {_fmt_day(period_to) if period_to else 'today'}"

    def _srow(label: str, value: str, color=None) -> None:
        pdf.set_x(110)
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(32, 6, _ascii(label))
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(*(color or _TEXT))
        pdf.cell(58, 6, _fit(pdf, value, 57), ln=1)

    _srow("Period", period)
    _srow("Total credited", _money(total_credit, currency), _CREDIT)
    _srow("Total debited", _money(total_debit, currency), _DEBIT)
    _srow("Closing balance", _money(balance, currency), _PRIMARY)

    pdf.set_y(max(left_bottom, pdf.get_y()) + 3)
    pdf.set_draw_color(220, 226, 230)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    # ----- Ledger table -----
    pdf.table_head()
    if not transactions:
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 10, "No transactions for this period.", ln=1, align="C")
        pdf.set_text_color(*_TEXT)
    else:
        pdf.set_font("Arial", "", 8)
        stripe = False
        for t in transactions:
            # repeat the table head on a fresh page
            if pdf.get_y() > 270:
                pdf.add_page()
                pdf.table_head()
                pdf.set_font("Arial", "", 8)
            credit = bool(t.get("is_credit"))
            amt = t.get("amount") or 0
            fill = stripe
            if fill:
                pdf.set_fill_color(*_STRIPE)
            cells = [
                (_fmt_dt(t.get("date")), _COLS[0][1], "L", _TEXT),
                (t.get("purpose") or ("Wallet funding" if credit else "Service payment"), _COLS[1][1], "L", _TEXT),
                (_money(amt, currency) if credit else "", _COLS[2][1], "R", _CREDIT),
                ("" if credit else _money(amt, currency), _COLS[3][1], "R", _DEBIT),
                (_money(t.get("balance_after"), currency), _COLS[4][1], "R", _MUTED),
            ]
            for text, w, align, color in cells:
                pdf.set_text_color(*color)
                pdf.cell(w, 6.5, _fit(pdf, text, w - 2), border=0, align=align, fill=fill)
            pdf.ln(6.5)
            pdf.set_text_color(*_TEXT)
            stripe = not stripe

    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out, str) else bytes(out)
