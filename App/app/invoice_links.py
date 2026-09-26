"""Signed, expiring download links for issued invoices (host-only build).

A guest has no account, so the only way they download an invoice is the token in
the e-mail the host chose to send. The token carries the invoice id and a prefix
of its stored PDF hash, so an old link stops working if the PDF ever changed.
"""
from __future__ import annotations

from itsdangerous import BadSignature, URLSafeTimedSerializer

from . import config, db

_DL = URLSafeTimedSerializer(config.secret_key(), salt="ubyhost-invoice-download")
DOWNLOAD_MAX_AGE = 30 * 86400


def download_token(invoice_id: int, pdf_sha256: str) -> str:
    return _DL.dumps({"i": invoice_id, "h": (pdf_sha256 or "")[:16]})


def read_download_token(token: str) -> int | None:
    try:
        data = _DL.loads(token, max_age=DOWNLOAD_MAX_AGE)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    row = db.query_one("SELECT * FROM invoice WHERE id = ?", (data.get("i"),))
    if not row or not row["pdf_sha256"]:
        return None
    if (row["pdf_sha256"] or "")[:16] != data.get("h"):
        return None
    return int(row["id"])
