"""Golden pages and the string catalog for the marketing pages in go/internal/web/public (brief 1620).

Pages: /jak-to-funguje (product.html), /cenik (pricing.html), /pruvodce/{slug} (public_guide.html).

Run from App/:
    .venv/bin/python scripts/public_pages_golden.py          write the files
    .venv/bin/python scripts/public_pages_golden.py --check  exit 1 and name each stale file

It writes:
  go/internal/web/public/catalog_pages.json            strings, guides, rates, icons (embedded by Go)
  go/internal/web/public/testdata/pages/cases.json     one entry per case: request, env, expected headers
  go/internal/web/public/testdata/pages/<case>.html    the FastAPI page, normalized

It reuses the case runner of public_legal_golden.py (same throwaway SQLite database,
same config patching, same normalize()).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import public_legal_golden as base  # noqa: E402  (sets the env, imports the app)

from app import db, host_i18n, templating  # noqa: E402
from app.public_guides import GUIDE_TRANSLATIONS  # noqa: E402
from app.routes import legal  # noqa: E402

REPO, PKG = base.REPO, base.PKG
TESTDATA = PKG / "testdata" / "pages"

# Every key the three pages and their header and footer read, under these prefixes.
KEY_PREFIXES = (
    "product.", "pricing.", "landing.", "privacy_first.", "guide.",
    "a11y.skip_to_content", "a11y.main_navigation", "lang.switch",
    "legal.footer_nav_label", "legal.footer_short", "terms.footer_short",
    "privacy.footer_short", "dpa.footer_short", "subprocessors.footer_short",
)
POSTHOG = base.POSTHOG
SIGNUP = base.SIGNUP
GUIDES = ("hlaseni-cizincu-ubyport", "online-ubytovaci-kniha")


def _cases() -> list[dict]:
    cases = []

    def add(name, path, query="", cookies=None, env=None):
        cases.append({"name": name, "path": path, "query": query,
                      "cookies": cookies or {}, "env": {**base.BASE_ENV, **(env or {})}})

    for page, path in (("product", "/jak-to-funguje"), ("pricing", "/cenik")):
        add(f"{page}-cs", path)
        add(f"{page}-en", path, query="lang=en")
        add(f"{page}-posthog", path, env=POSTHOG)
        add(f"{page}-cookie-en", path, cookies={"ubyhost_lang": "en"})
        add(f"{page}-cookie-vi", path, cookies={"ubyhost_lang": "vi"})
        add(f"{page}-query-cs-cookie-en", path, query="lang=cs", cookies={"ubyhost_lang": "en"})
    add("product-http-base", "/jak-to-funguje", query="lang=en", env={"UBYHOST_PUBLIC_BASE_URL": "http://127.0.0.1:8080/"})
    add("pricing-signup", "/cenik", env=SIGNUP)
    add("pricing-signup-cookie-vi", "/cenik", cookies={"ubyhost_lang": "vi"}, env=SIGNUP)
    add("pricing-signup-utm-en", "/cenik",
        query="lang=en&utm_source=google&utm_medium=cpc&utm_campaign=spring&plan=max&interval=month&apts=3&ttlock=1&click=garbage&x=1",
        env=SIGNUP)
    add("pricing-signup-posthog", "/cenik", env={**SIGNUP, **POSTHOG})
    for slug in GUIDES:
        add(f"guide-{slug}-cs", f"/pruvodce/{slug}")
        add(f"guide-{slug}-en", f"/pruvodce/{slug}", query="lang=en")
        add(f"guide-{slug}-posthog", f"/pruvodce/{slug}", env=POSTHOG)
        add(f"guide-{slug}-cookie-en", f"/pruvodce/{slug}", cookies={"ubyhost_lang": "en"})
    add("guide-http-base", "/pruvodce/hlaseni-cizincu-ubyport", query="lang=en",
        env={"UBYHOST_PUBLIC_BASE_URL": "http://127.0.0.1:8080/"})
    add("guide-unknown-slug", "/pruvodce/no-such-guide")
    add("guide-unknown-slug-en", "/pruvodce/no-such-guide", query="lang=en")
    return cases


def _icon(name: str) -> str:
    env = templating.templates.env
    return str(env.from_string("{% from '_icons.html' import icon %}{{ icon('" + name + "', 14) }}").render())


def catalog() -> str:
    strings = {
        lang: {k: v for k, v in sorted(host_i18n.STRINGS[lang].items()) if k.startswith(KEY_PREFIXES)}
        for lang in host_i18n.PUBLIC_LANGUAGES
    }
    guides = {
        lang: {"order": list(items), "items": items}
        for lang, items in GUIDE_TRANSLATIONS.items()
    }
    data = {
        "strings": strings,
        "guides": guides,
        "rates": legal.PUBLIC_RATES,
        "icons": {"check": _icon("check"), "external-link": _icon("external-link")},
    }
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def render_case(case: dict) -> tuple[dict, str]:
    # og:image reads the template global public_base_url, which templating.py
    # fixed at import time; patch it with the case's base URL like config.
    globals_ = {"public_base_url": base.config_values(case["env"])["PUBLIC_BASE_URL"]}
    with mock.patch.dict(templating.templates.env.globals, globals_):
        entry, html = base.render_case(case)
    if entry["expected"]["status"] != 200:
        entry["expected"]["body"] = html.strip()
    return entry, html


def outputs() -> dict[Path, str]:
    db.init_db()
    files = {PKG / "catalog_pages.json": catalog()}
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
