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
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from . import db, passport_photos, reporting, validation
from .csv_safety import csv_safe

RETENTION_YEARS = 6
# Police-inspection ZIPs are built one PDF at a time on disk — not held in RAM.
MAX_INSPECTION_PDFS = 100

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_fonts() -> None:
    """Use a font that can actually render Czech diacritics.

    The built-in Type 1 fonts only cover Latin-1, which mangles characters like
    ř and ě. Bitstream Vera ships with reportlab but does NOT cover Latin
    Extended-A (it drops ě, ř, ů, ň, ť), so the vendored DejaVu Sans is used
    instead; Helvetica stays as the fallback.
    """
    global FONT_REGULAR, FONT_BOLD
    fonts_dir = os.path.join(os.path.dirname(__file__), "static", "fonts")
    try:
        pdfmetrics.registerFont(
            TTFont("DejaVu", os.path.join(fonts_dir, "DejaVuSans.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("DejaVu-Bold", os.path.join(fonts_dir, "DejaVuSans-Bold.ttf"))
        )
        FONT_REGULAR, FONT_BOLD = "DejaVu", "DejaVu-Bold"
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
        "       a.id AS apartment_id, a.internal_name, a.uby_idub "
        "FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status != 'ignored' AND g.archived_at IS NULL "
        "AND g.restricted_at IS NULL "
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
    by_hand = reporting.guest_filed_by_hand(row)
    if by_hand:
        # WP23: the host filed this guest in the UbyPort web application.
        reported = "yes - filed by hand in UbyPort"
    stamp = ""
    if by_hand:
        stamp = row["manual_reference"] or ""
    elif row["submission_id"]:
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
        "reported_at": (row["manual_filed_at"] if by_hand else row["submitted_at"]) or "",
        "stamp": stamp,
        "_guest_id": row["id"],
        "_apartment_id": row["apartment_id"],
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


def housebook_archived_rows(
    apartment_id: Optional[int] = None, owner_user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Archived house-book entries that can be restored."""
    sql = (
        "SELECT g.*, r.date_from AS res_from, r.date_to AS res_to, r.id AS res_id, "
        "       a.id AS apartment_id, a.internal_name, a.uby_idub "
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
                "_apartment_id": row["apartment_id"],
            }
        )
    return out


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
        writer.writerow([csv_safe(export_row.get(key, "")) for key, _label in HOUSEBOOK_COLUMNS])
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)


def housebook_csv(rows: List[Dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([label for _key, label in HOUSEBOOK_COLUMNS])
    for row in rows:
        writer.writerow([csv_safe(row.get(key, "")) for key, _label in HOUSEBOOK_COLUMNS])
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
    by_hand = reporting.guest_filed_by_hand(guest)
    status = status_map.get(guest["submit_state"], guest["submit_state"])
    if by_hand:
        status = "Reported to the Foreign Police (filed by hand in UbyPort)"
    pdf.drawRightString(width - 20 * mm, y - 7 * mm, status)
    filed = guest["manual_filed_at"] if by_hand else guest["submitted_at"]
    if filed:
        pdf.setFillGray(0.4)
        line = f"at {filed}"
        if by_hand and guest["manual_reference"]:
            line += f", ref. {guest['manual_reference']}"
        pdf.drawRightString(width - 20 * mm, y - 12 * mm, line)

    if guest["notice_version"]:
        pdf.setFont(FONT_REGULAR, 7)
        pdf.setFillGray(0.45)
        pdf.drawString(
            left,
            19 * mm,
            f"Privacy notice v{guest['notice_version']} acknowledged "
            f"{guest['notice_ack_at'] or ''} ({guest['notice_lang'] or ''})",
        )

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


# --- retention -----------------------------------------------------------
#
# Six years is a floor set by § 101(4) zákon 326/1999 Sb. and § 3g(4) zákon
# 565/1990 Sb., and under GDPR's storage-limitation principle it is also a
# ceiling. Both laws count "from the last entry" of the book; for a book kept
# continuously that would mean never deleting, so the owner's decision (legal
# positions, section 4) reads it per record: six years from the end of each
# stay, the rule § 101(4) itself applies to the paper forms. Deletion runs once
# a year: a record whose six years end in year Y goes on 31 January of Y + 1.
# The host DPA states this reading; the host can export the book first.

PURGE_MONTH = 1
PURGE_DAY = 31


def retention_cutoff(today: Optional[date] = None) -> date:
    """Records whose stay ended before this date are due for deletion.

    A stay ending in year Y reaches six years in Y + 6 and is deleted on
    31 January of Y + 7. So from 31 January of this year every stay that ended
    up to 31 December seven years ago is due; before that day, one year less.
    """
    today = today or date.today()
    if today >= date(today.year, PURGE_MONTH, PURGE_DAY):
        last_year_due = today.year - RETENTION_YEARS - 1
    else:
        last_year_due = today.year - RETENTION_YEARS - 2
    return date(last_year_due + 1, 1, 1)


def expired_guest_ids(
    today: Optional[date] = None, owner_user_id: Optional[int] = None
) -> List[int]:
    """Guest records past their six years and their 31 January deletion day.

    ``date()`` is applied to both sides of the ``COALESCE`` so a malformed
    ``stay_to`` (SQLite ``date()`` returns NULL for it) falls back to the
    reservation's end instead of sorting after every cutoff and living forever.
    """
    rows = db.query(
        "SELECT g.id AS id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE COALESCE(date(g.stay_to), date(r.date_to)) < ? "
        "AND (? IS NULL OR a.owner_user_id = ?)",
        (retention_cutoff(today).isoformat(), owner_user_id, owner_user_id),
    )
    return [row["id"] for row in rows]


def due_guest_ids(
    today: Optional[date] = None,
    within_days: int = 30,
    owner_user_id: Optional[int] = None,
) -> List[int]:
    """Guest records that reach their retention cutoff within the next N days."""
    start = retention_cutoff(today).isoformat()
    end = retention_cutoff((today or date.today()) + timedelta(days=within_days)).isoformat()
    rows = db.query(
        "SELECT g.id AS id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE COALESCE(date(g.stay_to), date(r.date_to)) >= ? "
        "AND COALESCE(date(g.stay_to), date(r.date_to)) < ? "
        "AND (? IS NULL OR a.owner_user_id = ?)",
        (start, end, owner_user_id, owner_user_id),
    )
    return [row["id"] for row in rows]


def due_guest_counts(today: Optional[date] = None, within_days: int = 30) -> Dict[Optional[int], int]:
    """How many records per owner reach their cutoff within the next N days."""
    start = retention_cutoff(today).isoformat()
    end = retention_cutoff((today or date.today()) + timedelta(days=within_days)).isoformat()
    rows = db.query(
        "SELECT a.owner_user_id AS owner, COUNT(*) AS n FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE COALESCE(date(g.stay_to), date(r.date_to)) >= ? "
        "AND COALESCE(date(g.stay_to), date(r.date_to)) < ? "
        "GROUP BY a.owner_user_id",
        (start, end),
    )
    return {row["owner"]: row["n"] for row in rows}


def purge_orphan_submissions(
    today: Optional[date] = None, owner_user_id: Optional[int] = None
) -> int:
    """Delete submission rows no surviving guest row points at.

    ``guest.submission_id`` is the current link and ``guest.receipt_submission_id``
    is where that guest's Dorucenka lives; both are ``ON DELETE SET NULL``, so a
    submission no surviving guest points at through either column is unreachable
    from every screen while still holding the request envelope.

    Only rows past the retention cutoff go, so that deleting a guest by hand
    cannot take a recent Dorucenka with it: the receipt PDF is the host's proof
    that something *was* filed, and it has to survive until the six years are
    up. Blanking the envelope is what stops the passport numbers leaking, and
    ``reporting.purge_submission_payloads`` does that after 90 days.
    """
    rows = db.query(
        "SELECT s.id AS id FROM submission s "
        "JOIN apartment a ON a.id = s.apartment_id "
        "WHERE s.created_at < ? AND (? IS NULL OR a.owner_user_id = ?) "
        "AND NOT EXISTS (SELECT 1 FROM guest g "
        "                WHERE g.submission_id = s.id OR g.receipt_submission_id = s.id)",
        (retention_cutoff(today).isoformat(), owner_user_id, owner_user_id),
    )
    if not rows:
        return 0
    ids = [row["id"] for row in rows]
    marks = ", ".join("?" for _ in ids)
    db.execute(f"DELETE FROM submission WHERE id IN ({marks})", ids)
    db.audit(
        "submission_orphan_purge",
        f"deleted {len(ids)} submission record(s) with no surviving guest",
    )
    return len(ids)


def purge_expired(
    today: Optional[date] = None, owner_user_id: Optional[int] = None
) -> int:
    ids = expired_guest_ids(today, owner_user_id=owner_user_id)
    if ids:
        # Drop the image before the row: once the row is gone nothing in the app
        # can find the file again, and an orphaned passport scan is the worst
        # thing to leave behind at the exact moment the basis for holding it ends.
        for guest_id in ids:
            passport_photos.delete_photo(guest_id)
        marks = ", ".join("?" for _ in ids)
        db.execute(f"DELETE FROM guest WHERE id IN ({marks})", ids)
        db.audit(
            "retention_purge",
            f"deleted {len(ids)} guest record(s) whose stay ended before "
            f"{retention_cutoff(today).isoformat()}",
        )
    # The guests those submissions described are gone, so the envelope they
    # carried has no owner left to be evidence for.
    purge_orphan_submissions(today, owner_user_id=owner_user_id)
    return len(ids)
