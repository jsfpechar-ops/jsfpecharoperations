"""Records which host accepted which document version, and when (BE-1).

Acceptance is per account and per document version, so bumping a version in
``config`` makes that document pending again without touching earlier rows. The
mechanism is deliberately separate from the wording: the plan's Rule 6 gates
legal copy, not this evidence.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from . import config, db

DOCUMENTS = ("terms", "privacy", "dpa")


def current_versions() -> Dict[str, str]:
    """Read the configured versions on every call, so a bump is picked up."""
    return {
        "terms": config.TERMS_VERSION,
        "privacy": config.PRIVACY_VERSION,
        "dpa": config.DPA_VERSION,
    }


def pending(user_id: int) -> List[str]:
    """The documents whose current version this account has not accepted."""
    versions = current_versions()
    accepted = {
        (row["document"], row["version"])
        for row in db.query(
            "SELECT document, version FROM legal_acceptance WHERE user_account_id = ?",
            (user_id,),
        )
    }
    return [doc for doc in DOCUMENTS if (doc, versions[doc]) not in accepted]


def accepted(user_id: int) -> List[Dict[str, Any]]:
    """Every acceptance row for an account, newest first (ids and versions only)."""
    return [
        dict(row)
        for row in db.query(
            "SELECT document, version, accepted_at, method "
            "FROM legal_acceptance WHERE user_account_id = ? "
            "ORDER BY accepted_at DESC, id DESC",
            (user_id,),
        )
    ]


def record(
    user_id: int, docs: Iterable[str], method: str, request: Optional[Any] = None
) -> List[str]:
    """Insert one row per document (idempotent) and audit the event.

    The audit detail carries ids and versions only — never an IP, user agent or
    name (Rule 8); the IP and user agent live on the acceptance row itself.
    """
    versions = current_versions()
    wanted = [doc for doc in DOCUMENTS if doc in set(docs)]
    if not wanted:
        return []

    ip = ""
    user_agent = ""
    if request is not None:
        ip = request.client.host if request.client else ""
        user_agent = (request.headers.get("user-agent") or "")[:300]

    account = db.query_one("SELECT username FROM user_account WHERE id = ?", (user_id,))
    actor = account["username"] if account else "host"
    accepted_at = db.utcnow()

    for doc in wanted:
        db.execute(
            "INSERT OR IGNORE INTO legal_acceptance "
            "(user_account_id, document, version, accepted_at, method, ip, user_agent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, doc, versions[doc], accepted_at, method, ip, user_agent),
        )

    detail = " ".join(f"{doc}_v{versions[doc]}" for doc in wanted)
    db.audit(
        "legal_accepted",
        detail=f"{detail} method={method}",
        actor=actor,
        owner_user_id=user_id,
    )
    return wanted


# The old login line logged "terms_vX privacy_vY dpa_vZ accepted" as free text.
_LOGIN_DETAIL = re.compile(
    r"terms_v(?P<terms>\S+)\s+privacy_v(?P<privacy>\S+)\s+dpa_v(?P<dpa>\S+)\s+accepted"
)


def backfill_from_audit() -> int:
    """One-shot: turn legacy login acceptance lines into accepted rows.

    Idempotent through the UNIQUE constraint. Returns how many rows were
    inserted, so the deploy step can log a count (not personal data).
    """
    inserted = 0
    rows = db.query(
        "SELECT at, owner_user_id, detail FROM audit "
        "WHERE action = 'login' AND detail LIKE 'terms_v%accepted' ORDER BY at"
    )
    for row in rows:
        match = _LOGIN_DETAIL.search(row["detail"] or "")
        if not match or not row["owner_user_id"]:
            continue
        for doc in DOCUMENTS:
            if db.execute(
                "INSERT OR IGNORE INTO legal_acceptance "
                "(user_account_id, document, version, accepted_at, method) "
                "VALUES (?, ?, ?, ?, 'backfill')",
                (row["owner_user_id"], doc, match.group(doc), row["at"]),
            ):
                inserted += 1
    return inserted
