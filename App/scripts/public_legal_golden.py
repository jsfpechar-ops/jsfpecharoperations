"""Golden pages and the string catalog for go/internal/web/public (brief 1270).

Run from App/:
    .venv/bin/python scripts/public_legal_golden.py          write the files
    .venv/bin/python scripts/public_legal_golden.py --check  exit 1 and name each stale file

It writes:
  go/internal/web/public/catalog.json        strings, cookie table, section ids (embedded by Go)
  go/internal/web/public/testdata/cases.json one entry per case: request, env, expected headers
  go/internal/web/public/testdata/<case>.html the FastAPI page, normalized (see normalize())

Each case renders the page with the FastAPI TestClient against a throwaway
SQLite database. The env of a case is applied by patching app.config with the
values config.py would have read from that env (config_values()), because
config.py reads the environment once at import time.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parent
PKG = REPO / "go" / "internal" / "web" / "public"
TESTDATA = PKG / "testdata"

_TMP = Path(tempfile.mkdtemp(prefix="public-legal-golden-"))
os.environ.pop("UBYHOST_DATABASE_URL", None)
os.environ.update(
    {
        "UBYHOST_DATA_DIR": str(_TMP),
        "UBYHOST_DB": str(_TMP / "golden.db"),
        "UBYHOST_SECRET_KEY": "public-legal-golden-secret-not-real-0123",
        "UBYHOST_ENABLE_SCHEDULER": "0",
        "UBYHOST_BOOTSTRAP_ADMIN": "0",
        "UBYHOST_UBYPORT_ENV": "mock",
        "UBYHOST_MAIL_BACKEND": "console",
    }
)
sys.path.insert(0, str(APP_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from app import config, cookie_inventory, db, host_i18n  # noqa: E402
from app.main import app  # noqa: E402
from app.routes import legal  # noqa: E402

# The catalog keys the Go templates read: every key under these prefixes.
KEY_PREFIXES = (
    "legal.", "terms.", "privacy.", "dpa.", "subprocessors.", "cookies.",
    "privacy_first.line", "landing.nav.", "landing.footer.guestbook",
    "landing.footer.login", "a11y.skip_to_content", "a11y.main_navigation",
    "lang.switch",
)

BASE_ENV = {
    "UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
    "UBYHOST_DEPLOYMENT": "local",
    "UBYHOST_OPERATOR_NAME": "Demo Operator s.r.o.",
    "UBYHOST_OPERATOR_ICO": "12345678",
    "UBYHOST_OPERATOR_DIC": "CZ12345678",
    "UBYHOST_OPERATOR_ADDRESS": "Václavské náměstí 1, 110 00 Praha 1",
    "UBYHOST_OPERATOR_EMAIL": "",
    "UBYHOST_OPERATOR_REGISTRY_URL": "https://or.justice.cz/ias/ui/rejstrik-$firma?ico=12345678&jenPlatne=VSECHNY",
    "UBYHOST_SIGNUP_ENABLED": "0",
    "UBYHOST_META_DATASET_ID": "",
    "UBYHOST_META_ACCESS_TOKEN": "",
    "UBYHOST_WEB_PUSH": "1",
    "POSTHOG_PROJECT_API_KEY": "",
    "POSTHOG_HOST": "https://eu.i.posthog.com",
    "POSTHOG_ASSETS_HOST": "https://eu-assets.i.posthog.com",
    "UBYHOST_LEGAL_EFFECTIVE_DATE": "2026-10-05",
    "UBYHOST_TERMS_VERSION": "1.7",
    "UBYHOST_PRIVACY_VERSION": "1.8",
    "UBYHOST_DPA_VERSION": "1.8",
}
PAGES = ("/legal", "/terms", "/privacy", "/dpa", "/subprocessors")
NO_OPERATOR = {"UBYHOST_OPERATOR_NAME": "", "UBYHOST_OPERATOR_ICO": "", "UBYHOST_OPERATOR_DIC": "",
               "UBYHOST_OPERATOR_ADDRESS": "", "UBYHOST_OPERATOR_REGISTRY_URL": ""}
SIGNUP = {"UBYHOST_SIGNUP_ENABLED": "1"}
META = {"UBYHOST_META_DATASET_ID": "123456", "UBYHOST_META_ACCESS_TOKEN": "golden-token"}
POSTHOG = {"POSTHOG_PROJECT_API_KEY": "phc_golden_key"}


def _cases() -> list[dict]:
    cases = []

    def add(name, path, query="", cookies=None, env=None):
        cases.append({"name": name, "path": path, "query": query,
                      "cookies": cookies or {}, "env": {**BASE_ENV, **(env or {})}})

    for path in PAGES:
        slug = path.strip("/")
        add(f"{slug}-cs", path)
        add(f"{slug}-en", path, query="lang=en")
        add(f"{slug}-posthog", path, env=POSTHOG)
    add("terms-cookie-en", "/terms", cookies={"ubyhost_lang": "en"})
    add("terms-cookie-vi", "/terms", cookies={"ubyhost_lang": "vi"})
    add("terms-query-cs-cookie-en", "/terms", query="lang=cs", cookies={"ubyhost_lang": "en"})
    add("legal-no-dic-email", "/legal", env={"UBYHOST_OPERATOR_DIC": "", "UBYHOST_OPERATOR_EMAIL": "ops@ubyhost.example"})
    add("privacy-placeholders", "/privacy", env=NO_OPERATOR)
    add("privacy-production-empty", "/privacy", env={**NO_OPERATOR, "UBYHOST_DEPLOYMENT": "production"})
    add("privacy-signup", "/privacy", env=SIGNUP)
    add("privacy-signup-meta-en", "/privacy", query="lang=en", env={**SIGNUP, **META})
    add("privacy-meta-without-signup", "/privacy", env=META)
    add("privacy-posthog-en", "/privacy", query="lang=en", env=POSTHOG)
    add("subprocessors-signup", "/subprocessors", env=SIGNUP)
    add("subprocessors-signup-meta", "/subprocessors", env={**SIGNUP, **META})
    add("subprocessors-push-off", "/subprocessors", env={"UBYHOST_WEB_PUSH": "0"})
    add("terms-effective-env", "/terms", query="lang=en",
        env={"UBYHOST_LEGAL_EFFECTIVE_DATE": "2027-01-31", "UBYHOST_TERMS_VERSION": "2.0"})
    add("dpa-http-base", "/dpa", query="lang=en", env={"UBYHOST_PUBLIC_BASE_URL": "http://127.0.0.1:8080/"})
    return cases


def config_values(env: dict) -> dict:
    """What config.py reads from env (config.py lines 299, 360, 369, 447-454, 473-477, 484, 498, 584-585, 603, 609, 618)."""
    return {
        "DEPLOYMENT": env["UBYHOST_DEPLOYMENT"].lower(),
        "WEB_PUSH": env["UBYHOST_WEB_PUSH"].strip().lower() not in ("0", "false", "no"),
        "PUBLIC_BASE_URL": env["UBYHOST_PUBLIC_BASE_URL"].rstrip("/"),
        "OPERATOR_NAME": env["UBYHOST_OPERATOR_NAME"].strip(),
        "OPERATOR_ICO": env["UBYHOST_OPERATOR_ICO"].strip(),
        "OPERATOR_DIC": env["UBYHOST_OPERATOR_DIC"].strip(),
        "OPERATOR_ADDRESS": env["UBYHOST_OPERATOR_ADDRESS"].strip(),
        "OPERATOR_EMAIL": env["UBYHOST_OPERATOR_EMAIL"].strip() or "support@ubyhost.com",
        "OPERATOR_REGISTRY_URL": env["UBYHOST_OPERATOR_REGISTRY_URL"].strip(),
        "POSTHOG_PROJECT_API_KEY": env["POSTHOG_PROJECT_API_KEY"].strip(),
        "POSTHOG_HOST": env["POSTHOG_HOST"].strip().rstrip("/"),
        "POSTHOG_ASSETS_HOST": env["POSTHOG_ASSETS_HOST"].strip().rstrip("/"),
        "TERMS_VERSION": env["UBYHOST_TERMS_VERSION"],
        "PRIVACY_VERSION": env["UBYHOST_PRIVACY_VERSION"],
        "DPA_VERSION": env["UBYHOST_DPA_VERSION"],
        "SIGNUP_ENABLED": env["UBYHOST_SIGNUP_ENABLED"].lower() in ("1", "true", "yes"),
        "META_DATASET_ID": env["UBYHOST_META_DATASET_ID"].strip(),
        "META_ACCESS_TOKEN": env["UBYHOST_META_ACCESS_TOKEN"].strip(),
        "LEGAL_EFFECTIVE_DATE": date.fromisoformat(env["UBYHOST_LEGAL_EFFECTIVE_DATE"].strip() or "2026-10-05"),
    }


_SPACE = re.compile(r"[ \t\n\r\f\v]+")


def normalize(html: str) -> str:
    """ASCII whitespace runs become one space, a space between two tags goes, ends trimmed.

    The Go test applies the same three rules (normalize in public_test.go).
    Non-breaking spaces in the copy are not whitespace here, so they must match.
    """
    return _SPACE.sub(" ", html).replace("> <", "><").strip()


def _cookie(header: str) -> dict:
    """One Set-Cookie header as comparable fields (attribute order and case differ between stacks)."""
    parts = [p.strip() for p in header.split(";")]
    name, _, value = parts[0].partition("=")
    out = {"name": name, "value": value, "path": "", "max_age": "", "samesite": "", "secure": False, "httponly": False}
    for attr in parts[1:]:
        key, _, val = attr.partition("=")
        key = key.strip().lower()
        if key == "path":
            out["path"] = val
        elif key == "max-age":
            out["max_age"] = val
        elif key == "samesite":
            out["samesite"] = val.lower()
        elif key == "secure":
            out["secure"] = True
        elif key == "httponly":
            out["httponly"] = True
    return out


def render_case(case: dict) -> tuple[dict, str]:
    url = case["path"] + (f"?{case['query']}" if case["query"] else "")
    with mock.patch.multiple(config, **config_values(case["env"])):
        client = TestClient(app, cookies=case["cookies"])
        response = client.get(url)
    cookies = [_cookie(h) for h in response.headers.get_list("set-cookie")]
    expected = {
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "cache_control": response.headers.get("cache-control", ""),
        "csp": response.headers.get("content-security-policy", ""),
        # The anonymous CSRF cookie is not ported: no public legal page has a form.
        "set_cookies": [c for c in cookies if c["name"] == host_i18n.LANG_COOKIE],
    }
    return {**case, "expected": expected}, normalize(response.text) + "\n"


def catalog() -> str:
    strings = {
        lang: {k: v for k, v in sorted(host_i18n.STRINGS[lang].items()) if k.startswith(KEY_PREFIXES)}
        for lang in host_i18n.PUBLIC_LANGUAGES
    }
    data = {
        "strings": strings,
        "terms_sections": list(legal.TERMS_SECTION_IDS),
        "privacy_sections": list(legal.PRIVACY_SECTION_IDS),
        "dpa_sections": list(legal.DPA_SECTION_IDS),
        "subprocessor_ids": list(legal.SUBPROCESSOR_IDS),
        "recipient_ids": list(legal.RECIPIENT_IDS),
        "cookie_inventory": [
            {"name": r["name"], "party": r["party"], "purpose": r["purpose"], "lifetime": r["lifetime"]}
            for r in cookie_inventory.COOKIE_INVENTORY
        ],
        "cookieless_services": [
            {"name": s["name"], "party": s["party"], "note": s["note"]}
            for s in cookie_inventory.COOKIELESS_SERVICES
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    db.init_db()
    files = {PKG / "catalog.json": catalog()}
    cases = []
    for case in _cases():
        entry, html = render_case(case)
        cases.append(entry)
        files[TESTDATA / f"{case['name']}.html"] = html
    files[TESTDATA / "cases.json"] = json.dumps(cases, ensure_ascii=False, indent=1) + "\n"
    return files


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    for path, text in outputs().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        if check:
            stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO)}")
    for path in stale:
        print(f"stale: {path.relative_to(REPO)}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
