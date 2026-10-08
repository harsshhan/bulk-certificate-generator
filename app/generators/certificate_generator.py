from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_certificate(
    recipient_name: str,
    event_name: str,
    event_date: str,
    output_path: str,
) -> None:
    output_file = Path(output_path)

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf = canvas.Canvas(
        str(output_file),
        pagesize=A4,
    )

    width, height = A4

    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(
        width / 2,
        height - 150,
        "Certificate of Participation",
    )

    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(
        width / 2,
        height - 220,
        "This certificate is proudly presented to",
    )

    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(
        width / 2,
        height - 280,
        recipient_name,
    )

    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(
        width / 2,
        height - 340,
        f"for participating in {event_name}",
    )

    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(
        width / 2,
        height - 390,
        f"Date: {event_date}",
    )

    pdf.save()