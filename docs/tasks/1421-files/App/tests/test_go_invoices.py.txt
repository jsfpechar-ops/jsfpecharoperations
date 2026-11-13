"""go/internal/web/invoices reads i18n.json and testdata/draft_golden.json (briefs 1420, 1421).

The catalog is written by scripts/go_host_i18n.py from i18n_keys.txt; the draft
golden by scripts/invoices_golden.py from the real App/app/invoices.py. Neither
needs a database or a network.
"""

import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT = APP_DIR / "scripts" / "invoices_golden.py"
PKG = APP_DIR.parent / "go" / "internal" / "web" / "invoices"


def test_invoices_catalog_matches_host_strings():
    sys.path.insert(0, str(APP_DIR / "scripts"))
    from go_host_i18n import read_keys, render

    keys = read_keys(PKG / "i18n_keys.txt")
    assert "invoice.issued_flash" in keys
    assert (PKG / "i18n.json").read_text(encoding="utf-8") == render(keys)


def test_invoices_draft_golden_is_current():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], cwd=APP_DIR,
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
