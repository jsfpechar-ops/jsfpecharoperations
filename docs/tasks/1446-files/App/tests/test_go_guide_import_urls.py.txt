"""The Go copy of guest_guide_import.normalise_url is checked against testdata/guide_import_urls.json; it must not drift."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "guide_import_urls_golden.py"


def test_go_guide_import_urls_match_python():
    result = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
