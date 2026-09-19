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
WATERMARK_LINE = "SAMPLE — NOT REAL / UKÁZKA"
WATERMARK_LINE_2 = "NEPOUŽÍVAT — TRÉNINKOVÝ DOKUMENT"

# Measured from official PDFs (points, pdfplumber top-left origin).
LEFT_MARGIN = 70.8
VALUE_COL = 180.1
RIGHT_MARGIN = 525.0
POUCENI_NUM_X = 88.8
POUCENI_TEXT_X = 106.8
BODY_WIDTH = RIGHT_MARGIN - LEFT_MARGIN

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_MONO = "Helvetica"
FONT_TITLE = "Helvetica-Bold"

TITLE_SLANT = 0.22


# Czech letters (Ř, č, ů, ě) sit outside WinAnsi, so the built-in Helvetica
# cannot render this document. Each set is (names..., file paths...); the first
# set whose files all exist wins. Linux containers ship DejaVu; macOS workstations
# get Verdana, the closest metric relative of DejaVu Sans (both descend from
# Bitstream Vera), so the sample keeps its production layout.
_FONT_SETS = (
    (
        ("DejaVuSans", "DejaVuSans-Bold", "DejaVuSansMono"),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ),
    ),
    (
        ("Verdana", "Verdana-Bold", "CourierNew"),
        (
            "/System/Library/Fonts/Supplemental/Verdana.ttf",
            "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
            "/System/Library/Fonts/Supplemental/Courier New.ttf",
        ),
    ),
)


def _register_fonts() -> None:
    global FONT_REGULAR, FONT_BOLD, FONT_MONO, FONT_TITLE
    for names, paths in _FONT_SETS:
        if not all(os.path.isfile(path) for path in paths):
            continue
        try:
            for path, name in zip(paths, names):
                pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            continue
        FONT_REGULAR, FONT_BOLD, FONT_MONO = names
        FONT_TITLE = FONT_BOLD
        return


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


def page_content_streams(pdf_bytes: bytes) -> list[bytes]:
    """Return decompressed content stream bytes for each page."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    streams: list[bytes] = []
    for page in reader.pages:
        content = page.get_contents()
        if content is None:
            streams.append(b"")
        elif isinstance(content, list):
            streams.append(b"".join(part.get_data() for part in content))
        else:
            streams.append(content.get_data())
    return streams


def _y(height: float, top: float) -> float:
    """Convert pdfplumber-style distance-from-top to ReportLab baseline."""
    return height - top


def _draw_cover_letter(pdf: pdfcanvas.Canvas, width: float, height: float) -> None:
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

    important_prefix = "DŮLEŽITÉ:"
    pdf.setFont(FONT_BOLD, 11)
    pdf.drawString(56.7, _y(height, 466.3), important_prefix)
    prefix_end_x = (
        56.7
        + pdfmetrics.stringWidth(important_prefix, FONT_BOLD, 11)
        + pdfmetrics.stringWidth(" ", FONT_REGULAR, 11)
    )
    important = (
        "Aby se přiložený PDF dokument otevřel a zobrazil správně, doporučujeme jej otevřít "
        "v programu Adobe Acrobat Reader (prohlížeč PDF) nebo v internetovém prohlížeči MS "
        "Edge (prohlížeč WWW a PDF), nejlépe v nejnovějších verzích. V programu Adobe "
        "Acrobat a jiných editorech PDF dokumentů, se obsah nemusí zobrazit správně, nebo může "
        "zcela chybět."
    )
    _draw_wrapped_paragraph_with_hanging_first_line(
        pdf,
        height,
        first_line_x=prefix_end_x,
        body_x=56.7,
        top=466.3,
        text=important,
        first_width=RIGHT_MARGIN - prefix_end_x,
        body_width=BODY_WIDTH,
        font_size=11,
        leading=13,
    )

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

    _draw_training_footer(pdf)
    _draw_page_watermark(pdf, width, height)


def _draw_credential_extract(pdf: pdfcanvas.Canvas, width: float, height: float) -> None:
    title = "VÝPIS Z DATABÁZE PŘIHLAŠOVACÍCH ÚDAJŮ"
    title_w = _slanted_string_width(title, FONT_TITLE, 15)
    _draw_slanted_string(pdf, (width - title_w) / 2, _y(height, 73.1), title, FONT_TITLE, 15)

    subtitle = "Přihlašovací údaje pro robotické vkládání Ubyport Webová služba"
    pdf.setFont(FONT_BOLD, 11)
    sub_w = pdfmetrics.stringWidth(subtitle, FONT_BOLD, 11)
    pdf.drawString((width - sub_w) / 2, _y(height, 101.2), subtitle)

    _draw_extract_label_value(
        pdf, height, "Přihlašovací jméno:", SAMPLE_WS_USER, label_top=146.5, value_top=144.4
    )
    _draw_extract_label_value(
        pdf, height, "Přístupové heslo:", SAMPLE_WS_PASSWORD, label_top=179.3, value_top=177.2
    )
    _draw_extract_label_value(pdf, height, "IDUB:", SAMPLE_IDUB, label_top=212.1, value_top=209.9)

    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(LEFT_MARGIN, _y(height, 244.9), "Ubytovací zařízení:")
    _highlight_mono_value(pdf, height, 242.7, SAMPLE_FACILITY_LINE1)
    _highlight_mono_value(pdf, height, 275.5, SAMPLE_FACILITY_LINE2, x=LEFT_MARGIN)

    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(LEFT_MARGIN, _y(height, 371.9), "Poučení:")

    pouceni_items = (
        "Tento účet slouží pro robotické vkládání dat prostřednictvím webové služby a "
        "nemůže být použit k jiným účelům.",
        "Ztratí-li nebo zapomene-li uživatel heslo, může požádat Ředitelství služby "
        "cizinecké policie o vygenerování nového hesla.",
        "Uživatel se řídí provozním řádem Internetové aplikace Ubyport.",
        "Při podezření na porušení provozního řádu Internetové aplikace Ubyport nebo "
        "jiné činnosti ohrožující kybernetickou",
        "bezpečnost může být uživatel zablokován.",
    )
    y_top = 384.6
    for idx, item in enumerate(pouceni_items, start=1):
        y_top = _draw_pouceni_item(pdf, height, idx, item, y_top)

    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(LEFT_MARGIN, _y(height, 598.2), f"V Praze dne {SAMPLE_EXTRACT_DATE}")
    issuer = "Vystavilo: Ředitelství služby cizinecké policie"
    issuer_size = 11.0
    while issuer_size >= 9.5 and pdfmetrics.stringWidth(issuer, FONT_REGULAR, issuer_size) > (
        RIGHT_MARGIN - 306.6
    ):
        issuer_size -= 0.5
    pdf.setFont(FONT_REGULAR, issuer_size)
    pdf.drawString(306.6, _y(height, 619.9), issuer)

    annotation_top = 632.0
    annotation_top = _draw_field_mapping_block(pdf, height, annotation_top)
    annotation_top = _draw_off_letter_callout(
        pdf,
        height,
        annotation_top,
        "Facility abbreviation (zkratka)",
        f"{SAMPLE_ZKRATKA} — five letters on file with the police. Often matches the suffix "
        f"after UBY-WS_ in your login ({SAMPLE_WS_USER} → {SAMPLE_ZKRATKA}). Real WS PDFs "
        "usually omit this label.",
    )
    _draw_off_letter_callout(
        pdf,
        height,
        annotation_top,
        "Contact at registration",
        f"{SAMPLE_CONTACT} — e-mail or phone from your original accommodation registration "
        "or the UbyPort portal profile. Police WS letters often do not print it.",
    )

    _draw_training_footer(pdf)
    _draw_page_watermark(pdf, width, height)


def _draw_extract_label_value(
    pdf: pdfcanvas.Canvas,
    height: float,
    label: str,
    value: str,
    *,
    label_top: float,
    value_top: float,
) -> None:
    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(LEFT_MARGIN, _y(height, label_top), label)
    _highlight_mono_value(pdf, height, value_top, value)


def _highlight_mono_value(
    pdf: pdfcanvas.Canvas,
    height: float,
    top: float,
    value: str,
    *,
    x: float | None = None,
) -> None:
    value_x = x if x is not None else VALUE_COL
    value_size = 14.0
    pdf.setFont(FONT_MONO, value_size)
    text_w = pdfmetrics.stringWidth(value, FONT_MONO, value_size)
    baseline = _y(height, top)
    box_h = value_size + 6
    pdf.saveState()
    pdf.setFillColorRGB(1.0, 0.95, 0.55, alpha=0.75)
    pdf.rect(value_x - 2, baseline - 3, text_w + 8, box_h, fill=1, stroke=0)
    pdf.restoreState()
    pdf.setFillColor(colors.black)
    pdf.drawString(value_x, baseline, value)


def _draw_pouceni_item(
    pdf: pdfcanvas.Canvas,
    height: float,
    number: int,
    text: str,
    top: float,
) -> float:
    pdf.setFont(FONT_REGULAR, 11)
    pdf.drawString(POUCENI_NUM_X, _y(height, top), f"{number}.")
    wrap_width = RIGHT_MARGIN - POUCENI_TEXT_X
    lines = _wrap_to_width(text, wrap_width, FONT_REGULAR, 11)
    y = top
    for line in lines:
        pdf.drawString(POUCENI_TEXT_X, _y(height, y), line)
        y += 12.7
    return y + 0.5


def _draw_field_mapping_block(pdf: pdfcanvas.Canvas, height: float, top: float) -> float:
    left = LEFT_MARGIN
    box_width = RIGHT_MARGIN - left
    notes = (
        f"Přihlašovací jméno → UbyHost Web-service login ({SAMPLE_WS_USER})",
        f"Přístupové heslo → UbyHost Web-service password ({SAMPLE_WS_PASSWORD})",
        f"IDUB → UbyHost IDUB ({SAMPLE_IDUB})",
        "Ubytovací zařízení → Facility name, first line only, max 35 chars "
        f"(«{SAMPLE_FACILITY_LINE1[:35]}»)",
    )
    lines: list[str] = []
    for note in notes:
        lines.extend(_wrap_to_width(note, box_width - 6 * mm, FONT_REGULAR, 7.5))
    box_h = 5 * mm + len(lines) * 3.1 * mm
    y_rl = _y(height, top)
    pdf.saveState()
    pdf.setFillColorRGB(0.97, 0.98, 1.0, alpha=0.95)
    pdf.setStrokeColor(colors.HexColor("#0B5394"))
    pdf.setLineWidth(0.4)
    pdf.roundRect(left, y_rl - box_h, box_width, box_h, 2 * mm, fill=1, stroke=1)
    pdf.restoreState()
    pdf.setFillColor(colors.HexColor("#0B5394"))
    pdf.setFont(FONT_BOLD, 7.5)
    pdf.drawString(left + 2 * mm, y_rl - 3.5 * mm, "UbyHost — map highlighted values above")
    pdf.setFont(FONT_REGULAR, 7.5)
    pdf.setFillColor(colors.HexColor("#0B5394"))
    ty = y_rl - 6.5 * mm
    for line in lines:
        pdf.drawString(left + 2 * mm, ty, f"→ {line}")
        ty -= 3.1 * mm
    pdf.setFillColor(colors.black)
    return top + box_h + 6


def _draw_off_letter_callout(
    pdf: pdfcanvas.Canvas,
    height: float,
    top: float,
    title: str,
    body: str,
) -> float:
    """Draw callout; return next top (pdfplumber coords) below this box."""
    left = LEFT_MARGIN
    box_width = RIGHT_MARGIN - left
    lines = _wrap_to_width(body, box_width - 8 * mm, FONT_REGULAR, 8)
    box_h = 6 * mm + len(lines) * 3.2 * mm
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
        ty -= 3.2 * mm
    return top + box_h + 6


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


def _draw_wrapped_paragraph_with_hanging_first_line(
    pdf: pdfcanvas.Canvas,
    height: float,
    *,
    first_line_x: float,
    body_x: float,
    top: float,
    text: str,
    first_width: float,
    body_width: float,
    font_size: float,
    leading: float,
) -> None:
    pdf.setFont(FONT_REGULAR, font_size)
    words = text.split()
    if not words:
        return
    lines: list[tuple[float, str]] = []
    current = words[0]
    idx = 1
    max_w = first_width
    x_pos = first_line_x
    while idx <= len(words):
        while idx < len(words):
            candidate = f"{current} {words[idx]}"
            if pdfmetrics.stringWidth(candidate, FONT_REGULAR, font_size) <= max_w:
                current = candidate
                idx += 1
            else:
                break
        lines.append((x_pos, current))
        if idx >= len(words):
            break
        current = words[idx]
        idx += 1
        max_w = body_width
        x_pos = body_x

    y_top = top
    for x_pos, line in lines:
        pdf.drawString(x_pos, _y(height, y_top), line)
        y_top += leading


def _slanted_string_width(text: str, font: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, font, size) + size * TITLE_SLANT * len(text) * 0.15


def _draw_slanted_string(
    pdf: pdfcanvas.Canvas,
    x: float,
    y: float,
    text: str,
    font: str,
    size: float,
) -> None:
    pdf.saveState()
    pdf.setFont(font, size)
    pdf.translate(x, y)
    pdf.transform(1, 0, TITLE_SLANT, 1, 0, 0)
    pdf.drawString(0, 0, text)
    pdf.restoreState()


def _draw_page_watermark(pdf: pdfcanvas.Canvas, width: float, height: float) -> None:
    """Draw on top of page content so the mark stays visible when printed."""
    pdf.saveState()
    pdf.setFillColorRGB(0.45, 0.45, 0.45)
    try:
        pdf.setFillAlpha(0.28)
    except AttributeError:
        pass
    pdf.setFont(FONT_BOLD, 34)
    pdf.translate(width * 0.5, height * 0.52)
    pdf.rotate(42)
    pdf.drawCentredString(0, 14, WATERMARK_LINE)
    pdf.setFont(FONT_BOLD, 26)
    pdf.drawCentredString(0, -22, WATERMARK_LINE_2)
    pdf.restoreState()


def _draw_training_footer(pdf: pdfcanvas.Canvas) -> None:
    pdf.setFont(FONT_REGULAR, 7)
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
