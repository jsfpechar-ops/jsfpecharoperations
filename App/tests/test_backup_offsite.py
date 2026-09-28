"""backup-s3.sh copies only encrypted archives and refuses a plaintext snapshot.

The script is exercised with a fake `rclone` and a fake `docker` on PATH, so the
test is about the arguments it builds and the guard it applies, not about the
network or a real Docker host.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
S3_SCRIPT = REPO_ROOT / "deploy" / "lightsail" / "scripts" / "backup-s3.sh"

FAKE_DOCKER = """#!/usr/bin/env bash
set -u
if printf '%s' "$*" | grep -q '\\*\\.age'; then
  [ "${FAKE_HAS_AGE:-1}" = "1" ]
  exit $?
fi
if [ "${1:-}" = "compose" ]; then
  printf '%s\\n' "${FAKE_STAMP:-20260928T030000Z}"
  exit 0
fi
if [ "${1:-}" = "cp" ]; then
  dest="${!#}"
  rm -rf "${dest}"
  mkdir -p "${dest}"
  : > "${dest}/ubyhost-backup.tar.age"
  exit 0
fi
exit 0
"""

FAKE_RCLONE = """#!/usr/bin/env bash
set -u
printf '%s\\n' "$*" >> "${FAKE_RCLONE_LOG}"
if [ "${1:-}" = "listremotes" ]; then
  printf '%s:\\n' "${FAKE_RCLONE_REMOTE:-s3}"
fi
exit 0
"""

FAKE_LIB_DOCKER = """#!/usr/bin/env bash
ubyhost_container_ref() { printf 'fakecontainer\\n'; }
"""

FAKE_BACKUP = "#!/usr/bin/env bash\nexit 0\n"


def _write_exec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run(tmp_path: Path, *, has_age: bool) -> subprocess.CompletedProcess[str]:
    root = tmp_path / "root"
    scripts = root / "scripts"
    bin_dir = tmp_path / "bin"
    scripts.mkdir(parents=True)
    bin_dir.mkdir()
    shutil.copy(S3_SCRIPT, scripts / "backup-s3.sh")
    _write_exec(scripts / "backup.sh", FAKE_BACKUP)
    _write_exec(scripts / "lib-docker.sh", FAKE_LIB_DOCKER)
    _write_exec(bin_dir / "docker", FAKE_DOCKER)
    _write_exec(bin_dir / "rclone", FAKE_RCLONE)
    (root / ".env").write_text("UBYHOST_S3_BUCKET=test-bucket\n", encoding="utf-8")

    log = tmp_path / "rclone.log"
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["UBYHOST_S3_BUCKET"] = "test-bucket"
    env["FAKE_RCLONE_LOG"] = str(log)
    env["FAKE_HAS_AGE"] = "1" if has_age else "0"
    return subprocess.run(
        ["bash", str(scripts / "backup-s3.sh")],
        capture_output=True,
        text=True,
        env=env,
    )


def test_s3_upload_copies_only_age_archives(tmp_path: Path):
    result = _run(tmp_path, has_age=True)
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "rclone.log").read_text(encoding="utf-8")
    assert "copy" in log
    assert "--include *.age" in log


def test_s3_upload_refuses_a_plaintext_snapshot(tmp_path: Path):
    result = _run(tmp_path, has_age=False)
    assert result.returncode != 0
    assert "refusing to upload plaintext" in result.stderr.lower()
    log = (tmp_path / "rclone.log").read_text(encoding="utf-8")
    assert "copy" not in log
