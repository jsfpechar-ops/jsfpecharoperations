"""A local stand-in for the UbyPort SOAP service.

Real credentials are issued per accommodation facility by the Foreign Police
and take days to arrive, so this exists to exercise the whole pipeline now. It
deliberately reproduces the behaviour that actually bites in production:

* per-record error codes returned positionally in ChybyZaznamu
* the duplicate check that the police re-enabled on 1 September 2025, returned
  as an error that cannot be corrected
* "reported late" once the three-working-day window has passed
* a real PDF Doručenka in base64, so the download path is genuinely tested

Run it with:  python -m mock_ubyport.server
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, Request, Response
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.deadlines import add_working_days  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s mock-ubyport: %(message)s")
log = logging.getLogger("mock-ubyport")

STATE_FILE = Path(os.environ.get("MOCK_UBYPORT_STATE", Path(__file__).parent / "mock_state.json"))
MAX_BATCH = 32

NS_DATA = "http://schemas.datacontract.org/2004/07/WS_UBY"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

app = FastAPI(title="Mock UbyPort", docs_url=None, redoc_url=None)

# code -> (short text, is_correctable)
ERROR_CODES: Dict[str, Tuple[str, bool]] = {
    "5": ("Název ubytovatele není vyplněn", True),
    "6": ("Kontakt na ubytovatele není vyplněn", True),
    "7": ("Okres není vyplněn", True),
    "8": ("Obec není vyplněna", True),
    "9": ("Část obce není vyplněna", True),
    "10": ("Ulice není vyplněna", True),
    "11": ("Číslo orientační není vyplněno", True),
    "12": ("PSČ není vyplněno nebo je nekorektní", True),
    "13": ("IDUB nebo zkratka nesouhlasí s registrací", True),
    "101": ("Příjmení není vyplněno nebo obsahuje nepovolené znaky", True),
    "102": ("Datum narození je nekorektní", True),
    "103": ("Státní příslušnost není v číselníku", True),
    "106": ("Číslo cestovního dokladu je nekorektní", True),
    "108": ("Datum do není vyšší než datum od", True),
    "112": ("Oznámeno pozdě", False),
    "150": ("Duplicitní záznam - data nebyla převzata", False),
}


def _load_state() -> Dict[str, List[str]]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except ValueError:
            pass
    return {"seen": []}


def _save_state(state: Dict[str, List[str]]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=1))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(parent: ET.Element, name: str) -> Optional[str]:
    for child in parent:
        if _local(child.tag) == name:
            if child.get(f"{{{NS_XSI}}}nil") == "true":
                return None
            return (child.text or "").strip() or None
    return None


def _find(root: ET.Element, name: str) -> Optional[ET.Element]:
    for element in root.iter():
        if _local(element.tag) == name:
            return element
    return None


def _soap(body: str) -> Response:
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
        f"<s:Header /><s:Body>{body}</s:Body></s:Envelope>"
    )
    return Response(envelope, media_type="text/xml; charset=utf-8")


def _parse_iso(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _validate_header(header: ET.Element) -> List[str]:
    codes: List[str] = []
    idub = _text(header, "uIdub") or ""
    mark = _text(header, "uMark") or ""
    if not (12 <= len(idub) <= 14) or not idub.isalnum():
        codes.append("13")
    if len(mark) != 5 or not mark.isalpha():
        codes.append("13")
    if not _text(header, "uName"):
        codes.append("5")
    if not _text(header, "uOb"):
        codes.append("8")
    psc = _text(header, "uPsc") or ""
    if len(psc) != 5 or not psc.isdigit():
        codes.append("12")
    return sorted(set(codes), key=lambda c: int(c))


def _validate_guest(guest: ET.Element, idub: str, seen: List[str]) -> Tuple[List[str], Optional[str]]:
    """Return (error codes, dedupe fingerprint or None)."""
    codes: List[str] = []
    surname = _text(guest, "cSurN")
    birth = _text(guest, "cDate")
    nationality = _text(guest, "cNati")
    document = _text(guest, "cDocN")
    start = _parse_iso(_text(guest, "cFrom"))
    end = _parse_iso(_text(guest, "cUntil"))

    if not surname:
        codes.append("101")
    if not birth or len(birth) != 8 or not birth.isdigit():
        codes.append("102")
    if not nationality or len(nationality) != 3:
        codes.append("103")
    if not document or (document != "INPASS" and (len(document) < 6 or not document.isalnum())):
        codes.append("106")
    if start and end and end <= start:
        codes.append("108")

    # Reported late: three working days after accommodation began.
    if start and date.today() > add_working_days(start, 3):
        codes.append("112")

    fingerprint = None
    if start and document and not codes:
        fingerprint = f"{idub}|{document}|{start.isoformat()}"
        if fingerprint in seen:
            codes.append("150")

    return codes, fingerprint


def _receipt_pdf(idub: str, mark: str, rows: List[Dict[str, str]], stamp: str) -> str:
    """A small but real PDF, so the host application's download path is tested."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as pdfcanvas
    except ImportError:
        return base64.b64encode(b"%PDF-1.4 mock receipt").decode("ascii")

    buffer = io.BytesIO()
    pdf = pdfcanvas.Canvas(buffer, pagesize=A4)
    _width, height = A4
    y = height - 25 * mm
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(20 * mm, y, "DORUCENKA (mock)")
    pdf.setFont("Helvetica", 9)
    y -= 8 * mm
    pdf.drawString(20 * mm, y, f"IDUB {idub}   zkratka {mark}")
    y -= 5 * mm
    pdf.drawString(20 * mm, y, f"Prijato: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 5 * mm
    pdf.drawString(20 * mm, y, f"Identifikacni kod: {stamp}")
    y -= 10 * mm
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(20 * mm, y, "Zaznamy")
    pdf.setFont("Helvetica", 8.5)
    for index, row in enumerate(rows, start=1):
        y -= 6 * mm
        if y < 25 * mm:
            pdf.showPage()
            y = height - 25 * mm
            pdf.setFont("Helvetica", 8.5)
        status = "PREVZATO" if row["status"] == "ok" else "NEPREVZATO"
        pdf.drawString(20 * mm, y, f"{index:>2}. {row['name'][:38]:<40} {row['doc'][:16]:<18} {status}")
        if row["errors"]:
            y -= 4.5 * mm
            pdf.drawString(28 * mm, y, f"    {row['errors'][:110]}")
    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawString(20 * mm, 15 * mm, "Vygenerovano lokalnim testovacim serverem - nema pravni ucinky.")
    pdf.showPage()
    pdf.save()
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@app.post("/ws_uby/ws_uby.svc")
@app.post("/ws_uby_test/ws_uby.svc")
async def ws_uby(request: Request):
    action = (request.headers.get("SOAPAction") or "").strip('"')
    method = action.rsplit("/", 1)[-1] if action else ""
    raw = await request.body()

    try:
        root = ET.fromstring(raw.decode("utf-8"))
    except (ET.ParseError, UnicodeDecodeError) as exc:
        log.warning("unparseable request: %s", exc)
        return _soap(
            '<s:Fault xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<faultcode>s:Client</faultcode>"
            "<faultstring>Request body is not valid XML</faultstring></s:Fault>"
        )

    if not method:
        for candidate in ("ZapisUbytovane", "TestDostupnosti", "MaximalniDelkaSeznamu", "DejMiCiselnik"):
            if _find(root, candidate) is not None:
                method = candidate
                break

    log.info("%s", method or "unknown method")

    if method == "TestDostupnosti":
        return _soap(
            '<TestDostupnostiResponse xmlns="http://UBY.pcr.cz/WS_UBY">'
            "<TestDostupnostiResult>true</TestDostupnostiResult></TestDostupnostiResponse>"
        )

    if method == "MaximalniDelkaSeznamu":
        return _soap(
            '<MaximalniDelkaSeznamuResponse xmlns="http://UBY.pcr.cz/WS_UBY">'
            f"<MaximalniDelkaSeznamuResult>{MAX_BATCH}</MaximalniDelkaSeznamuResult>"
            "</MaximalniDelkaSeznamuResponse>"
        )

    if method == "DejMiCiselnik":
        element = _find(root, "CoChci")
        kind = (element.text or "").strip() if element is not None else ""
        return _soap(_ciselnik(kind))

    if method == "ZapisUbytovane":
        return _soap(_zapis(root))

    return _soap(
        '<s:Fault xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
        "<faultcode>s:Client</faultcode>"
        f"<faultstring>Unknown method: {method}</faultstring></s:Fault>"
    )


def _ciselnik(kind: str) -> str:
    entries: List[Dict[str, str]] = []
    if kind == "Chyby":
        for code, (text, _correctable) in ERROR_CODES.items():
            entries.append(
                {
                    "Id": "0",
                    "Kod2": f"ERR_CZE_{code.zfill(3)}",
                    "Kod3": text,
                    "TextCZ": "",
                    "TextENG": "INFORMACE",
                    "TextKratkyCZ": code,
                    "TextKratkyENG": text,
                }
            )
    elif kind == "UcelyPobytu":
        purposes = [
            ("00", "ZDRAVOTNÍ"), ("01", "OBCHODNÍ"), ("02", "KULTURNÍ"),
            ("03", "NÁVŠTĚVA RODINY NEBO PŘÁTEL"), ("04", "POZVÁNÍ"),
            ("05", "OFICIÁLNÍ (POLITICKÝ)"), ("06", "PODNIKÁNÍ – OSVČ"),
            ("07", "SPORTOVNÍ"), ("10", "TURISTIKA"), ("11", "STUDIUM (ŠKOLENÍ, STÁŽ)"),
            ("12", "TRANZIT (průjezd)"), ("13", "LETIŠTNÍ TRANZIT (letištní průjezd)"),
            ("27", "ZAMĚSTNÁNÍ"), ("93", "TZV. ADS vízum udělované občanu Číny"),
            ("99", "OSTATNÍ / JINÉ"),
        ]
        for code, label in purposes:
            entries.append({"Id": "0", "Kod2": code, "Kod3": "", "TextCZ": f"{code} - {label}",
                            "TextENG": "", "TextKratkyCZ": "", "TextKratkyENG": ""})
    else:  # Staty
        sample = [
            ("104", "AF", "AFG", "Afghánská islámská republika", "Afghanistan", "Afghánistán"),
            ("203", "CZ", "CZE", "Česká republika", "Czech Republic", "Česko"),
            ("276", "DE", "DEU", "Spolková republika Německo", "Germany", "Německo"),
            ("826", "GB", "GBR", "Spojené království", "United Kingdom", "Spojené království"),
            ("840", "US", "USA", "Spojené státy americké", "United States", "Spojené státy"),
            ("804", "UA", "UKR", "Ukrajina", "Ukraine", "Ukrajina"),
            ("616", "PL", "POL", "Polská republika", "Poland", "Polsko"),
            ("040", "AT", "AUT", "Rakouská republika", "Austria", "Rakousko"),
            ("356", "IN", "IND", "Indická republika", "India", "Indie"),
            ("392", "JP", "JPN", "Japonsko", "Japan", "Japonsko"),
        ]
        for ident, code2, code3, full_cs, full_en, short_cs in sample:
            entries.append({"Id": ident, "Kod2": code2, "Kod3": code3, "TextCZ": full_cs,
                            "TextENG": full_en, "TextKratkyCZ": short_cs, "TextKratkyENG": ""})

    items = []
    for entry in entries:
        fields = "".join(f"<a:{key}>{_escape(value)}</a:{key}>" for key, value in entry.items())
        items.append(f"<a:CiselnikType>{fields}</a:CiselnikType>")
    return (
        '<DejMiCiselnikResponse xmlns="http://UBY.pcr.cz/WS_UBY">'
        f'<DejMiCiselnikResult xmlns:a="{NS_DATA}" xmlns:i="{NS_XSI}">'
        f"{''.join(items)}</DejMiCiselnikResult></DejMiCiselnikResponse>"
    )


def _escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# SeznamUbytovanych members in the order WCF's DataContractSerializer expects
# them: ordinal sort, so upper-case names first (appendix 5, section 5.1.1).
SEZNAM_MEMBER_ORDER = (
    "Ubytovani", "VracetPDF",
    "uCont", "uHomN", "uIdub", "uMark", "uName", "uOb", "uObCa", "uOkr", "uOriN", "uPsc", "uStr",
)


def _dcs_members_read(seznam: ET.Element) -> List[str]:
    """Which Seznam members a DataContractSerializer would actually bind.

    It reads members strictly in contract order: for each element it searches
    forward from the last bound member, and an element whose slot has already
    passed is skipped as unknown. That is how a VracetPDF sent after uStr is
    silently lost on the real service, and the mock must lose it too.
    """
    bound: List[str] = []
    position = -1
    for child in seznam:
        name = _local(child.tag)
        try:
            index = SEZNAM_MEMBER_ORDER.index(name, position + 1)
        except ValueError:
            continue
        bound.append(name)
        position = index
    return bound


def _zapis(root: ET.Element) -> str:
    header = _find(root, "Seznam")
    if header is None:
        return (
            '<s:Fault xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<faultcode>s:Client</faultcode>"
            "<faultstring>Missing Seznam element</faultstring></s:Fault>"
        )

    idub = _text(header, "uIdub") or ""
    mark = _text(header, "uMark") or ""
    # Only honoured where the real service would read it; out of order it is
    # dropped and defaults to false, exactly like WCF.
    pdf_flag_bound = "VracetPDF" in _dcs_members_read(header)
    want_pdf = pdf_flag_bound and (_text(header, "VracetPDF") or "false").lower() == "true"
    if _text(header, "VracetPDF") and not pdf_flag_bound:
        log.warning("ZapisUbytovane: VracetPDF out of contract order, ignored (no Dorucenka)")

    container = _find(header, "Ubytovani")
    guests = [child for child in container] if container is not None else []

    if len(guests) > MAX_BATCH:
        return (
            '<s:Fault xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<faultcode>s:Client</faultcode>"
            f"<faultstring>Seznam is longer than {MAX_BATCH} records</faultstring></s:Fault>"
        )

    header_codes = _validate_header(header)
    state = _load_state()
    seen = state.get("seen", [])

    record_errors: List[str] = []
    rows: List[Dict[str, str]] = []
    accepted_fingerprints: List[str] = []

    for guest in guests:
        codes, fingerprint = _validate_guest(guest, idub, seen)
        # A header problem stops the whole batch being taken over.
        record_errors.append(";" + "".join(f"{code};" for code in codes))
        name = f"{_text(guest, 'cSurN') or '?'} {_text(guest, 'cFirstN') or ''}".strip()
        rows.append(
            {
                "name": name,
                "doc": _text(guest, "cDocN") or "?",
                "status": "ok" if not codes and not header_codes else "bad",
                "errors": ", ".join(ERROR_CODES.get(code, (code, True))[0] for code in codes),
            }
        )
        if fingerprint and not codes:
            accepted_fingerprints.append(fingerprint)

    if not header_codes and accepted_fingerprints:
        state["seen"] = (seen + accepted_fingerprints)[-5000:]
        _save_state(state)

    stamp = _pseudo_stamp()
    # The Chyby members in the order the real service serialises them
    # (alphabetical, appendix 5 sections 4.2 and 5.1.1).
    parts = [f"<a:ChybyHlavicky>{''.join(f'{c};' for c in header_codes)}</a:ChybyHlavicky>"]
    strings = "".join(f"<b:string>{value}</b:string>" for value in record_errors)
    parts.append(
        '<a:ChybyZaznamu xmlns:b="http://schemas.microsoft.com/2003/10/Serialization/Arrays">'
        f"{strings}</a:ChybyZaznamu>"
    )
    if want_pdf:
        receipt = _receipt_pdf(idub, mark, rows, stamp)
        if header_codes or any(row["status"] == "bad" for row in rows):
            parts.append(f"<a:DokumentChybyPotvrzeni>{receipt}</a:DokumentChybyPotvrzeni>")
        parts.append(f"<a:DokumentPotvrzeni>{receipt}</a:DokumentPotvrzeni>")
    else:
        parts.append('<a:DokumentChybyPotvrzeni i:nil="true" />')
        parts.append('<a:DokumentPotvrzeni i:nil="true" />')
    parts.append(f"<a:PseudoRazitko>{stamp}</a:PseudoRazitko>")

    log.info(
        "ZapisUbytovane: idub=%s guests=%d header_errors=%s accepted=%d",
        idub, len(guests), header_codes or "none",
        sum(1 for row in rows if row["status"] == "ok"),
    )

    return (
        '<ZapisUbytovaneResponse xmlns="http://UBY.pcr.cz/WS_UBY">'
        f'<ZapisUbytovaneResult xmlns:a="{NS_DATA}" xmlns:i="{NS_XSI}">'
        f"{''.join(parts)}</ZapisUbytovaneResult></ZapisUbytovaneResponse>"
    )


def _pseudo_stamp() -> str:
    import uuid

    return str(uuid.uuid4()).upper()


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "mock-ubyport", "max_batch": MAX_BATCH}


@app.get("/sample-airbnb.ics")
def sample_calendar():
    """An Airbnb-shaped calendar, so the host can try the app before they have
    a real export link. The dates move with today so it never goes stale."""
    from datetime import timedelta

    today = date.today()
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID;X-RICAL-TZSOURCE=TZINFO:-//Airbnb Inc//Hosting Calendar 0.8.8//EN",
        "CALSCALE:GREGORIAN",
        "VERSION:2.0",
        "X-WR-CALNAME:UbyHost sample calendar",
    ]
    stays = [
        ("arriving-today", today, 4, "Reserved", "0431"),
        ("arrived-yesterday", today - timedelta(days=1), 3, "Reserved", "7788"),
        ("next-week", today + timedelta(days=7), 5, "Reserved", "1290"),
        ("blocked", today + timedelta(days=3), 2, "Airbnb (Not available)", None),
    ]
    for name, start, nights, summary, phone in stays:
        lines += [
            "BEGIN:VEVENT",
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{start + timedelta(days=nights):%Y%m%d}",
            f"UID:sample-{name}@airbnb.com",
            f"SUMMARY:{summary}",
        ]
        if phone:
            lines.append(
                "DESCRIPTION:Reservation URL: https://www.airbnb.com/hosting/reservations/"
                f"details/HMSAMPLE{phone}\\nPhone Number (Last 4 Digits): {phone}"
            )
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return Response(
        content="\r\n".join(lines) + "\r\n", media_type="text/calendar; charset=utf-8"
    )


@app.post("/reset")
def reset():
    """Forget the duplicate history, so a test scenario can be replayed."""
    _save_state({"seen": []})
    return {"status": "reset"}


if __name__ == "__main__":
    port = int(
        (sys.argv[1] if len(sys.argv) > 1 else None)
        or os.environ.get("MOCK_UBYPORT_PORT", "8081")
    )
    host = os.environ.get("MOCK_UBYPORT_HOST", "127.0.0.1")
    log.info("mock UbyPort listening on http://%s:%s/ws_uby/ws_uby.svc", host, port)
    uvicorn.run(app, host=host, port=port, log_level="warning")
