# app/utils/card_pdf.py
"""
Membership-card PDF generation (dual-faced).

Renders a print-ready, two-sided membership card onto a single A4 page:
a FRONT (hospital + cardholder identity) and a BACK (QR verification, signature
strip and terms). Print, cut along the crop marks, and glue the two faces
back-to-back to produce a physical CR80-style card.

Uses PyFPDF (fpdf 1.7.2) — already a project dependency — so no extra package
is required. Flat rectangles only (PyFPDF has no rounded corners / alpha).
"""
from __future__ import annotations

import os
import tempfile
from datetime import date, datetime
from typing import Optional

import qrcode
from fpdf import FPDF


# --- Palette (0-255 RGB) --------------------------------------------------
_INK = (15, 23, 42)          # slate-900 card background
_INK_DEEP = (2, 6, 23)       # slate-950 (mag-stripe / footer band)
_EMERALD = (16, 185, 129)    # emerald-500 accent
_EMERALD_DK = (5, 150, 105)  # emerald-600
_WHITE = (255, 255, 255)
_MUTED = (148, 163, 184)     # slate-400
_LINE = (51, 65, 85)         # slate-700 divider
_SIG = (226, 232, 240)       # slate-200 signature strip
_INK_SOFT = (30, 41, 59)     # slate-800 chip
_CROP = (170, 170, 170)
_CAPTION = (120, 130, 145)

# --- Geometry (mm) on A4 (210 x 297) -------------------------------------
_PAGE_W = 210.0
_CARD_W = 150.0
_CARD_H = 92.0
_CARD_X = (_PAGE_W - _CARD_W) / 2.0
_FRONT_Y = 20.0
_GAP = 16.0
_BACK_Y = _FRONT_Y + _CARD_H + _GAP
_PAD = 12.0


# --- helpers --------------------------------------------------------------
def _format_card_number(number: str) -> str:
    n = (number or "").strip()
    if "-" in n or " " in n:
        return n
    return " ".join(n[i : i + 4] for i in range(0, len(n), 4)) or n


def _fmt_my(value) -> str:
    if value is None:
        return "--"
    if isinstance(value, (date, datetime)):
        return value.strftime("%m / %y")
    return str(value)


def _fmt_long_date(value) -> str:
    if value is None:
        return "--"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value)


def _ascii(text) -> str:
    """PyFPDF core fonts are latin-1 only; sanitise unusual glyphs."""
    if text is None:
        return ""
    text = (
        str(text)
        .replace("₦", "NGN ")  # naira sign
        .replace("—", "-")      # em dash
        .replace("–", "-")      # en dash
        .replace("’", "'")      # curly apostrophe
        .replace("‘", "'")
    )
    return text.encode("latin-1", "replace").decode("latin-1")


def _qr_temp_png(payload: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=1)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color=(15, 23, 42), back_color="white").convert("RGB")
    fd, path = tempfile.mkstemp(suffix=".png", prefix="cardqr_")
    os.close(fd)
    img.save(path, format="PNG")
    return path


def _fit(pdf: FPDF, text: str, max_w: float) -> str:
    if pdf.get_string_width(text) <= max_w:
        return text
    ell = "..."
    while text and pdf.get_string_width(text + ell) > max_w:
        text = text[:-1]
    return (text.rstrip() + ell) if text else text


def _text(pdf, x, y, s, *, font="Arial", style="", size=10, color=_WHITE):
    pdf.set_font(font, style, size)
    pdf.set_text_color(*color)
    pdf.text(x, y, _ascii(s))


def _center(pdf, cx, y, s, *, font="Arial", style="", size=10, color=_WHITE):
    pdf.set_font(font, style, size)
    pdf.set_text_color(*color)
    s = _ascii(s)
    pdf.text(cx - pdf.get_string_width(s) / 2.0, y, s)


def _crop_marks(pdf: FPDF, x: float, y: float, w: float, h: float) -> None:
    pdf.set_draw_color(*_CROP)
    pdf.set_line_width(0.2)
    m, o = 3.0, 1.8  # mark length, offset from corner
    for (cx, cy, dx, dy) in [
        (x, y, -1, -1), (x + w, y, 1, -1), (x, y + h, -1, 1), (x + w, y + h, 1, 1),
    ]:
        pdf.line(cx + dx * o, cy, cx + dx * (o + m), cy)
        pdf.line(cx, cy + dy * o, cx, cy + dy * (o + m))


def _status_colors(status: str):
    s = (status or "").upper()
    if s == "ACTIVE":
        return _EMERALD, (5, 46, 34)      # emerald pill, dark text
    if s in ("SUSPENDED", "INACTIVE"):
        return (245, 158, 11), (69, 39, 6)  # amber
    return (148, 163, 184), (15, 23, 42)   # slate


def _fit_font(pdf: FPDF, text: str, max_w: float, base: float, font="Arial", style="B") -> str:
    """Set the font at ``base`` size, then truncate ``text`` with an ellipsis so
    it fits ``max_w`` — measured at the size it will actually be drawn."""
    pdf.set_font(font, style, base)
    return _fit(pdf, text, max_w)


# --- FRONT ----------------------------------------------------------------
def _draw_front(pdf, *, hospital, name, mrn, global_id, card_number, status,
                expiry, date_issued, photo_path=None):
    x, y, W, H = _CARD_X, _FRONT_Y, _CARD_W, _CARD_H
    inner = x + _PAD

    pdf.set_fill_color(*_INK)
    pdf.rect(x, y, W, H, style="F")
    pdf.set_fill_color(*_EMERALD)
    pdf.rect(x, y, 4, H, style="F")

    # --- Photo column (right) + global ID underneath -----------------
    photo_w, photo_h = 24.0, 30.0
    photo_x = x + W - _PAD - photo_w
    photo_y = y + 22.0
    # white frame behind the photo
    pdf.set_fill_color(*_WHITE)
    pdf.rect(photo_x - 1.2, photo_y - 1.2, photo_w + 2.4, photo_h + 2.4, style="F")
    drew_photo = False
    if photo_path and os.path.exists(photo_path):
        try:
            pdf.image(photo_path, photo_x, photo_y, photo_w, photo_h)
            drew_photo = True
        except Exception:
            drew_photo = False
    if not drew_photo:
        # placeholder: soft slate box with the cardholder's initial
        pdf.set_fill_color(*_INK_SOFT)
        pdf.rect(photo_x, photo_y, photo_w, photo_h, style="F")
        _center(pdf, photo_x + photo_w / 2, photo_y + photo_h / 2 + 4,
                (name or "?").strip()[:1].upper(), style="B", size=26, color=_MUTED)
    # thin border framing the photo
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.rect(photo_x, photo_y, photo_w, photo_h)

    gid = _ascii((global_id or "").strip())
    if gid:
        _center(pdf, photo_x + photo_w / 2, photo_y + photo_h + 5.5,
                "GLOBAL ID", style="B", size=6, color=_EMERALD)
        # shrink the mono ID until it fits a box a little wider than the photo
        box = photo_w + 12.0
        size = 8.0
        pdf.set_font("Courier", "B", size)
        while size > 5.0 and pdf.get_string_width(gid) > box:
            size -= 0.5
            pdf.set_font("Courier", "B", size)
        _center(pdf, photo_x + photo_w / 2, photo_y + photo_h + 10.5, gid,
                font="Courier", style="B", size=size, color=_WHITE)

    # --- Header (left of the photo) ----------------------------------
    initial = (hospital or "C").strip()[:1].upper() or "C"
    pdf.set_fill_color(*_EMERALD)
    pdf.rect(inner, y + 9, 9, 9, style="F")
    _center(pdf, inner + 4.5, y + 15.4, initial, style="B", size=12, color=(5, 46, 34))

    # Status pill sits to the LEFT of the photo now.
    pill_bg, pill_fg = _status_colors(status)
    st = _ascii((status or "").upper() or "ACTIVE")
    pdf.set_font("Arial", "B", 7)
    pw = pdf.get_string_width(st) + 8
    px = photo_x - 5 - pw
    pdf.set_fill_color(*pill_bg)
    pdf.rect(px, y + 9.5, pw, 6.5, style="F")
    _text(pdf, px + 4, y + 14, st, style="B", size=7, color=pill_fg)

    _text(pdf, inner + 13, y + 12.5, "MEMBERSHIP CARD", style="B", size=7, color=_EMERALD)
    pdf.set_font("Arial", "B", 14)
    _text(pdf, inner + 13, y + 18.5,
          _fit(pdf, hospital or "Hospital", (px - 6) - (inner + 13)),
          style="B", size=14, color=_WHITE)

    # Divider (spans only left of the photo)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.line(inner, y + 27, photo_x - 6, y + 27)

    left_w = (photo_x - 6) - inner  # usable width to the left of the photo

    # Cardholder identity
    _text(pdf, inner, y + 39, "CARDHOLDER", style="B", size=7, color=_MUTED)
    _text(pdf, inner, y + 47, _fit_font(pdf, (name or "-").upper(), left_w, 16),
          style="B", size=16, color=_WHITE)
    if mrn:
        mrn_s = str(mrn).strip()
        if not mrn_s.upper().startswith("MRN"):
            mrn_s = f"MRN {mrn_s}"
        _text(pdf, inner, y + 52.5, _fit(pdf, mrn_s, left_w), size=8, color=_MUTED)

    # Card number
    _text(pdf, inner, y + 64, "CARD NUMBER", style="B", size=7, color=_MUTED)
    _text(pdf, inner, y + 71.5, _fit(pdf, _format_card_number(card_number), left_w),
          font="Courier", style="B", size=14, color=_WHITE)

    # Issued / valid-thru along the bottom-left
    _text(pdf, inner, y + 80, "ISSUED", size=6, color=_MUTED)
    _text(pdf, inner + 15, y + 80, _fmt_my(date_issued), style="B", size=8, color=_WHITE)
    _text(pdf, inner + 33, y + 80, "VALID THRU", size=6, color=_MUTED)
    _text(pdf, inner + 57, y + 80, _fmt_my(expiry), style="B", size=8, color=_WHITE)

    _crop_marks(pdf, x, y, W, H)
    _center(pdf, _PAGE_W / 2, y - 4, "FRONT", size=7, color=_CAPTION)


# --- BACK -----------------------------------------------------------------
def _draw_back(pdf, *, hospital, card_number, qr_path, date_issued):
    x, y, W, H = _CARD_X, _BACK_Y, _CARD_W, _CARD_H
    inner = x + _PAD

    pdf.set_fill_color(*_INK)
    pdf.rect(x, y, W, H, style="F")
    pdf.set_fill_color(*_EMERALD)
    pdf.rect(x, y, 4, H, style="F")

    # Signature / magnetic strip near the top
    pdf.set_fill_color(*_INK_DEEP)
    pdf.rect(x + 4, y + 9, W - 4, 11, style="F")
    _text(pdf, inner, y + 16.2, "AUTHORISED SIGNATURE", style="B", size=6.5, color=_MUTED)
    pdf.set_fill_color(*_SIG)
    pdf.rect(x + W - _PAD - 58, y + 11, 58, 7, style="F")

    # QR block (right)
    qr_size = 30.0
    qr_x = x + W - qr_size - _PAD
    qr_y = y + 30
    pdf.set_fill_color(*_WHITE)
    pdf.rect(qr_x - 2.5, qr_y - 2.5, qr_size + 5, qr_size + 5, style="F")
    pdf.image(qr_path, qr_x, qr_y, qr_size, qr_size)
    _center(pdf, qr_x + qr_size / 2, qr_y + qr_size + 6, "SCAN TO VERIFY", style="B", size=6.5, color=_EMERALD)

    # Left column: card number + terms
    _text(pdf, inner, y + 34, "CARD NUMBER", style="B", size=6.5, color=_MUTED)
    _text(pdf, inner, y + 40, _format_card_number(card_number), font="Courier", style="B", size=12, color=_WHITE)

    terms = [
        "This card is the property of the issuing hospital and is",
        "non-transferable. It must be presented for identification",
        "and wallet transactions at any service point.",
        "If found, please return it to the hospital.",
    ]
    ty = y + 50
    col_w = (qr_x - 2.5) - inner - 4
    pdf.set_font("Arial", "", 7.5)
    for line in terms:
        _text(pdf, inner, ty, _fit(pdf, line, col_w), size=7.5, color=_MUTED)
        ty += 4.6

    # Footer band
    pdf.set_fill_color(*_INK_DEEP)
    pdf.rect(x + 4, y + H - 12, W - 4, 12, style="F")
    _text(pdf, inner, y + H - 4.5, _fit(pdf, hospital or "Hospital", W - 2 * _PAD - 40),
          style="B", size=8, color=_WHITE)
    issued = f"Issued {_fmt_long_date(date_issued)}" if date_issued else "Official membership card"
    pdf.set_font("Arial", "", 7)
    iw = pdf.get_string_width(_ascii(issued))
    _text(pdf, x + W - _PAD - iw, y + H - 4.5, issued, size=7, color=_MUTED)

    _crop_marks(pdf, x, y, W, H)
    _center(pdf, _PAGE_W / 2, y - 4, "BACK", size=7, color=_CAPTION)


def build_membership_card_pdf(
    *,
    hospital_name: str,
    patient_name: str,
    card_number: str,
    patient_mrn: Optional[str] = None,
    global_id: Optional[str] = None,
    status: Optional[str] = None,
    expiry: Optional[object] = None,
    date_issued: Optional[object] = None,
    qr_payload: Optional[str] = None,
    photo_path: Optional[str] = None,
) -> bytes:
    """Build a dual-faced, print-ready membership-card PDF and return the bytes."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()

    qr_path = _qr_temp_png(qr_payload or card_number or "")
    try:
        _draw_front(
            pdf,
            hospital=hospital_name,
            name=patient_name,
            mrn=patient_mrn,
            global_id=global_id,
            card_number=card_number,
            status=status,
            expiry=expiry,
            date_issued=date_issued,
            photo_path=photo_path,
        )
        _draw_back(
            pdf,
            hospital=hospital_name,
            card_number=card_number,
            qr_path=qr_path,
            date_issued=date_issued,
        )

        # Print guidance under both cards.
        _center(
            pdf, _PAGE_W / 2, _BACK_Y + _CARD_H + 12,
            "Print at 100% (no scaling), cut along the marks, and place the two faces back-to-back.",
            size=8, color=_CAPTION,
        )

        out = pdf.output(dest="S")
        return out.encode("latin-1") if isinstance(out, str) else bytes(out)
    finally:
        try:
            os.remove(qr_path)
        except OSError:
            pass
