"""House book (domovní kniha) exports and the signed registration form.

The house book is a legal obligation in its own right: it holds the data in
the scope of the registration form plus the start and end of the stay, entries
must be made currently and legibly, and it has to be kept for six years after
the last entry. Paper documents signed by the foreigner count as a substitute
for the book, which is why each guest's completed form is rendered as a PDF
carrying their signature.
"""
from __future__ import annotations

import base64
import csv
import io
import os
import re
import zipfile
from datetime import date, datetime
from typing import Any, Dict, Iterator, List, Optional

import reportlab
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from . import db, reporting, validation

RETENTION_YEARS = 6
# Police-inspection ZIPs are built one PDF at a time on disk — not held in RAM.
MAX_INSPECTION_PDFS = 100

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_fonts() -> None:
    """Use a font that can actually render Czech diacritics.

    The built-in Type 1 fonts only cover Latin-1, which mangles characters like
    ř and ě. Bitstream Vera ships with reportlab and covers Latin Extended-A.
    """
    global FONT_REGULAR, FONT_BOLD
    fonts_dir = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    try:
        pdfmetrics.registerFont(TTFont("Vera", os.path.join(fonts_dir, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("Vera-Bold", os.path.join(fonts_dir, "VeraBd.ttf")))
        FONT_REGULAR, FONT_BOLD = "Vera", "Vera-Bold"
    except Exception:
        pass  # fall back to Helvetica


_register_fonts()


HOUSEBOOK_COLUMNS = [
    ("apartment", "Apartment"),
    ("idub", "IDUB"),
    ("stay_from", "Stay from"),
    ("stay_to", "Stay to"),
    ("surname", "Surname"),
    ("first_name", "Given name(s)"),
    ("birth_date", "Date of birth"),
    ("nationality", "Nationality"),
    ("doc_number", "Travel document no."),
    ("visa_number", "Visa no."),
    ("residence", "Permanent residence abroad"),
    ("purpose", "Purpose of stay"),
    ("note", "Note"),
    ("signed", "Signed"),
    ("reported", "Reported to police"),
    ("reported_at", "Reported at"),
    ("stamp", "Receipt stamp"),
]


def _housebook_sql(
    apartment_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    owner_user_id: Optional[int] = None,
) -> tuple[str, List[Any]]:
    sql = (
        "SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id, "
        "       a.internal_name, a.uby_idub "
        "FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status != 'ignored' AND g.archived_at IS NULL "
        "AND (? IS NULL OR a.owner_user_id = ?)"
    )
    params: List[Any] = [owner_user_id, owner_user_id]
    if apartment_id:
        sql += " AND a.id = ?"
        params.append(apartment_id)
    if date_from:
        sql += " AND COALESCE(g.stay_from, r.date_from) >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND COALESCE(g.stay_from, r.date_from) <= ?"
        params.append(date_to)
    sql += " ORDER BY COALESCE(g.stay_from, r.date_from), g.id"
    return sql, params


def _housebook_export_row(row: Dict[str, Any]) -> Dict[str, Any]:
    reported = {
        "sent": "yes",
        "not_required": "not required (Czech national)",
        "error": "NO - rejected",
        "blocked": "NO - rejected, cannot be corrected",
        "pending": "not yet",
    }.get(row["submit_state"], row["submit_state"])
    stamp = ""
    if row["submission_id"]:
        sub = db.query_one("SELECT pseudo_stamp FROM submission WHERE id = ?", (row["submission_id"],))
        stamp = (sub["pseudo_stamp"] if sub else "") or ""
    return {
        "apartment": row["internal_name"],
        "idub": row["uby_idub"] or "",
        "stay_from": row["stay_from"] or row["res_from"],
        "stay_to": row["stay_to"] or row["res_to"],
        "surname": row["surname"] or "",
        "first_name": row["first_name"] or "",
        "birth_date": validation.format_birth_date(row["birth_date"]),
        "nationality": row["nationality"] or "",
        "doc_number": row["doc_number"] or "",
        "visa_number": row["visa_number"] or "",
        "residence": validation.compose_residence(
            row["res_street"] or "", row["res_city"] or "", (row["res_country"] or "").upper()
        ),
        "purpose": validation.purpose_label(row["purpose"] or "", "cs"),
        "note": row["note"] or "",
        "signed": "yes" if reporting.guest_has_signature(row) else "no",
        "reported": reported,
        "reported_at": row["submitted_at"] or "",
        "stamp": stamp,
        "_guest_id": row["id"],
    }


def housebook_rows(
    apartment_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    owner_user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Chronological house-book entries, newest stay last."""
    sql, params = _housebook_sql(apartment_id, date_from, date_to, owner_user_id)
    return [_housebook_export_row(row) for row in db.query(sql, params)]


def _parse_import_date(value: str) -> Optional[str]:
    """Accept ISO dates or Czech DD.MM.YYYY from exported spreadsheets."""
    value = (value or "").strip()
    if not value:
        return None
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return value
    if len(value) == 10 and value[2] == "." and value[5] == ".":
        day, month, year = value.split(".")
        if day.isdigit() and month.isdigit() and year.isdigit():
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return None


def _parse_import_birth(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) == 10 and value[2] == "." and value[5] == ".":
        day, month, year = value.split(".")
        if day.isdigit() and month.isdigit() and year.isdigit():
            return f"{day.zfill(2)}{month.zfill(2)}{year}"
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[:8] if len(digits) >= 8 else ""


def _split_residence(value: str) -> tuple[str, str, str]:
    """Best-effort split of a one-line residence into street, city, country."""
    value = (value or "").strip()
    if not value:
        return "", "", ""
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) >= 3:
        return parts[0], parts[1], parts[-1][:3].upper()
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return value, "", ""


def import_csv(content: bytes, apartment_id: int) -> Dict[str, Any]:
    """Import historical house-book rows from a semicolon-separated CSV export."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if not rows:
        return {"imported": 0, "skipped": 0, "errors": ["The file is empty."]}

    header = [cell.strip().lower() for cell in rows[0]]
    label_to_key = {label.lower(): key for key, label in HOUSEBOOK_COLUMNS}
    indexes: Dict[str, int] = {}
    for index, label in enumerate(header):
        key = label_to_key.get(label)
        if key:
            indexes[key] = index
    required = ("stay_from", "stay_to", "surname", "first_name")
    missing = [name for name in required if name not in indexes]
    if missing:
        return {
            "imported": 0,
            "skipped": 0,
            "errors": [
                "Could not find required columns: "
                + ", ".join(name.replace("_", " ") for name in missing)
                + ". Use the same format as the house-book export."
            ],
        }

    apartment = db.query_one("SELECT id FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return {"imported": 0, "skipped": 0, "errors": ["Unknown apartment."]}

    imported = 0
    skipped = 0
    errors: List[str] = []
    now = db.utcnow()

    for line_no, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue

        def cell(key: str) -> str:
            index = indexes.get(key)
            if index is None or index >= len(row):
                return ""
            return row[index].strip()

        stay_from = _parse_import_date(cell("stay_from"))
        stay_to = _parse_import_date(cell("stay_to"))
        surname = cell("surname")
        first_name = cell("first_name")
        if not (stay_from and stay_to and surname):
            skipped += 1
            errors.append(f"Line {line_no}: missing stay dates or surname.")
            continue

        residence = cell("residence")
        street, city, country = _split_residence(residence)
        reported = cell("reported").lower()
        if reported.startswith("yes"):
            submit_state = "sent"
            submitted_at = cell("reported_at") or now
        elif reported.startswith("not required"):
            submit_state = "not_required"
            submitted_at = None
        else:
            submit_state = "pending"
            submitted_at = None

        uid = f"import-{apartment_id}-{stay_from}-{stay_to}-{surname}-{first_name}-{line_no}"
        reservation = db.query_one(
            "SELECT id FROM reservation WHERE apartment_id = ? AND uid = ?",
            (apartment_id, uid),
        )
        if not reservation:
            reservation_id = db.insert(
                "reservation",
                {
                    "apartment_id": apartment_id,
                    "source": "import",
                    "uid": uid,
                    "date_from": stay_from,
                    "date_to": stay_to,
                    "summary": f"Imported: {surname} {first_name}".strip(),
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                },
            )
        else:
            reservation_id = reservation["id"]

        signed = cell("signed").lower().startswith("y")
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": surname[:35],
                "first_name": first_name[:35],
                "birth_date": _parse_import_birth(cell("birth_date")),
                "nationality": cell("nationality")[:3].upper(),
                "doc_number": cell("doc_number")[:20],
                "visa_number": cell("visa_number")[:20],
                "res_street": street[:48],
                "res_city": city[:48],
                "res_country": country[:3].upper(),
                "purpose": (cell("purpose") or "10").split()[0][:2],
                "note": cell("note")[:255],
                "stay_from": stay_from,
                "stay_to": stay_to,
                "signature_png": "imported" if signed else None,
                "signed_at": now if signed else None,
                "filled_at": now,
                "entered_by": "import",
                "submit_state": submit_state,
                "submitted_at": submitted_at,
                "created_at": now,
                "updated_at": now,
            },
        )
        imported += 1

    if imported:
        db.audit("housebook_import", f"apartment={apartment_id} rows={imported}")
    return {"imported": imported, "skipped": skipped, "errors": errors[:8]}


SAMPLE_HOUSEBOOK_ROW = {
    "apartment": "My apartment",
    "idub": "100227887600",
    "stay_from": "2026-09-03",
    "stay_to": "2026-09-10",
    "surname": "SMITH",
    "first_name": "John Paul",
    "birth_date": "15.03.1985",
    "nationality": "GBR",
    "doc_number": "123456789",
    "visa_number": "",
    "residence": "Baker Street 221B, London, GBR",
    "purpose": "10 - TURISTIKA",
    "note": "",
    "signed": "yes",
    "reported": "yes",
    "reported_at": "2026-09-04",
    "stamp": "",
}


def housebook_archived_rows(
    apartment_id: Optional[int] = None, owner_user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Archived house-book entries that can be restored."""
    sql = (
        "SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id, "
        "       a.internal_name, a.uby_idub "
        "FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE g.archived_at IS NOT NULL AND (? IS NULL OR a.owner_user_id = ?)"
    )
    params: List[Any] = [owner_user_id, owner_user_id]
    if apartment_id:
        sql += " AND a.id = ?"
        params.append(apartment_id)
    sql += " ORDER BY g.archived_at DESC, g.id DESC"
    out: List[Dict[str, Any]] = []
    for row in db.query(sql, params):
        out.append(
            {
                "apartment": row["internal_name"],
                "stay_from": row["stay_from"] or row["res_from"],
                "stay_to": row["stay_to"] or row["res_to"],
                "surname": row["surname"] or "",
                "first_name": row["first_name"] or "",
                "archived_at": row["archived_at"] or "",
                "_guest_id": row["id"],
            }
        )
    return out


def sample_housebook_csv() -> bytes:
    """Filled example guests can copy when importing a paper house book."""
    return housebook_csv([SAMPLE_HOUSEBOOK_ROW])


def iter_housebook_csv_rows(rows: List[Dict[str, Any]]) -> Iterator[bytes]:
    """Stream an already-fetched house-book export row-by-row."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    yield b"\xef\xbb\xbf"
    writer.writerow([label for _key, label in HOUSEBOOK_COLUMNS])
    yield buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)
    for export_row in rows:
        writer.writerow([export_row.get(key, "") for key, _label in HOUSEBOOK_COLUMNS])
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)


def iter_housebook_csv(
    apartment_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    owner_user_id: Optional[int] = None,
) -> Iterator[bytes]:
    """Stream house-book CSV row-by-row instead of buffering the whole file."""
    yield from iter_housebook_csv_rows(
        housebook_rows(apartment_id, date_from, date_to, owner_user_id)
    )


def housebook_csv(rows: List[Dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([label for _key, label in HOUSEBOOK_COLUMNS])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _label in HOUSEBOOK_COLUMNS])
    # Excel in a Czech locale opens semicolon-separated UTF-8 with BOM cleanly.
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


# --- signed registration form -------------------------------------------

def _draw_field(pdf, x: float, y: float, label: str, value: str, width: float) -> None:
    pdf.setFont(FONT_REGULAR, 7)
    pdf.setFillGray(0.35)
    pdf.drawString(x, y + 12, label)
    pdf.setFillGray(0)
    pdf.setFont(FONT_REGULAR, 10)
    text = value or "-"
    while pdf.stringWidth(text, FONT_REGULAR, 10) > width - 4 and len(text) > 4:
        text = text[:-2]
    pdf.drawString(x, y, text)
    pdf.setStrokeGray(0.75)
    pdf.line(x, y - 3, x + width, y - 3)


def _pdf_entry_name(row: Dict[str, Any]) -> str:
    parts = [
        str(row.get("stay_from") or ""),
        str(row.get("surname") or ""),
        str(row.get("first_name") or ""),
    ]
    stem = "-".join(part for part in parts if part).strip("-") or f"guest-{row['_guest_id']}"
    stem = re.sub(r"[^\w.\-]+", "_", stem, flags=re.UNICODE)
    return f"{stem[:96]}.pdf"


def build_housebook_pdfs_zip(rows: List[Dict[str, Any]], dest_path: str) -> int:
    """Write signed registration forms to a zip file on disk, one PDF at a time.

    Keeps memory use low: only one guest PDF is rendered at a time instead of
    buffering the whole archive in RAM.
    """
    count = 0
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in rows:
            guest_id = row.get("_guest_id")
            if not guest_id:
                continue
            archive.writestr(_pdf_entry_name(row), registration_form_pdf(int(guest_id)))
            count += 1
    return count


def housebook_pdfs_zip(rows: List[Dict[str, Any]]) -> bytes:
    """In-memory zip for tests. Production uses build_housebook_pdfs_zip on disk."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in rows:
            guest_id = row.get("_guest_id")
            if not guest_id:
                continue
            archive.writestr(_pdf_entry_name(row), registration_form_pdf(int(guest_id)))
    return buffer.getvalue()


def registration_form_pdf(guest_id: int) -> bytes:
    """One guest's registration form, including their signature.

    This is the document that stands in for a page of the house book.
    """
    guest = db.query_one(
        "SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, "
        "       a.internal_name, a.uby_idub, a.uby_name, a.uby_mark, "
        "       a.addr_street, a.addr_house_no, a.addr_orient_no, a.addr_obec, "
        "       a.addr_obec_cast, a.addr_zip, a.addr_okres "
        "FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id WHERE g.id = ?",
        (guest_id,),
    )
    if not guest:
        raise ValueError(f"Guest {guest_id} not found")

    buffer = io.BytesIO()
    pdf = pdfcanvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left = 20 * mm
    inner = width - 40 * mm

    pdf.setFont(FONT_BOLD, 14)
    pdf.drawString(left, height - 25 * mm, "Přihlašovací tiskopis cizince")
    pdf.setFont(FONT_REGULAR, 10)
    pdf.setFillGray(0.35)
    pdf.drawString(left, height - 31 * mm, "Foreigner's registration form / house book entry")
    pdf.setFillGray(0)

    address_parts = [
        " ".join(p for p in [guest["addr_street"], _house_label(guest)] if p),
        guest["addr_obec_cast"],
        " ".join(p for p in [guest["addr_zip"], guest["addr_obec"]] if p),
    ]
    facility_address = ", ".join(p for p in address_parts if p)

    y = height - 45 * mm
    pdf.setFont(FONT_BOLD, 10)
    pdf.drawString(left, y, "Ubytovatel / Accommodation provider")
    y -= 8 * mm
    _draw_field(pdf, left, y, "NÁZEV ZAŘÍZENÍ / FACILITY", guest["uby_name"] or guest["internal_name"], inner * 0.6)
    _draw_field(pdf, left + inner * 0.65, y, "IDUB", guest["uby_idub"] or "", inner * 0.35)
    y -= 14 * mm
    _draw_field(pdf, left, y, "ADRESA / ADDRESS", facility_address, inner)

    y -= 18 * mm
    pdf.setFont(FONT_BOLD, 10)
    pdf.drawString(left, y, "Ubytovaný cizinec / Accommodated foreigner")
    y -= 8 * mm

    half = inner * 0.48
    right_x = left + inner * 0.52

    _draw_field(pdf, left, y, "PŘÍJMENÍ / SURNAME", guest["surname"] or "", half)
    _draw_field(pdf, right_x, y, "JMÉNO / GIVEN NAME(S)", guest["first_name"] or "", half)
    y -= 14 * mm
    _draw_field(pdf, left, y, "DATUM NAROZENÍ / DATE OF BIRTH",
                validation.format_birth_date(guest["birth_date"]), half)
    _draw_field(pdf, right_x, y, "STÁTNÍ OBČANSTVÍ / NATIONALITY",
                f"{guest['nationality'] or ''} {validation.country_name(guest['nationality'] or '', 'en')}".strip(),
                half)
    y -= 14 * mm
    _draw_field(pdf, left, y, "ČÍSLO CESTOVNÍHO DOKLADU / TRAVEL DOCUMENT NO.",
                guest["doc_number"] or "", half)
    _draw_field(pdf, right_x, y, "ČÍSLO VÍZA / VISA NO.", guest["visa_number"] or "", half)
    y -= 14 * mm
    _draw_field(
        pdf, left, y, "BYDLIŠTĚ V ZAHRANIČÍ / PERMANENT RESIDENCE ABROAD",
        validation.compose_residence(
            guest["res_street"] or "", guest["res_city"] or "", (guest["res_country"] or "").upper()
        ),
        inner,
    )
    y -= 14 * mm
    _draw_field(pdf, left, y, "ÚČEL POBYTU / PURPOSE OF STAY",
                validation.purpose_label(guest["purpose"] or "", "cs"), half)
    _draw_field(pdf, right_x, y, "POZNÁMKA / NOTE", guest["note"] or "", half)
    y -= 14 * mm
    _draw_field(pdf, left, y, "OD / FROM", guest["stay_from"] or guest["res_from"], half)
    _draw_field(pdf, right_x, y, "DO / TO", guest["stay_to"] or guest["res_to"], half)

    # Signature block
    y -= 30 * mm
    pdf.setFont(FONT_BOLD, 10)
    pdf.drawString(left, y + 24 * mm, "Podpis cizince / Signature of the foreigner")
    if guest["signature_png"]:
        try:
            raw = guest["signature_png"].split(",", 1)[-1]
            image = ImageReader(io.BytesIO(base64.b64decode(raw)))
            pdf.drawImage(image, left, y, width=70 * mm, height=22 * mm,
                          preserveAspectRatio=True, anchor="sw", mask="auto")
        except Exception:
            pdf.setFont(FONT_REGULAR, 9)
            pdf.drawString(left, y + 8, "(signature could not be rendered)")
    pdf.setStrokeGray(0.6)
    pdf.line(left, y - 2 * mm, left + 80 * mm, y - 2 * mm)
    pdf.setFont(FONT_REGULAR, 8)
    pdf.setFillGray(0.4)
    signed = guest["signed_at"] or guest["filled_at"] or ""
    pdf.drawString(left, y - 7 * mm, f"Signed electronically: {signed}")

    # Reporting status, as required by rule 10.5(3).
    status_map = {
        "sent": "Reported to the Foreign Police",
        "not_required": "No reporting duty (Czech national)",
        "pending": "NOT YET REPORTED",
        "error": "REJECTED BY UBYPORT",
        "blocked": "REJECTED BY UBYPORT (not correctable)",
    }
    pdf.setFont(FONT_REGULAR, 9)
    pdf.setFillGray(0)
    pdf.drawRightString(width - 20 * mm, y - 7 * mm,
                        status_map.get(guest["submit_state"], guest["submit_state"]))
    if guest["submitted_at"]:
        pdf.setFillGray(0.4)
        pdf.drawRightString(width - 20 * mm, y - 12 * mm, f"at {guest['submitted_at']}")

    pdf.setFont(FONT_REGULAR, 7)
    pdf.setFillGray(0.45)
    pdf.drawString(
        left, 15 * mm,
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} - retain for {RETENTION_YEARS} years "
        "from the end of the stay (§ 101 Act 326/1999 Coll.)",
    )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _house_label(row) -> str:
    house = (row["addr_house_no"] or "").strip()
    orient = (row["addr_orient_no"] or "").strip()
    if house and orient:
        return f"{house}/{orient}"
    return house or orient


def retention_expiry(last_entry: date) -> date:
    return date(last_entry.year + RETENTION_YEARS, last_entry.month, last_entry.day)


# --- retention -----------------------------------------------------------
#
# Six years is a floor set by § 101, and under GDPR's storage-limitation
# principle it is also a ceiling: once it passes there is no longer a legal
# basis for holding a guest's passport number, so the record has to go.

def retention_cutoff(today: Optional[date] = None) -> date:
    today = today or date.today()
    try:
        return date(today.year - RETENTION_YEARS, today.month, today.day)
    except ValueError:  # 29 February in a leap year
        return date(today.year - RETENTION_YEARS, today.month, today.day - 1)


def expired_guest_ids(
    today: Optional[date] = None, owner_user_id: Optional[int] = None
) -> List[int]:
    """Guest records whose stay ended more than six years ago."""
    rows = db.query(
        "SELECT g.id AS id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE COALESCE(g.stay_to, r.date_to) < ? "
        "AND (? IS NULL OR a.owner_user_id = ?)",
        (retention_cutoff(today).isoformat(), owner_user_id, owner_user_id),
    )
    return [row["id"] for row in rows]


def purge_expired(
    today: Optional[date] = None, owner_user_id: Optional[int] = None
) -> int:
    ids = expired_guest_ids(today, owner_user_id=owner_user_id)
    if not ids:
        return 0
    marks = ", ".join("?" for _ in ids)
    db.execute(f"DELETE FROM guest WHERE id IN ({marks})", ids)
    db.audit("retention_purge", f"deleted {len(ids)} guest record(s) older than {RETENTION_YEARS} years")
    return len(ids)
