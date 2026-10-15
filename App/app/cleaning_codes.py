"""Permanent cleaning codes, separate from the guest PIN expiry lifecycle.

Only process_queue (called in the guest-code worker, sequentially) contacts the
provider. Candidate PINs and names survive timeouts; retries reconcile first.
"""
from __future__ import annotations

import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from . import auth, cleaning, db, ttlock


def _activate(cur, row: dict) -> None:
    current = cur.execute(
        "SELECT p.code_id, p.pending_code_id, a.active, a.archived_at, a.lock_id, a.lock_provider, a.owner_user_id "
        "FROM cleaning_property p JOIN apartment a ON a.id = p.apartment_id WHERE p.apartment_id = ?",
        (row["apartment_id"],),
    ).fetchone()
    managed = cur.execute("SELECT * FROM cleaning_code WHERE id = ?", (row["id"],)).fetchone()
    if managed["source"] == "ttlock":
        account = cur.execute("SELECT owner_user_id FROM lock_account WHERE id = ?",
                              (managed["lock_account_id"],)).fetchone()
        if (not current or not current["active"] or current["archived_at"] or
            current["pending_code_id"] != row["id"] or current["lock_provider"] != "ttlock" or
            str(current["lock_id"]) != managed["lock_id"] or not account or
            account["owner_user_id"] != current["owner_user_id"]):
            cur.execute(
                "UPDATE cleaning_code SET state = 'revoke_pending', attempts = 0, next_attempt_at = ?, "
                "claimed_at = NULL, updated_at = ? WHERE id = ?", (db.utcnow(), db.utcnow(), row["id"]),
            )
            cur.execute("UPDATE cleaning_property SET pending_code_id = NULL WHERE pending_code_id = ?", (row["id"],))
            return
    cur.execute(
        "UPDATE cleaning_property SET code_id = ?, pending_code_id = NULL, updated_at = ? "
        "WHERE apartment_id = ?", (row["id"], db.utcnow(), row["apartment_id"]),
    )
    cur.execute("UPDATE cleaning_code SET state = 'active', claimed_at = NULL, updated_at = ? WHERE id = ?",
                (db.utcnow(), row["id"]))
    if current and current["code_id"] and current["code_id"] != row["id"]:
        cur.execute(
            "UPDATE cleaning_code SET state = CASE WHEN source = 'ttlock' THEN 'revoke_pending' ELSE 'revoked' END, "
            "pin_enc = CASE WHEN source = 'manual' THEN NULL ELSE pin_enc END, attempts = 0, "
            "next_attempt_at = ?, updated_at = ? WHERE id = ?",
            (db.utcnow(), db.utcnow(), current["code_id"]),
        )


def save_manual(apartment_id: int, value: str) -> None:
    pin = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9*#-]{1,32}", pin):
        raise ValueError("code")
    cleaning.ensure_property(apartment_id)
    with db.immediate() as cur:
        pending = cur.execute(
            "SELECT c.* FROM cleaning_property p JOIN cleaning_code c ON c.id = p.pending_code_id "
            "WHERE p.apartment_id = ?", (apartment_id,),
        ).fetchone()
        if pending:
            if pending["state"] in ("issuing", "revoking"):
                raise ValueError("pending")
            # A timed-out creation may have succeeded. Preserve and reconcile
            # its operation before revoking; fallback must never orphan it.
            cur.execute(
                "UPDATE cleaning_code SET state = 'revoke_pending', attempts = 0, next_attempt_at = ? WHERE id = ?",
                (db.utcnow(), pending["id"]),
            )
        cur.execute(
            "INSERT INTO cleaning_code (apartment_id, source, pin_enc, operation_ref, state, created_at, updated_at) "
            "VALUES (?, 'manual', ?, ?, 'active', ?, ?) RETURNING id",
            (apartment_id, db.encrypt_field(pin), secrets.token_hex(16), db.utcnow(), db.utcnow()),
        )
        row_id = cur.fetchone()[0]
        _activate(cur, {"id": row_id, "apartment_id": apartment_id})


def queue_permanent(home: dict, owner_id: int | None) -> int:
    if auth.staging_no_login():
        raise ValueError("login_required")
    account = ttlock.account_for(owner_id) if owner_id is not None else None
    if (not ttlock.allowed_for(owner_id) or not account or account["status"] != "ok" or
        home["lock_provider"] != "ttlock" or not home["lock_id"] or
        str(home["lock_id"]) not in {str(x["lock_id"]) for x in ttlock.locks_of(account)}):
        raise ValueError("lock_setup")
    cleaning.ensure_property(home["id"])
    with db.immediate() as cur:
        prop = cur.execute(
            "SELECT pending_code_id FROM cleaning_property WHERE apartment_id = ?", (home["id"],),
        ).fetchone()
        if prop["pending_code_id"]:
            cur.execute(
                "UPDATE cleaning_code SET state = 'retrying', attempts = 1, next_attempt_at = ?, updated_at = ? "
                "WHERE id = ? AND state = 'failed'", (db.utcnow(), db.utcnow(), prop["pending_code_id"]),
            )
            return prop["pending_code_id"]
        now = db.utcnow()
        cur.execute(
            "INSERT INTO cleaning_code (apartment_id, source, pin_enc, lock_account_id, lock_id, "
            "operation_ref, state, next_attempt_at, created_at, updated_at) "
            "VALUES (?, 'ttlock', ?, ?, ?, ?, 'pending', ?, ?, ?) RETURNING id",
            (home["id"], db.encrypt_field(str(secrets.randbelow(9_000_000) + 1_000_000)),
             account["id"], str(home["lock_id"]), "UH Cleaning " + secrets.token_hex(8), now, now, now),
        )
        row_id = cur.fetchone()[0]
        cur.execute(
            "UPDATE cleaning_property SET pending_code_id = ?, updated_at = ? WHERE apartment_id = ?",
            (row_id, now, home["id"]),
        )
        return row_id


def _find(row: dict) -> str | None:
    # The narrow exact-name match is an idempotency lookup, never a code-list
    # poll. Do not retain unrelated PINs returned by TTLock.
    answer = ttlock._call(row["lock_account_id"], "/v3/lock/listKeyboardPwd", {
        "lockId": int(row["lock_id"]), "searchStr": row["operation_ref"],
        "pageNo": 1, "pageSize": 20, "orderBy": 1,
    }, ttlock.NORMAL)
    matches = [entry for entry in answer.get("list", []) if
               entry.get("keyboardPwdName") == row["operation_ref"]]
    if len(matches) > 1:
        raise ttlock.TTLockError("ambiguous operation", kind="permission")
    if not matches:
        return None
    entry = matches[0]
    if int(entry.get("keyboardPwdType") or 0) != 2 or not hmac.compare_digest(
        str(entry.get("keyboardPwd") or ""), db.decrypt_field(row["pin_enc"]),
    ):
        raise ttlock.TTLockError("operation mismatch", kind="permission")
    return str(entry["keyboardPwdId"])


def _failure(row: dict, error: ttlock.TTLockError, revoking: bool) -> None:
    transient = error.kind in {"offline", "transient", "network", "rate", "budget"}
    retry = transient and row["attempts"] < 5
    state = ("revoke_pending" if retry else "revoke_failed") if revoking else ("retrying" if retry else "failed")
    delay = (1, 5, 15, 60, 240)[min(row["attempts"] - 1, 4)]
    db.update("cleaning_code", row["id"], {
        "state": state, "claimed_at": None, "last_error": error.kind,
        "next_attempt_at": (datetime.now(timezone.utc) + timedelta(minutes=delay)).isoformat(),
        "updated_at": db.utcnow(),
    })


def process_queue() -> int:
    if auth.staging_no_login() or not ttlock.enabled():
        return 0
    now = db.utcnow()
    db.execute(
        "UPDATE cleaning_code SET state = 'revoke_pending', attempts = 0, next_attempt_at = ? "
        "WHERE source = 'ttlock' AND state = 'active' AND NOT EXISTS ("
        "SELECT 1 FROM apartment a JOIN lock_account la ON la.id = cleaning_code.lock_account_id "
        "WHERE a.id = cleaning_code.apartment_id AND a.active = 1 AND a.archived_at IS NULL "
        "AND a.lock_provider = 'ttlock' AND a.lock_id = cleaning_code.lock_id "
        "AND la.owner_user_id = a.owner_user_id)", (now,),
    )
    stale = (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
    db.execute(
        "UPDATE cleaning_code SET state = 'retrying', claimed_at = NULL "
        "WHERE state = 'issuing' AND claimed_at < ?", (stale,),
    )
    db.execute(
        "UPDATE cleaning_code SET state = 'revoke_pending', claimed_at = NULL "
        "WHERE state = 'revoking' AND claimed_at < ?", (stale,),
    )
    rows = db.query(
        "SELECT c.* FROM cleaning_code c JOIN cleaning_property p ON p.apartment_id = c.apartment_id "
        "WHERE c.state IN ('pending', 'retrying', 'revoke_pending') "
        "AND (c.next_attempt_at IS NULL OR c.next_attempt_at <= ?) ORDER BY c.id LIMIT 10", (now,),
    )
    processed = 0
    for raw in rows:
        row = dict(raw)
        revoking = row["state"] == "revoke_pending"
        expected = row["state"]
        attempts = row["attempts"] + 1
        if not db.update_if("cleaning_code", row["id"], {
            "state": "revoking" if revoking else "issuing", "claimed_at": now,
            "attempts": attempts, "updated_at": now,
        }, {"state": expected, "attempts": row["attempts"]}):
            continue
        row["attempts"] = attempts
        try:
            if not row["lock_account_id"]:
                raise ttlock.TTLockError("connection removed", kind="permission")
            if revoking:
                code_id = _find(row) if attempts > 1 else (row["provider_code_id"] or _find(row))
                if code_id:
                    ttlock.delete_code(row["lock_account_id"], row["lock_id"], code_id)
                db.update("cleaning_code", row["id"], {
                    "state": "revoked", "pin_enc": None, "claimed_at": None, "updated_at": db.utcnow(),
                })
            else:
                code_id = _find(row) if attempts > 1 else None
                if not code_id:
                    code_id = ttlock.add_permanent_code(
                        row["lock_account_id"], row["lock_id"],
                        db.decrypt_field(row["pin_enc"]), row["operation_ref"],
                    )
                with db.immediate() as cur:
                    cur.execute("UPDATE cleaning_code SET provider_code_id = ? WHERE id = ?", (code_id, row["id"]))
                    _activate(cur, row)
            processed += 1
        except ttlock.TTLockError as error:
            _failure(row, error, revoking)
    return processed


def remove(apartment_id: int) -> None:
    cleaning.ensure_property(apartment_id)
    with db.immediate() as cur:
        prop = cur.execute("SELECT * FROM cleaning_property WHERE apartment_id = ?", (apartment_id,)).fetchone()
        for code_id in (prop["code_id"], prop["pending_code_id"]):
            if not code_id:
                continue
            row = cur.execute("SELECT * FROM cleaning_code WHERE id = ?", (code_id,)).fetchone()
            if row["state"] in ("issuing", "revoking"):
                raise ValueError("pending")
            cur.execute(
                "UPDATE cleaning_code SET state = ?, pin_enc = ?, attempts = 0, next_attempt_at = ?, updated_at = ? "
                "WHERE id = ?",
                ("revoke_pending" if row["source"] == "ttlock" else "revoked",
                 row["pin_enc"] if row["source"] == "ttlock" else None, db.utcnow(), db.utcnow(), code_id),
            )
        cur.execute(
            "UPDATE cleaning_property SET code_id = NULL, pending_code_id = NULL, updated_at = ? WHERE apartment_id = ?",
            (db.utcnow(), apartment_id),
        )
