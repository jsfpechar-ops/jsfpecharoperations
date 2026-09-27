"""Prove backup_data.sh snapshots SQLite, encrypts in production, retains by time.

Encryption uses `age`. Tests that need it skip when `age`/`age-keygen` are not
on PATH. The development path stays plaintext so local work keeps working; the
production path must never leave a readable database or key behind.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_data.sh"
AGE = shutil.which("age")
AGE_KEYGEN = shutil.which("age-keygen")


def _require_age() -> None:
    if not AGE or not AGE_KEYGEN:
        pytest.skip("age/age-keygen not on PATH")


def _seed_db(data_dir: Path, note: str = "live-row") -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "ubyhost.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO marker (note) VALUES (?)", (note,))
    conn.commit()
    conn.close()
    (data_dir / "secret_key").write_text("k" * 48)


def _run_backup(
    data_dir: Path, extra_env: dict[str, str] | None = None, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["UBYHOST_DATA_DIR"] = str(data_dir)
    env["UBYHOST_DB"] = str(data_dir / "ubyhost.db")
    env["UBYHOST_BACKUP_DIR"] = str(data_dir / "backups")
    for key in ("UBYHOST_DEPLOYMENT", "UBYHOST_BACKUP_AGE_RECIPIENT",
                "UBYHOST_BACKUP_RETENTION_DAYS"):
        env.pop(key, None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


def _keypair(tmp_path: Path) -> tuple[Path, str]:
    _require_age()
    identity = tmp_path / "age-identity.txt"
    proc = subprocess.run(
        [AGE_KEYGEN, "-o", str(identity)], capture_output=True, text=True, check=True
    )
    match = re.search(r"(age1[0-9a-z]{20,})", proc.stderr)
    assert match, proc.stderr
    return identity, match.group(1)


def _snapshot_dirs(backup_root: Path) -> list[str]:
    return sorted(path.name for path in backup_root.iterdir() if path.is_dir())


def test_backup_uses_sqlite_snapshot_and_retains_by_days(tmp_path: Path):
    data_dir = tmp_path / "data"
    _seed_db(data_dir)

    backup_root = data_dir / "backups"
    backup_root.mkdir()
    for stamp in ("20200101T000000Z", "20200102T000000Z", "20200103T000000Z"):
        (backup_root / stamp).mkdir()

    result = _run_backup(data_dir, {"UBYHOST_BACKUP_RETENTION_DAYS": "30"})
    assert "Backup written" in result.stdout
    remaining = _snapshot_dirs(backup_root)
    # Time-based, not the old "keep the last 10": the three old folders go.
    assert len(remaining) == 1
    newest = remaining[0]
    snapshot = backup_root / newest / "ubyhost.db"
    assert snapshot.is_file()
    copied = sqlite3.connect(snapshot)
    try:
        assert copied.execute("SELECT note FROM marker").fetchone()[0] == "live-row"
    finally:
        copied.close()
    assert (backup_root / newest / "secret_key").read_text() == "k" * 48
    assert stat.S_IMODE(backup_root.stat().st_mode) & 0o077 == 0


def test_production_backup_is_encrypted_and_keeps_no_plaintext(tmp_path: Path):
    _require_age()
    data_dir = tmp_path / "data"
    _seed_db(data_dir)
    identity, recipient = _keypair(tmp_path)

    _run_backup(
        data_dir,
        {
            "UBYHOST_DEPLOYMENT": "production",
            "UBYHOST_BACKUP_AGE_RECIPIENT": recipient,
        },
    )

    backup_root = data_dir / "backups"
    dest = backup_root / _snapshot_dirs(backup_root)[0]
    assert (dest / "ubyhost-backup.tar.age").is_file()
    for leaked in ("ubyhost.db", "secret_key", "initial_admin_credentials",
                   "ubyhost-backup.tar"):
        assert not (dest / leaked).exists(), leaked

    extract = tmp_path / "out"
    extract.mkdir()
    subprocess.run(
        [AGE, "-d", "-i", str(identity), "-o", str(extract / "b.tar"),
         str(dest / "ubyhost-backup.tar.age")],
        check=True,
    )
    with tarfile.open(extract / "b.tar") as archive:
        archive.extractall(extract, filter="data")
    copied = sqlite3.connect(extract / "ubyhost.db")
    try:
        assert copied.execute("SELECT note FROM marker").fetchone()[0] == "live-row"
    finally:
        copied.close()
    assert (extract / "secret_key").read_text() == "k" * 48

    marker = json.loads((backup_root / ".last_success.json").read_text())
    assert marker["encrypted"] is True
    assert marker["bytes"] > 0
    assert marker["retention_days"] == 30
    assert stat.S_IMODE((backup_root / ".last_success.json").stat().st_mode) == 0o600


def test_production_without_a_recipient_fails_and_leaves_nothing(tmp_path: Path):
    data_dir = tmp_path / "data"
    _seed_db(data_dir)

    result = _run_backup(data_dir, {"UBYHOST_DEPLOYMENT": "production"}, check=False)
    assert result.returncode != 0
    assert "Refusing to write an unencrypted backup" in result.stderr
    assert not (data_dir / "backups").exists()


def test_development_keeps_the_plaintext_layout(tmp_path: Path):
    data_dir = tmp_path / "data"
    _seed_db(data_dir)

    _run_backup(data_dir)
    backup_root = data_dir / "backups"
    dest = backup_root / _snapshot_dirs(backup_root)[0]
    assert (dest / "ubyhost.db").is_file()
    assert not (dest / "ubyhost-backup.tar.age").exists()
    marker = json.loads((backup_root / ".last_success.json").read_text())
    assert marker["encrypted"] is False


def test_a_recipient_encrypts_even_outside_production(tmp_path: Path):
    _require_age()
    data_dir = tmp_path / "data"
    _seed_db(data_dir)
    _identity, recipient = _keypair(tmp_path)

    _run_backup(data_dir, {"UBYHOST_BACKUP_AGE_RECIPIENT": recipient})
    dest = data_dir / "backups" / _snapshot_dirs(data_dir / "backups")[0]
    assert (dest / "ubyhost-backup.tar.age").is_file()
    assert not (dest / "ubyhost.db").exists()
