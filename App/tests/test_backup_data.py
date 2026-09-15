"""Prove backup_data.sh snapshots SQLite and retains the last 10 folders."""
from __future__ import annotations

import os
import sqlite3
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_data.sh"


def _run_backup(data_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["UBYHOST_DATA_DIR"] = str(data_dir)
    env["UBYHOST_DB"] = str(data_dir / "ubyhost.db")
    env["UBYHOST_BACKUP_DIR"] = str(data_dir / "backups")
    return subprocess.run(
        ["bash", str(SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def test_backup_uses_sqlite_snapshot_and_keeps_last_ten(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "ubyhost.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO marker (note) VALUES ('live-row')")
    conn.commit()
    conn.close()
    (data_dir / "secret_key").write_text("k" * 48)

    backup_root = data_dir / "backups"
    backup_root.mkdir()
    for index in range(11):
        (backup_root / f"2020010{index:02d}T000000Z").mkdir()

    result = _run_backup(data_dir)
    assert "Backup written" in result.stdout
    remaining = sorted(path.name for path in backup_root.iterdir() if path.is_dir())
    assert len(remaining) == 10
    newest = max(remaining)
    snapshot = backup_root / newest / "ubyhost.db"
    assert snapshot.is_file()
    copied = sqlite3.connect(snapshot)
    try:
        note = copied.execute("SELECT note FROM marker").fetchone()[0]
    finally:
        copied.close()
    assert note == "live-row"
    assert (backup_root / newest / "secret_key").read_text() == "k" * 48
    mode = stat.S_IMODE(backup_root.stat().st_mode)
    assert mode & 0o077 == 0
