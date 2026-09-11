"""Builds live_tests/fixtures/ - the fixed, structurally different
document set run_live_tests.py exercises. Regenerable on purpose (run
this to rebuild the fixtures from scratch) rather than hand-edited
binaries - see specs/slice-51/spec.md.

    python3 live_tests/build_fixtures.py
"""

from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _build_csv():
    (FIXTURES_DIR / "income_statement.csv").write_text(
        "period,revenue,cogs,opex\n"
        "FY2024,41200000,26800000,7900000\n"
        "FY2025,48600000,30500000,8700000\n"
        "FY2026,58400000,35100000,9600000\n",
        encoding="utf-8",
    )


def _build_docx():
    doc = Document()
    doc.add_paragraph("Meridian Robotics Inc. - Q3 2026 Quarterly Review")
    doc.add_paragraph(
        "Revenue reached $58.4 million in the third quarter, up from "
        "$52.1 million a year earlier. Operating margin expanded to "
        "21.3% from 18.7% in the prior-year quarter, driven by continued "
        "discipline in fulfillment costs."
    )
    doc.add_paragraph(
        "Net income was $9.8 million, compared with $7.2 million in the "
        "same quarter last year. Management reiterated full-year revenue "
        "guidance of $230.0 million. The Board approved a $15.0 million "
        "share repurchase authorization during the quarter."
    )
    doc.save(FIXTURES_DIR / "quarterly_review.docx")


def _build_two_column_pdf():
    path = FIXTURES_DIR / "two_column_review.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    w, h = letter
    left_x, right_x = 60, w / 2 + 20
    top = h - 90

    left_lines = [
        "Meridian Robotics Inc.",
        "Quarterly Business Review",
        "Third Quarter, Fiscal 2026",
        "",
        "Meridian designs and sells",
        "warehouse automation robots",
        "for mid-size distribution",
        "centers across North America.",
        "The company operates two",
        "segments: Hardware and",
        "Services.",
    ]
    right_lines = [
        "Financial Highlights",
        "",
        "Revenue: $58.4 million, up",
        "from $52.1 million a year",
        "earlier.",
        "Operating margin: 21.3%,",
        "up from 18.7% in the prior-",
        "year quarter.",
        "Net income: $9.8 million,",
        "versus $7.2 million a year",
        "earlier.",
    ]
    for i, line in enumerate(left_lines):
        c.drawString(left_x, top - i * 16, line)
    for i, line in enumerate(right_lines):
        c.drawString(right_x, top - i * 16, line)
    c.save()


def _build_image_exhibit_pdf():
    png_path = FIXTURES_DIR / "_chart_snippet.png"
    img = Image.new("RGB", (420, 160), "white")
    ImageDraw.Draw(img).text((20, 65), "Q4 Revenue Guidance: $64.0 million", fill="black")
    img.save(png_path)

    path = FIXTURES_DIR / "chart_exhibit.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(60, 720, "Meridian Robotics Inc. - Supplemental Exhibit")
    c.drawString(
        60, 695,
        "The chart below summarizes management's forward guidance for the coming quarter.",
    )
    c.drawImage(str(png_path), 60, 520, width=320, height=120)
    c.save()
    png_path.unlink()  # only the PDF is the fixture; the source PNG was a build step


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    _build_csv()
    _build_docx()
    _build_two_column_pdf()
    _build_image_exhibit_pdf()
    print(f"fixtures written to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
