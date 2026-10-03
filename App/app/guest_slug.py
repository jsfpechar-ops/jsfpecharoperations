"""Readable guest links: ``/l/{readable}-{code}`` beside the permanent token.

The permanent ``apartment.permalink_token`` stays the secret every guest-side
control is keyed on (the PIN cookie, the PIN fingerprint, the lockout and the
rate limits). A slug is only another name for it, resolved back to the
apartment before anything else happens, so a guest who switches between the
old and the new link is never asked for the PIN twice and cannot reset the
lockout by switching.

* The readable part comes from the property's name: accents folded, lower
  case, ``a-z0-9-``, at most 40 characters cut at a word boundary.
* The code is six characters from the token alphabet. It is never edited; the
  host may rename the readable part, and every earlier slug keeps redirecting
  to the current one.
* Generating a new guest link (the "link leaked" button) retires every slug
  with the token, because an old slug that still redirected would hand the new
  link to whoever held the leaked one.
"""
from __future__ import annotations

import re
import secrets
import sqlite3
import unicodedata
from typing import Optional

from . import auth, db

CODE_LENGTH = 6
READABLE_MAX = 40
# Used when a property name folds to nothing (only symbols or a script with no
# Latin form) or to a reserved word.
FALLBACK_READABLE = "stay"
# Every path segment under /l/{key}/ today. Never a readable part, so a slug
# can never be mistaken for one in a log, a test or a hand-typed link.
RESERVED = frozenset(
    {"pin", "privacy", "claim", "confirm", "party", "another", "new", "edit", "save"}
)

# Letters NFKD does not split into a base letter and an accent.
_FOLD_EXTRA = str.maketrans(
    {
        "ß": "ss", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "ø": "o", "Ø": "o",
        "ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "ð": "d", "þ": "th", "ı": "i",
    }
)
_NOT_SLUG = re.compile(r"[^a-z0-9]+")
_SLUG_SHAPE = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\Z")


def fold(text: Optional[str]) -> str:
    """``"Vinohrady – Studio Žižkov"`` -> ``"vinohrady-studio-zizkov"``, uncut."""
    value = (text or "").translate(_FOLD_EXTRA)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return _NOT_SLUG.sub("-", value.lower()).strip("-")


def readable_part(text: Optional[str]) -> str:
    """The readable part for a name, or ``""`` if nothing usable is left.

    Cut at the last word boundary inside the limit, so a long name loses whole
    words rather than ending in half of one. A single word longer than the
    limit is cut hard; there is no boundary to respect.
    """
    value = fold(text)
    if len(value) > READABLE_MAX:
        head = value[: READABLE_MAX + 1]
        if head.endswith("-"):
            value = head[:-1]
        elif "-" in head[:READABLE_MAX]:
            value = head[:READABLE_MAX].rsplit("-", 1)[0]
        else:
            value = value[:READABLE_MAX]
    return value.strip("-")


def is_reserved(readable: str) -> bool:
    return readable in RESERVED


def validate_readable(text: Optional[str]) -> tuple[str, str]:
    """Normalise a host's input. Returns ``(readable, error)``; error is ``""``,
    ``"empty"`` or ``"reserved"``."""
    readable = readable_part(text)
    if not readable:
        return "", "empty"
    if is_reserved(readable):
        return readable, "reserved"
    return readable, ""


def new_code() -> str:
    return "".join(secrets.choice(auth.PERMALINK_ALPHABET) for _ in range(CODE_LENGTH))


def compose(readable: str, code: str) -> str:
    return f"{readable}-{code}"


def code_of(slug: str) -> str:
    return slug.rsplit("-", 1)[-1]


def readable_of(slug: str) -> str:
    return slug.rsplit("-", 1)[0]


def looks_like_slug(key: str) -> bool:
    """Cheap shape check before the database is asked."""
    if not key or len(key) > READABLE_MAX + 1 + CODE_LENGTH or "-" not in key:
        return False
    return bool(_SLUG_SHAPE.match(key)) and len(code_of(key)) == CODE_LENGTH


def _generated_readable(name: Optional[str]) -> str:
    readable = readable_part(name)
    if not readable or is_reserved(readable):
        return FALLBACK_READABLE
    return readable


# --- lookups -------------------------------------------------------------

def lookup(key: str):
    """The ``apartment_slug`` row for a key, matched case-insensitively."""
    key = (key or "").strip().lower()
    if not looks_like_slug(key):
        return None
    return db.query_one(
        "SELECT slug, apartment_id, is_current FROM apartment_slug WHERE slug = ?",
        (key,),
    )


def current(apartment_id: int) -> Optional[str]:
    row = db.query_one(
        "SELECT slug FROM apartment_slug WHERE apartment_id = ? AND is_current = 1",
        (apartment_id,),
    )
    return row["slug"] if row else None


def link_key(apartment) -> str:
    """What goes after ``/l/`` in a link the host copies: the slug if one
    exists, else the permanent token (which keeps working for ever)."""
    if not apartment:
        return ""
    return ensure(apartment) or (apartment["permalink_token"] or "")


# --- writes --------------------------------------------------------------

def _insert_current(cur, apartment_id: int, readable: str) -> str:
    """Insert a fresh current slug on an open cursor. Retries a code clash."""
    for _ in range(8):
        slug = compose(readable, new_code())
        if cur.execute(
            "SELECT 1 FROM apartment_slug WHERE slug = ?", (slug,)
        ).fetchone():
            continue
        cur.execute(
            "INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at) "
            "VALUES (?, ?, 1, ?)",
            (slug, apartment_id, db.utcnow()),
        )
        return slug
    raise RuntimeError("could not find a free guest link code")


def ensure(apartment) -> Optional[str]:
    """The apartment's current slug, created from its name if it has none.

    Rows inserted before this feature, by the demo seed or by a test fixture
    have no slug until something asks; asking is what creates it.
    """
    if not apartment or not apartment["permalink_token"]:
        return None
    existing = current(int(apartment["id"]))
    if existing:
        return existing
    try:
        with db.immediate() as cur:
            row = cur.execute(
                "SELECT slug FROM apartment_slug WHERE apartment_id = ? AND is_current = 1",
                (int(apartment["id"]),),
            ).fetchone()
            if row:
                return row["slug"]
            return _insert_current(
                cur, int(apartment["id"]), _generated_readable(apartment["internal_name"])
            )
    except sqlite3.IntegrityError:
        # Another request created it between our read and our write.
        return current(int(apartment["id"]))


def rename(apartment_id: int, readable: str) -> Optional[str]:
    """Point the apartment at ``{readable}-{same code}``; the old slug redirects.

    ``readable`` must already have passed ``validate_readable``. Renaming back
    to an earlier name reuses that row. Returns the current slug, or ``None``
    if the name is taken by another property with the same code (rare: the
    code is random, not unique per apartment).
    """
    existing = current(apartment_id)
    if not existing:
        return None
    target = compose(readable, code_of(existing))
    if target == existing:
        return existing
    try:
        with db.immediate() as cur:
            row = cur.execute(
                "SELECT apartment_id FROM apartment_slug WHERE slug = ?", (target,)
            ).fetchone()
            if row and int(row["apartment_id"]) != int(apartment_id):
                return None
            cur.execute(
                "UPDATE apartment_slug SET is_current = 0 "
                "WHERE apartment_id = ? AND is_current = 1",
                (apartment_id,),
            )
            if row:
                cur.execute(
                    "UPDATE apartment_slug SET is_current = 1 WHERE slug = ?", (target,)
                )
            else:
                cur.execute(
                    "INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at) "
                    "VALUES (?, ?, 1, ?)",
                    (target, apartment_id, db.utcnow()),
                )
    except sqlite3.IntegrityError:
        return None
    return target


def rotate(apartment_id: int, readable: Optional[str] = None) -> str:
    """Drop every slug of the apartment and issue one with a new code.

    For "Generate a new link": the old token stops working, so its slugs must
    stop too, not redirect to the replacement.
    """
    with db.immediate() as cur:
        if readable is None:
            row = cur.execute(
                "SELECT slug FROM apartment_slug WHERE apartment_id = ? AND is_current = 1",
                (apartment_id,),
            ).fetchone()
            name = cur.execute(
                "SELECT internal_name FROM apartment WHERE id = ?", (apartment_id,)
            ).fetchone()
            readable = (
                readable_of(row["slug"])
                if row
                else _generated_readable(name["internal_name"] if name else "")
            )
        cur.execute("DELETE FROM apartment_slug WHERE apartment_id = ?", (apartment_id,))
        return _insert_current(cur, apartment_id, readable)


def backfill(conn) -> int:
    """Give every apartment without a current slug one; returns how many.

    Runs from ``db.init_db`` on its own connection, so it cannot use the
    pooled helpers. Idempotent: an apartment that has a slug is not selected.
    """
    rows = conn.execute(
        "SELECT a.id, a.internal_name FROM apartment a "
        "WHERE a.permalink_token IS NOT NULL AND NOT EXISTS ("
        "  SELECT 1 FROM apartment_slug s WHERE s.apartment_id = a.id AND s.is_current = 1)"
    ).fetchall()
    for row in rows:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _insert_current(conn, int(row["id"]), _generated_readable(row["internal_name"]))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return len(rows)
