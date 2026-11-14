"""The Go account pages (briefs 1505, 1506) read their texts from go/internal/web/auth/acct_i18n.json.

auth_account_golden.py writes this catalog from acct_i18n_keys.txt; this test
fails when host_i18n changes and the file goes stale.
Regenerate with: .venv/bin/python scripts/auth_account_golden.py
"""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
PKG = APP_DIR.parent / "go" / "internal" / "web" / "auth"
sys.path.insert(0, str(APP_DIR / "scripts"))

import go_host_i18n  # noqa: E402


def test_account_catalog_is_fresh():
    keys = go_host_i18n.read_keys(PKG / "acct_i18n_keys.txt")
    assert keys, "no keys listed"
    assert (PKG / "acct_i18n.json").read_text(encoding="utf-8") == go_host_i18n.render(keys)


def test_every_listed_key_has_english_and_czech():
    """Vietnamese may miss a key: both sides fall back to English."""
    from app import host_i18n

    for key in go_host_i18n.expand(go_host_i18n.read_keys(PKG / "acct_i18n_keys.txt")):
        for lang in ("en", "cs"):
            assert host_i18n.STRINGS[lang].get(key), f"{key} has no {lang} text"
