"""The Go Quick answers data (guide_facts.json) is generated from guide_facts and i18n and must not drift."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "go_guide_facts_i18n.py"


def test_go_guide_facts_match_python():
    result = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
