"""Host-facing downloads: CSV, PDF, bulk zips and the archive browser.

Every route here answers with bytes or a filtered list rather than the host's
main pages, so they live apart from ``routes/admin.py``. ``admin.router``
includes this router, so the host POST protection and the route order are
unchanged.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from .. import (
    access,
    auth,
    claim,
    db,
    dsr,
    housebook,
    passport_photos,
    reporting,
    retention,
    stays_export,
    workspace_export,
)
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import query_date as _query_date
from .admin_helpers import query_int as _query_int

router = APIRouter()

# The archive browser's tabs; anything else falls back to "all".
ARCHIVED_TYPES = ("all", "stays", "properties", "housebook", "entities")


@router.get("/reservations.csv")
def reservations_export(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    date_from = _query_date(request, "from")
    date_to = _query_date(request, "to")
    if not (date_from and date_to):
        return _back("/reservations", err=_flash(request, "flash.error.export_range_required"))
    stamp = datetime.now().strftime("%Y%m%d")
    sql, params = stays_export._export_sql(
        date_from=date_from,
        date_to=date_to,
        apartment_id=_query_int(request, "apartment"),
        owner_user_id=access.owner_id(request),
    )
    rows = db.query(sql, params)
    db.audit("export_reservations_csv", f"rows={len(rows)}")
    return StreamingResponse(
        stays_export.iter_export_csv_rows(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="stays-{stamp}.csv"'},
    )


@router.get("/guests/{guest_id}/form.pdf")
def guest_form_pdf(guest_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.guest(request, guest_id):
        return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
    try:
        pdf = housebook.registration_form_pdf(guest_id)
    except ValueError:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_guest"))
    db.audit("export_registration_pdf", f"guest_id={guest_id}")
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="registration-form-{guest_id}.pdf"'},
    )


@router.get("/guests/{guest_id}/export.json")
def guest_export_json(guest_id: int, request: Request):
    """The Art 15/20 bundle for one guest: decrypted fields, ids, no image copy."""
    guard = auth.require_login(request)
    if guard:
        return guard
    if not access.guest(request, guest_id):
        return Response("Not found.", status_code=404, media_type="text/plain")
    bundle = dsr.guest_export(guest_id)
    if bundle is None:
        return Response("Not found.", status_code=404, media_type="text/plain")
    db.audit("export_guest_dsr", f"guest_id={guest_id}")
    return Response(
        json.dumps(bundle, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="guest-{guest_id}.json"'},
    )


def _zip_download(
    background_tasks: BackgroundTasks,
    rows: List[Any],
    builder,
    filename: str,
):
    """Build a zip on disk, stream it, and unlink the temp file afterwards.

    Returns None when the builder wrote no entries, so the caller can answer
    with a message instead of an empty archive.
    """
    import os
    import tempfile

    from starlette.responses import FileResponse

    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        written = builder(rows, path)
    except Exception:
        os.unlink(path)
        raise
    if not written:
        os.unlink(path)
        return None
    background_tasks.add_task(os.unlink, path)
    return FileResponse(path, media_type="application/zip", filename=filename)


@router.get("/submissions/receipts.zip")
def submissions_receipts_zip(request: Request, background_tasks: BackgroundTasks):
    """Bulk-download stored Doručenka PDFs as a zip built on disk."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    date_from = _query_date(request, "from")
    date_to = _query_date(request, "to")
    sql = (
        # build_receipts_zip reads these four columns and nothing else; s.* would
        # pull both SOAP envelopes and the error PDF as well.
        "SELECT s.id, s.created_at, s.pseudo_stamp, s.receipt_pdf "
        "FROM submission s JOIN apartment a ON a.id = s.apartment_id "
        "WHERE a.owner_user_id IS ? AND s.receipt_pdf IS NOT NULL AND TRIM(s.receipt_pdf) != ''"
    )
    params: List[Any] = [owner_id]
    if date_from:
        sql += " AND date(s.created_at) >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date(s.created_at) <= ?"
        params.append(date_to)
    sql += " ORDER BY s.created_at DESC"
    rows = db.query(sql, params)
    if not rows:
        return _back("/submissions", err=_flash(request, "flash.error.no_receipts"))
    if len(rows) > reporting.MAX_RECEIPT_DOWNLOADS:
        return _back(
            "/submissions",
            err=_flash(
                request,
                "flash.error.too_many_receipts",
                count=len(rows),
                limit=reporting.MAX_RECEIPT_DOWNLOADS,
            ),
        )
    response = _zip_download(
        background_tasks,
        rows,
        reporting.build_receipts_zip,
        f"dorucenky-{datetime.now().strftime('%Y%m%d')}.zip",
    )
    if response is None:
        return _back("/submissions", err=_flash(request, "flash.error.no_receipts"))
    db.audit("export_receipts_zip", f"rows={len(rows)}")
    return response


def _pdf_response(base64_text: Optional[str], filename: str):
    if not base64_text:
        return Response("No document was returned for this submission.", status_code=404,
                        media_type="text/plain")
    try:
        raw = base64.b64decode(base64_text)
    except Exception:
        return Response("Stored document is not valid base64.", status_code=500, media_type="text/plain")
    return Response(
        raw,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/submissions/{submission_id}/receipt.pdf")
def submission_receipt(submission_id: int, request: Request):
    """The Doručenka. Rule 10.4(3) and (4): the host must be able to see and save it."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owned = access.submission(request, submission_id)
    row = db.query_one("SELECT receipt_pdf FROM submission WHERE id = ?", (submission_id,)) if owned else None
    if owned:
        db.audit("export_submission_pdf", f"submission_id={submission_id} which=receipt")
    return _pdf_response(row["receipt_pdf"] if row else None, f"dorucenka-{submission_id}.pdf")


@router.get("/submissions/{submission_id}/errors.pdf")
def submission_errors(submission_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owned = access.submission(request, submission_id)
    row = db.query_one("SELECT error_pdf FROM submission WHERE id = ?", (submission_id,)) if owned else None
    if owned:
        db.audit("export_submission_pdf", f"submission_id={submission_id} which=errors")
    return _pdf_response(row["error_pdf"] if row else None, f"dorucenka-chyby-{submission_id}.pdf")


@router.get("/submissions/{submission_id}/{which}.xml")
def submission_xml(submission_id: int, which: str, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    if which not in ("request", "response"):
        return Response("Unknown document.", status_code=404, media_type="text/plain")
    owned = access.submission(request, submission_id)
    if not owned:
        return Response("Not found.", status_code=404, media_type="text/plain")
    row = db.query_one(
        f"SELECT {which}_xml AS body FROM submission WHERE id = ?", (submission_id,)
    )
    db.audit("export_submission_xml", f"submission_id={submission_id} which={which}")
    return Response((row["body"] if row else "") or "", media_type="application/xml")


@router.get("/housebook.csv")
def housebook_download(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    stamp = datetime.now().strftime("%Y%m%d")
    rows = housebook.housebook_rows(
        _query_int(request, "apartment"),
        _query_date(request, "from") or None,
        _query_date(request, "to") or None,
        owner_user_id=access.owner_id(request),
    )
    db.audit("export_housebook_csv", f"rows={len(rows)}")
    return StreamingResponse(
        housebook.iter_housebook_csv_rows(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="domovni-kniha-{stamp}.csv"'},
    )


@router.get("/housebook/pdfs.zip")
def housebook_pdfs_download(request: Request, background_tasks: BackgroundTasks):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = housebook.housebook_rows(
        _query_int(request, "apartment"),
        _query_date(request, "from") or None,
        _query_date(request, "to") or None,
        owner_user_id=access.owner_id(request),
    )
    if not rows:
        return _back("/housebook", err=_flash(request, "flash.error.no_housebook_matches"))
    if len(rows) > housebook.MAX_INSPECTION_PDFS:
        return _back(
            "/housebook",
            err=_flash(
                request,
                "flash.error.too_many_entries",
                count=len(rows),
                limit=housebook.MAX_INSPECTION_PDFS,
            ),
        )
    response = _zip_download(
        background_tasks,
        rows,
        housebook.build_housebook_pdfs_zip,
        f"domovni-kniha-pdf-{datetime.now().strftime('%Y%m%d')}.zip",
    )
    if response is None:
        return _back("/housebook", err=_flash(request, "flash.error.no_housebook_matches"))
    db.audit("export_housebook_pdfs", f"rows={len(rows)}")
    return response


@router.post("/settings/workspace-export")
def settings_workspace_export(request: Request, background_tasks: BackgroundTasks):
    """ZIP of everything in the signed-in workspace (scheduled-deletion window)."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    if not account or not account["deletion_due_at"]:
        return _back("/settings", err=_flash(request, "flash.error.workspace_export_not_scheduled"))
    path = workspace_export.build_workspace_zip(owner_id)
    db.audit(
        "workspace_exported",
        f"user={owner_id}",
        actor=account["username"],
        owner_user_id=owner_id,
    )
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"workspace-{owner_id}.zip",
        background=BackgroundTask(os.unlink, path),
    )


@router.get("/settings/archived")
def settings_archived_view(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    item_type = request.query_params.get("type", "all")
    if item_type not in ARCHIVED_TYPES:
        item_type = "all"

    counts = {
        "stays": int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM reservation r "
                "JOIN apartment a ON a.id = r.apartment_id "
                "WHERE r.archived_at IS NOT NULL AND a.owner_user_id IS ?",
                (owner_id,),
            )["n"]
        ),
        "properties": int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM apartment "
                "WHERE archived_at IS NOT NULL AND owner_user_id IS ?",
                (owner_id,),
            )["n"]
        ),
        "housebook": int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM guest g "
                "JOIN reservation r ON r.id = g.reservation_id "
                "JOIN apartment a ON a.id = r.apartment_id "
                "WHERE g.archived_at IS NOT NULL AND a.owner_user_id IS ?",
                (owner_id,),
            )["n"]
        ),
        "entities": int(
            db.query_one(
                "SELECT COUNT(*) AS n FROM legal_entity "
                "WHERE archived_at IS NOT NULL AND owner_user_id IS ?",
                (owner_id,),
            )["n"]
        ),
    }
    counts["all"] = counts["stays"] + counts["properties"] + counts["housebook"] + counts["entities"]

    archived_stays: List[Dict[str, Any]] = []
    archived_properties: List[Dict[str, Any]] = []
    archived_housebook: List[Dict[str, Any]] = []
    archived_entities: List[Dict[str, Any]] = []

    if item_type in ("all", "stays"):
        archived_stays = db.query(
            "SELECT r.*, a.internal_name FROM reservation r "
            "JOIN apartment a ON a.id = r.apartment_id "
            "WHERE r.archived_at IS NOT NULL AND a.owner_user_id IS ? "
            "ORDER BY r.archived_at DESC, r.id DESC",
            (owner_id,),
        )
    if item_type in ("all", "properties"):
        archived_properties = db.query(
            "SELECT a.*, "
            "  (SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = a.id) AS reservations "
            "FROM apartment a "
            "WHERE a.archived_at IS NOT NULL AND a.owner_user_id IS ? "
            "ORDER BY a.archived_at DESC",
            (owner_id,),
        )
    if item_type in ("all", "housebook"):
        archived_housebook = housebook.housebook_archived_rows(owner_user_id=owner_id)
    if item_type in ("all", "entities"):
        archived_entities = db.query(
            "SELECT e.* FROM legal_entity e "
            "WHERE e.archived_at IS NOT NULL AND e.owner_user_id IS ? "
            "ORDER BY e.archived_at DESC",
            (owner_id,),
        )

    return render(
        request,
        "settings_archived.html",
        {
            "item_type": item_type,
            "counts": counts,
            "archived_stays": archived_stays,
            "archived_properties": archived_properties,
            "archived_housebook": archived_housebook,
            "archived_entities": archived_entities,
        },
    )


@router.post("/settings/purge-expired")
def purge_expired_records(request: Request):
    """Storage limitation: delete what the six-year duty no longer covers."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_user_id = access.owner_id(request)
    # One code path with the scheduled job (BE-2): the button only forces
    # ``dry_run=False`` for this owner.
    summary = retention.run(
        claim.prague_today(), dry_run=False, owner_user_id=owner_user_id
    )
    deleted = summary["counts"].get("guests", 0)
    purged_invoices = summary["counts"].get("invoices", 0)
    # A passport image has no six-year basis, so the same button clears the
    # ones left over from stays that ended long ago.
    photos = passport_photos.purge_stale(owner_user_id=owner_user_id)
    # The request envelope holds every reported guest's passport number, so it
    # goes on a much shorter clock than the record it belongs to.
    blanked = reporting.purge_submission_payloads(owner_user_id=owner_user_id)
    parts = []
    if deleted:
        parts.append(f"{deleted} guest record(s) past the retention period")
    if photos:
        parts.append(f"{photos} passport image(s) no longer needed")
    if blanked:
        parts.append(f"{blanked} submission envelope(s) no longer needed")
    if purged_invoices:
        parts.append(f"{purged_invoices} invoice(s) past the retention period")
    if not parts:
        return _back("/settings", msg=_flash(request, "flash.settings.nothing_to_purge"))
    return _back(
        "/settings",
        msg=_flash(request, "flash.settings.purged", parts=" and ".join(parts)),
    )
