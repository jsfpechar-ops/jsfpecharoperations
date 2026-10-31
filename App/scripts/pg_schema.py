#!/usr/bin/env python3
"""Inspect or explicitly apply the PostgreSQL schema; never migrate at app startup."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402


def _record_backup_receipt(raw: str, stanza: str, database: str) -> dict:
    """Validate pgBackRest info JSON and atomically publish a secret-free receipt."""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("pgBackRest info JSON is invalid.") from exc
    if not isinstance(payload, list):
        raise RuntimeError("pgBackRest info JSON has an unsupported shape.")
    matches = [item for item in payload if isinstance(item, dict) and item.get("name") == stanza]
    if len(matches) != 1:
        raise RuntimeError("pgBackRest info does not contain exactly the requested stanza.")
    item = matches[0]
    if not _status_ok(item.get("status")):
        raise RuntimeError("pgBackRest stanza status is not successful.")
    backups = []
    for repo in item.get("repo", []):
        if not isinstance(repo, dict) or not _status_ok(repo.get("status")):
            raise RuntimeError("pgBackRest repository status is not successful.")
        for backup in repo.get("backup", []):
            if not isinstance(backup, dict):
                continue
            stamp = backup.get("timestamp") or {}
            start, stop = stamp.get("start"), stamp.get("stop")
            if isinstance(start, (int, float)) and isinstance(stop, (int, float)) and stop > 0:
                backups.append((float(stop), backup))
    if not backups:
        raise RuntimeError("pgBackRest info contains no completed backup.")
    _stop, latest = max(backups, key=lambda pair: pair[0])
    label = latest.get("label")
    kind = latest.get("type")
    if not isinstance(label, str) or not label or kind not in {"full", "diff", "incr"}:
        raise RuntimeError("latest pgBackRest backup record is incomplete.")
    stamp = latest["timestamp"]
    start = datetime.fromtimestamp(stamp["start"], timezone.utc)
    stop = datetime.fromtimestamp(stamp["stop"], timezone.utc)
    verified = datetime.now(timezone.utc)
    receipt = {
        "format_version": 1,
        "database": database,
        "target_fingerprint": config._database_target_fingerprint(config.DATABASE_URL),
        "stanza": stanza,
        "backup_label": label,
        "backup_type": kind,
        "started_at_utc": start.isoformat(timespec="seconds"),
        "stopped_at_utc": stop.isoformat(timespec="seconds"),
        "verified_at_utc": verified.isoformat(timespec="seconds"),
        "backup_ok": True,
        "check_ok": True,
        "info_ok": True,
    }
    output = config.DATA_DIR / "backups" / "postgresql" / "latest-verified.json"
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        output.parent.chmod(0o700)
    except OSError:
        pass
    if output.is_symlink():
        raise RuntimeError("PostgreSQL backup receipt path must not be a symlink.")
    fd, temp_name = tempfile.mkstemp(dir=output.parent, prefix=".latest-verified.", suffix=".tmp")
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(receipt, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, output)
        try:
            descriptor = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            raise RuntimeError("Backup receipt was published but directory durability failed.") from None
    finally:
        temp.unlink(missing_ok=True)
    return receipt


def _status_ok(status) -> bool:
    return isinstance(status, dict) and status.get("code") == 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "check", "apply", "seal-authority", "record-backup"))
    parser.add_argument("--expect-database", required=True)
    parser.add_argument("--stanza")
    args = parser.parse_args(argv)
    try:
        if config.DB_BACKEND != "postgresql":
            raise RuntimeError("Set UBYHOST_DATABASE_URL to select PostgreSQL.")
        actual = db.current_database_name()
        marker_path = config.DATABASE_AUTHORITY_FILE
        if marker_path.exists():
            marker = __import__("json").loads(marker_path.read_text(encoding="utf-8"))
            if marker.get("database") != actual or marker.get("schema") != "public":
                raise RuntimeError("Connected PostgreSQL target does not match the durable authority marker.")
        if actual != args.expect_database:
            raise RuntimeError("Connected database does not match --expect-database.")
        if args.action == "plan":
            print(f"PostgreSQL {actual}: schema version {db.expected_schema_version()} is planned; no changes made.")
            return 0
        if args.action == "seal-authority":
            marker = config.seal_database_authority(args.expect_database)
            print(f"PostgreSQL authority sealed for database={actual}; marker_format={marker['format_version']}.")
            return 0
        if args.action == "record-backup":
            if not args.stanza:
                raise RuntimeError("record-backup requires --stanza.")
            raw = sys.stdin.read(1_000_001)
            if len(raw) > 1_000_000:
                raise RuntimeError("pgBackRest info input exceeds the supported size.")
            receipt = _record_backup_receipt(raw, args.stanza, actual)
            print(
                f"Verified PostgreSQL backup receipt written: database={actual}, "
                f"stanza={receipt['stanza']}, label={receipt['backup_label']}."
            )
            return 0
        if args.action == "apply":
            status = db.apply_postgresql_schema()
        else:
            status = db.postgres_schema_status()
            if not status["current"]:
                raise RuntimeError("PostgreSQL schema is not current; run the explicit apply command.")
        print(
            f"PostgreSQL schema {args.action} OK: database={actual}, "
            f"version={status['actual_version']}, tables={status['actual_tables']}."
        )
        return 0
    except Exception as exc:
        print(f"PostgreSQL schema {args.action} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
