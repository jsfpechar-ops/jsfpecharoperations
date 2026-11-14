"""Golden pages and the string catalog for the Go sign-up pages (brief 1507).

Pages: GET/POST /signup (signup.html, signup_sent.html) and GET/POST
/signup/verify (signup_verify.html), all on the auth_base.html shell.

Run from App/:
    .venv/bin/python scripts/signup_pages_golden.py          write the files
    .venv/bin/python scripts/signup_pages_golden.py --check  exit 1 and name each stale file

It writes:
  go/internal/web/auth/signup_catalog.json          strings and the check icon (embedded by Go)
  go/internal/web/auth/testdata/signup/cases.json   one entry per case: request, env, Python's answer
  go/internal/web/auth/testdata/signup/<case>.html  the FastAPI page, normalized, CSRF token masked

Each case runs the real route with the FastAPI TestClient on the throwaway
SQLite database of public_legal_golden.py. The context the route hands to
render() and the keyword arguments it hands to signup.register() are recorded,
so the Go test can check its own context and its RegisterInput against them.
Only the parts that need a database or the network are replaced: the
Turnstile answer, the rate-limit answers, register(), pending_account(),
activate(), and the clock of the click value.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from unittest import mock
from urllib.parse import urlencode

import public_legal_golden as base  # noqa: E402  (sets the env, imports the app)

from itsdangerous import URLSafeTimedSerializer  # noqa: E402

from app import auth, config, db, host_i18n, login_link, security, signup, templating, turnstile  # noqa: E402
from app.main import app  # noqa: E402
from app.routes import signup as signup_routes  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

logging.disable(logging.INFO)  # the access log of every case would drown the output

REPO = base.REPO
PKG = REPO / "go" / "internal" / "web" / "auth"
TESTDATA = PKG / "testdata" / "signup"

SECRET = "public-legal-golden-secret-not-real-0123"  # set by public_legal_golden
NONCE = "signup-golden-csrf-nonce"
NOW_MS = 1798761600000  # 2027-01-01T00:00:00Z, the clock of the click values
SITE_KEY = "0x4AAAAAAE0LDM2eoIjssN00"

# The keys the four templates read: every signup.* key plus the shell's.
KEY_PREFIXES = ("signup.",)
SHELL_KEYS = (
    "a11y.skip_to_content", "lang.en", "lang.cs", "lang.vi",
    "env.mock_title", "env.mock_body", "env.mock_production_title", "env.mock_production_body", "how.toggle",
    "auth.notice.2fa_expired", "auth.notice.form_expired", "auth.notice.logged_out", "auth.notice.email_changed",
    "auth.not_you", "legal.footer_link", "terms.footer_link", "privacy.footer_link", "dpa.footer_link",
    "login.hero_title", "login.hero_body", "landing.demo.scene.calendar", "landing.demo.scene.form",
    "landing.demo.scene.receipt", "landing.demo.queue.ready",
)

ENV = {
    **base.BASE_ENV,
    "UBYHOST_SECRET_KEY": SECRET,
    "UBYHOST_SIGNUP_ENABLED": "1",
    "UBYHOST_UBYPORT_ENV": "mock",
    "UBYHOST_OPERATOR_EMAIL": "ops@ubyhost.example",
    "TURNSTILE_SITE_KEY": SITE_KEY,
    "TURNSTILE_SECRET": "",
    "TURNSTILE_HOSTNAMES": "",
}
META = {"UBYHOST_META_DATASET_ID": "123456", "UBYHOST_META_ACCESS_TOKEN": "golden-token"}
TURNSTILE_ON = {"TURNSTILE_SECRET": "golden-turnstile-secret", "TURNSTILE_HOSTNAMES": "ubyhost.example"}
CSRF_TOKEN = URLSafeTimedSerializer(SECRET, salt="ubyhost-csrf").dumps({"nonce": security._nonce_binding(NONCE)})

_CSRF_VALUE = re.compile(r'(name="_csrf" value=")[^"]*(")|(name="csrf-token" content=")[^"]*(")')


def mask(html: str) -> str:
    """The CSRF token is new on every request; the Go test masks it the same way."""
    return _CSRF_VALUE.sub(lambda m: (m.group(1) or m.group(3)) + "CSRF" + (m.group(2) or m.group(4)), html)


def _click(ids: dict) -> str:
    return signup.issue_click(ids, seen_ms=NOW_MS - 60_000)


GCLID = "Cj0KCQ-golden_gclid"
FBCLID = "IwAR-golden_fbclid"


def _cases() -> list[dict]:
    both = _click({"gclid": GCLID, "fbclid": FBCLID})
    google = _click({"gclid": GCLID})
    ok_form = [("email", " Anna.Nova+airbnb@Example.CZ "), ("accept", "1")]
    cases = []

    def add(name, method, path, query="", form=None, cookies=None, env=None, signed_in=False, patch=None):
        cases.append({
            "name": name, "method": method, "path": path, "query": query, "form": form or [],
            "cookies": cookies or {}, "env": {**ENV, **(env or {})}, "signed_in": signed_in,
            "patch": patch or {},
        })

    G, P = "GET", "POST"
    # GET /signup
    add("form-cs", G, "/signup")
    add("form-en", G, "/signup", query="lang=en")
    add("form-cookie-vi", G, "/signup", cookies={"ubyhost_lang": "vi"})
    add("form-query-cs-cookie-en", G, "/signup", query="lang=cs", cookies={"ubyhost_lang": "en"})
    add("form-off", G, "/signup", env={"UBYHOST_SIGNUP_ENABLED": "0"})
    add("form-signed-in", G, "/signup", signed_in=True)
    add("form-turnstile", G, "/signup", query="lang=en", env=TURNSTILE_ON)
    add("form-production", G, "/signup", env={"UBYHOST_DEPLOYMENT": "production"})
    add("form-live-ubyport", G, "/signup", env={"UBYHOST_UBYPORT_ENV": "production"})
    add("form-notice", G, "/signup", query="notice=logged_out&lang=en")
    add("form-utm-selection", G, "/signup",
        query="lang=en&utm_source=google&utm_medium=cpc+ads&utm_campaign=spring_2027&plan=max&interval=year"
              "&apts=3&ttlock=1&x=1&utm_source=bad%3Cvalue")
    add("form-gclid-mint", G, "/signup", query=f"gclid={GCLID}&utm_source=google")
    add("form-gclid-fbclid-meta", G, "/signup", query=f"lang=en&gclid={GCLID}&fbclid={FBCLID}", env=META)
    add("form-fbclid-no-meta", G, "/signup", query=f"fbclid={FBCLID}")
    add("form-click-kept", G, "/signup", query="click=" + google + "&apartments=12")
    add("form-click-bad", G, "/signup", query="click=forged.value&apartments=51")
    # POST /signup
    add("submit-ok", P, "/signup", form=ok_form + [("workspace", "  Chata   u lesa ")],
        patch={"register": True})
    add("submit-ok-derived-workspace", P, "/signup", query="lang=en",
        form=ok_form + [("marketing_opt_in", "1"), ("utm_source", "google"), ("plan", "standard"), ("apts", "4")],
        patch={"register": True})
    add("submit-ok-consents", P, "/signup",
        form=ok_form + [("click", both), ("ads_consent", "1"), ("meta_consent", "0"), ("interval", "month")],
        env=META, patch={"register": True})
    add("submit-ok-cookie-vi", P, "/signup", form=[("email", "x@example.cz"), ("accept", "1")],
        cookies={"ubyhost_lang": "vi"}, patch={"register": True})
    add("submit-turnstile", P, "/signup", form=ok_form + [("workspace", "Vila")], patch={"turnstile": False})
    add("submit-rate-limited", P, "/signup", form=ok_form, patch={"rate_limited": True})
    add("submit-bad-email", P, "/signup", form=[("email", "not an <email>"), ("accept", "1")])
    add("submit-long-email", P, "/signup", form=[("email", "ž" * 250 + "@example.cz"), ("accept", "1")])
    add("submit-empty-email-en", P, "/signup", query="lang=en", form=[("accept", "1")])
    add("submit-long-workspace", P, "/signup", form=[("email", "a@example.cz"), ("workspace", "x" * 121), ("accept", "1")])
    add("submit-no-accept", P, "/signup",
        form=[("email", "a@example.cz"), ("marketing_opt_in", "1"), ("click", google), ("ads_consent", "1"),
              ("utm_campaign", "jaro"), ("ttlock", "0")])
    add("submit-no-accept-en", P, "/signup", query="lang=en",
        form=[("email", "b@example.cz"), ("accept", "yes"), ("click", both), ("meta_consent", "1")], env=META)
    add("submit-signed-in", P, "/signup", form=ok_form, signed_in=True, patch={"register": True})
    add("submit-off", P, "/signup", form=ok_form, env={"UBYHOST_SIGNUP_ENABLED": "0"})
    # GET /signup/verify
    add("verify-expired", G, "/signup/verify", query="t=forged")
    add("verify-expired-no-token-en", G, "/signup/verify", query="lang=en")
    add("verify-form", G, "/signup/verify", query="t=golden.Token-value_1", patch={"pending": True})
    add("verify-form-escape-vi", G, "/signup/verify", query="t=a%22b%3Cc%26d%27e&lang=vi", patch={"pending": True})
    add("verify-form-signed-in", G, "/signup/verify", query="t=golden", signed_in=True, patch={"pending": True})
    add("verify-off", G, "/signup/verify", query="t=x", env={"UBYHOST_SIGNUP_ENABLED": "0"})
    # POST /signup/verify
    add("verify-submit-expired", P, "/signup/verify", form=[("t", "forged")])
    add("verify-submit-locked", P, "/signup/verify", query="lang=en", form=[("t", "golden")], patch={"locked": True})
    add("verify-submit-race", P, "/signup/verify", form=[("t", "golden")], patch={"pending": True, "activate": False})
    return cases


def _cookie(header: str) -> dict:
    out = base._cookie(header)
    if out["name"] != host_i18n.LANG_COOKIE:
        out["value"] = "" if not out["value"] else "set"
    return out


def _host_user() -> tuple[int, int]:
    row = db.query_one("SELECT id, session_version FROM user_account WHERE username = ?", ("golden-host",))
    if row:
        return row["id"], row["session_version"]
    uid = db.insert("user_account", {
        "username": "golden-host", "email": "host@example.cz", "role": "host", "active": 1,
        "password_hash": "", "session_version": 1, "created_at": db.utcnow(),
    })
    return uid, 1


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return dict(value) if hasattr(value, "keys") else str(value)


def render_case(case: dict) -> tuple[dict, str]:
    env = case["env"]
    values = base.config_values(env)
    turnstile_on = bool(env["TURNSTILE_SITE_KEY"] and env["TURNSTILE_SECRET"] and env["TURNSTILE_HOSTNAMES"])
    globals_ = {
        "deployment_tier": values["DEPLOYMENT"],
        "ubyport_env": env["UBYHOST_UBYPORT_ENV"].lower(),
        "turnstile_site_key": env["TURNSTILE_SITE_KEY"] if turnstile_on else "",
        "public_base_url": values["PUBLIC_BASE_URL"],
    }
    seen: dict = {}
    real_render = templating.render

    def spy_render(request, name, context=None, status_code=200):
        seen["template"] = name
        seen["context"] = _jsonable(dict(context or {}))
        return real_render(request, name, context, status_code=status_code)

    def spy_register(**kwargs):
        kwargs.pop("request", None)
        seen["register"] = _jsonable(kwargs)
        return "created"

    patch = case["patch"]
    pending = {"id": 1, "username": "golden-host", "signup_verify_nonce": "n"} if patch.get("pending") else None
    cookies = {security.CSRF_COOKIE: NONCE, **case["cookies"]}
    if case["signed_in"]:
        uid, sv = _host_user()
        cookies[auth.SESSION_COOKIE] = auth.issue_session(uid, sv)
    url = case["path"] + (f"?{case['query']}" if case["query"] else "")
    patches = [
        mock.patch.multiple(config, UBYPORT_ENV=env["UBYHOST_UBYPORT_ENV"].lower(), **values),
        mock.patch.dict(templating.templates.env.globals, globals_),
        mock.patch.object(signup_routes, "render", spy_render),
        mock.patch.object(signup, "_now_ms", lambda: NOW_MS),
        mock.patch.object(signup, "register", spy_register),
        mock.patch.object(signup, "record_attempt", lambda *a, **k: None),
        mock.patch.object(signup, "rate_limited", lambda *a, **k: bool(patch.get("rate_limited"))),
        mock.patch.object(turnstile, "verify", lambda *a, **k: patch.get("turnstile", True)),
        mock.patch.object(signup, "pending_account", lambda token: pending),
        mock.patch.object(signup, "activate", lambda account: patch.get("activate", True)),
        mock.patch.object(login_link, "consume_blocked", lambda key: bool(patch.get("locked"))),
        mock.patch.object(login_link, "record_consume_failure", lambda key: None),
    ]
    for p in patches:
        p.start()
    try:
        client = TestClient(app, base_url="http://testserver")
        headers = {"cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()), "accept": "application/json"}
        if case["method"] == "GET":
            response = client.get(url, headers=headers, follow_redirects=False)
        else:
            headers["content-type"] = "application/x-www-form-urlencoded"
            pairs = [tuple(p) for p in case["form"]] + [("_csrf", CSRF_TOKEN)]
            response = client.post(url, content=urlencode(pairs), headers=headers, follow_redirects=False)
    finally:
        for p in reversed(patches):
            p.stop()
    expected = {
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "location": response.headers.get("location", ""),
        "set_cookies": [_cookie(h) for h in response.headers.get_list("set-cookie")],
        "template": seen.get("template", ""),
        "context": seen.get("context"),
        "register": seen.get("register"),
    }
    html = ""
    if expected["template"]:
        html = mask(base.normalize(response.text)) + "\n"
    else:
        expected["body"] = response.text
    return {**case, "expected": expected}, html


def _icon(name: str) -> str:
    env = templating.templates.env
    return str(env.from_string("{% from '_icons.html' import icon %}{{ icon('" + name + "', 14) }}").render())


def catalog() -> str:
    strings = {
        lang: {k: v for k, v in sorted(table.items()) if k.startswith(KEY_PREFIXES) or k in SHELL_KEYS}
        for lang, table in host_i18n.STRINGS.items()
    }
    data = {"strings": strings, "check_icon": _icon("check")}
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def outputs() -> dict:
    db.init_db()
    files = {PKG / "signup_catalog.json": catalog()}
    cases = []
    for case in _cases():
        entry, html = render_case(case)
        cases.append(entry)
        if html:
            files[TESTDATA / f"{case['name']}.html"] = html
    out = {"secret": SECRET, "nonce": NONCE, "now_ms": NOW_MS, "cases": cases}
    files[TESTDATA / "cases.json"] = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
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
