"""go/internal/hostweb/layout/layout_test.go compares the Go host layout with
the Python one through go/internal/hostweb/layout/testdata/ (brief 1380).
A change to base.html, host_page.html, a shell include or a ported macro makes
these files stale: rerun scripts/go_layout_golden.py and port the change to Go.
Go-first string overrides in go/internal/hostweb/i18n_go_overrides.json are
overlaid onto host_i18n.STRINGS before checking so Go copy can advance without
editing retired Python catalogs."""
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = APP_DIR / "scripts"
OVERRIDES = APP_DIR.parent / "go" / "internal" / "hostweb" / "i18n_go_overrides.json"

_RUNNER = (
    "import json, sys; from pathlib import Path; "
    f"sys.path.insert(0, {str(SCRIPT_DIR)!r}); "
    "import go_layout_golden as g; g.setup(); "
    "from app import host_i18n; "
    f"ov = Path({str(OVERRIDES)!r}); "
    "ov.exists() and [host_i18n.STRINGS.setdefault(l, {}).update(t) for l, t in json.loads(ov.read_text(encoding='utf-8')).items()]; "
    "sys.exit(g.main(['--check']))"
)


def test_go_layout_golden_files_are_current():
    result = subprocess.run(
        [sys.executable, "-c", _RUNNER], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
