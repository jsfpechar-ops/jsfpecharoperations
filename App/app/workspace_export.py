"""Workspace export for termination (BE-10)."""
from __future__ import annotations

import base64
import json
import os
import tempfile
import zipfile
from typing import List, Optional

from . import db, housebook, stay_fee_filing


def _safe_pdf(base64_text: Optional[str]) -> Optional[bytes]:
    if not base64_text:
        return None
    try:
        return base64.b64decode(base64_text)
    except Exception:
        return None


def guest_ids(owner_user_id: int) -> List[int]:
    return [
        row["id"]
        for row in db.query(
            "SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
            "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id IS ?",
            (owner_user_id,),
        )
    ]


def build_workspace_zip(owner_user_id: int) -> str:
    """Write a ZIP of everything the workspace holds; return its temp path.

    The caller streams it and unlinks it. Nothing is deleted here.
    """
    rows = housebook.housebook_rows(owner_user_id=owner_user_id)
    archived = housebook.housebook_archived_rows(owner_user_id=owner_user_id)
    guests = guest_ids(owner_user_id)

    fd, path = tempfile.mkstemp(suffix=".zip", prefix="workspace-")
    os.close(fd)
    counts = {"guests": len(guests), "receipts": 0, "invoices": 0, "stay_fee_filings": 0}
    stay_fee_files: List[str] = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("housebook.csv", b"".join(housebook.iter_housebook_csv_rows(rows)))
        if archived:
            try:
                archive.writestr(
                    "archived_housebook.csv",
                    b"".join(housebook.iter_housebook_csv_rows(archived)),
                )
            except Exception:
                pass
        for guest_id in guests:
            try:
                archive.writestr(
                    f"guests/{guest_id}.pdf", housebook.registration_form_pdf(guest_id)
                )
            except Exception:
                continue
        for submission in db.query(
            "SELECT s.id, s.receipt_pdf FROM submission s "
            "JOIN apartment a ON a.id = s.apartment_id "
            "WHERE a.owner_user_id IS ? AND s.receipt_pdf IS NOT NULL",
            (owner_user_id,),
        ):
            pdf = _safe_pdf(submission["receipt_pdf"])
            if pdf:
                archive.writestr(f"receipts/{submission['id']}.pdf", pdf)
                counts["receipts"] += 1
        for row in db.query(
            "SELECT f.* FROM stay_fee_filing f "
            "JOIN apartment a ON a.id = f.apartment_id "
            "WHERE a.owner_user_id IS ? AND f.superseded_at IS NULL",
            (owner_user_id,),
        ):
            pdf = stay_fee_filing.pdf_bytes(row)
            csv = stay_fee_filing.csv_bytes(row)
            base = f"stay_fees/{row['apartment_id']}-{row['period_key']}-v{row['version']}"
            if pdf:
                name = f"{base}.pdf"
                archive.writestr(name, pdf)
                stay_fee_files.append(name)
            if csv:
                name = f"{base}.csv"
                archive.writestr(name, csv)
                stay_fee_files.append(name)
            if pdf or csv:
                counts["stay_fee_filings"] += 1
        for invoice in db.query(
            "SELECT id, pdf_blob FROM invoice WHERE owner_user_id IS ?", (owner_user_id,)
        ):
            blob = invoice["pdf_blob"]
            if not blob:
                continue
            if isinstance(blob, str):
                blob = blob.encode("latin-1")
            archive.writestr(f"invoices/{invoice['id']}.pdf", blob)
            counts["invoices"] += 1
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "generated_at": db.utcnow(),
                    "owner_user_id": owner_user_id,
                    "counts": counts,
                    "housebook_rows": len(rows),
                    "archived_rows": len(archived),
                    "stay_fee_files": stay_fee_files,
                },
                indent=2,
            ),
        )
    return path
