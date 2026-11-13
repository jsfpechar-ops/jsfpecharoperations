"""go/internal/hostweb/layout/layout_test.go compares the Go host layout with
the Python one through go/internal/hostweb/layout/testdata/ (brief 1380).
A change to base.html, host_page.html, a shell include or a ported macro makes
these files stale: rerun scripts/go_layout_golden.py and port the change to Go."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "go_layout_golden.py"


def test_go_layout_golden_files_are_current():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
