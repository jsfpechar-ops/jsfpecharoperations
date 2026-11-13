"""Write go/internal/pdf/testdata/invoice_pdf_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/invoice_pdf_golden.py

It runs invoice_pdf.render for each fixture in CASES with the reportlab canvas
replaced by a recorder, and writes the draw operations (text with font, size,
colour and position; rectangles; lines; images; links; the preview watermark)
plus the too_long answer. go/internal/pdf/invoice_test.go lays out the same
fixtures in Go and compares the operations (numbers within 0.01 pt).
The QR image op carries the SPAYD text it encodes, not the pixels.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "pdf" / "testdata" / "invoice_pdf_golden.json"

BASE = {
    "number": "2026-0042", "kind": "invoice", "vat_status": "payer",
    "seller_name": "Novák Apartments s.r.o.", "seller_seat": "Dlouhá 12, 110 00 Praha 1",
    "seller_ico": "12345678", "seller_dic": "CZ12345678",
    "seller_registry": "Vedená u Městského soudu v Praze, oddíl C, vložka 123456",
    "seller_email": "host@example.test", "seller_phone": "+420 777 000 111",
    "seller_iban": "CZ6508000000192000145399", "seller_bank_account": "192000145399/0800", "seller_bic": "GIBACZPX",
    "buyer_name": "Jan Dvořák", "buyer_street": "Hlavní 1", "buyer_zip": "602 00", "buyer_city": "Brno",
    "buyer_country_name": "", "buyer_ico": "", "buyer_dic": "",
    "issue_date": "2026-11-03", "duzp": "2026-11-03", "due_date": "2026-11-17", "paid_on": None, "vs": "2026004200",
    "paid_via_label": "", "stay_label": "", "corrects_number": "", "correction_reason": "", "correction_date": "",
    "note": "", "partial_correction": False, "total_haler": 0,
}


def item(desc, qty=1, unit="noc", rate=21, base=None, vat=None, gross=None):
    if rate is None:
        return {"description": desc, "quantity": qty, "unit": unit, "vat_rate": None,
                "base_haler": gross, "vat_haler": 0, "gross_haler": gross}
    return {"description": desc, "quantity": qty, "unit": unit, "vat_rate": rate,
            "base_haler": base, "vat_haler": vat, "gross_haler": gross if gross is not None else base + vat}


def inv(**kw):
    d = dict(BASE)
    d.update(kw)
    return d


LONG = ("Poznámka k dokladu s dlouhým textem, který se musí zalomit na několik řádků, "
        "protože se nevejde na jeden. Obsahuje také nezlomitelnou mezeru a velmi dlouhé slovo "
        "Nejdelšíslovonasvětěkterénemá žádnou mezeru uvnitř a přesto je potřeba ho vykreslit. ") * 2

CASES = [
    {"name": "cs_payer_unpaid_qr", "lang": "cs", "inv": inv(total_haler=1210000, stay_label="12.–15. 11. 2026"),
     "items": [item("Ubytování Praha, 3 noci", 3, "noc", 12, 300000, 36000), item("Úklid", 1, "ks", 21, 800000, 168000),
               item("Městská taxa", 1, "ks", None, gross=58000)]},
    {"name": "en_nonpayer_unpaid_qr", "lang": "en",
     "inv": inv(vat_status="non_payer", seller_dic="", seller_bic="", total_haler=123456789, note="Thank you."),
     "items": [item("Subscription", 2, "ks", None, gross=100000000), item("Setup fee " * 12, 1, "ks", None, gross=23456789)]},
    {"name": "cs_storno_negative", "lang": "cs",
     "inv": inv(kind="storno", number="2026-0043", corrects_number="2026-0042", correction_reason="Chybná částka",
                total_haler=-1210000),
     "items": [item("Storno ubytování", -3, "noc", 12, -300000, -36000, -336000), item("Storno úklid", -1, "ks", 21, -999999, -210000)]},
    {"name": "en_credit_note_partial", "lang": "en",
     "inv": inv(kind="storno", partial_correction=True, number="2026-0044", corrects_number="2026-0042",
                correction_reason="Price difference", total_haler=-12100),
     "items": [item("Discount", 1, "ks", 21, -10000, -2100)]},
    {"name": "cs_corrective_with_date", "lang": "cs",
     "inv": inv(kind="corrective", number="2026-0045", corrects_number="2026-0042", correction_reason="Oprava sazby DPH",
                correction_date="2026-11-10", total_haler=-5000),
     "items": [item("Oprava", 1, "ks", 12, -4464, -536)]},
    {"name": "en_corrective_nonpayer", "lang": "en",
     "inv": inv(kind="corrective", vat_status="non_payer", number="2026-0046", corrects_number="2026-0042",
                correction_reason="Typo", correction_date="2026-11-10", total_haler=-100, seller_iban=""),
     "items": [item("Fix", 1, "ks", None, gross=-100)]},
    {"name": "cs_paid_pill", "lang": "cs",
     "inv": inv(paid_on="2026-11-05", paid_via_label="Platební karta", total_haler=250000, stay_label="1.–3. 11."),
     "items": [item("Ubytování", 2, "noc", 12, 223214, 26786)]},
    {"name": "en_preview_foreign_buyer", "lang": "en", "preview": True,
     "inv": inv(buyer_name="Hans Müller GmbH", buyer_street="Hauptstraße 5", buyer_zip="10115", buyer_city="Berlin",
                buyer_country_name="Německo", buyer_ico="123", buyer_dic="DE123456789", total_haler=100000),
     "items": [item("Stay", 1, "ks", 21, 82645, 17355)]},
    {"name": "cs_long_text_wrap", "lang": "cs",
     "inv": inv(total_haler=500000, note=LONG, seller_seat="Velmi dlouhá ulice s číslem popisným 1234/56, Praha 1 - Staré Město, Česká republika",
                buyer_name="Společnost s ručením omezeným s velmi dlouhým názvem, která se musí zalomit",
                buyer_street="Ulice 1", buyer_ico="12345678", buyer_dic="CZ12345678"),
     "items": [item("Velmi dlouhý popis položky " * 8, 1, "ks", 21, 413223, 86777)]},
    {"name": "cs_too_long", "lang": "cs", "inv": inv(total_haler=100, note=("Dlouhá poznámka " * 400)),
     "items": [item("Položka", 1, "ks", 21, 83, 17)]},
    {"name": "en_zero_total_no_qr_many_items", "lang": "en",
     "inv": inv(total_haler=0, seller_registry="", seller_email="", seller_phone=""),
     "items": [item(f"Item {i}", 1, "ks", 21, 0, 0, 0) for i in range(4)]},
]


class Recorder:
    ops: list = []


def _build_recorder():
    from reportlab.pdfgen import canvas as pdfcanvas

    class Rec(pdfcanvas.Canvas):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.fill, self.stroke, self.lw = (0, 0, 0), (0, 0, 0), 1.0
            self.font, self.size = "Helvetica", 12
            self.title = self.author = None
            self.wm = None

        def setTitle(self, t):
            self.title = t
            super().setTitle(t)

        def setAuthor(self, a):
            self.author = a
            super().setAuthor(a)

        def setCreator(self, c):
            Recorder.ops.append({"op": "meta", "title": self.title, "author": self.author, "creator": c})
            super().setCreator(c)

        def setFillColorRGB(self, r, g, b, alpha=None):
            self.fill = (r, g, b)
            super().setFillColorRGB(r, g, b, alpha)

        def setStrokeColorRGB(self, r, g, b, alpha=None):
            self.stroke = (r, g, b)
            super().setStrokeColorRGB(r, g, b, alpha)

        def setLineWidth(self, w):
            self.lw = w
            super().setLineWidth(w)

        def setFont(self, name, size, leading=None):
            self.font, self.size = name, size
            super().setFont(name, size, leading)

        def _text(self, x, y, s, align):
            Recorder.ops.append({"op": "text", "s": s, "font": self.font, "size": self.size,
                                 "color": list(self.fill), "x": x, "y": y, "align": align})

        def drawString(self, x, y, s, *a, **kw):
            self._text(x, y, s, "left")
            super().drawString(x, y, s, *a, **kw)

        def drawRightString(self, x, y, s, *a, **kw):
            self._text(x, y, s, "right")
            super().drawRightString(x, y, s, *a, **kw)

        def _rect(self, x, y, w, h, r, stroke, fill):
            op = {"op": "rect", "x": x, "y": y, "w": w, "h": h, "r": r}
            if fill:
                op["fill"] = list(self.fill)
            if stroke:
                op["stroke"], op["lw"] = list(self.stroke), self.lw
            Recorder.ops.append(op)

        def rect(self, x, y, w, h, stroke=1, fill=0):
            self._rect(x, y, w, h, 0, stroke, fill)
            super().rect(x, y, w, h, stroke=stroke, fill=fill)

        def roundRect(self, x, y, w, h, radius, stroke=1, fill=0):
            self._rect(x, y, w, h, radius, stroke, fill)
            super().roundRect(x, y, w, h, radius, stroke=stroke, fill=fill)

        def line(self, x1, y1, x2, y2):
            Recorder.ops.append({"op": "line", "x": x1, "y": y1, "x2": x2, "y2": y2,
                                 "lw": self.lw, "color": list(self.stroke)})
            super().line(x1, y1, x2, y2)

        def drawImage(self, image, x, y, width=None, height=None, mask=None, **kw):
            op = {"op": "image", "name": "mark" if mask == "auto" else "qr", "x": x, "y": y, "w": width, "h": height}
            if op["name"] == "qr":
                op["payload"] = Recorder.payload
            Recorder.ops.append(op)
            super().drawImage(image, x, y, width, height, mask=mask, **kw)

        def linkURL(self, url, rect, relative=0, **kw):
            Recorder.ops.append({"op": "link", "url": url, "x": rect[0], "y": rect[1], "x2": rect[2], "y2": rect[3]})
            super().linkURL(url, rect, relative=relative, **kw)

        def setFillAlpha(self, a):
            self.wm = {"alpha": a, "color": list(self.fill)}
            super().setFillAlpha(a)

        def translate(self, x, y):
            if self.wm is not None:
                self.wm.update(x=x, y=y)
            super().translate(x, y)

        def rotate(self, theta):
            if self.wm is not None:
                self.wm["angle"] = theta
            super().rotate(theta)

        def drawCentredString(self, x, y, s, *a, **kw):
            wm = self.wm
            Recorder.ops.append({"op": "watermark", "s": s, "font": self.font, "size": self.size,
                                 "color": wm["color"], "alpha": wm["alpha"], "angle": wm["angle"],
                                 "x": wm["x"], "y": wm["y"]})
            super().drawCentredString(x, y, s, *a, **kw)

    return Rec


def render() -> str:
    from app import invoice_pdf, payments

    real_qr = payments.qr_png_bytes

    def qr(payload):
        Recorder.payload = payload
        return real_qr(payload)

    payments.qr_png_bytes = qr
    invoice_pdf.pdfcanvas = types.SimpleNamespace(Canvas=_build_recorder())
    out = []
    for case in CASES:
        Recorder.ops = []
        long = invoice_pdf.too_long(case["inv"], case["items"], case["lang"])
        Recorder.ops = []
        if long:
            ops = []
        else:
            invoice_pdf.render(case["inv"], case["items"], case["lang"], preview=bool(case.get("preview")))
            ops = Recorder.ops
        out.append({"name": case["name"], "lang": case["lang"], "preview": bool(case.get("preview")),
                    "invoice": case["inv"], "items": case["items"], "too_long": long, "ops": ops})
    return json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "invoice_pdf_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
