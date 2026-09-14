"""Annotated sample of Foreign Police UbyPort web-service credential documents.

Layout and Czech wording follow the official cover letter (Vyřízení) and the
``Výpis z databáze přihlašovacích údajů`` extract. All facility and case data
are fictional; prominent SAMPLE watermarks mark the file as a UbyHost training aid.

Regenerate the committed static file with::

    python tools/generate_ubyport_sample_pdf.py
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Iterable

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
SAMPLE_FACILITY_LINE1 = "BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,"
SAMPLE_FACILITY_LINE2 = "PRAHA 2, FIKTVNÍ, 1234/56)"
SAMPLE_CONTACT = "+420 777 000 111"

# Fictional cover-letter metadata (not real case numbers or recipients).
SAMPLE_JID = "PCR00DEMOsample001"
SAMPLE_CASE_REF = "CPR-302-445/ČJ-2026-880014"
SAMPLE_DS_BARCODE = "380.0000.0000001"
SAMPLE_RECIPIENT_NAME = "Jan Ukázkový"
SAMPLE_RECIPIENT_ISDS = "demo9999"
SAMPLE_LETTER_DATE = "15. dubna 2026"
SAMPLE_EXTRACT_DATE = "15.04.2026"
SAMPLE_PROCESSOR = "Marie Ukázková"
SAMPLE_SIGNATORY = "plk. Mgr. Demo Vedoucí"
SAMPLE_SIGNATORY_ROLE = "vedoucí odboru"

STATIC_RELATIVE = Path("docs") / "ubyport-ws-credential-sample.pdf"

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"

# Positions measured from official PDFs (pdfplumber top-left coords, in points).
LEFT_MARGIN = 70.8
VALUE_COL = 177.0
BODY_WIDTH = 453.0


def _register_fonts() -> None:
    global FONT_REGULAR, FONT_BOLD, FONT_OBLIQUE
    candidates = (
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold"),
    )
    try:
        for path, name in candidates:
            if os.path.isfile(path):
                pdfmetrics.registerFont(TTFont(name, path))
        FONT_REGULAR, FONT_BOLD, FONT_OBLIQUE = "DejaVuSans", "DejaVuSans-Bold", "DejaVuSans"
    except Exception:
        pass


_register_fonts()


def default_static_path(base_dir: Path | None = None) -> Path:
    root = base_dir or Path(__file__).resolve().parent
    return root / "static" / STATIC_RELATIVE


def build_sample_pdf() -> bytes:
    """Return PDF bytes: page 1 cover letter, page 2 credential extract."""
    buffer = io.BytesIO()
    width, height = A4
    pdf = pdfcanvas.Canvas(buffer, pagesize=A4)
    pdf.setAuthor("UbyHost (sample)")
    pdf.setTitle("SAMPLE — UbyPort web-service documents (fictional)")
    pdf.setSubject("Training aid only — not a real police document")

    _draw_cover_letter(pdf, width, height)
    pdf.showPage()
    _draw_credential_extract(pdf, width, height)
    pdf.save()
    return buffer.getvalue()


def write_sample_pdf(path: Path | None = None) -> Path:
    target = path or default_static_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_sample_pdf())
    return target


def _y(height: float, top: float) -> float:
    """Convert pdfplumber-style distance-from-top to ReportLab baseline."""
    return height - top


def _draw_cover_letter(pdf: pdfcanvas.Canvas, width: float, height: float) -> None:
    _draw_page_watermark(pdf, width, height)
    _draw_training_footer(pdf)

    pdf.setFont(FONT_REGULAR, 8)
    pdf.drawRightString(width - 56.7, _y(height, 22.2), f"JID: {SAMPLE_JID}")

    pdf.setFont(FONT_REGULAR, 10)
    header_x = 172.9
    pdf.drawString(header_x, _y(height, 68.1), "ŘEDITELSTVÍ SLUŽBY CIZINECKÉ POLICIE")
    pdf.drawString(header_x, _y(height, 91.1), "Informační odbor")

    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(56.7, _y(height, 157.3), f"Č. j. {SAMPLE_CASE_REF}")
    pdf.drawString(359.8, _y(height, 157.3), f"Praha {SAMPLE_LETTER_DATE}")
    pdf.drawString(359.8, _y(height, 170.3), "Počet stran: 1")
    pdf.drawString(359.8, _y(height, 183.3), "Přílohy: 1 el.soubor")

    pdf.drawString(56.7, _y(height, 219.3), SAMPLE_RECIPIENT_NAME)
    pdf.drawString(56.7, _y(height, 232.3), f"ISDS: {SAMPLE_RECIPIENT_ISDS}")

    pdf.setFont(FONT_BOLD, 11)
    pdf.drawString(56.7, _y(height, 271.9), "Ubyport- Webová služba - přiděleno")

    pdf.setFont(FONT_REGULAR, 11)
    body: Iterable[str] = (
        "V příloze Vám zasílám požadované přihlašovací údaje pro systém Ubyport - Webová "
        "služba.",
        "Pro implementaci webové služby do Vašeho hotelového programu kontaktujte výrobce "
        "Vašeho hotelového programu.",
        "Přidělením těchto přihlašovacích údajů nejsou nijak dotčeny (zůstávají plně funkční) "
        "přihlašovací údaje do Internetové aplikace Ubyport, která tak zůstává zálohou pro "
        "oznamování ubytovaných cizinců v případě, že by měl systém Ubyport - webová služba "
        "poruchu a nešlo by dočasně prostřednictvím něj oznamovat ubytované cizince.",
    )
    y_top = 336.3
    for paragraph in body:
        y_top = _draw_wrapped_paragraph(
            pdf, height, 56.7, y_top, paragraph, BODY_WIDTH, 11, leading=13
        )
        y_top += 13

    y_top = 466.3
    pdf.setFont(FONT_BOLD, 11)
    pdf.drawString(56.7, _y(height, y_top), "DŮLEŽITÉ:")
    important = (
        "Aby se přiložený PDF dokument otevřel a zobrazil správně, doporučujeme jej otevřít "
        "v programu Adobe Acrobat Reader (prohlížeč PDF) nebo v internetovém prohlížeči MS "
        "Edge (prohlížeč WWW a PDF), nejlépe v nejnovějších verzích. V programu Adobe "
        "Acrobat a jiných editorech PDF dokumentů, se obsah nemusí zobrazit správně, nebo může "
        "zcela chybět."
    )
    _draw_wrapped_paragraph(pdf, height, 56.7, y_top, important, BODY_WIDTH, 11, leading=13)

    pdf.setFont(FONT_REGULAR, 9)
    pdf.drawString(56.7, _y(height, 578.0), "Zpracoval:")
    pdf.drawString(56.7, _y(height, 591.0), SAMPLE_PROCESSOR)

    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(352.3, _y(height, 602.3), SAMPLE_SIGNATORY)
    pdf.drawString(368.8, _y(height, 615.3), SAMPLE_SIGNATORY_ROLE)

    pdf.setFont(FONT_REGULAR, 10)
    pdf.drawString(360.1, _y(height, 716.8), "Olšanská 2")
    pdf.drawString(360.1, _y(height, 728.8), "130 51 Praha")
    pdf.drawString(360.1, _y(height, 764.8), "Tel.: +420 725 798 600")
    pdf.drawString(360.0, _y(height, 776.8), "E-mail: podatelna@policie.gov.cz")
    pdf.drawString(360.0, _y(height, 788.8), "ID DS: demo0000")
    pdf.setFont(FONT_REGULAR, 7)
    pdf.drawRightString(width - 56.7, _y(height, 815.5), SAMPLE_DS_BARCODE)


def _draw_credential_extract(pdf: pdfcanvas.Canvas, width: float, height: float) -> None:
    _draw_page_watermark(pdf, width, height)
    _draw_training_footer(pdf)

    title = "VÝPIS Z DATABÁZE PŘIHLAŠOVACÍCH ÚDAJŮ"
    pdf.setFont(FONT_BOLD, 15)
    title_w = pdfmetrics.stringWidth(title, FONT_BOLD, 15)
    pdf.drawString((width - title_w) / 2, _y(height, 73.1), title)

    subtitle = "Přihlašovací údaje pro robotické vkládání Ubyport Webová služba"
    pdf.setFont(FONT_REGULAR, 11)
    sub_w = pdfmetrics.stringWidth(subtitle, FONT_REGULAR, 11)
    pdf.drawString((width - sub_w) / 2, _y(height, 101.2), subtitle)

    fields: list[tuple[str, str, str, float]] = [
        ("Přihlašovací jméno:", SAMPLE_WS_USER, "UbyHost → Web-service login", 146.5),
        ("Přístupové heslo:", SAMPLE_WS_PASSWORD, "UbyHost → Web-service password (enter once)", 179.3),
        ("IDUB:", SAMPLE_IDUB, "UbyHost → IDUB", 212.1),
    ]
    for label, value, note, top in fields:
        _draw_extract_field(pdf, height, label, value, note, top)

    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(LEFT_MARGIN, _y(height, 244.9), "Ubytovací zařízení:")
    _highlight_value(pdf, height, 244.9, SAMPLE_FACILITY_LINE1, value_size=14)
    pdf.setFont(FONT_REGULAR, 14)
    pdf.drawString(VALUE_COL, _y(height, 275.5), SAMPLE_FACILITY_LINE2)
    _draw_field_note(
        pdf,
        height,
        285.0,
        "UbyHost → Facility name — first line only, max 35 chars "
        f"(here: «{SAMPLE_FACILITY_LINE1[:35]}»)",
    )

    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(LEFT_MARGIN, _y(height, 371.9), "Poučení:")

    pouceni = (
        "1. Tento účet slouží pro robotické vkládání dat prostřednictvím webové služby a "
        "nemůže být použit k jiným účelům.",
        "2. Ztratí-li nebo zapomene-li uživatel heslo, může požádat Ředitelství služby "
        "cizinecké policie o vygenerování nového hesla.",
        "3. Uživatel se řídí provozním řádem Internetové aplikace Ubyport.",
        "4. Při podezření na porušení provozního řádu Internetové aplikace Ubyport nebo "
        "jiné činnosti ohrožující kybernetickou",
        "5. bezpečnost může být uživatel zablokován.",
    )
    y_top = 384.6
    for line in pouceni:
        pdf.drawString(88.8 if line[0].isdigit() else LEFT_MARGIN, _y(height, y_top), line)
        y_top += 12.7

    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(LEFT_MARGIN, _y(height, 598.2), f"V Praze dne {SAMPLE_EXTRACT_DATE}")
    pdf.drawString(306.6, _y(height, 619.9), "Vystavilo: Ředitelství služby cizinecké policie")

    extra_top = 638.0
    extra_top = _draw_off_letter_callout(
        pdf,
        height,
        extra_top,
        "Facility abbreviation (zkratka)",
        f"{SAMPLE_ZKRATKA} — five letters on file with the police. Often matches the suffix "
        f"after UBY-WS_ in your login ({SAMPLE_WS_USER} → {SAMPLE_ZKRATKA}). Real WS PDFs "
        "usually omit this label.",
    )
    _draw_off_letter_callout(
        pdf,
        height,
        extra_top,
        "Contact at registration",
        f"{SAMPLE_CONTACT} — e-mail or phone from your original accommodation registration "
        "or the UbyPort portal profile. Police WS letters often do not print it.",
    )


def _draw_extract_field(
    pdf: pdfcanvas.Canvas,
    height: float,
    label: str,
    value: str,
    note: str,
    top: float,
) -> None:
    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(LEFT_MARGIN, _y(height, top), label)
    _highlight_value(pdf, height, top, value, value_size=14)
    _draw_field_note(pdf, height, top + 11, note)


def _highlight_value(
    pdf: pdfcanvas.Canvas,
    height: float,
    top: float,
    value: str,
    *,
    value_size: float,
) -> None:
    pdf.setFont(FONT_REGULAR, value_size)
    text_w = pdfmetrics.stringWidth(value, FONT_REGULAR, value_size)
    box_h = value_size + 6
    baseline = _y(height, top)
    pdf.saveState()
    pdf.setFillColorRGB(1.0, 0.95, 0.55, alpha=0.75)
    pdf.rect(VALUE_COL - 2, baseline - 3, text_w + 8, box_h, fill=1, stroke=0)
    pdf.restoreState()
    pdf.setFillColor(colors.black)
    pdf.drawString(VALUE_COL, baseline, value)


def _draw_field_note(pdf: pdfcanvas.Canvas, height: float, top: float, note: str) -> None:
    pdf.setFont(FONT_OBLIQUE, 7.5)
    pdf.setFillColor(colors.HexColor("#0B5394"))
    note_top = top + 8
    for chunk in _wrap(note, 105):
        pdf.drawString(LEFT_MARGIN, _y(height, note_top), f"→ {chunk}")
        note_top += 9
    pdf.setFillColor(colors.black)


def _draw_off_letter_callout(
    pdf: pdfcanvas.Canvas,
    height: float,
    top: float,
    title: str,
    body: str,
) -> float:
    """Draw callout; return next top (pdfplumber coords) below this box."""
    left = 56.7
    box_width = 482.0
    lines = _wrap(body, 98)
    box_h = 7 * mm + len(lines) * 3.4 * mm
    y_rl = _y(height, top)
    pdf.saveState()
    pdf.setFillColorRGB(0.93, 0.96, 1.0, alpha=0.92)
    pdf.setStrokeColor(colors.HexColor("#0B5394"))
    pdf.setLineWidth(0.5)
    pdf.roundRect(left, y_rl - box_h, box_width, box_h, 2.5 * mm, fill=1, stroke=1)
    pdf.restoreState()
    pdf.setFillColor(colors.HexColor("#0B5394"))
    pdf.setFont(FONT_BOLD, 8)
    pdf.drawString(left + 2.5 * mm, y_rl - 4 * mm, f"Not on typical WS PDF — {title}")
    pdf.setFont(FONT_REGULAR, 8)
    pdf.setFillColor(colors.black)
    ty = y_rl - 7.5 * mm
    for line in lines:
        pdf.drawString(left + 2.5 * mm, ty, line)
        ty -= 3.4 * mm
    return top + box_h + 8


def _draw_wrapped_paragraph(
    pdf: pdfcanvas.Canvas,
    height: float,
    x: float,
    top: float,
    text: str,
    max_width: float,
    font_size: float,
    *,
    leading: float,
) -> float:
    pdf.setFont(FONT_REGULAR, font_size)
    lines = _wrap_to_width(text, max_width, FONT_REGULAR, font_size)
    y_top = top
    for line in lines:
        pdf.drawString(x, _y(height, y_top), line)
        y_top += leading
    return y_top - leading


def _draw_page_watermark(pdf: pdfcanvas.Canvas, width: float, height: float) -> None:
    pdf.saveState()
    pdf.setFillColorRGB(0.75, 0.75, 0.75, alpha=0.12)
    pdf.setFont(FONT_BOLD, 42)
    pdf.translate(width * 0.35, height * 0.55)
    pdf.rotate(42)
    pdf.drawCentredString(0, 0, "SAMPLE — NOT REAL")
    pdf.restoreState()


def _draw_training_footer(pdf: pdfcanvas.Canvas) -> None:
    pdf.setFont(FONT_OBLIQUE, 7)
    pdf.setFillColor(colors.HexColor("#666666"))
    pdf.drawString(
        15 * mm,
        8 * mm,
        "UbyHost training illustration — fictional data only. Do not use these credentials in production.",
    )
    pdf.setFillColor(colors.black)


def _wrap_to_width(text: str, max_width: float, font: str, size: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


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
