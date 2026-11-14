"""The Go copies of the signed-out auth pages keep Python's asset versions (brief 1502).

go/internal/web/auth/authpage/templates/ ports auth_base.html and the login
pages; testdata/login.json pins the HTML only as it was when it was recorded.
A cache-busting ?v= bump in a Python template must reach the Go copy too, or
the Go page serves stale CSS or JavaScript. Regenerate the golden with
.venv/bin/python scripts/auth_login_golden.py after changing either side.
"""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
PY = APP_DIR / "app" / "templates"
GO = APP_DIR.parent / "go" / "internal" / "web" / "auth" / "authpage" / "templates"
PAIRS = {
    "auth_base.html": "base.html",
    "login.html": "login.html",
    "login_sent.html": "login_sent.html",
    "login_link.html": "login_link.html",
    "two_factor_login.html": "two_factor_login.html",
}
ASSET = re.compile(r"""(?:/static/|https://challenges\.cloudflare\.com/)[^"'\s]+""")


def test_go_auth_pages_use_python_asset_urls():
    for py_name, go_name in PAIRS.items():
        py_assets = sorted(set(ASSET.findall((PY / py_name).read_text(encoding="utf-8"))))
        go_assets = sorted(set(ASSET.findall((GO / go_name).read_text(encoding="utf-8"))))
        assert go_assets == py_assets, f"{go_name} differs from {py_name}"
