"""The hlášení PDF in the owner's "Invoice companion" design.

Design: docs/plans/stay-fee-remittance/invoice-companion/DESIGN.md (selected by
the owner on 30 Sep 2026). This module only validates and draws; the figures
come from ``stay_fee.hlaseni``. All amounts are integer CZK. The document is
Czech only - it goes to a Czech office.
"""
from __future__ import annotations

import base64
import io
import os
from datetime import date, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

_FONT_DIR = os.path.join(os.path.dirname(__file__), "static", "fonts")
pdfmetrics.registerFont(TTFont("UHRemit", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("UHRemit-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
REG, BOLD = "UHRemit", "UHRemit-Bold"
MARK = os.path.join(os.path.dirname(__file__), "static", "ubyhost-mark.png")

W, H = A4
M = 18 * mm
R = W - M
INK = (0x1B / 255, 0x1F / 255, 0x25 / 255)
SECONDARY = (0x50 / 255, 0x50 / 255, 0x4C / 255)
MUTED = (0x73 / 255, 0x73 / 255, 0x6E / 255)
LINE = (0xDE / 255, 0xDE / 255, 0xD9 / 255)
CANVAS = (0xF7 / 255, 0xF7 / 255, 0xF5 / 255)
CORAL = (0xD3 / 255, 0x54 / 255, 0x45 / 255)

# "za srpen 2026": the preposition takes the accusative, which for month names
# is the nominative form, not the genitive "srpna".
MONTHS = ("leden", "únor", "březen", "duben", "květen", "červen",
          "červenec", "srpen", "září", "říjen", "listopad", "prosinec")


def _required(value, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Missing {label}")
    return text


def _int(value, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _shift(first: date, months: int) -> date:
    index = first.year * 12 + first.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def validate(report: dict) -> None:
    """Refuse a blank or internally inconsistent document before download."""
    for key in ("payer_name", "recipient_name", "vs", "period_start", "period_end", "issued_on"):
        _required(report.get(key), key)
    start = date.fromisoformat(report["period_start"])
    end = date.fromisoformat(report["period_end"])
    date.fromisoformat(report["issued_on"])
    quarterly = report.get("cadence") == "quarterly"
    months = 3 if quarterly else 1
    if start.day != 1 or (quarterly and (start.month - 1) % 3) \
            or end != _shift(start, months) - timedelta(days=1):
        raise ValueError("Report period must be one complete calendar month or quarter")
    total_nights = total_czk = 0
    for row in report.get("rows") or []:
        _required(row.get("property_name"), "property_name")
        nights = _int(row.get("liable_nights"), "liable_nights")
        rate = _int(row.get("rate_czk"), "rate_czk")
        amount = _int(row.get("amount_czk"), "amount_czk")
        if nights * rate != amount:
            raise ValueError("Facility amount does not match nights × rate")
        total_nights += nights
        total_czk += amount
    if report.get("liable_nights") != total_nights or report.get("total_czk") != total_czk:
        raise ValueError("Report totals do not match facility rows")
    exempt = 0
    for item in report.get("not_charged", []):
        _required(item.get("reason"), "not_charged reason")
        _int(item.get("count"), "not_charged count")
        exempt += _int(item.get("nights"), "not_charged nights")
    if report.get("exempt_nights", exempt) != exempt:
        raise ValueError("Exempt nights do not match the non-chargeable reasons")


# --- drawing primitives (unchanged from the kit) -----------------------------

def _text(c, x, y, value, *, size=9, bold=False, color=INK, right=False):
    c.setFont(BOLD if bold else REG, size)
    c.setFillColorRGB(*color)
    (c.drawRightString if right else c.drawString)(x, y, str(value))


def _label(c, x, y, value, *, right=False, color=MUTED):
    _text(c, x, y, value.upper(), size=6.8, bold=True, color=color, right=right)


def _rule(c, y, *, strong=False):
    c.setStrokeColorRGB(*(INK if strong else LINE))
    c.setLineWidth(0.8 if strong else 0.55)
    c.line(M, y, R, y)


def _card(c, x, y, width, height, *, tinted=False):
    c.setFillColorRGB(*(CANVAS if tinted else (1, 1, 1)))
    c.setStrokeColorRGB(*LINE)
    c.roundRect(x, y, width, height, 3 * mm, fill=1, stroke=0 if tinted else 1)


def _split(value, width, *, size, bold=False):
    parts = []
    for block in str(value or "").splitlines():
        parts.extend(simpleSplit(block, BOLD if bold else REG, size, width) or [""])
    return parts


def _wrap(c, x, y, value, width, *, size=8.5, bold=False, color=INK, leading=12):
    for part in _split(value, width, size=size, bold=bold):
        _text(c, x, y, part, size=size, bold=bold, color=color)
        y -= leading
    return y


def _date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.day}. {parsed.month}. {parsed.year}"


def period_phrase(report: dict) -> str:
    """'srpen 2026' or '3. čtvrtletí 2026' (after the word 'za')."""
    start = date.fromisoformat(report["period_start"])
    if report.get("cadence") == "quarterly":
        return f"{(start.month - 1) // 3 + 1}. čtvrtletí {start.year}"
    return f"{MONTHS[start.month - 1]} {start.year}"


def _plural(n: int, one: str, few: str, many: str) -> str:
    """Czech counted noun: 1 lůžkoden, 2-4 lůžkodny, 0 and 5+ lůžkodnů."""
    word = one if n == 1 else few if 2 <= n <= 4 else many
    return f"{n} {word}"


def _nights(n: int) -> str:
    return _plural(n, "lůžkoden", "lůžkodny", "lůžkodnů")


def _amount(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " Kč"


# --- page parts --------------------------------------------------------------

def _footer(c, page: int):
    _rule(c, 20 * mm)
    c.drawImage(ImageReader(MARK), M, 12.7 * mm, 4.5 * mm, 4.5 * mm, mask="auto")
    _text(c, M + 6.5 * mm, 14 * mm, "UbyHost", size=8.5, bold=True)
    _text(c, M + 32 * mm, 14 * mm, "Vytvořeno v UbyHost", size=7, color=MUTED)
    _text(c, R, 14 * mm, f"Strana {page}", size=7, color=MUTED, right=True)


def _page_top(c, report: dict, *, continuation=False, sample=False):
    c.setFillColorRGB(*CORAL)
    c.rect(0, H - 1.6 * mm, W, 1.6 * mm, fill=1, stroke=0)
    if sample:
        _label(c, M, H - 9 * mm, "NÁHLED · UKÁZKOVÁ DATA", color=CORAL)
    if continuation:
        _label(c, M, H - 18 * mm, "HLÁŠENÍ K MÍSTNÍMU POPLATKU Z POBYTU · POKRAČOVÁNÍ", color=CORAL)
        _text(c, R, H - 18 * mm, period_phrase(report), size=8, right=True)
        return H - 31 * mm

    # Identity header: the payer (the issuer) left, the document right.
    top = H - 26 * mm
    _label(c, M, top, "PLÁTCE POPLATKU")
    payer_lines = simpleSplit(report["payer_name"], BOLD, 13, 95 * mm)
    size = 13 if len(payer_lines) <= 2 else 10
    if size == 10:
        payer_lines = simpleSplit(report["payer_name"], BOLD, 10, 95 * mm)
    y = top - 8 * mm
    for part in payer_lines[:3]:
        _text(c, M, y, part, size=size, bold=True)
        y -= 5.7 * mm
    id_bits = [f"IČO {report['payer_ico']}"] if report.get("payer_ico") else []
    id_bits.append(f"VS {report['vs']}")
    _text(c, M, min(y + 1 * mm, top - 14 * mm), " · ".join(id_bits), size=8, color=SECONDARY)

    kind = "ČTVRTLETNÍ HLÁŠENÍ K MÍSTNÍMU" if report.get("cadence") == "quarterly" else "HLÁŠENÍ K MÍSTNÍMU"
    _label(c, R, top, kind, right=True, color=CORAL)
    _text(c, R, top - 8 * mm, "poplatku z pobytu", size=15, bold=True, right=True)
    _text(c, R, top - 15 * mm, f"za {period_phrase(report)}", size=9, color=SECONDARY, right=True)

    # Two cards: recipient (the office) and period / created.
    left_w = 104 * mm
    right_x = M + left_w + 6 * mm
    inner_w = left_w - 10 * mm
    name_lines = _split(report["recipient_name"], inner_w, size=9, bold=True)
    detail = "\n".join(p for p in (report.get("recipient_address"), report.get("recipient_contact")) if p)
    detail_lines = _split(detail, inner_w, size=7.3) if detail else []
    card_h = max(23 * mm, 17 * mm + (len(name_lines) - 1) * 11 + len(detail_lines) * 9.5 + (2 if detail_lines else 0))
    card_y = H - 52 * mm - card_h
    _card(c, M, card_y, left_w, card_h, tinted=True)
    _label(c, M + 5 * mm, card_y + card_h - 7 * mm, "PŘÍJEMCE · SPRÁVCE POPLATKU")
    yy = _wrap(c, M + 5 * mm, card_y + card_h - 14 * mm, report["recipient_name"], inner_w,
               size=9, bold=True, leading=11)
    if detail_lines:
        _wrap(c, M + 5 * mm, yy - 1, detail, inner_w, size=7.3, color=SECONDARY, leading=9.5)
    _card(c, right_x, card_y + card_h - 23 * mm, R - right_x, 23 * mm)
    _label(c, right_x + 5 * mm, card_y + card_h - 7 * mm, "OBDOBÍ / VYHOTOVENO")
    _text(c, right_x + 5 * mm, card_y + card_h - 14 * mm,
          f"{_date(report['period_start'])} – {_date(report['period_end'])}", size=7.5, bold=True)
    _text(c, right_x + 5 * mm, card_y + card_h - 19 * mm, _date(report["issued_on"]),
          size=7.5, color=MUTED)

    y = card_y - 9 * mm
    for line in (report.get("payer_seat"), report.get("payer_contact")):
        if line:
            _text(c, M, y, line, size=7.5, color=SECONDARY)
            y -= 5 * mm
    return y - 10 * mm


def _table_header(c, y):
    _label(c, M, y, "VÝPOČET ZA ZAŘÍZENÍ")
    _rule(c, y - 5 * mm, strong=True)
    headings = ((M, "ZAŘÍZENÍ", False), (R - 62 * mm, "LŮŽKODNY K POPLATKU", True),
                (R - 39 * mm, "SAZBA", True), (R, "POPLATEK", True))
    for x, text, right in headings:
        _label(c, x, y - 12 * mm, text, right=right)
    _rule(c, y - 16 * mm)
    return y - 25 * mm


def _row_height(row):
    name_lines = simpleSplit(row["property_name"], BOLD, 9, 79 * mm)
    address_lines = simpleSplit(row.get("property_address") or "", REG, 7.7, 79 * mm)
    return max(14 * mm, (len(name_lines) * 4.5 + len(address_lines) * 4 + 5) * mm)


def _table_row(c, y, row):
    bottom = y - _row_height(row)
    after_name = _wrap(c, M, y, row["property_name"], 79 * mm, size=9, bold=True, leading=4.5 * mm)
    if row.get("property_address"):
        _wrap(c, M, after_name - 0.3 * mm, row["property_address"], 79 * mm,
              size=7.7, color=MUTED, leading=4 * mm)
    _text(c, R - 62 * mm, y - 1 * mm, row["liable_nights"], size=9, right=True)
    _text(c, R - 39 * mm, y - 1 * mm, _amount(row["rate_czk"]), size=9, right=True)
    _text(c, R, y - 1 * mm, _amount(row["amount_czk"]), size=9, bold=True, right=True)
    _rule(c, bottom + 2 * mm)
    return bottom - 3 * mm


def _summary(c, y, report):
    summary_h = 27 * mm
    box_w = 78 * mm
    box_x = R - box_w
    _card(c, box_x, y - summary_h, box_w, summary_h, tinted=True)
    payee = (report.get("payee") or "").strip()
    _label(c, box_x + 5 * mm, y - 8 * mm, f"CELKEM K ODVODU NA ÚČET {payee}" if payee else "CELKEM K ODVODU OBCI")
    _text(c, R - 5 * mm, y - 20 * mm, _amount(report["total_czk"]), size=19, bold=True, right=True)
    _label(c, M, y - 8 * mm, "SOUHRN")
    _text(c, M, y - 15 * mm, _nights(report["liable_nights"]) + " podléhá poplatku", size=8.5, color=SECONDARY)
    _text(c, M, y - 21 * mm, _nights(report["exempt_nights"]) + " osvobozeno", size=8.5, color=SECONDARY)
    _text(c, M, y - 26.5 * mm, "Lůžkoden = osoba × počet nocí", size=7, color=MUTED)
    y -= summary_h + 10 * mm
    if report.get("not_charged"):
        _label(c, M, y, "OSVOBOZENÉ OSOBY")
        _rule(c, y - 3.5 * mm)
        y -= 10 * mm
        for item in report["not_charged"]:
            _text(c, M, y, item["reason"], size=8.5)
            _text(c, R, y, f"{item['count']} os. · {_nights(item['nights'])}", size=8.5, right=True)
            _rule(c, y - 3.5 * mm)
            y -= 9 * mm
    return y - 8 * mm


def _signature(c, y, report):
    _label(c, M, y, "ZA PLÁTCE")
    _text(c, M, y - 8 * mm, f"Datum: {_date(report['issued_on'])}", size=7.8, color=SECONDARY)
    _text(c, M, y - 13 * mm, "Podpis, razítko / elektronické podání", size=7.8, color=MUTED)
    line_y = y - 11 * mm
    if report.get("signature_png"):
        raw = report["signature_png"].split(",", 1)[-1]
        image = ImageReader(io.BytesIO(base64.b64decode(raw)))
        iw, ih = image.getSize()
        scale = min(45 * mm / iw, 13 * mm / ih)
        c.drawImage(image, R - iw * scale, line_y + 1.5 * mm, iw * scale, ih * scale, mask="auto")
    elif report.get("signature_name"):
        _text(c, R, line_y + 2 * mm, report["signature_name"], size=9, bold=True, right=True)
    c.setStrokeColorRGB(*LINE)
    c.line(M + 80 * mm, line_y, R, line_y)
    y -= 21 * mm
    if report.get("instruction"):
        y = _wrap(c, M, y, report["instruction"], R - M, size=7, color=MUTED, leading=9.5)
    return y


def _signature_height(report) -> float:
    lines = len(_split(report.get("instruction") or "", R - M, size=7)) if report.get("instruction") else 0
    return 22 * mm + lines * 9.5


def render(report: dict, *, sample: bool = False) -> bytes:
    """Return the Czech A4 hlášení in the Invoice companion design.

    ``sample=True`` labels a mockup made with fictional data. It is not a
    preview bypass: the same identity and arithmetic checks still apply.
    """
    validate(report)
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4, pageCompression=1)
    c.setTitle(f"Hlášení k místnímu poplatku z pobytu – {period_phrase(report)}")
    c.setAuthor(report["payer_name"])
    c.setCreator("UbyHost")
    page = 1
    y = _table_header(c, _page_top(c, report, sample=sample))
    rows = report.get("rows") or []
    if not rows or not report["total_czk"] and not report.get("exempt_nights"):
        _text(c, M, y, "V tomto období nevznikla povinnost odvést poplatek.", size=9, color=SECONDARY)
        y -= 12 * mm
    for row in rows:
        if y - _row_height(row) < 55 * mm:
            _footer(c, page)
            c.showPage()
            page += 1
            y = _table_header(c, _page_top(c, report, continuation=True, sample=sample))
        y = _table_row(c, y, row)
    need = (27 + 10 + (10 if report.get("not_charged") else 0)
            + len(report.get("not_charged", [])) * 9 + 8) * mm + _signature_height(report)
    if y - need < 24 * mm:
        _footer(c, page)
        c.showPage()
        page += 1
        y = _page_top(c, report, continuation=True, sample=sample)
    y = _summary(c, y, report)
    _signature(c, y, report)
    _footer(c, page)
    c.showPage()
    c.save()
    return buf.getvalue()
