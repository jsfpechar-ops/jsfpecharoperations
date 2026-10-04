#!/usr/bin/env python3
"""Re-encrypt everything stored encrypted under the current data key (WP16).

Run from ``App/`` with the same environment as the app (``UBYHOST_DB``,
``UBYHOST_DATA_DIR``, ``UBYHOST_SECRET_KEY``, ``UBYHOST_DATA_KEYS``)::

    .venv/bin/python scripts/reencrypt.py --dry-run
    .venv/bin/python scripts/reencrypt.py --backup /path/to/fresh/ubyhost.db
    .venv/bin/python scripts/reencrypt.py --check

What it does, table by table and in batches of ``--batch-size`` rows:

* every ``*_enc`` column, the stay-fee filing PDF/CSV blobs and the claim
  secret inside queued mail are re-encrypted under the first key in
  ``UBYHOST_DATA_KEYS``; a value already under that key is skipped;
* a field that is still in its plaintext column (rows saved before its
  ``*_enc`` column existed, for example birth date, street, town and the
  UbyPort request envelope) is encrypted into the ``*_enc`` column and the
  plaintext is blanked;
* passport photo files are re-encrypted in place; a legacy unencrypted file is
  encrypted and the plaintext file removed.

Idempotent and resumable: nothing records progress, because a value already
under the current key is simply skipped, so a run that is interrupted is
finished by running it again. Every write is compare-and-set against the value
that was read, so the app can keep running; a row the app changed in between
is counted as ``changed_meanwhile`` and picked up by the next run.

A value no configured key can decrypt is never touched; it is counted as
``unreadable`` and the run exits non-zero.

Writing runs refuse to start without ``--backup`` naming a backup file that
exists, is not empty, is not the live database, and is younger than
``--max-backup-age-hours``. ``--dry-run`` and ``--check`` write nothing and do
not need one.

``--rollback-new-fields`` is for going back to a release older than WP16 while
that release's key is still the only key in use: it moves birth date, street,
town and the request envelope back into their plaintext columns, which is all
an older release reads.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db, mail, passport_photos  # noqa: E402

# Columns that hold a Fernet token and nothing else. The *_enc columns of
# db.ENCRYPTED_COLUMNS are added below, so a field encrypted by a later
# release is covered without editing this list.
TOKEN_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("apartment", "uby_ws_password_enc"),
    ("user_account", "totp_secret_enc"),
    ("legal_entity", "signature_png_enc"),
    ("stay_fee_adjustment", "reason_enc"),
    ("stay_fee_filing", "payload_enc"),
    ("stay_fee_filing", "pdf_enc"),
    ("stay_fee_filing", "csv_enc"),
)

# The fields WP16 started encrypting. Only these are moved back by
# --rollback-new-fields: the older fields were encrypted by earlier releases,
# which already read them from their *_enc columns.
WP16_FIELDS: Tuple[Tuple[str, str, str], ...] = (
    ("guest", "birth_date", "birth_date_enc"),
    ("guest", "res_street", "res_street_enc"),
    ("guest", "res_city", "res_city_enc"),
    ("submission", "request_xml", "request_xml_enc"),
)

DEFAULT_BATCH = 200
DEFAULT_MAX_BACKUP_AGE_HOURS = 3.0


@dataclass
class Counts:
    scanned: int = 0
    current: int = 0
    rotated: int = 0
    encrypted: int = 0
    blanked: int = 0
    restored: int = 0
    unreadable: int = 0
    changed_meanwhile: int = 0

    def pending(self) -> int:
        """What a writing run would still change, plus what it cannot."""
        return self.rotated + self.encrypted + self.blanked + self.unreadable


@dataclass
class Report:
    dry_run: bool
    targets: Dict[str, Counts] = field(default_factory=dict)

    def counts(self, name: str) -> Counts:
        return self.targets.setdefault(name, Counts())

    @property
    def unreadable(self) -> int:
        return sum(c.unreadable for c in self.targets.values())

    @property
    def pending(self) -> int:
        return sum(c.pending() for c in self.targets.values())

    def lines(self) -> List[str]:
        out = []
        for name in sorted(self.targets):
            c = self.targets[name]
            out.append(
                f"{name}: scanned={c.scanned} current={c.current} rotated={c.rotated} "
                f"encrypted={c.encrypted} blanked={c.blanked} restored={c.restored} "
                f"unreadable={c.unreadable} changed_meanwhile={c.changed_meanwhile}"
            )
        return out


def token_targets() -> List[Tuple[str, str]]:
    targets = list(TOKEN_COLUMNS)
    for table, columns in db.ENCRYPTED_COLUMNS.items():
        for enc in columns.values():
            targets.append((table, enc))
    return targets


# --- preconditions -------------------------------------------------------

def check_backup(
    path: Optional[str],
    max_age_hours: float = DEFAULT_MAX_BACKUP_AGE_HOURS,
    now: Optional[float] = None,
) -> Path:
    """The backup file, or SystemExit saying why it is not good enough."""
    if not path:
        raise SystemExit(
            "Refusing to write: pass --backup with the path of a backup taken just now "
            "(for example the ubyhost.db or the .tar/.tar.age from scripts/backup_data.sh)."
        )
    backup = Path(path).expanduser()
    if not backup.is_file():
        raise SystemExit(f"Refusing to write: backup {backup} does not exist or is not a file.")
    if backup.stat().st_size == 0:
        raise SystemExit(f"Refusing to write: backup {backup} is empty.")
    try:
        if backup.resolve() == Path(config.DB_PATH).resolve():
            raise SystemExit("Refusing to write: --backup points at the live database.")
    except OSError:
        pass
    age_hours = ((now if now is not None else time.time()) - backup.stat().st_mtime) / 3600
    if age_hours > max_age_hours:
        raise SystemExit(
            f"Refusing to write: backup {backup} is {age_hours:.1f} hours old; take a new "
            f"one (limit {max_age_hours:g} hours, see --max-backup-age-hours)."
        )
    return backup


def require_keys(writing: bool) -> None:
    """Stop before encrypting under a key the running app does not have."""
    if config.legacy_data_key_enabled():
        try:
            config.require_secret_key()
        except RuntimeError as exc:
            raise SystemExit(
                f"Refusing to run: {exc}. Without the app's session secret the legacy key "
                "cannot be derived and nothing old can be read."
            ) from exc
    try:
        db.check_data_keys()
    except db.DataKeyError as exc:
        raise SystemExit(f"Refusing to run: {exc}.") from exc
    if writing and not config.data_keys():
        raise SystemExit(
            "Refusing to write: UBYHOST_DATA_KEYS is not set, so there is no new key to "
            "re-encrypt to. Set it in the app's .env first (see the runbook)."
        )


def open_database() -> None:
    """Make sure UBYHOST_DB is an existing UbyHost database, then add new columns."""
    path = Path(config.DB_PATH)
    if not path.exists():
        raise SystemExit(f"No database at {path}. Point UBYHOST_DB at the file the app uses.")
    found = db.query_one(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'guest'"
    )
    if not found:
        raise SystemExit(f"{path} does not look like a UbyHost database.")
    db.init_db()


# --- the work ------------------------------------------------------------

def _batches(sql: str, batch_size: int, extra: Iterable[Any] = ()) -> Iterable[List[Any]]:
    """Rows of ``sql`` (which must filter ``id > ?`` and end in ``LIMIT ?``) by id."""
    last = 0
    while True:
        rows = db.query(sql, (*extra, last, batch_size))
        if not rows:
            return
        last = int(rows[-1]["id"])
        yield rows


def _write(statements: List[Tuple[str, Tuple[Any, ...], str]], counts: Counts) -> None:
    """Run one batch of compare-and-set UPDATEs in one short transaction.

    Each statement names the counter it was counted under; one that matched no
    row (the app changed the value since it was read) moves to
    ``changed_meanwhile`` and is left for the next run.
    """
    if not statements:
        return
    with db.immediate() as cur:
        for sql, params, done in statements:
            cur.execute(sql, params)
            if cur.rowcount != 1:
                setattr(counts, done, getattr(counts, done) - 1)
                counts.changed_meanwhile += 1


def rotate_column(table: str, column: str, report: Report, batch_size: int) -> None:
    counts = report.counts(f"{table}.{column}")
    # The alias keeps the query helper from decrypting the row: this needs the
    # raw token, not the value.
    sql = (
        f"SELECT id, {column} AS token FROM {table} "
        f"WHERE {column} IS NOT NULL AND id > ? ORDER BY id LIMIT ?"
    )
    for rows in _batches(sql, batch_size):
        statements = []
        for row in rows:
            token = row["token"]
            if not token:
                continue
            counts.scanned += 1
            if db.token_is_current(token):
                counts.current += 1
                continue
            try:
                fresh = db.rotate_token(token)
            except db.DecryptionError:
                counts.unreadable += 1
                continue
            counts.rotated += 1
            statements.append((
                f"UPDATE {table} SET {column} = ? WHERE id = ? AND {column} = ?",
                (fresh, row["id"], token),
                "rotated",
            ))
        if not report.dry_run:
            _write(statements, counts)


def encrypt_plaintext(table: str, name: str, enc: str, report: Report, batch_size: int) -> None:
    """Move a field still in its plaintext column into its *_enc column."""
    counts = report.counts(f"{table}.{name}")
    sql = (
        f"SELECT id, {name} AS plain, {enc} AS token FROM {table} "
        f"WHERE {name} IS NOT NULL AND {name} <> '' AND id > ? ORDER BY id LIMIT ?"
    )
    for rows in _batches(sql, batch_size):
        statements = []
        for row in rows:
            counts.scanned += 1
            if row["token"]:
                # Already encrypted; the plaintext is a stale copy. The token
                # itself is handled by rotate_column.
                counts.blanked += 1
                statements.append((
                    f"UPDATE {table} SET {name} = NULL WHERE id = ? AND {name} = ?",
                    (row["id"], row["plain"]),
                    "blanked",
                ))
                continue
            counts.encrypted += 1
            statements.append((
                f"UPDATE {table} SET {enc} = ?, {name} = NULL "
                f"WHERE id = ? AND {name} = ? AND {enc} IS NULL",
                (db.encrypt_field(row["plain"]), row["id"], row["plain"]),
                "encrypted",
            ))
        if not report.dry_run:
            _write(statements, counts)


def rotate_outbox(report: Report, batch_size: int) -> None:
    """The claim secret queued mail keeps beside its body, inside the JSON payload."""
    counts = report.counts(f"email_outbox.payload[{mail.CLAIM_SECRET_KEY}]")
    sql = (
        "SELECT id, payload FROM email_outbox WHERE payload LIKE ? "
        "AND id > ? ORDER BY id LIMIT ?"
    )
    for rows in _batches(sql, batch_size, extra=(f"%{mail.CLAIM_SECRET_KEY}%",)):
        statements = []
        for row in rows:
            try:
                payload = json.loads(row["payload"] or "{}")
            except ValueError:
                continue
            token = payload.get(mail.CLAIM_SECRET_KEY) if isinstance(payload, dict) else None
            if not token:
                continue
            counts.scanned += 1
            if db.token_is_current(token):
                counts.current += 1
                continue
            try:
                payload[mail.CLAIM_SECRET_KEY] = db.rotate_token(token)
            except db.DecryptionError:
                counts.unreadable += 1
                continue
            counts.rotated += 1
            statements.append((
                "UPDATE email_outbox SET payload = ? WHERE id = ? AND payload = ?",
                (json.dumps(payload), row["id"], row["payload"]),
                "rotated",
            ))
        if not report.dry_run:
            _write(statements, counts)


def _write_private(target: Path, data: bytes) -> None:
    tmp = target.with_name(target.name + ".reencrypt-tmp")
    tmp.write_bytes(data)
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, target)


def rotate_photos(report: Report) -> None:
    counts = report.counts("passport_photos (files)")
    directory = passport_photos.PHOTOS_DIR
    if not directory.is_dir():
        return
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name.endswith(".reencrypt-tmp"):
            continue
        if path.name.endswith(passport_photos.ENC_SUFFIX):
            counts.scanned += 1
            token = path.read_bytes()
            if db.token_is_current(token):
                counts.current += 1
                continue
            try:
                fresh = db.rotate_token(token)
            except db.DecryptionError:
                counts.unreadable += 1
                continue
            counts.rotated += 1
            if not report.dry_run:
                _write_private(path, fresh)
        elif path.suffix.lower() in passport_photos.ALL_EXTENSIONS:
            counts.scanned += 1
            target = path.with_name(path.name + passport_photos.ENC_SUFFIX)
            counts.encrypted += 1
            if report.dry_run:
                continue
            if not target.exists():
                _write_private(target, db.encrypt_blob(path.read_bytes()))
            path.unlink()


def run(dry_run: bool, batch_size: int = DEFAULT_BATCH, vacuum: bool = True) -> Report:
    report = Report(dry_run=dry_run)
    # Plaintext first, so a field it encrypts is already under the new key and
    # the token pass finds it current.
    for table, columns in db.ENCRYPTED_COLUMNS.items():
        for name, enc in columns.items():
            encrypt_plaintext(table, name, enc, report, batch_size)
    for table, column in token_targets():
        rotate_column(table, column, report, batch_size)
    rotate_outbox(report, batch_size)
    rotate_photos(report)
    blanked = sum(c.encrypted + c.blanked for c in report.targets.values())
    if vacuum and blanked and not dry_run:
        # secure_delete overwrites freed pages, but VACUUM is what makes sure
        # the old plaintext and the old ciphertext are not left in the file.
        db.execute("VACUUM")
    return report


def rollback_new_fields(dry_run: bool, batch_size: int = DEFAULT_BATCH) -> Report:
    """Decrypt the WP16 fields back into their plaintext columns and clear *_enc."""
    report = Report(dry_run=dry_run)
    for table, name, enc in WP16_FIELDS:
        counts = report.counts(f"{table}.{name}")
        sql = (
            f"SELECT id, {enc} AS token FROM {table} "
            f"WHERE {enc} IS NOT NULL AND id > ? ORDER BY id LIMIT ?"
        )
        for rows in _batches(sql, batch_size):
            statements = []
            for row in rows:
                counts.scanned += 1
                try:
                    plain = db.decrypt_field(row["token"])
                except db.DecryptionError:
                    counts.unreadable += 1
                    continue
                counts.restored += 1
                statements.append((
                    f"UPDATE {table} SET {name} = ?, {enc} = NULL WHERE id = ? AND {enc} = ?",
                    (plain, row["id"], row["token"]),
                    "restored",
                ))
            if not dry_run:
                _write(statements, counts)
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-encrypt stored data under the first key in UBYHOST_DATA_KEYS."
    )
    parser.add_argument("--backup", help="path of a backup taken just before this run")
    parser.add_argument("--dry-run", action="store_true", help="count, write nothing")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero while anything is not under the current key or still plaintext",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument(
        "--max-backup-age-hours", type=float, default=DEFAULT_MAX_BACKUP_AGE_HOURS
    )
    parser.add_argument("--no-vacuum", action="store_true", help="skip the final VACUUM")
    parser.add_argument(
        "--rollback-new-fields",
        action="store_true",
        help="move the WP16 fields back to plaintext, before deploying an older release",
    )
    args = parser.parse_args(argv)
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")

    read_only = args.dry_run or args.check
    if not read_only:
        check_backup(args.backup, args.max_backup_age_hours)
    require_keys(writing=not read_only and not args.rollback_new_fields)
    open_database()

    if args.rollback_new_fields:
        report = rollback_new_fields(dry_run=read_only, batch_size=args.batch_size)
    else:
        report = run(
            dry_run=read_only, batch_size=args.batch_size, vacuum=not args.no_vacuum
        )
    for line in report.lines():
        print(line)
    if read_only:
        print("Dry run: nothing was written.")
    if report.unreadable:
        print(f"{report.unreadable} value(s) could not be decrypted with any configured key.")
        return 2
    if args.check and report.pending:
        print(f"{report.pending} value(s) still need re-encryption.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
