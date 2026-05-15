# app/utils/visit_tag.py
from __future__ import annotations

"""
E-Patient Visit Tag Generator for Carepoint HMS.

Purpose
-------
Generates a visit tag PDF containing:
- Hospital branding (name)
- Patient demographics
- Visit code encoded as a QR code
- Visit date and priority
- Clinic pathway (visit flow steps)

The tag is generated as a PDF file (bytes) that can be:
- Emailed as an attachment
- Returned as a downloadable file for front-desk printing

Dependencies
------------
- qrcode[pil]  (QR code generation)
- Pillow       (image handling for qrcode)
- fpdf         (PDF generation)
"""

import base64
import io
import logging
import os
import tempfile
from datetime import datetime
from typing import Optional

try:
    import qrcode
    _QR_AVAILABLE = True
except ImportError:
    _QR_AVAILABLE = False

try:
    from fpdf import FPDF
    _FPDF_AVAILABLE = True
except ImportError:
    _FPDF_AVAILABLE = False

logger = logging.getLogger(__name__)


def generate_qr_code_base64(data: str, box_size: int = 8, border: int = 2) -> str:
    """
    Generate a QR code image and return it as a base64-encoded PNG string.

    Args:
        data: The string to encode in the QR code.
        box_size: Pixel size of each QR module.
        border: Number of border modules.

    Returns:
        str: Base64-encoded PNG image string.

    Raises:
        RuntimeError: If the qrcode library is not installed.
    """
    if not _QR_AVAILABLE:
        raise RuntimeError(
            "qrcode library is not installed. "
            "Install it with: pip install qrcode[pil] Pillow"
        )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f766e", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode("utf-8")


def _generate_qr_code_tempfile(data: str, box_size: int = 10, border: int = 2) -> str:
    """
    Generate a QR code and save it to a temporary JPEG file.

    JPEG is used instead of PNG because fpdf 1.7.2 handles JPEG
    more reliably across all platforms.

    Returns:
        str: Absolute path to the temporary JPEG file.
    """
    if not _QR_AVAILABLE:
        raise RuntimeError("qrcode library is not installed.")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0d6b63", back_color="white")

    # Ensure RGB mode (no alpha channel) for JPEG compatibility
    pil_img = img.get_image() if hasattr(img, "get_image") else img
    if hasattr(pil_img, "mode") and pil_img.mode != "RGB":
        from PIL import Image as PILImage
        pil_img = pil_img.convert("RGB")

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    pil_img.save(tmp, format="JPEG", quality=95)
    tmp.close()
    return tmp.name



def generate_visit_tag_pdf(
    *,
    hospital_name: str,
    patient_name: str,
    patient_hospital_number: str,
    visit_code: str,
    visit_date: datetime,
    priority: str = "NORMAL",
    clinic_pathway: Optional[list[dict]] = None,
    pathway_name: Optional[str] = None,
) -> bytes:
    """
    Generate an E-Patient Visit Tag as a PDF document.

    The PDF contains:
    - Hospital header
    - QR code encoding the visit_code
    - Patient details
    - Visit metadata
    - Clinic pathway steps (if available)

    Args:
        hospital_name: Name of the hospital / clinic.
        patient_name: Full patient name.
        patient_hospital_number: Patient's hospital/MRN number.
        visit_code: The unique visit code.
        visit_date: Visit date/time.
        priority: Visit priority string (NORMAL, URGENT, EMERGENCY).
        clinic_pathway: Optional list of pathway step dicts with keys:
            step_order, service_point_name, is_required, status
        pathway_name: Optional name of the VisitFlowTemplate. Used as
            the section heading. Falls back to 'CLINIC PATHWAY'.

    Returns:
        bytes: PDF file content.
    """
    if not _FPDF_AVAILABLE:
        raise RuntimeError("fpdf library is not installed. Install it with: pip install fpdf")

    pdf = FPDF(orientation="P", unit="mm", format=(100, 200))
    pdf.set_auto_page_break(auto=True, margin=8)
    pdf.add_page()

    # ---- Colors ----
    teal_r, teal_g, teal_b = 13, 116, 136  # Dark teal
    dark_r, dark_g, dark_b = 17, 24, 39    # Near-black
    gray_r, gray_g, gray_b = 107, 114, 128  # Muted gray
    light_bg_r, light_bg_g, light_bg_b = 240, 253, 250  # Teal tint

    page_w = 100  # mm

    # ---- Header bar ----
    pdf.set_fill_color(teal_r, teal_g, teal_b)
    pdf.rect(0, 0, page_w, 22, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(0, 4)
    pdf.cell(page_w, 7, hospital_name, ln=1, align="C")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(204, 251, 241)
    pdf.cell(page_w, 5, "E-PATIENT VISIT TAG", ln=1, align="C")

    # ---- QR Code ----
    qr_path = None
    try:
        qr_path = _generate_qr_code_tempfile(visit_code, box_size=8, border=2)
        qr_size = 38  # mm
        qr_x = (page_w - qr_size) / 2
        pdf.image(qr_path, x=qr_x, y=26, w=qr_size, h=qr_size)
    except Exception as exc:
        logger.warning("QR code generation failed for PDF: %s", exc)

    # ---- Visit Code ----
    pdf.set_xy(0, 66)
    pdf.set_text_color(15, 118, 110)
    pdf.set_font("Courier", "B", 13)
    pdf.cell(page_w, 6, visit_code, ln=1, align="C")
    pdf.set_text_color(gray_r, gray_g, gray_b)
    pdf.set_font("Helvetica", "", 6)
    pdf.cell(page_w, 4, "Scan QR code or present this tag at any service point", ln=1, align="C")

    # ---- Divider ----
    y_div = pdf.get_y() + 3
    pdf.set_draw_color(229, 231, 235)
    pdf.line(10, y_div, page_w - 10, y_div)

    # ---- Patient Details ----
    pdf.set_xy(8, y_div + 4)
    label_w = 30
    value_w = page_w - label_w - 16

    def _detail_row(label: str, value: str, bold_value: bool = False):
        y = pdf.get_y()
        pdf.set_text_color(gray_r, gray_g, gray_b)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_xy(8, y)
        pdf.cell(label_w, 5, label, align="R")
        pdf.set_text_color(dark_r, dark_g, dark_b)
        pdf.set_font("Helvetica", "B" if bold_value else "", 8)
        pdf.set_xy(8 + label_w + 2, y)
        pdf.cell(value_w, 5, value, ln=1)

    _detail_row("Patient", patient_name, bold_value=True)
    _detail_row("Hospital No.", patient_hospital_number)

    formatted_date = visit_date.strftime("%d %b %Y, %I:%M %p") if visit_date else ""
    _detail_row("Visit Date", formatted_date)

    # Priority badge
    priority_upper = (priority or "NORMAL").upper()
    _detail_row("Priority", priority_upper)

    # ---- Clinic Pathway ----
    if clinic_pathway:
        y_pathway = pdf.get_y() + 4
        pdf.set_draw_color(229, 231, 235)
        pdf.line(10, y_pathway, page_w - 10, y_pathway)

        pdf.set_xy(0, y_pathway + 3)
        pdf.set_text_color(teal_r, teal_g, teal_b)
        pdf.set_font("Helvetica", "B", 8)
        heading = (pathway_name or "CLINIC PATHWAY").upper()
        pdf.cell(page_w, 5, heading, ln=1, align="C")

        pdf.set_xy(8, pdf.get_y() + 1)

        for step in clinic_pathway:
            y = pdf.get_y()

            # Step number circle
            step_num = str(step.get("step_order", ""))
            pdf.set_fill_color(teal_r, teal_g, teal_b)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 6)
            circle_x = 12
            circle_y = y + 0.5
            pdf.ellipse(circle_x, circle_y, 5, 5, "F")
            pdf.set_xy(circle_x, circle_y + 0.5)
            pdf.cell(5, 4, step_num, align="C")

            # Step name
            service_name = step.get("service_point_name", "—")
            is_required = step.get("is_required", True)
            suffix = "" if is_required else " (optional)"
            pdf.set_text_color(dark_r, dark_g, dark_b)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_xy(20, y + 0.5)
            pdf.cell(page_w - 28, 5, f"{service_name}{suffix}", ln=1)

            # Connector line to next step
            if step != clinic_pathway[-1]:
                next_y = pdf.get_y()
                pdf.set_draw_color(teal_r, teal_g, teal_b)
                pdf.line(14.5, circle_y + 5, 14.5, next_y + 0.5)

    # ---- Footer ----
    footer_y = pdf.get_y() + 6
    pdf.set_draw_color(229, 231, 235)
    pdf.line(10, footer_y, page_w - 10, footer_y)
    pdf.set_xy(0, footer_y + 2)
    pdf.set_text_color(156, 163, 175)
    pdf.set_font("Helvetica", "", 5)
    year = datetime.now().year
    pdf.cell(page_w, 4, f"{year} {hospital_name}  |  Powered by CarePoint HMS", ln=1, align="C")

    # Generate the PDF output BEFORE cleaning up the QR temp file.
    # fpdf uses lazy image loading — it reads the file at output() time.
    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    # Now safe to delete the temp QR image
    if qr_path and os.path.exists(qr_path):
        try:
            os.unlink(qr_path)
        except OSError:
            pass

    return pdf_bytes

