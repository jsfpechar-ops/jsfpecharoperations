"""Write hlaseni_golden.json from the real Python renderer (verification aid).

Run from the repo root (needs reportlab and Pillow; install into a venv under
/var/tmp, never commit it):

    python3 go/internal/stayfeepdf/testdata/gen_golden.py

It runs App/app/stay_fee_remittance_pdf.render for each case with the reportlab
canvas replaced by a recorder and writes the draw operations per page. The Go
test lays out the same cases and compares text, fonts, sizes, colours and
positions (within 0.01 pt).
"""
import base64
import io
import json
import os
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
APP = ROOT / "App"
OUT = HERE / "hlaseni_golden.json"


def png_b64():
    from PIL import Image
    im = Image.new("RGBA", (200, 60), (0, 0, 0, 0))
    for x in range(10, 190):
        im.putpixel((x, 30 + (x % 7)), (20, 20, 120, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def row(name, addr, nights, rate):
    return {"property_name": name, "property_address": addr, "liable_nights": nights,
            "rate_czk": rate, "amount_czk": nights * rate}


def rep(rows, **kw):
    d = {"payer_name": "Novák Apartments s.r.o.", "payer_seat": "Dlouhá 12, 110 00 Praha 1",
         "payer_ico": "12345678", "payer_contact": "host@example.test", "vs": "1234567890",
         "recipient_name": "Městský úřad Example", "recipient_address": "Náměstí 1, 100 00 Praha",
         "recipient_contact": "podatelna@example.test", "payee": "", "instruction": "",
         "cadence": "monthly", "period_start": "2026-08-01", "period_end": "2026-08-31",
         "issued_on": "2026-09-03", "rows": rows, "not_charged": [],
         "signature_png": "", "signature_name": ""}
    d.update(kw)
    d["liable_nights"] = sum(r["liable_nights"] for r in rows)
    d["total_czk"] = sum(r["amount_czk"] for r in rows)
    d["exempt_nights"] = sum(i["nights"] for i in d["not_charged"])
    return d


LONG = "Velmi dlouhý název zařízení s mnoha slovy, který se musí zalomit na více řádků " * 2
CASES = [
    {"name": "month_single_signed_name", "sample": False,
     "report": rep([row("Byt Praha", "Hlavní 1, 110 00 Praha", 21, 50)], signature_name="Jan Novák")},
    {"name": "quarter_not_charged_payee_instruction_png", "sample": False,
     "report": rep([row("Byt A", "Ulice 1, Brno", 1, 21), row("Byt B", "", 3, 50), row("Byt C", "X", 4, 21), row("Byt D", "", 5, 21)],
                   cadence="quarterly", period_start="2026-07-01", period_end="2026-09-30", payee="Obec Example",
                   instruction="Platbu pošlete na účet obce.\nVariabilní symbol uveďte vždy. " * 3,
                   not_charged=[{"reason": "Mladší 18 let", "count": 2, "nights": 6},
                                {"reason": "Osvobozeno ubytovatelem (důvod v evidenční knize)", "count": 1, "nights": 1}],
                   signature_png=png_b64())},
    {"name": "long_names_wrap", "sample": False,
     "report": rep([row(LONG, "Velmi dlouhá adresa " * 8, 10, 50)],
                   payer_name="Společnost s ručením omezeným s velmi dlouhým názvem plátce, která se musí zalomit na tři řádky a více ano",
                   recipient_name=LONG, recipient_address="Adresa úřadu " * 10)},
    {"name": "many_rows_two_pages_sample", "sample": True,
     "report": rep([row(f"Byt číslo {i}", f"Ulice {i}, Praha", i + 1, 50) for i in range(14)],
                   not_charged=[{"reason": "Mladší 18 let", "count": 20, "nights": 40}])},
    {"name": "zero_period", "sample": False, "report": rep([], period_start="2026-02-01", period_end="2026-02-28")},
    {"name": "removal_negative_row", "sample": False,
     "report": rep([row("Byt", "A", 11, 50), row("Byt", "A", -1, 50)])},
    {"name": "bad_total_refused", "sample": False,
     "report": dict(rep([row("Byt", "A", 2, 50)]), total_czk=1)},
]


class Recorder:
    ops: list = []


def build_recorder():
    from reportlab.pdfgen import canvas as pdfcanvas

    class Rec(pdfcanvas.Canvas):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.fill, self.stroke, self.lw = (0, 0, 0), (0, 0, 0), 1.0
            self.font, self.size = "Helvetica", 12
            self.title = self.author = None
            Recorder.ops = [[]]

        def setTitle(self, t):
            self.title = t
            super().setTitle(t)

        def setAuthor(self, a):
            self.author = a
            super().setAuthor(a)

        def setCreator(self, c):
            Recorder.ops[0].append({"op": "meta", "title": self.title, "author": self.author, "creator": c})
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
            Recorder.ops[-1].append({"op": "text", "s": s, "font": self.font, "size": self.size,
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
            Recorder.ops[-1].append(op)

        def rect(self, x, y, w, h, stroke=1, fill=0):
            self._rect(x, y, w, h, 0, stroke, fill)
            super().rect(x, y, w, h, stroke=stroke, fill=fill)

        def roundRect(self, x, y, w, h, radius, stroke=1, fill=0):
            self._rect(x, y, w, h, radius, stroke, fill)
            super().roundRect(x, y, w, h, radius, stroke=stroke, fill=fill)

        def line(self, x1, y1, x2, y2):
            Recorder.ops[-1].append({"op": "line", "x": x1, "y": y1, "x2": x2, "y2": y2,
                                     "lw": self.lw, "color": list(self.stroke)})
            super().line(x1, y1, x2, y2)

        def drawImage(self, image, x, y, width=None, height=None, mask=None, **kw):
            # the footer mark is drawn 4.5 mm wide; anything else is the signature
            name = "mark" if abs(width - 12.755905511811024) < 1e-6 else "signature"
            Recorder.ops[-1].append({"op": "image", "name": name, "x": x, "y": y, "w": width, "h": height})
            super().drawImage(image, x, y, width, height, mask=mask, **kw)

        def showPage(self):
            Recorder.ops.append([])
            super().showPage()

    return Rec


def render():
    from app import stay_fee_remittance_pdf as mod
    mod.pdfcanvas = types.SimpleNamespace(Canvas=build_recorder())
    out = []
    for case in CASES:
        Recorder.ops = [[]]
        try:
            mod.render(case["report"], sample=case["sample"])
        except ValueError as exc:
            out.append({"name": case["name"], "report": case["report"], "sample": case["sample"],
                        "error": str(exc), "pages": []})
            continue
        pages = [p for p in Recorder.ops if p]
        out.append({"name": case["name"], "report": case["report"], "sample": case["sample"],
                    "error": "", "pages": pages})
    return json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "g.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")
