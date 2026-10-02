"""Invoice PDF renderer.

Copied from docs/plans/invoice-design/invoice_pdf_reference.py (the design is
finished; do not restyle). The document belongs to the HOST (the supplier);
UbyHost branding is limited to the coral rule, the coral document-type label and
the footer credit linked to ubyhost.com.

``inv`` is a dict with the invoice-table snapshot columns plus these view fields:
  buyer_country_name (Czech country name, empty for CZE), paid_via_label,
  stay_label, corrects_number (storno/ODD only). Items are invoice_item rows.
"""
from __future__ import annotations

import io
import os
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from . import payments

# ---- fonts: DejaVu Sans covers all of Czech; vendored under static/fonts ----
_FONT_DIR = os.path.join(os.path.dirname(__file__), "static", "fonts")
pdfmetrics.registerFont(TTFont("UHSans", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("UHSans-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
REG, BOLD = "UHSans", "UHSans-Bold"

# ---- brand tokens (docs/LOGO.md, static/tokens.css) ----
INK = (0x1B / 255, 0x1F / 255, 0x25 / 255)
INK_2 = (0x50 / 255, 0x50 / 255, 0x4C / 255)
MUTED = (0x73 / 255, 0x73 / 255, 0x6E / 255)
FAINT = (0x92 / 255, 0x92 / 255, 0x8C / 255)
LINE = (0xDE / 255, 0xDE / 255, 0xD9 / 255)
CANVAS = (0xF7 / 255, 0xF7 / 255, 0xF5 / 255)
CORAL = (0xD3 / 255, 0x54 / 255, 0x45 / 255)
GREEN = (0x16 / 255, 0x70 / 255, 0x44 / 255)
GREEN_BG = (0xE6 / 255, 0xF5 / 255, 0xEC / 255)

MARK_PATH = os.path.join(os.path.dirname(__file__), "static", "ubyhost-mark.png")
FOOTER_URL = "https://ubyhost.com/?utm_source=invoice&utm_medium=pdf"

W, H = A4
M = 18 * mm
CW = W - 2 * M

LABELS = {
    "cs": {
        "invoice": "Faktura", "tax_invoice": "Faktura – daňový doklad", "storno": "Storno faktury",
        "corrective": "Opravný daňový doklad", "no": "č.", "to": "k dokladu č.",
        "supplier": "Dodavatel", "customer": "Odběratel", "ico": "IČO", "dic": "DIČ",
        "issued": "Datum vystavení", "duzp": "Datum zdanitelného plnění", "due": "Datum splatnosti",
        "vs": "Variabilní symbol", "method": "Forma úhrady", "transfer": "Převodem",
        "stay": "Pobyt", "desc": "Popis", "qty": "Množství", "price": "Cena",
        "net": "Bez DPH", "rate": "Sazba", "vat": "DPH", "gross": "Celkem",
        "outside_vat": "mimo DPH", "recap": "Rekapitulace DPH", "base": "Základ",
        "total": "Celkem k úhradě", "paid_total": "Celkem uhrazeno", "paid": "UHRAZENO",
        "pay_title": "Platební údaje", "account": "Číslo účtu", "amount": "Částka",
        "qr": "QR Platba", "non_payer": "Nejsem plátce DPH.", "reason": "Důvod",
        "correction_date": "Den uskutečnění opravy (§ 42 odst. 3 zákona o DPH)",
        "footer": "Vystaveno v UbyHost – registrace hostů a faktury pro ubytovatele", "page": "Strana 1/1", "preview": "NÁHLED – NEPLATNÝ DOKLAD",
    },
    "en": {
        "invoice": "Invoice", "tax_invoice": "Tax invoice", "storno": "Cancellation of invoice",
        "corrective": "Credit note (corrective tax document)", "no": "No.", "to": "to document No.",
        "supplier": "Supplier", "customer": "Customer", "ico": "Company ID (IČO)", "dic": "VAT ID (DIČ)",
        "issued": "Issue date", "duzp": "Tax point (DUZP)", "due": "Due date",
        "vs": "Payment reference (VS)", "method": "Payment method", "transfer": "Bank transfer",
        "stay": "Stay", "desc": "Description", "qty": "Qty", "price": "Price",
        "net": "Net", "rate": "VAT rate", "vat": "VAT", "gross": "Total",
        "outside_vat": "outside VAT", "recap": "VAT summary", "base": "Base",
        "total": "Total due", "paid_total": "Total paid", "paid": "PAID",
        "pay_title": "Payment details", "account": "Account (CZ)", "amount": "Amount",
        "qr": "QR Platba", "non_payer": "Not a VAT payer (Nejsem plátce DPH).", "reason": "Reason",
        "correction_date": "Date of correction (§ 42(3) VAT Act)",
        "footer": "Issued with UbyHost – guest registration and invoicing for hosts", "page": "Page 1/1", "preview": "PREVIEW – NOT A VALID DOCUMENT",
    },
}


def money(haler: int) -> str:
    """1 234,50 Kč — always Czech format (the document is issued in CZ)."""
    value = Decimal(haler) / 100
    text = f"{abs(value):,.2f}".replace(",", "\u00a0").replace(".", ",")
    return ("−" if haler < 0 else "") + text + " Kč"


def cz_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(d)}. {int(m)}. {y}"


def _text(c, x, y, s, font=REG, size=9, color=INK, right=False):
    c.setFont(font, size)
    c.setFillColorRGB(*color)
    (c.drawRightString if right else c.drawString)(x, y, s)


def _label(c, x, y, s, right=False):
    _text(c, x, y, s.upper(), BOLD, 6.5, MUTED, right)


def _wrap(c, x, y, s, width, font=REG, size=9, color=INK, leading=None):
    leading = leading or size * 1.35
    for line in simpleSplit(s or "", font, size, width):
        _text(c, x, y, line, font, size, color)
        y -= leading
    return y


class TooLong(ValueError):
    """The content would run into the footer: an issued PDF must be one clean page."""


def too_long(inv: dict, items: list, lang: str = "cs") -> bool:
    try:
        render(inv, items, lang, strict=True)
    except TooLong:
        return True
    return False


def render(
    inv: dict, items: list, lang: str = "cs", preview: bool = False, strict: bool = False
) -> bytes:
    L = LABELS[lang]
    payer = inv["vat_status"] == "payer"
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4, pageCompression=1)
    c.setTitle(f"{L['invoice']} {inv['number']}")
    c.setAuthor(inv["seller_name"])
    c.setCreator("UbyHost")

    c.setFillColorRGB(*CORAL)
    c.rect(0, H - 1.6 * mm, W, 1.6 * mm, stroke=0, fill=1)

    top = H - M - 2 * mm
    _label(c, M, top + 6 * mm, L["supplier"])
    _text(c, M, top, inv["seller_name"], BOLD, 15, INK)
    y = top - 5.5 * mm
    y = _wrap(c, M, y, inv["seller_seat"], 90 * mm, size=8.5, color=INK_2)
    ids = []
    if inv.get("seller_ico"):
        ids.append(f"{L['ico']} {inv['seller_ico']}")
    if payer and inv.get("seller_dic"):
        ids.append(f"{L['dic']} {inv['seller_dic']}")
    if ids:
        _text(c, M, y, "   ·   ".join(ids), size=8.5, color=INK_2)

    kind = inv["kind"]
    title = {"invoice": L["tax_invoice"] if payer else L["invoice"],
             "storno": L["storno"], "corrective": L["corrective"]}[kind]
    _text(c, W - M, top + 0.5 * mm, title.upper(), BOLD, 8, CORAL, right=True)
    if lang != "cs":
        cs_title = {"invoice": LABELS["cs"]["tax_invoice"] if payer else LABELS["cs"]["invoice"],
                    "storno": LABELS["cs"]["storno"], "corrective": LABELS["cs"]["corrective"]}[kind]
        _text(c, W - M, top + 4.2 * mm, cs_title, REG, 7, MUTED, right=True)
    _text(c, W - M, top - 8 * mm, inv["number"], BOLD, 20, INK, right=True)
    if inv.get("corrects_number"):
        _text(c, W - M, top - 13.5 * mm, f"{L['to']} {inv['corrects_number']}", size=8.5, color=INK_2, right=True)

    card_top = top - 24 * mm
    card_h = 36 * mm
    gap = 6 * mm
    left_w = CW * 0.56
    right_w = CW - left_w - gap
    c.setFillColorRGB(*CANVAS)
    c.roundRect(M, card_top - card_h, left_w, card_h, 3 * mm, stroke=0, fill=1)
    _label(c, M + 5 * mm, card_top - 6.5 * mm, L["customer"])
    buyer_lines = [
        inv["buyer_name"],
        inv.get("buyer_street", ""),
        " ".join(p for p in [inv.get("buyer_zip", ""), inv.get("buyer_city", "")] if p),
        inv.get("buyer_country_name", ""),
        "   ·   ".join(p for p in [
            f"{L['ico']} {inv['buyer_ico']}" if inv.get("buyer_ico") else "",
            f"{L['dic']} {inv['buyer_dic']}" if inv.get("buyer_dic") else ""] if p),
    ]
    yy = card_top - 12.5 * mm
    for j, line in enumerate([ln for ln in buyer_lines if ln]):
        yy = _wrap(c, M + 5 * mm, yy, line, left_w - 10 * mm,
                   font=BOLD if j == 0 else REG, size=10.5 if j == 0 else 8.5,
                   color=INK if j == 0 else INK_2, leading=4.5 * mm)

    facts = [(L["issued"], cz_date(inv["issue_date"]))]
    if payer and inv.get("duzp"):
        facts.append((L["duzp"], cz_date(inv["duzp"])))
    if inv.get("due_date") and not inv.get("paid_on"):
        facts.append((L["due"], cz_date(inv["due_date"])))
    facts.append((L["vs"], inv["vs"]))
    facts.append((L["method"], inv.get("paid_via_label") if inv.get("paid_on") else L["transfer"]))
    rx = M + left_w + gap
    c.setStrokeColorRGB(*LINE); c.setLineWidth(0.6)
    c.roundRect(rx, card_top - card_h, right_w, card_h, 3 * mm, stroke=1, fill=0)
    row_h = (card_h - 6 * mm) / len(facts)
    for i, (lab, val) in enumerate(facts):
        ly = card_top - 6.5 * mm - i * row_h
        _text(c, rx + 5 * mm, ly, lab, REG, 8, MUTED)
        _text(c, rx + right_w - 5 * mm, ly, val or "—", BOLD, 8.5, INK, right=True)
    fy = card_top - card_h

    sy = fy - 9 * mm
    if inv.get("stay_label"):
        _label(c, M, sy, L["stay"])
        _text(c, M + 14 * mm, sy, inv["stay_label"], size=8.5, color=INK_2)
        sy -= 8 * mm

    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.8)
    c.line(M, sy, W - M, sy)
    hy = sy - 4.6 * mm
    if payer:
        cols = [(L["desc"], M, False), (L["net"], W - M - 72 * mm, True), (L["rate"], W - M - 52 * mm, True),
                (L["vat"], W - M - 30 * mm, True), (L["gross"], W - M, True)]
    else:
        cols = [(L["desc"], M, False), (L["qty"], W - M - 38 * mm, True), (L["price"], W - M, True)]
    for lab, x, right in cols:
        _label(c, x, hy, lab, right=right)
    ry = hy - 3 * mm
    c.setStrokeColorRGB(*LINE)
    c.setLineWidth(0.5)
    c.line(M, ry, W - M, ry)
    desc_w = (CW - 100 * mm) if payer else (CW - 50 * mm)
    for it in items:
        lines = simpleSplit(it["description"], REG, 9, desc_w)[:2]
        row_top = ry - 5.2 * mm
        yy = row_top
        for ln in lines:
            _text(c, M, yy, ln, size=9)
            yy -= 4.2 * mm
        if payer and it.get("vat_rate") is not None:
            qty = max(it.get("quantity", 1), 1)
            unit_net = (it.get("base_haler") or 0) // qty
            detail = f"{qty} {it.get('unit', '')} × {money(unit_net)}".strip()
            _text(c, M, yy, detail, size=8, color=MUTED)
            yy -= 4.2 * mm
        if payer:
            if it.get("vat_rate") is None:
                _text(c, W - M - 72 * mm, row_top, money(it["gross_haler"]), size=9, right=True)
                _text(c, W - M - 52 * mm, row_top, L["outside_vat"], size=8, color=MUTED, right=True)
                _text(c, W - M - 30 * mm, row_top, "—", size=9, color=MUTED, right=True)
            else:
                _text(c, W - M - 72 * mm, row_top, money(it["base_haler"]), size=9, right=True)
                _text(c, W - M - 52 * mm, row_top, f"{it['vat_rate']} %", size=9, right=True)
                _text(c, W - M - 30 * mm, row_top, money(it["vat_haler"]), size=9, right=True)
        else:
            _text(c, W - M - 38 * mm, row_top, str(it.get("quantity", 1)), size=9, right=True)
        _text(c, W - M, row_top, money(it["gross_haler"]), BOLD, 9, INK, right=True)
        ry = yy - 1.5 * mm
        c.setStrokeColorRGB(*LINE)
        c.line(M, ry, W - M, ry)

    ty = ry - 9 * mm
    if payer:
        _label(c, M, ty, L["recap"])
        rates = {}
        for it in items:
            if it.get("vat_rate") is not None:
                r = rates.setdefault(it["vat_rate"], [0, 0, 0])
                r[0] += it["base_haler"]; r[1] += it["vat_haler"]; r[2] += it["gross_haler"]
        yy = ty - 5 * mm
        for rate, (b, v, g) in sorted(rates.items()):
            _text(c, M, yy, f"{rate} %", size=8.5, color=INK_2)
            # Right edges leave room for "Základ 99 999,99 Kč" after the rate.
            _text(c, M + 50 * mm, yy, f"{L['base']} {money(b)}", size=8.5, color=INK_2, right=True)
            _text(c, M + 84 * mm, yy, f"{L['vat']} {money(v)}", size=8.5, color=INK_2, right=True)
            yy -= 4.5 * mm
    paid = bool(inv.get("paid_on"))
    box_w, box_h = 78 * mm, 22 * mm
    bx, by = W - M - box_w, ty - box_h + 4 * mm
    c.setFillColorRGB(*CANVAS)
    c.roundRect(bx, by, box_w, box_h, 3 * mm, stroke=0, fill=1)
    is_invoice = kind == "invoice"
    _label(c, bx + 5 * mm, by + box_h - 7 * mm,
           (L["paid_total"] if paid else L["total"]) if is_invoice else L["gross"])
    _text(c, bx + box_w - 5 * mm, by + 5.5 * mm, money(inv["total_haler"]), BOLD, 17, INK, right=True)
    if paid and is_invoice:
        pill = f"{L['paid']} {cz_date(inv['paid_on'])}"
        pw = pdfmetrics.stringWidth(pill, BOLD, 6.5) + 5 * mm
        px = bx + box_w - 5 * mm - pw
        c.setFillColorRGB(*GREEN_BG)
        c.roundRect(px, by + box_h - 8.6 * mm, pw, 4.8 * mm, 2.4 * mm, stroke=0, fill=1)
        _text(c, px + 2.5 * mm, by + box_h - 7 * mm, pill, BOLD, 6.5, GREEN)

    py = by - 12 * mm
    if not paid and inv["total_haler"] > 0 and inv.get("seller_iban"):
        _label(c, M, py, L["pay_title"])
        rows = []
        if inv.get("seller_bank_account") and "/" in inv["seller_bank_account"]:
            rows.append((L["account"], inv["seller_bank_account"]))
        rows.append(("IBAN", payments.format_iban(inv["seller_iban"])))
        if inv.get("seller_bic"):
            rows.append(("BIC / SWIFT", inv["seller_bic"]))
        rows += [(L["vs"], inv["vs"]), (L["amount"], money(inv["total_haler"]))]
        yy = py - 6 * mm
        for lab, val in rows:
            _text(c, M, yy, lab, size=8.5, color=MUTED)
            _text(c, M + 42 * mm, yy, val, BOLD, 9, INK)
            yy -= 5 * mm
        png = payments.qr_png_bytes(payments.spayd(
            inv["seller_iban"], Decimal(inv["total_haler"]) / 100, inv["vs"],
            f"FAKTURA {inv['number']}", inv.get("seller_bic") or ""))
        q = 30 * mm
        qx, qy = W - M - q, py - q - 1 * mm
        c.drawImage(ImageReader(io.BytesIO(png)), qx, qy, q, q)
        cap_w = pdfmetrics.stringWidth(L["qr"], BOLD, 7)
        _text(c, qx + (q - cap_w) / 2, qy - 3.5 * mm, L["qr"], BOLD, 7, MUTED)
        py = min(yy, qy - 8 * mm)
    else:
        py = by - 6 * mm

    ny = py - 4 * mm
    if kind in ("storno", "corrective") and inv.get("correction_reason"):
        ny = _wrap(c, M, ny, f"{L['reason']}: {inv['correction_reason']}", CW, size=8.5, color=INK_2)
    if kind == "corrective" and inv.get("correction_date"):
        ny = _wrap(c, M, ny, f"{L['correction_date']}: {cz_date(inv['correction_date'])}", CW, size=8.5, color=INK_2)
    if inv.get("note"):
        ny = _wrap(c, M, ny, inv["note"], CW, size=8.5, color=INK_2)
    if not payer:
        ny = _wrap(c, M, ny, L["non_payer"], CW, size=8.5, color=INK_2)

    fy2 = M + 10 * mm
    # ny is the next baseline; the last line's descenders sit about 2 mm above
    # it, and the registry line's cap height reaches about 7 mm above fy2.
    if strict and ny + 2 * mm < fy2 + 7 * mm:
        raise TooLong()
    reg = inv.get("seller_registry") or ""
    contact = "   ·   ".join(p for p in [inv.get("seller_email"), inv.get("seller_phone")] if p)
    if reg:
        _text(c, M, fy2 + 4.5 * mm, reg, size=7, color=MUTED)
    if contact:
        _text(c, M, fy2, contact, size=7, color=MUTED)
    c.setStrokeColorRGB(*LINE); c.setLineWidth(0.5)
    c.line(M, M + 5 * mm, W - M, M + 5 * mm)
    mark = 3.6 * mm
    c.drawImage(MARK_PATH, M, M - 0.4 * mm, mark, mark, mask="auto")
    credit = f"{L['footer']}  ·  ubyhost.com"
    _text(c, M + mark + 1.8 * mm, M + 0.4 * mm, credit, size=7, color=FAINT)
    cw_ = pdfmetrics.stringWidth(credit, REG, 7)
    c.linkURL(FOOTER_URL, (M, M - 1 * mm, M + mark + 1.8 * mm + cw_, M + 3.5 * mm), relative=0)
    _text(c, W - M, M + 0.4 * mm, L["page"], size=7, color=FAINT, right=True)

    if preview:
        c.saveState()
        c.setFillColorRGB(*CORAL); c.setFillAlpha(0.12)
        c.translate(W / 2, H / 2); c.rotate(35)
        c.setFont(BOLD, 34)
        c.drawCentredString(0, 0, L["preview"])
        c.restoreState()

    c.showPage()
    c.save()
    return buf.getvalue()
