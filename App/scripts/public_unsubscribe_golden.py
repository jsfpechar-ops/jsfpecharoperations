"""Golden pages, tokens and database effects for the mail unsubscribe page (brief 1623).

Python: App/app/routes/mail_unsubscribe.py, templates/mail_unsubscribe.html and auth_base.html.
Go: go/internal/web/public (brief 1624).

Run from App/:
    .venv/bin/python scripts/public_unsubscribe_golden.py          write the files
    .venv/bin/python scripts/public_unsubscribe_golden.py --check  exit 1 and name each stale file

It writes:
  go/internal/web/public/catalog_unsub.json            strings for the page and the auth shell (en, cs, vi)
  go/internal/web/public/testdata/unsub/cases.json     one entry per case: request, env, setup, expected response and rows
  go/internal/web/public/testdata/unsub/<case>.html    the FastAPI page, normalized, CSRF token blanked

Every case starts from the same two accounts on a throwaway SQLite database
(1 "host", opted in; 2 "opted", already opted out). The tokens are the real
lifecycle_mail tokens under the golden script's secret key.
"""
from __future__ import annotations

import json
import re
import sys
from unittest import mock

import public_legal_golden as base  # noqa: E402  (sets the env, imports the app)

from fastapi.testclient import TestClient  # noqa: E402

from app import config, db, host_i18n, lifecycle_mail, rate_limit, templating  # noqa: E402
from app.main import app  # noqa: E402

REPO, PKG = base.REPO, base.PKG
TESTDATA = PKG / "testdata" / "unsub"

# Every key the page, the auth shell and the env banner read, under these prefixes.
KEY_PREFIXES = (
    "unsubscribe.", "auth.notice.", "auth.not_you", "lang.", "a11y.skip_to_content",
    "legal.footer_link", "terms.footer_link", "privacy.footer_link", "dpa.footer_link",
    "login.hero_", "landing.demo.scene.", "landing.demo.queue.ready", "env.", "how.toggle",
)
ADDRESS = "tip@example.test"
SECRET = "public-legal-golden-secret-not-real-0123"
_CSRF = re.compile(r'(name="_csrf" value=|name="csrf-token" content=)"[^"]*"')


def tokens() -> dict[str, str]:
    return {
        "host": lifecycle_mail.unsubscribe_token(1, ADDRESS),
        "host_no_address": lifecycle_mail.unsubscribe_token(1),
        "opted": lifecycle_mail.unsubscribe_token(2, ADDRESS),
        "unknown_user": lifecycle_mail.unsubscribe_token(99, ADDRESS),
        "forged": "eyJ1IjoxfQ.forged-signature",
    }


def _cases() -> list[dict]:
    cases = []

    def add(name, method, who, query="", cookies=None, env=None, rate_events=0):
        cases.append({"name": name, "method": method, "who": who, "query": query, "cookies": cookies or {},
                      "env": {**base.BASE_ENV, **(env or {})}, "rate_events": rate_events})

    add("get-form-cs", "GET", "host")
    add("get-form-en", "GET", "host", query="lang=en")
    add("get-form-vi", "GET", "host", cookies={"ubyhost_lang": "vi"})
    add("get-form-cookie-en", "GET", "host", cookies={"ubyhost_lang": "en"})
    add("get-form-notice", "GET", "host", query="lang=en&notice=logged_out")
    add("get-form-notice-unknown", "GET", "host", query="notice=bogus")
    add("get-form-production", "GET", "host", query="lang=en", env={"UBYHOST_UBYPORT_ENV": "production", "UBYHOST_DEPLOYMENT": "production"})
    add("get-form-mock-production", "GET", "host", query="lang=en", env={"UBYHOST_UBYPORT_ENV": "mock", "UBYHOST_DEPLOYMENT": "production"})
    add("get-form-no-operator-email", "GET", "host", env={"UBYHOST_OPERATOR_EMAIL": "ops@ubyhost.example"})
    add("get-done-already-opted-out", "GET", "opted", query="lang=en")
    add("get-invalid-forged", "GET", "forged", query="lang=en")
    add("get-invalid-unknown-user", "GET", "unknown_user")
    add("get-blocked", "GET", "host", query="lang=en", rate_events=30)
    add("get-blocked-forged", "GET", "forged", rate_events=30)
    add("post-valid", "POST", "host", query="lang=en")
    add("post-valid-no-address", "POST", "host_no_address")
    add("post-valid-already-opted-out", "POST", "opted", query="lang=en")
    add("post-valid-while-blocked", "POST", "host", query="lang=en", rate_events=30)
    add("post-forged", "POST", "forged", query="lang=en")
    add("post-unknown-user", "POST", "unknown_user")
    add("post-forged-blocked", "POST", "forged", query="lang=en", rate_events=30)
    return cases


def normalize(html: str) -> str:
    return _CSRF.sub(r'\1""', base.normalize(html))


def _reset() -> None:
    for table in ("audit", "mail_suppression", "rate_limit_event", "user_account"):
        db.execute(f"DELETE FROM {table}")
    now = db.utcnow()
    db.execute(
        "INSERT INTO user_account (id, username, password_hash, created_at) VALUES (1, 'host', 'x', ?)", (now,))
    db.execute(
        "INSERT INTO user_account (id, username, password_hash, created_at, onboarding_emails_opt_out, "
        "onboarding_emails_opt_out_at) VALUES (2, 'opted', 'x', ?, 1, ?)", (now, now))


def _rows() -> dict:
    users = {
        str(r["id"]): {"opt_out": int(r["onboarding_emails_opt_out"] or 0), "opt_out_at_set": bool(r["onboarding_emails_opt_out_at"])}
        for r in db.query("SELECT id, onboarding_emails_opt_out, onboarding_emails_opt_out_at FROM user_account ORDER BY id")
    }
    return {
        "users": users,
        "suppressions": [dict(r) for r in db.query("SELECT email_hash, scope FROM mail_suppression ORDER BY email_hash")],
        "audit": [dict(r) for r in db.query(
            "SELECT actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id")],
        "rate_events": int(db.query_one("SELECT COUNT(*) AS n FROM rate_limit_event")["n"]),
    }


def render_case(case: dict, toks: dict[str, str]) -> tuple[dict, str]:
    _reset()
    for _ in range(case["rate_events"]):
        rate_limit.record("mail_unsubscribe", "testclient:mail_unsubscribe")
    token = toks[case["who"]]
    url = f"/mail/unsubscribe/{token}" + (f"?{case['query']}" if case["query"] else "")
    values = base.config_values(case["env"])
    values["UBYPORT_ENV"] = case["env"].get("UBYHOST_UBYPORT_ENV", "mock").lower()
    patched = {"public_base_url": values["PUBLIC_BASE_URL"], "deployment_tier": values["DEPLOYMENT"],
               "ubyport_env": values["UBYPORT_ENV"]}
    values.pop("UBYPORT_ENV")
    with mock.patch.multiple(config, **values), mock.patch.dict(templating.templates.env.globals, patched):
        client = TestClient(app, cookies=case["cookies"])
        response = client.request(case["method"], url)
    cookies = [base._cookie(h) for h in response.headers.get_list("set-cookie")]
    for cookie in cookies:
        if cookie["name"] == "ubyhost_csrf":
            cookie["value"] = ""  # a random nonce
    entry = {
        **case, "token": token,
        "expected": {
            "status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "cache_control": response.headers.get("cache-control", ""),
            "csp": response.headers.get("content-security-policy", ""),
            "set_cookies": [c for c in cookies if c["name"] in (host_i18n.LANG_COOKIE, "ubyhost_csrf")],
            "rows": _rows(),
        },
    }
    return entry, normalize(response.text) + "\n"


def catalog() -> str:
    strings = {
        lang: {k: v for k, v in sorted(host_i18n.STRINGS[lang].items()) if k.startswith(KEY_PREFIXES)}
        for lang in host_i18n.LANGUAGES
    }
    icon = templating.templates.env.from_string("{% from '_icons.html' import icon %}{{ icon('check', 14) }}").render()
    return json.dumps({"strings": strings, "check_icon": str(icon)}, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def outputs() -> dict:
    db.init_db()
    toks = tokens()
    files = {PKG / "catalog_unsub.json": catalog()}
    cases = []
    for case in _cases():
        entry, html = render_case(case, toks)
        cases.append(entry)
        files[TESTDATA / f"{case['name']}.html"] = html
    files[TESTDATA / "cases.json"] = json.dumps({"secret": SECRET, "address": ADDRESS, "tokens": toks, "cases": cases},
                                                ensure_ascii=False, indent=1) + "\n"
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
