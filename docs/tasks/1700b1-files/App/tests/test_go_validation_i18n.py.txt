"""The Go port of validation_i18n.localize reads tables generated from Python; they must not drift."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "go_validation_i18n.py"


def test_go_validation_i18n_match_python():
    result = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
