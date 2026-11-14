"""Writes golden values for the shared Go auth pieces (brief 1501).

Run from App/: .venv/bin/python scripts/auth_shared_golden.py
Port plumbing (go-first exception 1). Everything comes from the real
app.client_ip, rate_limit, turnstile, security, auth, host_i18n,
validation and mail_notify with fixed inputs and a frozen clock; nothing
touches a database or the network (requests.post is replaced). It writes:

  go/internal/clientip/testdata/clientip.json
  go/internal/turnstile/testdata/turnstile.json
  go/internal/web/auth/testdata/finish_login.json
  go/internal/mail/testdata/auth_mail.json
"""
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parent
SECRET = "auth-shared-golden-secret-0123456789-abcd"
NOW = 1798761600
ENV = {
    "UBYHOST_SECRET_KEY": SECRET,
    "UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example/",
    "UBYHOST_APP_BASE_URL": "https://app.ubyhost.example",
    "UBYHOST_OPERATOR_EMAIL": "ops@ubyhost.example",
}
os.environ.update(ENV)
sys.path.insert(0, str(APP_DIR))

import requests  # noqa: E402
from itsdangerous import URLSafeTimedSerializer  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import RedirectResponse, Response  # noqa: E402

from app import (  # noqa: E402
    auth,
    client_ip,
    config,
    host_i18n,
    mail,
    mail_notify,
    rate_limit,
    security,
    turnstile,
    validation,
)
from app.routes import admin_accounts  # noqa: E402

# _fail_open is replaced below; the "verification unavailable" warning with its
# traceback would only clutter the output.
logging.getLogger("ubyhost.turnstile").disabled = True


def write(rel, data):
    out = REPO / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {rel}")


def request(peer="198.51.100.7", headers=(), query=b"", method="POST"):
    scope = {
        "type": "http",
        "method": method,
        "path": "/login/link",
        "query_string": query,
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers],
        "client": (peer, 1234) if peer is not None else None,
        "server": ("app.ubyhost.example", 443),
        "scheme": "https",
    }
    return Request(scope)


# --- client_ip + rate_limit.client_key -------------------------------------
CIDRS = ["", "172.16.0.0/12", " 172.16.0.0/12 , 10.0.0.1 ", "10.0.0.0/8,fd00::/8", "172.16.5.9/12"]
PEERS = ["172.18.0.3", "10.0.0.1", "10.0.0.2", "198.51.100.7", "fd00::5", "::ffff:172.18.0.3", "", None]
HEADERS = [None, "203.0.113.9", " 203.0.113.9 ", "2001:DB8::0:1", "not-an-ip", "203.0.113.9, 1.2.3.4", "", "01.2.3.4"]
cases = []
for cidrs in CIDRS:
    for peer in PEERS:
        for header in HEADERS:
            with mock.patch.object(config, "TRUSTED_PROXY_CIDRS", cidrs):
                client_ip.reset_trusted_proxy_cache()
                hdrs = [] if header is None else [("CF-Connecting-IP", header)]
                req = request(peer, hdrs)
                client_ip.apply_visitor_client(req.scope, req.headers)
                req = Request(req.scope)
                cases.append({
                    "cidrs": cidrs, "peer": peer, "header": header,
                    "host": req.client.host if req.client else "",
                    "key": rate_limit.client_key(req),
                    "key_suffix": rate_limit.client_key(req, "host_login"),
                })
client_ip.reset_trusted_proxy_cache()
write("go/internal/clientip/testdata/clientip.json", {"cases": cases})

# --- turnstile -------------------------------------------------------------
ENV_CASES = [
    {},
    {"UBYHOST_DEPLOYMENT": "production"},
    {"UBYHOST_DEPLOYMENT": "production", "TURNSTILE_SECRET": " s3cret ", "TURNSTILE_HOSTNAMES": "ubyhost.com"},
    {"UBYHOST_DEPLOYMENT": "PRODUCTION", "TURNSTILE_SECRET": "s", "TURNSTILE_HOSTNAMES": " UbyHost.com , ,www.ubyhost.com"},
    {"UBYHOST_DEPLOYMENT": "staging", "TURNSTILE_SECRET": "s", "TURNSTILE_HOSTNAMES": "ubyhost.com"},
    {"UBYHOST_DEPLOYMENT": "production", "TURNSTILE_SECRET": "s", "TURNSTILE_HOSTNAMES": " , "},
    {"UBYHOST_DEPLOYMENT": "production", "TURNSTILE_SECRET": "s", "TURNSTILE_HOSTNAMES": "a.com",
     "TURNSTILE_SITE_KEY": " 0xOTHER "},
]
PROBE = (
    "import json; from app import config, turnstile; "
    "print(json.dumps({'required': turnstile.required(), 'enabled': config.TURNSTILE_ENABLED, "
    "'site_key': config.TURNSTILE_SITE_KEY, 'secret': config.TURNSTILE_SECRET, "
    "'hostnames': sorted(config.TURNSTILE_HOSTNAMES), 'deployment': config.DEPLOYMENT}))"
)
env_out = []
base_env = {k: v for k, v in os.environ.items()
            if not k.startswith("TURNSTILE_") and k != "UBYHOST_DEPLOYMENT"}
for case in ENV_CASES:
    run = subprocess.run([sys.executable, "-c", PROBE], cwd=APP_DIR, env={**base_env, **case},
                         capture_output=True, text=True, check=True)
    env_out.append({"env": case, **json.loads(run.stdout.strip().splitlines()[-1])})


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return json.loads(self._body)


OK = '{"success": true, "action": "host_login", "hostname": "ubyhost.com"}'
VERIFY = [
    ("ok", "tok", 200, OK),
    ("ok_upper_host", "tok", 200, '{"success": true, "action": "host_login", "hostname": "UbyHost.COM"}'),
    ("other_host", "tok", 200, '{"success": true, "action": "host_login", "hostname": "evil.example"}'),
    ("no_host", "tok", 200, '{"success": true, "action": "host_login"}'),
    ("null_host", "tok", 200, '{"success": true, "action": "host_login", "hostname": null}'),
    ("wrong_action", "tok", 200, '{"success": true, "action": "guest_claim", "hostname": "ubyhost.com"}'),
    ("no_action", "tok", 200, '{"success": true, "hostname": "ubyhost.com"}'),
    ("success_false", "tok", 200, '{"success": false, "action": "host_login", "hostname": "ubyhost.com"}'),
    ("success_one", "tok", 200, '{"success": 1, "action": "host_login", "hostname": "ubyhost.com"}'),
    ("success_string", "tok", 200, '{"success": "true", "action": "host_login", "hostname": "ubyhost.com"}'),
    ("empty_token", "", 200, OK),
    ("max_token", "t" * 2048, 200, OK),
    ("long_token", "t" * 2049, 200, OK),
    ("long_unicode_token", "é" * 2048, 200, OK),
    ("status_500", "tok", 500, OK),
    ("status_403", "tok", 403, OK),
    ("not_json", "tok", 200, "<html>busy</html>"),
    ("timeout", "tok", None, None),
    ("connection", "tok", "connection", None),
]
posted = []


def fake_post(url, data=None, timeout=None, **kwargs):
    posted.append({"url": url, "data": dict(data), "timeout": timeout, "extra": sorted(kwargs)})
    case = current["case"]
    if case[2] is None:
        raise requests.Timeout("timeout")
    if case[2] == "connection":
        raise requests.ConnectionError("refused")
    return FakeResponse(case[2], case[3])


current = {}
verify_out = []
with mock.patch.object(config, "DEPLOYMENT", "production"), \
        mock.patch.object(config, "TURNSTILE_ENABLED", True), \
        mock.patch.object(config, "TURNSTILE_SECRET", "s3cret value&x"), \
        mock.patch.object(config, "TURNSTILE_HOSTNAMES", {"ubyhost.com", "www.ubyhost.com"}), \
        mock.patch.object(turnstile.requests, "post", fake_post), \
        mock.patch.object(turnstile, "_fail_open", lambda request, action: "FAIL_OPEN"):
    for case in VERIFY:
        current["case"] = case
        posted.clear()
        got = turnstile.verify(request("203.0.113.9"), case[1], "host_login")
        verify_out.append({
            "name": case[0], "token": case[1], "status": case[2], "body": case[3],
            "result": "fail_open" if got == "FAIL_OPEN" else bool(got),
            "posted": posted[0] if posted else None,
        })
write("go/internal/turnstile/testdata/turnstile.json", {
    "env": env_out, "verify": verify_out, "verify_url": turnstile.VERIFY_URL,
    "hostnames": ["ubyhost.com", "www.ubyhost.com"], "secret": "s3cret value&x", "remoteip": "203.0.113.9",
    "unreachable": {"max": turnstile._UNREACHABLE_MAX_ATTEMPTS, "window": turnstile._UNREACHABLE_WINDOW_SECONDS},
})

# --- _finish_login pieces --------------------------------------------------
PATHS = [
    "", "/", "/reservations", "  /reservations?x=1  ", "/a/./b/../c", "/a//b", "//evil.example/x", "///x",
    "////x", "/%2F%2Fevil", "/x\\y", "https://evil.example/", "javascript:alert(1)", "relative",
    "/x#frag", "/x?q=a b&c=č", "/čeština", "/x?", "/..", "/a/", "/%zz", "/x\x01", "/%5Cx", "/?next=//e",
    "/x?y=1#z", "\t/tab", "/a%20b", "/a?b=%2F",
]
paths = []
for p in PATHS:
    safe = security.safe_local_path(p, "/")
    location = RedirectResponse(safe, status_code=303).headers["location"]
    paths.append({"in": p, "safe": safe, "location": location})

LANGS = [
    (b"", None), (b"lang=en", None), (b"lang=vi&lang=cs", None), (b"lang=de", "en"), (b"", "cs"),
    (b"", "vi"), (b"", "EN-gb"), (b"", " de "), (b"lang= CS", "cs"), (b"lang=VI", "vi"),
]
langs = []
for base in ["http://127.0.0.1:8080", "https://ubyhost.example"]:
    for query, cookie in LANGS:
        headers = [("cookie", f"ubyhost_lang={cookie}")] if cookie is not None else []
        response = Response()
        with mock.patch.object(config, "PUBLIC_BASE_URL", base):
            admin_accounts._keep_login_language(request(headers=headers, query=query), response)
        langs.append({"base": base, "query": query.decode(), "cookie": cookie,
                      "set_cookie": response.headers.get("set-cookie")})


def device_payload(token):
    return URLSafeTimedSerializer(SECRET, salt="ubyhost-device").loads(token)


cookies = []
for deployment, base in [("local", "http://127.0.0.1:8080"), ("production", "http://127.0.0.1:8080"),
                         ("local", "https://ubyhost.example")]:
    for remember in [True, False]:
        with mock.patch.object(config, "DEPLOYMENT", deployment), \
                mock.patch.object(config, "PUBLIC_BASE_URL", base), \
                mock.patch("time.time", return_value=float(NOW)):
            token = auth.issue_session(7, 3, remember=remember)
            response = Response()
            auth.attach_session(response, token, remember=remember)
            auth.attach_device(response, {"id": 7, "session_version": 3})
        headers = response.headers.getlist("set-cookie")
        device = headers[1].split(";")[0].split("=", 1)[1]
        device_fields = device_payload(device)
        cookies.append({
            "deployment": deployment, "base": base, "remember": remember,
            "session_token": token,
            "set_cookie": [h.replace(token, "TOKEN").replace(device, "DEVICE") for h in headers],
            "device_keys": list(device_fields), "device_did_len": len(device_fields["did"]),
            "device_uid_sv": [device_fields["uid"], device_fields["sv"]],
        })
write("go/internal/web/auth/testdata/finish_login.json", {
    "secret": SECRET, "now": NOW, "paths": paths, "langs": langs, "cookies": cookies,
})

# --- account mails ---------------------------------------------------------
LANGS_MAIL = ["en", "cs", "vi", "de", "CS-cz", ""]
APP = config.app_base_url()
mails = []
for kind, (prefix, path) in mail_notify.LINK_MAIL.items():
    link = f"{APP}{path}?t={mail.CLAIM_SECRET_MARKER}"
    for lang in LANGS_MAIL:
        for minutes in [15, 60, 119, 120, 125, 4320]:
            c = mail_notify.build_link_mail(kind=kind, link=link, minutes=minutes, lang=lang or None)
            mails.append({"builder": "link", "kind": kind, "link": link, "minutes": minutes, "lang": lang, **c})
MASKED = mail.mask_email("new.address@example.cz")
for side in ["old", "new"]:
    for by in ["support", "self"]:
        for lang in LANGS_MAIL:
            c = mail_notify.build_email_changed(side=side, new_masked=MASKED, lang=lang or None, by=by)
            mails.append({"builder": "email_changed", "side": side, "by": by, "masked": MASKED, "lang": lang, **c})
for name in ["MacBook", 'Klíč <b>&"x"</b>', "50% %(support)s"]:
    for lang in LANGS_MAIL:
        c = mail_notify.build_passkey_added(name=name, lang=lang or None)
        mails.append({"builder": "passkey_added", "name": name, "lang": lang, **c})
for stage in mail_notify.WORKSPACE_DELETION_STAGES:
    for lang in LANGS_MAIL:
        c = mail_notify.build_workspace_deletion(stage=stage, date="05.01.2027", lang=lang or None)
        mails.append({"builder": "workspace_deletion", "stage": stage, "date": "05.01.2027", "lang": lang, **c})

first_link = next(m for m in mails if m["builder"] == "link" and m["lang"] == "CS-cz")
notice = next(m for m in mails if m["builder"] == "passkey_added")
payloads = {
    "link": {
        "lang": host_i18n.normalise_language("CS-cz"),
        "json": json.dumps({"text": first_link["text"], "html": first_link["html"], "lang": "cs",
                            mail.CLAIM_SECRET_KEY: "ENC"}),
    },
    "notice": json.dumps({"text": notice["text"], "html": notice["html"], "lang": mail_notify.HOST_MAIL_LANGUAGE,
                          "reply_to": config.OPERATOR_EMAIL}),
    "link_key_token": "tok-123",
    "link_key": "login_link:7:" + hashlib.sha256(b"tok-123").hexdigest()[:24],
}
DATES = ["2027-01-05T10:00:00+00:00", "2027-01-05", "2027-1-5", "2027-01- 5", "2027-02-30", "", "garbage",
         "0000-01-01", "2027-13-01", "2027-01-05x", "27-01-05"]
dates = [{"in": d, "out": validation.fmt_date(d[:10])} for d in DATES]
write("go/internal/mail/testdata/auth_mail.json", {
    "env": ENV, "app_base": APP, "masked_new": MASKED, "mails": mails, "payloads": payloads, "dates": dates,
})
