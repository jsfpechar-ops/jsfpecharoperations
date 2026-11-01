"""The Go host string catalogs are generated from host_i18n and must not drift."""
import subprocess
import sys
from pathlib import Path

from app import host_i18n

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "go_host_i18n.py"
FIXTURE = {"plain": "Hi", "named": "Hello %(name)s"}


def test_go_catalogs_match_host_i18n():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_lookup_cases_match_go_hostweb_catalog_test():
    # The same three cases as TestCatalogCases in go/internal/hostweb.
    assert host_i18n.lookup(FIXTURE, {}, "plain") == "Hi"
    assert host_i18n.lookup(FIXTURE, {}, "named", name="Ana") == "Hello Ana"
    assert host_i18n.lookup(FIXTURE, {}, "missing") == "missing"
