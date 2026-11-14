"""Write go/internal/web/exports/testdata/registration_form_golden.json from the real Python.

Brief 1605. Run from App/ (no database needed):

    .venv/bin/python scripts/registration_form_golden.py           write the file
    .venv/bin/python scripts/registration_form_golden.py --check   exit 1 when stale

It runs housebook.registration_form_pdf for each fixture in CASES with the
database read replaced by the fixture row and the reportlab canvas replaced by
a recorder, and writes the draw operations (text with font, size, grey and
position; lines; the signature image box as drawImage fits it) together with
the row and reporting.signature_record's answer. exports/form_pdf_test.go
draws the same rows in Go and compares the operations (within 0.01 pt).
Fonts are written under the Go names (DejaVu is UHSans in go/internal/pdf).
The fixtures are made up.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "exports" / "testdata" / "registration_form_golden.json"
NOW_LOCAL = datetime(2026, 11, 13, 13, 5, 0)

# A 1x1 PNG and a 4x1 PNG (both valid signatures for the drawing).
PNG_1X1 = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
           "DwAChwGA60e6kgAAAABJRU5ErkJggg==")
PNG_4X1 = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAABCAYAAAD5PA/NAAAAD0lEQVR4nGNkYGD4"
           "z4AEAA0VAQE65TbjAAAAAElFTkSuQmCC")

BASE = {
    "id": 11, "reservation_id": 1, "surname": "Müller", "first_name": "Hans",
    "birth_date": "15061980", "nationality": "DEU", "doc_number": "C01X00T47", "visa_number": None,
    "res_street": "Hauptstr. 1", "res_city": "Berlin", "res_country": "deu", "purpose": "10",
    "note": None, "stay_from": None, "stay_to": None, "signature_png": PNG_1X1,
    "signed_at": "2026-05-01T10:00:00+00:00", "filled_at": "2026-05-01T09:59:00+00:00",
    "submit_state": "sent", "submitted_at": "2026-05-02T10:00:00+00:00", "manual_filed_at": None,
    "manual_reference": None, "notice_version": "2", "notice_ack_at": "2026-05-01T09:58:00+00:00",
    "notice_lang": "de", "signed_for_guest_id": None, "signed_for_role": None, "signed_for_at": None,
    "signed_for_wording": None, "res_from": "2026-05-01", "res_to": "2026-05-04",
    "internal_name": "Byt Dole", "uby_idub": "IDUB7", "uby_name": "Penzion U Lípy", "uby_mark": None,
    "addr_street": "Dlouhá", "addr_house_no": "12", "addr_orient_no": "3a", "addr_obec": "Praha",
    "addr_obec_cast": "Staré Město", "addr_zip": "110 00", "addr_okres": None,
}

ADULT = dict(BASE, id=21, first_name="Eva", surname="Nováková", birth_date="01011985")

CASES = [
    {"name": "own_signature_sent", "guest": dict(BASE)},
    {"name": "long_values_by_hand", "guest": dict(
        BASE, surname="Wolfeschlegelsteinhausenbergerdorff-Ostrava-Poruba", first_name="Maximilián Jindřich",
        nationality="XXX", uby_name=None, internal_name="Velmi dlouhý název ubytovacího zařízení v centru",
        addr_street="Nábřeží Kapitána Jaroše s velmi dlouhým názvem ulice", addr_orient_no=None,
        res_street="Calle de Alcalá 1234, escalera izquierda, piso tercero", res_city="Madrid", res_country="esp",
        purpose="99", note="Pozdní příjezd po půlnoci, klíče u souseda v přízemí",
        stay_from="2026-05-02", stay_to="2026-05-03", manual_filed_at="2026-05-02T08:00:00+00:00",
        manual_reference="UBY-12345", notice_version=None)},
    {"name": "signed_for_child", "adult": ADULT, "guest": dict(
        BASE, id=12, first_name="Kid", birth_date="01012020", signature_png=None, signed_at=None,
        filled_at=None, submit_state="pending", submitted_at=None, notice_version=None,
        signed_for_guest_id=21, signed_for_role="parent", signed_for_at="2026-05-01T10:05:00+00:00",
        signed_for_wording="v1")},
    {"name": "signed_for_unknown_role", "adult": ADULT, "guest": dict(
        BASE, id=13, first_name="Ann", birth_date="01012021", signature_png=None, signed_at=None,
        filled_at=None, submit_state="not_required", submitted_at=None,
        signed_for_guest_id=21, signed_for_role="cousin", signed_for_at=None, signed_for_wording=None)},
    {"name": "exempt_child", "guest": dict(
        BASE, id=14, first_name="Baby", birth_date="00002019", signature_png=None, signed_at=None,
        filled_at=None, submit_state="error", submitted_at=None, notice_version=None)},
    {"name": "imported_signature", "guest": dict(
        BASE, id=15, signature_png="imported", signed_at=None, filled_at=None, submit_state="blocked",
        submitted_at=None, birth_date=None, nationality=None, doc_number=None, res_street=None, res_city=None,
        res_country=None, purpose=None, uby_idub=None, addr_street=None, addr_house_no=None,
        addr_obec_cast=None, addr_zip=None, addr_obec=None)},
    {"name": "bad_base64_signature", "guest": dict(
        BASE, id=16, signature_png="data:image/png;base64,xx", submit_state="odd_state", submitted_at=None)},
    {"name": "wide_signature_no_house", "guest": dict(
        BASE, id=17, signature_png=PNG_4X1, addr_house_no=None, addr_orient_no="7", visa_number="VISA-1",
        stay_from="2026-05-01", stay_to="2026-05-04")},
    {"name": "no_signature", "guest": dict(
        BASE, id=18, signature_png=None, signed_at=None, submit_state="sent", manual_filed_at=None)},
]

GO_FONTS = {"DejaVu": "UHSans", "DejaVu-Bold": "UHSans-Bold"}


class Recorder:
    ops: list = []


def _build_recorder():
    from reportlab.lib.boxstuff import aspectRatioFix
    from reportlab.pdfgen import canvas as pdfcanvas

    class Rec(pdfcanvas.Canvas):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.fill, self.stroke, self.lw = (0, 0, 0), (0, 0, 0), 1.0
            self.font, self.size = "Helvetica", 12

        def setFillGray(self, g, alpha=None):
            self.fill = (g, g, g)
            super().setFillGray(g, alpha)

        def setStrokeGray(self, g, alpha=None):
            self.stroke = (g, g, g)
            super().setStrokeGray(g, alpha)

        def setLineWidth(self, w):
            self.lw = w
            super().setLineWidth(w)

        def setFont(self, name, size, leading=None):
            self.font, self.size = name, size
            super().setFont(name, size, leading)

        def _text(self, x, y, s, align):
            Recorder.ops.append({"op": "text", "s": s, "font": GO_FONTS.get(self.font, self.font),
                                 "size": self.size, "color": list(self.fill), "x": x, "y": y, "align": align})

        def drawString(self, x, y, s, *a, **kw):
            self._text(x, y, s, "left")
            super().drawString(x, y, s, *a, **kw)

        def drawRightString(self, x, y, s, *a, **kw):
            self._text(x, y, s, "right")
            super().drawRightString(x, y, s, *a, **kw)

        def line(self, x1, y1, x2, y2):
            Recorder.ops.append({"op": "line", "x": x1, "y": y1, "x2": x2, "y2": y2,
                                 "lw": self.lw, "color": list(self.stroke)})
            super().line(x1, y1, x2, y2)

        def drawImage(self, image, x, y, width=None, height=None, mask=None, **kw):
            # Only a drawn image is recorded: when reportlab raises, the form
            # draws the fallback line instead.
            result = super().drawImage(image, x, y, width, height, mask=mask, **kw)
            iw, ih = image.getSize()
            fx, fy, fw, fh, _scale = aspectRatioFix(kw.get("preserveAspectRatio", False), kw.get("anchor", "c"),
                                                     x, y, width, height, iw, ih)
            Recorder.ops.append({"op": "image", "name": "signature", "x": fx, "y": fy, "w": fw, "h": fh})
            return result

    return Rec


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D102
        return NOW_LOCAL


def render() -> str:
    from app import db, housebook, reporting

    housebook.pdfcanvas.Canvas = _build_recorder()
    out = []
    for case in CASES:
        guest, adult = case["guest"], case.get("adult")

        def query_one(sql, params=(), guest=guest, adult=adult):
            if "FROM guest g JOIN reservation r" in sql:
                return guest if params[0] == guest["id"] else None
            if sql.startswith("SELECT * FROM guest WHERE id = ?"):
                return adult if adult and params[0] == adult["id"] else None
            raise AssertionError(f"unexpected query: {sql}")

        Recorder.ops = []
        with mock.patch.object(db, "query_one", query_one), \
                mock.patch.object(housebook, "datetime", FrozenDatetime):
            record = reporting.signature_record(guest, {"date_from": guest["res_from"], "date_to": guest["res_to"]})
            Recorder.ops = []
            housebook.registration_form_pdf(guest["id"])
        out.append({"name": case["name"], "now": NOW_LOCAL.isoformat(), "guest": guest,
                    "record": record, "ops": Recorder.ops})
    return json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list) -> int:
    text = render()
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if "--check" in argv:
        if current != text:
            print(f"stale: {OUT}")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "registration_form_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    sys.exit(main(sys.argv[1:]))
