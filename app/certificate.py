"""The single predefined certificate template, drawn as a landscape A4 PDF."""

from datetime import date
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

NAVY = HexColor("#1B2A49")
GOLD = HexColor("#B8892B")
GREY = HexColor("#555555")

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
CENTER_X = PAGE_WIDTH / 2
TEXT_WIDTH = PAGE_WIDTH - 200  # widest a line of text may be


def fit_font_size(
    text: str, font: str, max_size: int, min_size: int = 14, max_width: float = TEXT_WIDTH
) -> int:
    """Largest font size (down to min_size) at which the text fits within max_width."""
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def render_certificate(
    path: Path,
    *,
    recipient_name: str,
    course_name: str,
    issuer: str,
    issue_date: date,
    certificate_id: str,
) -> None:
    """Write one certificate PDF to `path`. Raises if it cannot be written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    pdf.setTitle(f"Certificate - {recipient_name}")
    pdf.setAuthor(issuer)

    # Double border
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(4)
    pdf.rect(30, 30, PAGE_WIDTH - 60, PAGE_HEIGHT - 60)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1.5)
    pdf.rect(42, 42, PAGE_WIDTH - 84, PAGE_HEIGHT - 84)

    # Heading
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 40)
    pdf.drawCentredString(CENTER_X, PAGE_HEIGHT - 135, "CERTIFICATE")
    pdf.setFillColor(GOLD)
    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(CENTER_X, PAGE_HEIGHT - 165, "OF COMPLETION")

    # Recipient
    pdf.setFillColor(GREY)
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(CENTER_X, PAGE_HEIGHT - 225, "This is to certify that")

    name_size = fit_font_size(recipient_name, "Helvetica-Bold", 36)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", name_size)
    pdf.drawCentredString(CENTER_X, PAGE_HEIGHT - 280, recipient_name)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    pdf.line(CENTER_X - 220, PAGE_HEIGHT - 295, CENTER_X + 220, PAGE_HEIGHT - 295)

    # Course
    pdf.setFillColor(GREY)
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(CENTER_X, PAGE_HEIGHT - 335, "has successfully completed")

    course_size = fit_font_size(course_name, "Helvetica-Bold", 24)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", course_size)
    pdf.drawCentredString(CENTER_X, PAGE_HEIGHT - 375, course_name)

    # Footer: date on the left, issuer on the right
    left_x, right_x, footer_y = 190, PAGE_WIDTH - 190, 110
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(0.8)
    pdf.line(left_x - 90, footer_y, left_x + 90, footer_y)
    pdf.line(right_x - 90, footer_y, right_x + 90, footer_y)

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(left_x, footer_y + 8, issue_date.strftime("%d %B %Y"))
    issuer_size = fit_font_size(issuer, "Helvetica-Bold", 13, min_size=6, max_width=260)
    pdf.setFont("Helvetica-Bold", issuer_size)
    pdf.drawCentredString(right_x, footer_y + 8, issuer)

    pdf.setFillColor(GREY)
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(left_x, footer_y - 15, "Date of issue")
    pdf.drawCentredString(right_x, footer_y - 15, "Issued by")

    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(CENTER_X, 55, f"Certificate ID: {certificate_id}")

    pdf.showPage()
    pdf.save()
