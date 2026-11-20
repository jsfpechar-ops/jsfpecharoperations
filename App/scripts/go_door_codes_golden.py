"""Brief 1771: regenerate door-code job goldens (mail builders + testdata)."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
REPO = APP.parent
SCRIPTS = (
    "go_mailnotify_doorcode_golden.py",
    "go_mailnotify_fee_golden.py",
    "go_mailnotify_golden.py",
    "go_mailnotify_completion_golden.py",
)
OUTPUTS = (
    REPO / "go/internal/mailnotify/testdata/door_code_golden.json",
    REPO / "go/internal/mailnotify/testdata/fee_update_golden.json",
    REPO / "go/internal/mailnotify/testdata/reminders_golden.json",
    REPO / "go/internal/mailnotify/testdata/completion_golden.json",
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    check = "--check" in sys.argv
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    before = {p: _sha(p) for p in OUTPUTS if p.is_file()}
    for name in SCRIPTS:
        proc = subprocess.run(
            [sys.executable, str(APP / "scripts" / name)],
            cwd=APP,
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            sys.stderr.write((proc.stdout + proc.stderr)[-2000:])
            raise SystemExit(proc.returncode)
    after = {p: _sha(p) for p in OUTPUTS}
    if check and before != after:
        raise SystemExit("go_door_codes golden outputs changed; commit refreshed JSON")
    print("door_codes goldens OK", len(OUTPUTS), "files")


if __name__ == "__main__":
    main()
