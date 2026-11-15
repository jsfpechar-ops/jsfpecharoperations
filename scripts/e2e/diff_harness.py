#!/usr/bin/env python3
"""Differential e2e: the same requests against Python and Go, each on its own
clone of one seeded Postgres database, diffed on status, redirect, headers,
cookie flags and normalised body.

  /var/tmp/ubyvenv/bin/python scripts/e2e/diff_harness.py [--report out.json] [--flows-only]

Needs: Postgres server (UBYHOST_E2E_PG, default postgresql://postgres@127.0.0.1:5433),
the app venv python running this file, a Go toolchain. Never touches production:
databases are e2e_tpl / e2e_py / e2e_go on the server named above, ports 8101/8102.
Hard failures: status, Location, content-type, auth/CSRF outcome, cookie flags.
Soft: body text differences (listed, counted).
"""
import argparse
import urllib.parse
import json
import os
import re
import signal
import subprocess
import sys
import time

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import go_parity_check  # noqa: E402
import py_routes  # noqa: E402

PG = os.environ.get("UBYHOST_E2E_PG", "postgresql://postgres@127.0.0.1:5433")
PSQL = os.environ.get("UBYHOST_E2E_PSQL", "/usr/lib/postgresql/16/bin/psql")
PY_PORT, GO_PORT = 8101, 8102
BASE = {"py": f"http://127.0.0.1:{PY_PORT}", "go": f"http://127.0.0.1:{GO_PORT}"}
# WebAuthn needs a hostname (not an IP) as RP id, so the apps are configured with localhost and the browser Origin is localhost
PUBLIC = {"py": f"http://localhost:{PY_PORT}", "go": f"http://localhost:{GO_PORT}"}
ENV_COMMON = {
    "UBYHOST_SECRET_KEY": "e2e-secret-key-0123456789-abcdefghijkl",
    "UBYHOST_ENABLE_SCHEDULER": "0", "UBYHOST_BOOTSTRAP_ADMIN": "0",
    "UBYHOST_MAIL_BACKEND": "console", "UBYHOST_UBYPORT_ENV": "mock",
    "UBYHOST_DATA_DIR": "/var/tmp/e2e_data", "UBYHOST_GUEST_PIN": "0",
    "UBYHOST_ICAL_OPEN_SYNC_MINUTES": "0", "UBYHOST_SIGNUP_ENABLED": "1",
    "UBYHOST_BILLING_ENABLED": "1", "UBYHOST_BILLING_IBAN": "CZ6503000000000123456789", "UBYHOST_BILLING_BANK_ACCOUNT": "123456789/0300",
    "UBYHOST_STRIPE_MODE": "test", "UBYHOST_STRIPE_WEBHOOK_SECRET": "whsec_e2e_secret", "UBYHOST_STRIPE_SECRET_KEY": "sk_test_e2e",
}
HEADERS = ["content-type", "cache-control", "location", "x-frame-options", "referrer-policy",
           "x-content-type-options", "content-security-policy", "strict-transport-security",
           "content-disposition", "permissions-policy"]


def sql(db, stmt):
    subprocess.run([PSQL, PG + "/postgres", "-qc", stmt], check=True, capture_output=True)


def setup_databases():
    for d in ("e2e_py", "e2e_go", "e2e_tpl"):
        sql("", f"DROP DATABASE IF EXISTS {d}")
    sql("", "CREATE DATABASE e2e_tpl")
    env = dict(os.environ, **ENV_COMMON, UBYHOST_DATABASE_URL=PG + "/e2e_tpl")
    r = subprocess.run([sys.executable, os.path.join(HERE, "seed.py")], cwd=os.path.join(ROOT, "App"),
                       env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit("seed failed:\n" + r.stderr[-2000:])
    seed = json.loads(r.stdout.strip().splitlines()[-1])
    for d in ("e2e_py", "e2e_go"):
        sql("", f"CREATE DATABASE {d} TEMPLATE e2e_tpl")
    return seed


def start_servers():
    os.makedirs(ENV_COMMON["UBYHOST_DATA_DIR"], exist_ok=True)
    subprocess.run(["go", "build", "-o", "/var/tmp/ubyhost-web", "./cmd/ubyhost-web"],
                   cwd=os.path.join(ROOT, "go"), check=True)
    procs = []
    penv = dict(os.environ, **ENV_COMMON, UBYHOST_DATABASE_URL=PG + "/e2e_py", UBYHOST_PUBLIC_BASE_URL=PUBLIC["py"])
    procs.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PY_PORT),
                                   "--log-level", "warning"], cwd=os.path.join(ROOT, "App"), env=penv,
                                  stdout=open("/tmp/e2e_py.log", "w"), stderr=subprocess.STDOUT))
    genv = dict(os.environ, **ENV_COMMON, UBYHOST_DATABASE_URL=PG + "/e2e_go",
                UBYHOST_GO_ADDR=f"127.0.0.1:{GO_PORT}", UBYHOST_MIGRATIONS_DIR="App/migrations_pg",
                UBYHOST_GO_JOB_KINDS="", UBYHOST_JOB_QUEUE_KINDS="", UBYHOST_PUBLIC_BASE_URL=PUBLIC["go"])
    procs.append(subprocess.Popen(["/var/tmp/ubyhost-web"], cwd=ROOT, env=genv,
                                  stdout=open("/tmp/e2e_go.log", "w"), stderr=subprocess.STDOUT))
    for side in ("py", "go"):
        for _ in range(120):
            try:
                if httpx.get(BASE[side] + "/healthz", timeout=2).status_code in (200, 503):
                    break
            except Exception:
                time.sleep(0.5)
        else:
            stop(procs)
            sys.exit(f"{side} server did not start; see /tmp/e2e_{side}.log")
    return procs


def stop(procs):
    for p in procs:
        p.send_signal(signal.SIGTERM)
    for p in procs:
        try:
            p.wait(10)
        except Exception:
            p.kill()


class Side:
    """One server plus cookie jars per identity."""

    def __init__(self, name, seed):
        self.name, self.seed = name, seed
        self.jars = {}

    def client(self, who):
        if who not in self.jars:
            c = httpx.Client(base_url=BASE[self.name], follow_redirects=False, timeout=30)
            key = {"pkuser": "h1"}.get(who, who)
            if key in self.seed:
                c.cookies.set("ubyhost_session", self.seed[key]["session"], domain="127.0.0.1")
            self.jars[who] = c
        return self.jars[who]

    def csrf(self, who):
        """A token bound to this jar's CSRF cookie. A logged-in jar gets redirected away from /login, so ask a page it can open."""
        c = self.client(who)
        for path in ("/login", "/menu", "/signup"):
            r = c.get(path, headers={"accept": "text/html"})
            m = (re.search(r'name="_csrf"\s+value="([^"]+)"', r.text) or re.search(r'value="([^"]+)"\s+name="_csrf"', r.text)
                 or re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text))
            if m and m.group(1):
                return m.group(1)
        raise RuntimeError(f"{self.name}: no CSRF token for {who}")

    def send(self, who, method, path, *, csrf=False, data=None, origin="same", headers=None, json_body=None, content=None):
        c = self.client(who)
        h = dict(headers or {})
        if origin == "same":
            h["origin"] = PUBLIC[self.name]
        elif origin:
            h["origin"] = origin
        form = dict(data or {})
        if csrf:
            form["_csrf"] = self.csrf(who)
        kw = {}
        if content is not None:
            kw["content"] = content
        elif json_body is not None:
            kw["json"] = json_body
            if csrf:
                h["x-csrf-token"] = form["_csrf"]
        elif method in ("POST", "PUT", "DELETE", "PATCH"):
            kw["data"] = form
        try:
            r = c.request(method, path, headers=h, **kw)
        except Exception as e:  # connection reset etc.
            return {"error": repr(e)}
        return record(r)


NORM = [(re.compile(r'("(?:challenge|id|rawId|credential_id|user\.id|userHandle)"\s*:\s*")[A-Za-z0-9_-]{16,}'), r'\1X'),
        (re.compile(r'(name="_csrf"\s+value=")[^"]*'), r"\1X"), (re.compile(r'value="[^"]*"(\s+name="_csrf")'), r'value="X"\1'),
        (re.compile(r'nonce="[^"]*"'), 'nonce="N"'), (re.compile(r"'nonce-[^']*'"), "'nonce-N'"),
        (re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d(:\d\d)?(\.\d+)?(Z|[+-]\d\d:?\d\d)?"), "TS"),
        (re.compile(r"\s+"), " ")]


def norm_text(s):
    for rx, rep in NORM:
        s = rx.sub(rep, s)
    return s.strip()


def cookie_shape(sc):
    out = []
    for line in sc:
        parts = [p.strip() for p in line.split(";")]
        name = parts[0].split("=", 1)[0]
        flags = sorted(p.lower().split("=")[0] if not p.lower().startswith(("samesite", "path")) else p.lower() for p in parts[1:]
                       if not p.lower().startswith(("expires", "max-age")))
        value_empty = parts[0].split("=", 1)[1] in ("", '""') if "=" in parts[0] else False
        out.append([name, "cleared" if value_empty else "set", flags])
    return sorted(out)


def record(r):
    hdr = {k: norm_text(r.headers.get(k, "")) for k in HEADERS if k in r.headers}
    loc = hdr.get("location")
    if loc:
        hdr["location"] = re.sub(r"^https?://(127\.0\.0\.1|localhost):\d+", "", loc)
    ctype = r.headers.get("content-type", "")
    text = r.text
    if "json" in ctype:
        try:
            text = json.dumps(json.loads(text), sort_keys=True)
        except ValueError:
            pass
    body = text if ("text" in ctype or "json" in ctype or "xml" in ctype) else f"<{len(r.content)} bytes>"
    kc = sorted(re.findall(r"\d[\d\u00a0 ]*(?:[.,]\d+)?\s*(?:Kč|CZK)", r.text)) if "text" in ctype else []
    nums = sorted(set(re.findall(r"UBY-\d{4}-\d{4}", r.text))) if "text" in ctype else []
    return {"status": r.status_code, "not_ported": "x-ubyhost-not-ported" in r.headers, "sig": [sorted(re.sub(r"\s+", "", k) for k in kc), nums], "headers": hdr, "cookies": cookie_shape(r.headers.get_list("set-cookie")),
            "body": norm_text(body), "raw": text[:60000] if ("text" in ctype or "json" in ctype) else ""}


def compare(py, go):
    if "error" in py or "error" in go:
        return ["transport: py=%s go=%s" % (py.get("error"), go.get("error"))], []
    hard, soft = [], []
    if go["status"] == 501 and go.get("not_ported"):
        return [], ["NOT-PORTED: Go answers 501 X-Ubyhost-Not-Ported (Caddy re-sends GET/HEAD to Python; a POST would fail)"]
    if py["status"] >= 500 and go["status"] >= 500:
        return [], [f"BOTH-5XX py={py['status']} go={go['status']}"]
    if py["status"] >= 500 and go["status"] < 500:
        soft.append(f"PYTHON-500 (go {go['status']}): Python crashes where Go answers")
    elif py["status"] != go["status"]:
        hard.append(f"status py={py['status']} go={go['status']}")
    if py["status"] >= 500 and go["status"] < 500:
        return hard, soft
    for k in sorted(set(py["headers"]) | set(go["headers"])):
        a, b = py["headers"].get(k), go["headers"].get(k)
        if a != b:
            (hard if (k in ("location", "content-disposition") or (k == "content-type" and py["status"] < 300 and go["status"] < 300)) else soft).append(f"header {k}: py={str(a)[:80]!r} go={str(b)[:80]!r}")
    if py["cookies"] != go["cookies"]:
        hard.append(f"cookies py={py['cookies']} go={go['cookies']}")
    if py.get("sig") != go.get("sig") and py["status"] == go["status"]:
        from collections import Counter
        ca, cb = Counter(py["sig"][0]), Counter(go["sig"][0])
        hard.append(f"amounts/invoice numbers differ: only py {dict(ca - cb)} {sorted(set(py['sig'][1]) - set(go['sig'][1]))}; only go {dict(cb - ca)} {sorted(set(go['sig'][1]) - set(py['sig'][1]))}")
    if py["body"] != go["body"] and py["status"] == go["status"]:
        soft.append(f"body differs (py {len(py['body'])} chars, go {len(go['body'])} chars)")
    return hard, soft


def totp(secret):
    import pyotp
    return pyotp.TOTP(secret).now()


IDS = [None, "h1", "alfa", "admin"]  # anon, empty host, host with billing data (owner 2), admin
SKIP = {"/healthz", "/metrics", "/logout", "/account/logout-all", "/payments/qr/{request_id}"}  # last: Python keeps the preview page (only *.png goes to Go)


def sweep_cases(go_paths=None):
    res = go_parity_check.probe([{"method": m, "path": p} for m, p in py_routes.routes()])
    cases = []
    for r in res:
        if not r["handled"] or r["path"] in SKIP:
            continue
        path = re.sub(r"\{[^/}]*\}", "1", r["path"])
        m = r["method"]
        if go_paths and not any(go_parity_check.caddy_match(e, path) for e in go_paths):
            continue
        if m == "GET":
            cases += [(f"GET {r['path']} {w or 'anon'}", w, m, path, {}) for w in IDS]
        else:
            cases += [(f"{m} {r['path']} anon no-csrf", None, m, path, {})]
            for w in IDS[1:]:
                cases += [(f"{m} {r['path']} {w} no-csrf", w, m, path, {}),
                          (f"{m} {r['path']} {w} csrf empty", w, m, path, {"csrf": True}),
                          (f"{m} {r['path']} {w} csrf evil-origin", w, m, path, {"csrf": True, "origin": "https://evil.example"})]
    return cases


def flows(seed):
    """Each flow is (name, fn(side) -> list of (label, record)). Flows run in order."""
    def login_basic(s):
        out = []
        out.append(("GET /login", s.send(None, "GET", "/login")))
        out.append(("POST /login unknown email", s.send(None, "POST", "/login", csrf=True, data={"email": "nobody@e2e.test"})))
        out.append(("POST /login known email", s.send(None, "POST", "/login", csrf=True, data={"email": "h1@e2e.test"})))
        out.append(("POST /login bad email", s.send(None, "POST", "/login", csrf=True, data={"email": "nope"})))
        out.append(("POST /login no csrf", s.send(None, "POST", "/login", data={"email": "h1@e2e.test"})))
        return out

    def link_flow(s):
        out = []
        tok = seed["h1"]["link"]
        out.append(("GET /login/link?t=valid (must not spend)", s.send("fl1", "GET", f"/login/link?t={tok}")))
        out.append(("POST /login/link bad token", s.send("fl1", "POST", "/login/link", csrf=True, data={"t": "x" * 43})))
        out.append(("POST /login/link no csrf", s.send("fl1", "POST", "/login/link", data={"t": tok})))
        out.append(("POST /login/link valid", s.send("fl1", "POST", "/login/link", csrf=True, data={"t": tok})))
        out.append(("POST /login/link replay", s.send("fl1", "POST", "/login/link", csrf=True, data={"t": tok})))
        out.append(("GET /dashboard/calendar after login", s.send("fl1", "GET", "/dashboard/calendar")))
        out.append(("GET /predplatne after login", s.send("fl1", "GET", "/predplatne")))
        return out

    def twofa(s):
        out = []
        sec = seed["h2"]["totp_secret"]
        first = s.send("fl2", "POST", "/login/link", csrf=True, data={"t": seed["h2"]["link"]})
        out.append(("POST /login/link h2 (2FA host)", first))
        m = re.search(r'name="pending"\s+value="([^"]+)"', first.get("raw", "")) or re.search(r'value="([^"]+)"\s+name="pending"', first.get("raw", ""))
        pending = m.group(1) if m else "missing"
        out.append(("pending token found in 2FA page", {"status": 200 if m else 500, "headers": {}, "cookies": [], "body": ""}))
        out.append(("GET /dashboard/calendar before 2FA", s.send("fl2", "GET", "/dashboard/calendar")))
        out.append(("POST /login/2fa wrong code", s.send("fl2", "POST", "/login/2fa", csrf=True, data={"pending": pending, "code": "000000"})))
        out.append(("POST /login/2fa tampered pending", s.send("fl2", "POST", "/login/2fa", csrf=True, data={"pending": pending[:-3] + "xyz", "code": totp(sec)})))
        out.append(("POST /login/2fa no csrf", s.send("fl2", "POST", "/login/2fa", data={"pending": pending, "code": totp(sec)})))
        out.append(("POST /login/2fa empty code", s.send("fl2", "POST", "/login/2fa", csrf=True, data={"pending": pending, "code": ""})))
        out.append(("POST /login/2fa right code", s.send("fl2", "POST", "/login/2fa", csrf=True, data={"pending": pending, "code": totp(sec)})))
        out.append(("GET /dashboard/calendar after 2FA", s.send("fl2", "GET", "/dashboard/calendar")))
        # recovery code on a second login (new link is not available: reuse pending of the first, still within its TTL)
        rc = seed["h2"]["recovery_codes"][0]
        out.append(("POST /login/2fa recovery code (fresh jar)", s.send("fl3", "POST", "/login/2fa", csrf=True, data={"pending": pending, "code": rc})))
        out.append(("GET /dashboard/calendar after recovery", s.send("fl3", "GET", "/dashboard/calendar")))
        out.append(("POST /login/2fa recovery code replay", s.send("fl4", "POST", "/login/2fa", csrf=True, data={"pending": pending, "code": rc})))
        for i in range(7):
            out.append((f"POST /login/2fa wrong code burst {i}", s.send("fl5", "POST", "/login/2fa", csrf=True, data={"pending": pending, "code": "111111"})))
        out.append(("POST /login/2fa right code while blocked", s.send("fl5", "POST", "/login/2fa", csrf=True, data={"pending": pending, "code": totp(sec)})))
        return out

    def passkeys(s):
        return [("POST /login/passkey/options csrf", s.send(None, "POST", "/login/passkey/options", csrf=True, json_body={"email": "h1@e2e.test"})),
                ("POST /login/passkey/options no csrf", s.send(None, "POST", "/login/passkey/options", json_body={})),
                ("POST /login/passkey garbage", s.send(None, "POST", "/login/passkey", csrf=True, json_body={"credential": {}})),
                ("POST /account/passkeys/options anon", s.send(None, "POST", "/account/passkeys/options", csrf=True, json_body={})),
                ("POST /account/passkeys/options h1", s.send("h1", "POST", "/account/passkeys/options", csrf=True, json_body={})),
                ("POST /account/passkeys/options h1 no csrf", s.send("h1", "POST", "/account/passkeys/options", json_body={})),
                ("POST /account/passkeys/1/delete h1", s.send("h1", "POST", "/account/passkeys/1/delete", csrf=True)),
                ("POST /account/passkeys/1/rename h1", s.send("h1", "POST", "/account/passkeys/1/rename", csrf=True, data={"name": "x"}))]

    def signup(s):
        return [("GET /signup", s.send(None, "GET", "/signup")),
                ("POST /signup bad email", s.send(None, "POST", "/signup", csrf=True, data={"email": "x"})),
                ("POST /signup no csrf", s.send(None, "POST", "/signup", data={"email": "new@e2e.test"})),
                ("POST /signup ok", s.send(None, "POST", "/signup", csrf=True, data={"email": "new@e2e.test", "terms": "1", "accept_terms": "1"})),
                ("GET /signup/verify bad token", s.send(None, "GET", "/signup/verify?t=bad")),
                ("POST /signup/verify bad token", s.send(None, "POST", "/signup/verify", csrf=True, data={"t": "bad"}))]

    def billing_hooks(s):
        return [("POST /webhooks/stripe unsigned", s.send(None, "POST", "/webhooks/stripe", origin=None, json_body={"type": "x"})),
                ("POST /webhooks/stripe bad sig", s.send(None, "POST", "/webhooks/stripe", origin=None,
                                                         headers={"stripe-signature": "t=1,v1=deadbeef"}, json_body={"type": "x"})),
                ("GET /predplatne h1", s.send("h1", "GET", "/predplatne")),
                ("GET /predplatne anon", s.send(None, "GET", "/predplatne")),
                ("GET /predplatne admin", s.send("admin", "GET", "/predplatne"))]

    def money(s):
        out = []
        E = {"paid_on": "2026-11-15"}
        i1, i2, i3 = seed["invoices"]  # real invoices of host h1 (stored PDF + snapshot)
        # golden-fixture invoices: 19..23 unpaid of owners 5..9, 16/57 storno rows (owner 4)
        out.append(("POST mark-paid as host alfa (not admin)", s.send("alfa", "POST", f"/admin/fakturace/{i1}/zaplaceno", csrf=True, data=E)))
        out.append(("POST mark-paid as invoice owner h1", s.send("h1", "POST", f"/admin/fakturace/{i1}/zaplaceno", csrf=True, data=E)))
        out.append(("POST mark-paid admin no csrf", s.send("admin", "POST", f"/admin/fakturace/{i1}/zaplaceno", data=E)))
        out.append(("POST mark-paid admin evil origin", s.send("admin", "POST", f"/admin/fakturace/{i1}/zaplaceno", csrf=True, data=E, origin="https://evil.example")))
        out.append(("POST mark-paid admin bad date", s.send("admin", "POST", f"/admin/fakturace/{i1}/zaplaceno", csrf=True, data={"paid_on": "31.31.2026"})))
        out.append(("POST mark-paid admin ok", s.send("admin", "POST", f"/admin/fakturace/{i1}/zaplaceno", csrf=True, data=E)))
        out.append(("POST mark-paid admin again (already paid)", s.send("admin", "POST", f"/admin/fakturace/{i1}/zaplaceno", csrf=True, data=E)))
        out.append(("POST mark-paid admin unknown invoice", s.send("admin", "POST", "/admin/fakturace/99999/zaplaceno", csrf=True, data=E)))
        out.append(("POST mark-paid a storno row", s.send("admin", "POST", "/admin/fakturace/16/zaplaceno", csrf=True, data=E)))
        out.append(("POST storno as invoice owner h1", s.send("h1", "POST", f"/admin/fakturace/{i2}/storno", csrf=True, data={"reason": "x"})))
        out.append(("POST storno admin no reason", s.send("admin", "POST", f"/admin/fakturace/{i2}/storno", csrf=True, data={"reason": ""})))
        out.append(("POST storno admin no csrf", s.send("admin", "POST", f"/admin/fakturace/{i2}/storno", data={"reason": "e2e"})))
        out.append(("POST storno admin ok", s.send("admin", "POST", f"/admin/fakturace/{i2}/storno", csrf=True, data={"reason": "e2e test"})))
        out.append(("POST storno admin again", s.send("admin", "POST", f"/admin/fakturace/{i2}/storno", csrf=True, data={"reason": "e2e test"})))
        out.append(("POST storno a paid invoice", s.send("admin", "POST", f"/admin/fakturace/{i1}/storno", csrf=True, data={"reason": "e2e test"})))
        out.append(("POST storno a storno row", s.send("admin", "POST", "/admin/fakturace/16/storno", csrf=True, data={"reason": "e2e test"})))
        out.append(("POST storno workspace-deleted invoice", s.send("admin", "POST", "/admin/fakturace/18/storno", csrf=True, data={"reason": "e2e test"})))
        out.append(("GET admin page after changes", s.send("admin", "GET", "/admin/fakturace")))
        out.append(("GET admin page month this", s.send("admin", "GET", "/admin/fakturace?mesic=2026-11")))
        out.append(("GET /predplatne h1", s.send("h1", "GET", "/predplatne")))
        out.append(("GET /predplatne cenek (has storno)", s.send("cenek", "GET", "/predplatne")))
        for who in ("h1", "alfa", "cenek", "admin", None):
            out.append((f"GET own/other invoice pdf {i1} as {who}", s.send(who, "GET", f"/predplatne/faktury/{i1}.pdf")))
            out.append((f"GET storno pdf {i2} as {who}", s.send(who, "GET", f"/predplatne/faktury/{i2}.pdf")))
        for who in ("h1", "admin"):
            out.append((f"GET /admin/fakturace/{i1}.pdf as {who}", s.send(who, "GET", f"/admin/fakturace/{i1}.pdf")))
            out.append((f"GET /admin/fakturace/export as {who}", s.send(who, "GET", "/admin/fakturace/export?mesic=2026-11")))
            out.append((f"GET /admin/fakturace/export-vse as {who}", s.send(who, "GET", "/admin/fakturace/export-vse")))
        out.append(("POST /admin/fakturace/vypis no file", s.send("admin", "POST", "/admin/fakturace/vypis", csrf=True, data={})))
        return out

    def passkey_ceremony(s):
        import importlib.util
        spec = importlib.util.spec_from_file_location("pk", os.path.join(ROOT, "App", "scripts", "go_passkeys_golden.py"))
        pk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pk)
        pk.RP_ID, pk.ORIGIN = "localhost", PUBLIC[s.name]
        from cryptography.hazmat.primitives.asymmetric import ec
        import secrets as _sec
        key, cred = ec.generate_private_key(ec.SECP256R1()), _sec.token_bytes(32)
        out = []
        o = {"origin": BASE[s.name]}

        def chal(rec):
            try:
                d = json.loads(rec["raw"])
                return pk.base64url_to_bytes((d.get("publicKey") or d)["challenge"])
            except Exception:
                return None

        r = s.send("pkuser", "POST", "/account/passkeys/options", csrf=True, json_body={})
        out.append(("passkey register options (own session)", r))
        c = chal(r)
        if c:
            try:
                pk.USER_HANDLE = pk.base64url_to_bytes(json.loads(r["raw"])["user"]["id"])
            except Exception:
                pass
            cred_reg = pk._register(key, cred, c)
            out.append(("passkey register bad origin", s.send("pkuser", "POST", "/account/passkeys", csrf=True, json_body={"credential": dict(cred_reg, response=dict(cred_reg["response"], clientDataJSON=pk._b64(pk._client_data("webauthn.create", c).replace(PUBLIC[s.name].encode(), b"https://evil.example")))), "name": "evil"})))
            r2 = s.send("pkuser", "POST", "/account/passkeys/options", csrf=True, json_body={})
            c = chal(r2) or c
            cred_reg = pk._register(key, cred, c)
            out.append(("passkey register ok", s.send("pkuser", "POST", "/account/passkeys", csrf=True, json_body={"credential": cred_reg, "name": "e2e key"})))
            out.append(("passkey register replay (spent challenge)", s.send("pkuser", "POST", "/account/passkeys", csrf=True, json_body={"credential": cred_reg, "name": "e2e key"})))
            lo = s.send(None, "POST", "/login/passkey/options", csrf=True, json_body={})
            out.append(("passkey login options", lo))
            lc = chal(lo)
            if lc:
                assertion = pk._login(key, cred, lc)
                bad = json.loads(json.dumps(assertion))
                bad["response"]["signature"] = pk._b64(b"\x30\x06\x02\x01\x01\x02\x01\x01")
                out.append(("passkey login bad signature", s.send(None, "POST", "/login/passkey", csrf=True, json_body={"credential": bad})))
                lo2 = s.send(None, "POST", "/login/passkey/options", csrf=True, json_body={})
                lc2 = chal(lo2) or lc
                out.append(("passkey login ok", s.send("pklogin", "POST", "/login/passkey", csrf=True, json_body={"credential": pk._login(key, cred, lc2)})))
                out.append(("GET /dashboard/calendar after passkey login", s.send("pklogin", "GET", "/dashboard/calendar")))
                out.append(("passkey login replay (spent challenge)", s.send("pkreplay", "POST", "/login/passkey", csrf=True, json_body={"credential": pk._login(key, cred, lc2)})))
                lo3 = s.send(None, "POST", "/login/passkey/options", csrf=True, json_body={})
                lc3 = chal(lo3) or lc
                out.append(("passkey login unknown credential", s.send("pkother", "POST", "/login/passkey", csrf=True, json_body={"credential": pk._login(ec.generate_private_key(ec.SECP256R1()), _sec.token_bytes(32), lc3)})))
        out.append(("passkey delete by another host", s.send("cenek", "POST", "/account/passkeys/%d/delete" % 1, csrf=True)))
        out.append(("passkey rename by another host", s.send("cenek", "POST", "/account/passkeys/1/rename", csrf=True, data={"name": "x"})))
        return out

    def stripe_hooks(s):
        import hashlib, hmac
        sec = ENV_COMMON["UBYHOST_STRIPE_WEBHOOK_SECRET"].encode()

        def signed(body, ts=None):
            ts = int(time.time()) if ts is None else ts
            sig = hmac.new(sec, f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
            return {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}

        ev = json.dumps({"id": "evt_e2e_1", "type": "customer.created", "data": {"object": {}}}).encode()
        out = []
        out.append(("stripe valid signature, unknown type", s.send(None, "POST", "/webhooks/stripe", origin=None, headers=signed(ev), content=ev)))
        out.append(("stripe valid signature, duplicate event id", s.send(None, "POST", "/webhooks/stripe", origin=None, headers=signed(ev), content=ev)))
        out.append(("stripe wrong signature", s.send(None, "POST", "/webhooks/stripe", origin=None, headers=dict(signed(ev), **{"stripe-signature": "t=%d,v1=%s" % (time.time(), "0" * 64)}), content=ev)))
        out.append(("stripe old timestamp", s.send(None, "POST", "/webhooks/stripe", origin=None, headers=signed(ev, ts=int(time.time()) - 7200), content=ev)))
        out.append(("stripe body altered after signing", s.send(None, "POST", "/webhooks/stripe", origin=None, headers=signed(ev), content=ev + b" ")))
        out.append(("stripe missing signature header", s.send(None, "POST", "/webhooks/stripe", origin=None, content=ev, headers={"content-type": "application/json"})))
        return out

    def redirects(s):
        out = []
        for n in ["//evil.example", "https://evil.example/x", "/\\evil.example", "%2F%2Fevil.example", "/ok/path?x=1", "javascript:alert(1)"]:
            q = urllib.parse.quote(n, safe="/%:?=.")
            out.append((f"GET /login?next={n} as host", s.send("h1", "GET", f"/login?next={q}")))
            out.append((f"GET /account/accept?next={n} as host", s.send("h1", "GET", f"/account/accept?next={q}")))
            out.append((f"GET /login?next={n} anon", s.send(None, "GET", f"/login?next={q}")))
        return out

    def host_invoices(s):
        out = []
        a, b, c = seed["host_invoices"]
        E = {"reason": "e2e storno", "correction_date": ""}
        for who in ("h1", "alfa", "admin", None):
            out.append((f"GET /invoices/{a} as {who}", s.send(who, "GET", f"/invoices/{a}")))
            out.append((f"GET /invoices/{a}.pdf as {who}", s.send(who, "GET", f"/invoices/{a}.pdf")))
        out.append(("GET /invoices list h1", s.send("h1", "GET", "/invoices")))
        out.append(("GET /invoices list alfa", s.send("alfa", "GET", "/invoices")))
        out.append(("GET /invoice/d/<valid token> anon", s.send(None, "GET", f"/invoice/d/{seed['host_invoice_token']}")))
        out.append(("GET /invoice/d/<garbage> anon", s.send(None, "GET", "/invoice/d/garbage")))
        out.append(("POST paid as other host alfa", s.send("alfa", "POST", f"/invoices/{a}/paid", csrf=True)))
        out.append(("POST paid no csrf", s.send("h1", "POST", f"/invoices/{a}/paid")))
        out.append(("POST paid evil origin", s.send("h1", "POST", f"/invoices/{a}/paid", csrf=True, origin="https://evil.example")))
        out.append(("POST paid anon", s.send(None, "POST", f"/invoices/{a}/paid", csrf=True)))
        out.append(("POST paid ok", s.send("h1", "POST", f"/invoices/{a}/paid", csrf=True)))
        out.append(("POST paid again", s.send("h1", "POST", f"/invoices/{a}/paid", csrf=True)))
        out.append(("POST paid unknown id", s.send("h1", "POST", "/invoices/99999/paid", csrf=True)))
        out.append(("POST cancel as other host alfa", s.send("alfa", "POST", f"/invoices/{b}/cancel", csrf=True, data=E)))
        out.append(("POST cancel no csrf", s.send("h1", "POST", f"/invoices/{b}/cancel", data=E)))
        out.append(("POST cancel no reason", s.send("h1", "POST", f"/invoices/{b}/cancel", csrf=True, data={"reason": ""})))
        out.append(("POST cancel ok", s.send("h1", "POST", f"/invoices/{b}/cancel", csrf=True, data=E)))
        out.append(("POST cancel again (already cancelled)", s.send("h1", "POST", f"/invoices/{b}/cancel", csrf=True, data=E)))
        out.append(("GET /invoices list after changes", s.send("h1", "GET", "/invoices")))
        out.append(("GET /invoices/new h1", s.send("h1", "GET", "/invoices/new")))
        out.append(("POST /invoices/preview empty", s.send("h1", "POST", "/invoices/preview", csrf=True, data={})))
        out.append(("POST /invoices empty", s.send("h1", "POST", "/invoices", csrf=True, data={})))
        out.append(("GET /invoices/{c}.pdf as h1 (untouched)", s.send("h1", "GET", f"/invoices/{c}.pdf")))
        return out

    def logout(s):
        return [("POST /logout no csrf", s.send("fl1", "POST", "/logout")),
                ("POST /logout csrf", s.send("fl1", "POST", "/logout", csrf=True)),
                ("GET /dashboard/calendar after logout", s.send("fl1", "GET", "/dashboard/calendar"))]

    return [("link", link_flow), ("2fa", twofa), ("login", login_basic), ("passkeys", passkeys),
            ("signup", signup), ("billing", billing_hooks), ("money", money), ("host-invoices", host_invoices), ("passkey-ceremony", passkey_ceremony), ("stripe", stripe_hooks), ("redirects", redirects), ("logout", logout)]


def mixed_flows(seed, sides):
    """Python and Go together, as in a route-by-route cutover. Rows are assertions, not py/go diffs."""
    py, go = sides["py"], sides["go"]
    rows = []

    def row(case, rec, expect_status, expect_loc=None):
        bad = []
        if rec.get("status") != expect_status:
            bad.append(f"status {rec.get('status')} expected {expect_status}")
        if expect_loc is not None and rec.get("headers", {}).get("location") != expect_loc:
            bad.append(f"location {rec.get('headers', {}).get('location')!r} expected {expect_loc!r}")
        rows.append({"area": "mixed", "case": case, "hard": bad, "soft": [], "py": rec.get("status"), "go": rec.get("status")})

    def cookie(side, who):
        return side.client(who).cookies.get("ubyhost_session", domain="127.0.0.1") or next((c.value for c in side.client(who).cookies.jar if c.name == "ubyhost_session"), None)

    def inject(side, who, value):
        side.client(who).cookies.set("ubyhost_session", value, domain="127.0.0.1")

    # A: log in on Go, use the cookie on Python (and the reverse)
    for a, b, who in ((go, py, "cenek"), (py, go, "alfa")):
        r = a.send("mx_" + who, "POST", "/login/link", csrf=True, data={"t": seed[who]["link"]})
        row(f"login via {a.name}, link POST", r, 303)
        ck = cookie(a, "mx_" + who)
        if ck:
            inject(b, "mx2_" + who, ck)
            row(f"{a.name}-issued session cookie accepted by {b.name} (authed = 422 here, anon = 303)", b.send("mx2_" + who, "GET", "/dashboard/calendar"), 422)
        else:
            rows.append({"area": "mixed", "case": f"login via {a.name} set no session cookie", "hard": ["no cookie"], "soft": [], "py": 0, "go": 0})
        # a logout on one side must end the session on the other (same DB in production)
    # B: CSRF token and nonce cookie from a Python form posted to Go, and the reverse
    for a, b in ((py, go), (go, py)):
        tok = a.csrf("mxcsrf_" + a.name)
        c = a.client("mxcsrf_" + a.name)
        nonce = next((x.value for x in c.cookies.jar if x.name == "ubyhost_csrf"), "")
        bc = b.client("mxcsrf_from_" + a.name)
        bc.cookies.set("ubyhost_csrf", nonce, domain="127.0.0.1")
        r = bc.post("/login", data={"email": "nobody@e2e.test", "_csrf": tok}, headers={"origin": PUBLIC[b.name]})
        row(f"CSRF token+nonce from {a.name} form accepted by {b.name} (200 page, not 303 form_expired)", record(r), 200)
    # C: 2FA pending token from Go consumed by Python and the reverse
    for a, b in ((go, py), (py, go)):
        first = a.send("mx2fa_" + a.name, "POST", "/login/link", csrf=True, data={"t": seed["h3"]["link"]})
        m = re.search(r'name="pending"\s+value="([^"]+)"', first.get("raw", "")) or re.search(r'value="([^"]+)"\s+name="pending"', first.get("raw", ""))
        if not m:
            rows.append({"area": "mixed", "case": f"no 2FA pending from {a.name}", "hard": ["no pending token"], "soft": [], "py": 0, "go": 0})
            break
        r = b.send("mx2fb_" + b.name, "POST", "/login/2fa", csrf=True, data={"pending": m.group(1), "code": totp(seed["h3"]["totp_secret"])})
        row(f"2FA pending issued by {a.name} accepted by {b.name} (303 + session cookie)", r, 303)
        rows[-1]["hard"] += [] if any(c[0] == "ubyhost_session" for c in r.get("cookies", [])) else ["no session cookie set"]
        break  # h3 has one link only; do the first direction
    return rows


MIXED_USERS = "'user2', 'user4', 'host-three'"  # accounts the mixed Python<->Go flows log in (one side only)
DB_QUERIES = {
    "invoice": "SELECT id, owner_user_id, kind, corrects_invoice_id, number, total_haler, paid_on IS NOT NULL AS paid, marked_paid_at IS NOT NULL AS marked, correction_reason FROM invoice ORDER BY id",
    "platform_invoice": "SELECT id, owner_user_id, kind, corrects_id, number, total_haler, voided, paid_on, paid_via FROM platform_invoice ORDER BY id",
    "billing_account": "SELECT owner_user_id, status, plan, billing_interval, apartments_billed, cancel_at_period_end, carry_czk FROM billing_account ORDER BY owner_user_id",
    "audit": "SELECT action, CASE WHEN action IN ('guest_details_mail_on', 'guest_details_mail_off', 'stay_fee_emails_on', 'stay_fee_emails_off') THEN '*' ELSE actor END, owner_user_id, regexp_replace(detail, '[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.+Z-]*', 'TS', 'g') FROM audit WHERE NOT (action IN ('login', 'two_factor_login', 'two_factor_failed') AND (owner_user_id IN (SELECT id FROM user_account WHERE username IN ({mx})) OR actor IN ({mx}))) ORDER BY action, actor, owner_user_id, detail",
    "login_token": "SELECT user_account_id, purpose, remember, used_at IS NOT NULL AS used FROM login_token WHERE user_account_id NOT IN (SELECT id FROM user_account WHERE username IN ({mx})) ORDER BY user_account_id, purpose, used",
    "user_account": "SELECT id, username, role, active, session_version FROM user_account ORDER BY id",
    "legal_acceptance": "SELECT user_account_id, document, version, method FROM legal_acceptance ORDER BY 1,2,3",
    "email_outbox": "SELECT kind, owner_user_id, state FROM email_outbox ORDER BY kind, owner_user_id, state",
    "stripe_webhook_event": "SELECT event_type, mode FROM stripe_webhook_event ORDER BY 1,2",
    "passkey": "SELECT user_account_id FROM passkey ORDER BY 1",
}


def db_snapshot(dbname):
    out = {}
    for t, q in DB_QUERIES.items():
        r = subprocess.run([PSQL, PG + "/" + dbname, "-At", "-F", "|", "-c", q.replace("{mx}", MIXED_USERS)], capture_output=True, text=True)
        out[t] = r.stdout.splitlines() if r.returncode == 0 else ["ERROR " + r.stderr.strip()[:200]]
    return out


def db_compare(seed=None):
    """Rows each table holds after the same request sequence; any difference is a hard failure."""
    py, go = db_snapshot("e2e_py"), db_snapshot("e2e_go")
    rows = []
    for t in DB_QUERIES:
        a, b = py[t], go[t]
        only_py = [x for x in a if x not in b][:5]
        only_go = [x for x in b if x not in a][:5]
        hard = [] if a == b else [f"{t}: py {len(a)} rows, go {len(b)} rows; only py: {only_py}; only go: {only_go}"]
        rows.append({"area": "db-state", "case": t, "hard": hard, "soft": [], "py": len(a), "go": len(b)})
    # every other table: row counts must agree (finds side effects one side does not have)
    def counts(dbn):
        r = subprocess.run([PSQL, PG + "/" + dbn, "-At", "-c",
                            "SELECT table_name, (xpath('/row/c/text()', query_to_xml('SELECT count(*) AS c FROM ' || quote_ident(table_name), false, true, '')))[1]::text "
                            "FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1"], capture_output=True, text=True)
        return dict(line.split("|") for line in r.stdout.splitlines() if "|" in line)
    cp, cg = counts("e2e_py"), counts("e2e_go")
    skip = set(DB_QUERIES) | {"rate_limit_event", "console_mail_log", "goose_db_version", "schema_history", "request_log", "job_run", "job"}
    for t in sorted(set(cp) | set(cg)):
        if t in skip:
            continue
        if cp.get(t) != cg.get(t):
            rows.append({"area": "db-state", "case": "count " + t, "hard": [f"{t}: py {cp.get(t)} rows, go {cg.get(t)} rows"], "soft": [], "py": 0, "go": 0})
    if seed:
        i1, i2, _ = seed["invoices"]
        for name, dbn in (("py", "e2e_py"), ("go", "e2e_go")):
            def one(q, dbn=dbn):
                r = subprocess.run([PSQL, PG + "/" + dbn, "-At", "-c", q], capture_output=True, text=True)
                return r.stdout.strip()
            checks = [
                (f"invoice {i1} marked paid", one(f"SELECT paid_on IS NOT NULL FROM platform_invoice WHERE id={i1}") == "t"),
                (f"invoice {i2} voided", one(f"SELECT voided FROM platform_invoice WHERE id={i2}") in ("1", "t")),
                (f"one storno row with negative total for invoice {i2} (double submit made no second)", int(one(f"SELECT COUNT(*) FROM platform_invoice WHERE kind='storno' AND corrects_id={i2} AND total_haler<0") or 0) == 1),
                ("paid invoice was not stornoed", int(one(f"SELECT COUNT(*) FROM platform_invoice WHERE corrects_id={i1}") or 0) == 0),
                ("h1 passkey stored by the ceremony", int(one("SELECT COUNT(*) FROM passkey WHERE user_account_id=(SELECT id FROM user_account WHERE username='host-one')") or 0) == 1),
                ("host invoice A marked paid", one(f"SELECT marked_paid_at IS NOT NULL FROM invoice WHERE id={seed['host_invoices'][0]}") == "t"),
                ("host invoice B cancelled by exactly one storno with negative total", int(one(f"SELECT COUNT(*) FROM invoice WHERE kind='storno' AND corrects_invoice_id={seed['host_invoices'][1]} AND total_haler<0") or 0) == 1),
                ("host invoice C untouched", one(f"SELECT marked_paid_at IS NULL FROM invoice WHERE id={seed['host_invoices'][2]}") == "t"),
                ("a login link was spent", int(one("SELECT COUNT(*) FROM login_token WHERE used_at IS NOT NULL") or 0) >= 1),
            ]
            for label, ok in checks:
                rows.append({"area": "db-expect-" + name, "case": label, "hard": [] if ok else [f"FAILED on {name}: {label}"], "soft": [], "py": int(ok), "go": int(ok)})
    return rows


# Substrings of hard-difference messages that are accepted and documented (K1, K2 in the parity doc).
KNOWN = [
    "location: py='/settings/phone' go='/settings#settings-group-phone'",   # K1: push device delete lands on /settings#phone (Go) instead of /settings/phone (Python)
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    ap.add_argument("--flows-only", action="store_true")
    ap.add_argument("--go-paths", help="only sweep routes Caddy would send to Go for this UBYHOST_GO_PATHS value")
    a = ap.parse_args()
    seed = setup_databases()
    procs = start_servers()
    rows = []
    try:
        sides = {"py": Side("py", seed), "go": Side("go", seed)}
        rows += mixed_flows(seed, sides)  # first: before the 2FA brute-force cases fill the IP rate limit; DB queries below skip its users
        if not a.flows_only:
            for name, who, m, path, kw in sweep_cases(a.go_paths.replace('"', "").split() if a.go_paths else None):
                rec = {k: sides[k].send(who, m, path, **kw) for k in ("py", "go")}
                hard, soft = compare(rec["py"], rec["go"])
                rows.append({"area": "sweep", "case": name, "hard": hard, "soft": soft, "py": rec["py"].get("status"), "go": rec["go"].get("status")})
        for area, fn in flows(seed):
            res = {k: fn(sides[k]) for k in ("py", "go")}
            for (label, p), (_, g) in zip(res["py"], res["go"]):
                hard, soft = compare(p, g)
                rows.append({"area": area, "case": label, "hard": hard, "soft": soft, "py": p.get("status"), "go": g.get("status")})
        rows += db_compare(seed)
    finally:
        stop(procs)
    for r in rows:  # documented, accepted differences (docs/plans/go-parity-suite.md, "Known differences")
        if r["hard"] and all(any(k in x for k in KNOWN) for x in r["hard"]):
            r["soft"] = ["KNOWN: " + x for x in r["hard"]] + r["soft"]
            r["hard"] = []
    bad = [r for r in rows if r["hard"]]
    print(f"{len(rows)} cases, {len(bad)} with hard differences, {sum(1 for r in rows if r['soft'] and not r['hard'])} with soft differences only")
    for r in bad:
        print(f"HARD [{r['area']}] {r['case']}: " + "; ".join(r["hard"])[:300])
    if a.report:
        json.dump(rows, open(a.report, "w"), indent=1)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
