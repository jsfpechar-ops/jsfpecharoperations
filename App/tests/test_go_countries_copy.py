"""The Go service keeps a copy of the country list, because go:embed cannot
reach App/. If this fails, re-copy the file:

    cp App/app/data/countries.json go/internal/countries/countries.json
"""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent


def test_go_countries_copy_is_byte_identical():
    source = (APP_DIR / "app" / "data" / "countries.json").read_bytes()
    copy = (REPO_DIR / "go" / "internal" / "countries" / "countries.json").read_bytes()
    assert copy == source, (
        "go/internal/countries/countries.json differs from App/app/data/countries.json. "
        "Re-copy it: cp App/app/data/countries.json go/internal/countries/countries.json"
    )
