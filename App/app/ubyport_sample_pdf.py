"""Annotated sample of the Foreign Police UbyPort web-service credential letter.

The PDF uses entirely fictional facility data and prominent SAMPLE watermarks.
Hosts use it alongside the field guide in ``apartment_form.html`` to see which
values on a real police letter map into UbyHost — without uploading real secrets.

Regenerate the committed static file with::

    python tools/generate_ubyport_sample_pdf.py

"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Iterable, Tuple

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

# Fictional facility — must not match any real registration.
SAMPLE_IDUB = "209988776655"
SAMPLE_ZKRATKA = "DEMO1"
SAMPLE_WS_USER = f"UBY-WS_{SAMPLE_ZKRATKA}"
SAMPLE_WS_PASSWORD = "Uk@zKa-H3sl0-FAKE"
SAMPLE_FACILITY = "Ukázkové ubytování"
SAMPLE_FACILITY_SUFFIX = "(Praha 2 — fiktivní adresa)"
SAMPLE_CONTACT = "+420 777 000 111"
SAMPLE_ADDRESS = {
    "okres": "Praha",
    "obec": "Praha",
    "obec_cast": "Praha 2",
    "street": "Fiktivní",
    "house_no": "1234",
    "orient_no": "56",
    "zip": "12000",
}

STATIC_RELATIVE = Path("docs") / "ubyport-ws-credential-sample.pdf"

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"


def _register_fonts() -> None:
    global FONT_REGULAR, FONT_BOLD, FONT_OBLIQUE
    fonts_dir = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    try:
        pdfmetrics.registerFont(TTFont("Vera", os.path.join(fonts_dir, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("Vera-Bold", os.path.join(fonts_dir, "VeraBd.ttf")))
        pdfmetrics.registerFont(TTFont("Vera-Oblique", os.path.join(fonts_dir, "VeraIt.ttf")))
        FONT_REGULAR, FONT_BOLD, FONT_OBLIQUE = "Vera", "Vera-Bold", "Vera-Oblique"
    except Exception:
        pass


_register_fonts()


def default_static_path(base_dir: Path | None = None) -> Path:
    root = base_dir or Path(__file__).resolve().parent
    return root / "static" / STATIC_RELATIVE


def build_sample_pdf() -> bytes:
    """Return PDF bytes for the annotated fictional credential extract."""
    buffer = io.BytesIO()
    width, height = A4
    pdf = pdfcanvas.Canvas(buffer, pagesize=A4)
    pdf.setAuthor("UbyHost (sample)")
    pdf.setTitle("SAMPLE — UbyPort web-service credential extract (fictional)")
    pdf.setSubject("Training aid only — not a real police document")

    _draw_watermarks(pdf, width, height)
    y = height - 22 * mm
    pdf.setFont(FONT_BOLD, 13)
    pdf.drawString(18 * mm, y, "Výpis z databáze přihlašovacích údajů")
    y -= 6 * mm
    pdf.setFont(FONT_REGULAR, 8.5)
    pdf.setFillColor(colors.HexColor("#444444"))
    pdf.drawString(
        18 * mm,
        y,
        "Ukázkový dokument UbyHost — webová služba / robotické vkládání (fiktivní údaje).",
    )
    pdf.setFillColor(colors.black)
    y -= 10 * mm

    body_lines: Iterable[Tuple[str, str, str, bool]] = (
        ("IDUB:", SAMPLE_IDUB, "UbyHost → IDUB", True),
        ("Přihlašovací jméno:", SAMPLE_WS_USER, "UbyHost → Web-service login", True),
        ("Přístupové heslo:", SAMPLE_WS_PASSWORD, "UbyHost → Web-service password (enter once)", True),
        (
            "Ubytovací zařízení:",
            f"{SAMPLE_FACILITY} {SAMPLE_FACILITY_SUFFIX}",
            "UbyHost → Facility name — first line only, max 35 chars",
            True,
        ),
    )

    for label, value, note, on_letter in body_lines:
        y = _draw_label_value(pdf, y, label, value, note, on_letter=on_letter)

    y -= 4 * mm
    pdf.setFont(FONT_BOLD, 9)
    pdf.drawString(18 * mm, y, "Adresa ubytovacího zařízení (z registrace — často mimo WS PDF)")
    y -= 6 * mm
    pdf.setFont(FONT_REGULAR, 9)
    addr_rows = (
        ("Okres:", SAMPLE_ADDRESS["okres"], "UbyHost → District (okres)"),
        ("Obec:", SAMPLE_ADDRESS["obec"], "UbyHost → Municipality (obec)"),
        ("Část obce:", SAMPLE_ADDRESS["obec_cast"], "UbyHost → Part of municipality"),
        ("Ulice:", SAMPLE_ADDRESS["street"], "UbyHost → Street"),
        (
            "Č. popisné / orientační:",
            f"{SAMPLE_ADDRESS['house_no']}/{SAMPLE_ADDRESS['orient_no']}",
            "UbyHost → House no. / orientation no.",
        ),
        ("PSČ:", SAMPLE_ADDRESS["zip"], "UbyHost → Postcode"),
    )
    for label, value, note in addr_rows:
        y = _draw_label_value(pdf, y, label, value, note, on_letter=False, muted=True)

    y -= 6 * mm
    _draw_off_letter_callout(
        pdf,
        y,
        "Facility abbreviation (zkratka)",
        f"{SAMPLE_ZKRATKA} — five letters on file with the police. "
        f"Often the same as the suffix after UBY-WS_ in your login "
        f"({SAMPLE_WS_USER} → {SAMPLE_ZKRATKA}). Real WS PDFs usually omit this label.",
    )
    y -= 22 * mm
    _draw_off_letter_callout(
        pdf,
        y,
        "Contact at registration",
        f"{SAMPLE_CONTACT} — e-mail or phone from your original accommodation "
        "registration or the UbyPort portal profile. Police WS letters often do not print it.",
    )

    pdf.setFont(FONT_OBLIQUE, 7.5)
    pdf.setFillColor(colors.HexColor("#666666"))
    pdf.drawString(
        18 * mm,
        12 * mm,
        "SAMPLE / NOT REAL / DO NOT USE — fictional training PDF generated by UbyHost. "
        "Never paste these values into production.",
    )
    pdf.setFillColor(colors.black)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def write_sample_pdf(path: Path | None = None) -> Path:
    target = path or default_static_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_sample_pdf())
    return target


def _draw_watermarks(pdf: pdfcanvas.Canvas, width: float, height: float) -> None:
    pdf.saveState()
    pdf.setFillColorRGB(0.92, 0.35, 0.35, alpha=0.18)
    pdf.setFont(FONT_BOLD, 28)
    for text, x, y, angle in (
        ("SAMPLE", width * 0.18, height * 0.72, 35),
        ("NOT REAL", width * 0.12, height * 0.48, 35),
        ("DO NOT USE", width * 0.08, height * 0.24, 35),
    ):
        pdf.saveState()
        pdf.translate(x, y)
        pdf.rotate(angle)
        pdf.drawCentredString(0, 0, text)
        pdf.restoreState()
    pdf.restoreState()


def _draw_label_value(
    pdf: pdfcanvas.Canvas,
    y: float,
    label: str,
    value: str,
    note: str,
    *,
    on_letter: bool,
    muted: bool = False,
) -> float:
    left = 18 * mm
    label_width = 52 * mm
    value_x = left + label_width
    line_h = 5.2 * mm

    pdf.setFont(FONT_REGULAR, 9 if not muted else 8.5)
    if muted:
        pdf.setFillColor(colors.HexColor("#333333"))
    pdf.drawString(left, y, label)

    value_lines = _wrap(value, 58)
    box_top = y + 2.5 * mm
    box_bottom = y - (len(value_lines) - 1) * line_h - 3 * mm
    if on_letter:
        pdf.setFillColorRGB(1.0, 0.95, 0.55, alpha=0.85)
        pdf.rect(value_x - 1.5 * mm, box_bottom, 95 * mm, box_top - box_bottom, fill=1, stroke=0)
    pdf.setFillColor(colors.black if not muted else colors.HexColor("#222222"))
    vy = y
    for chunk in value_lines:
        pdf.drawString(value_x, vy, chunk)
        vy -= line_h

    pdf.setFont(FONT_OBLIQUE, 7)
    pdf.setFillColor(colors.HexColor("#0B5394"))
    note_y = box_bottom - 3.5 * mm
    for note_line in _wrap(note, 95):
        pdf.drawString(left, note_y, f"→ {note_line}")
        note_y -= 3.2 * mm

    pdf.setFillColor(colors.black)
    return note_y - 2 * mm


def _draw_off_letter_callout(pdf: pdfcanvas.Canvas, y: float, title: str, body: str) -> None:
    left = 18 * mm
    width = 175 * mm
    pdf.setFillColorRGB(0.93, 0.96, 1.0, alpha=0.95)
    pdf.setStrokeColor(colors.HexColor("#0B5394"))
    pdf.setLineWidth(0.6)
    lines = _wrap(body, 98)
    box_h = 8 * mm + len(lines) * 3.6 * mm
    pdf.roundRect(left, y - box_h + 4 * mm, width, box_h, 3 * mm, fill=1, stroke=1)
    pdf.setFillColor(colors.HexColor("#0B5394"))
    pdf.setFont(FONT_BOLD, 8.5)
    pdf.drawString(left + 3 * mm, y - 2 * mm, f"Not on typical WS PDF — {title}")
    pdf.setFont(FONT_REGULAR, 8)
    pdf.setFillColor(colors.black)
    ty = y - 6.5 * mm
    for line in lines:
        pdf.drawString(left + 3 * mm, ty, line)
        ty -= 3.6 * mm


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]
