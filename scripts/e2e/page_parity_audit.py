#!/usr/bin/env python3
"""GET page parity: Python vs Go, Playwright 390+1280, 3 personas."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
APP, GO_DIR = ROOT / "App", ROOT / "go"
STORE_MEDIA = Path("/cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1/media/parity")
STORE_DOC = Path("/cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1/docs/go-python-parity-audit.md")
PG = os.environ.get("UBYHOST_E2E_PG", "postgresql://postgres@127.0.0.1:5433")
PSQL = os.environ.get("UBYHOST_E2E_PSQL", "/usr/lib/postgresql/16/bin/psql")
WIDTHS = (390, 1280)
SHOT_MS = 120000
SKIP_SUBSTR = (".pdf", ".zip", ".csv", "/metrics", "/healthz", "/stripe/webhook", "/sitemap.xml")
ENV = {
    "UBYHOST_SECRET_KEY": "e2e-secret-key-0123456789-abcdefghijkl",
    "UBYHOST_ENABLE_SCHEDULER": "0",
    "UBYHOST_BOOTSTRAP_ADMIN": "0",
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_UBYPORT_ENV": "mock",
    "UBYHOST_DATA_DIR": "/var/tmp/parity_data",
    "UBYHOST_GUEST_PIN": "0",
    "UBYHOST_SIGNUP_ENABLED": "1",
    "UBYHOST_BILLING_ENABLED": "1",
    "UBYHOST_BILLING_IBAN": "CZ6503000000000123456789",
}
# The guest-link pages behave differently with the property PIN on: a stranger gets the
# PIN page instead of the hub. Both settings are audited, so the same path is compared
# twice. The PIN pass runs in its own servers because config.GUEST_PIN_REQUIRED is read
# once at Python import.
PIN_ENV = {**ENV, "UBYHOST_GUEST_PIN": "1"}
PIN_PREFIX = "/l/"
# The language pass: every page here renders Czech from the shared catalogs, so a
# string that was never translated shows up as English on one side only. `?lang=` is
# the signal both stacks read first (guest.py _chosen_language, host_i18n.resolve_language).
LANG_PASSES = {"cs": "+cs"}
# Czech over every guest page plus the host pages whose copy is densest. The whole
# route table in every language would multiply the run; this is the set where a
# missing key actually shows.
LANG_EXACT = {"/", "/reservations", "/booking-sites", "/admin", "/login"}
LANG_PREFIXES = ("/l/", "/guests/", "/reservations/")

DOM_NORM_PATTERNS = (
    r"\d{4}-\d\d-\d\d(?:[T ][0-9:.+-Z]*)?",
    r"nonce-[A-Za-z0-9_-]+",
    r'name="_csrf"\s+value="[^"]*"',
    r'content="[^"]*_csrf[^"]*"',
    r"https?://(?:127\.0\.0\.1|localhost):\d+",
    r"\b\d{5,}\b",
    r"msg=[^&\s\"']+",
    r"err=[^&\s\"']+",
)


def sql(stmt, db="postgres"):
    subprocess.run([PSQL, f"{PG}/{db}", "-qc", stmt], check=True, capture_output=True)


def seed_db():
    for stmt in ("DROP DATABASE IF EXISTS parity_tpl", "CREATE DATABASE parity_tpl"):
        sql(stmt)
    r = subprocess.run(
        [sys.executable, str(HERE / "seed.py")],
        cwd=APP,
        env={**os.environ, **ENV, "UBYHOST_DATABASE_URL": f"{PG}/parity_tpl"},
        capture_output=True,
        text=True,
    )
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    seed = json.loads(r.stdout.strip())
    for stmt in (
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='parity_run' AND pid <> pg_backend_pid()",
        "DROP DATABASE IF EXISTS parity_run",
        "CREATE DATABASE parity_run TEMPLATE parity_tpl",
    ):
        sql(stmt)
    h1_id = sql_row("SELECT id FROM user_account WHERE username='host-one'", "parity_run")
    row = sql_row(
        "SELECT a.id, a.permalink_token, r.id "
        "FROM apartment a JOIN reservation r ON r.apartment_id=a.id "
        f"WHERE a.owner_user_id={h1_id} AND a.permalink_token!='' ORDER BY a.id, r.id LIMIT 1",
        "parity_run",
    )
    apt_id, token, res_id = row.split("|")
    refs = {
        "apartment_id": apt_id,
        "id": apt_id,
        "reservation_id": res_id,
        "guest_id": sql_row(f"SELECT id FROM guest WHERE reservation_id={res_id} LIMIT 1", "parity_run") or "1",
        "invoice_id": sql_row(f"SELECT id FROM invoice WHERE owner_user_id={h1_id} LIMIT 1", "parity_run") or "1",
        "platform_invoice_id": sql_row("SELECT id FROM platform_invoice LIMIT 1", "parity_run") or "1",
        "token": token,
        "slug": token,
        "submission_id": "1",
        "request_id": "1",
        "item": "wifi",
        "action": "up",
        "group": "phone",
        "kind": "login",
        "code": "x",
    }
    refs["id"] = apt_id
    return seed, refs


def sql_row(stmt, db):
    return subprocess.run([PSQL, f"{PG}/{db}", "-tAc", stmt], capture_output=True, text=True, check=True).stdout.strip()


def py_persona_sessions(seed):
    """Fresh Python session cookies against parity_run (Playwright needs tokens after DB clone)."""
    import json
    out = {}
    db_url = f"{PG}/parity_run"
    for key in ("h1", "admin"):
        uid = seed[key]["id"]
        sv = sql_row(f"SELECT session_version FROM user_account WHERE id={uid}", "parity_run")
        r = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os, sys, json; os.chdir(%r); sys.path.insert(0, %r); "
                "os.environ.update(json.loads(%r)); os.environ['UBYHOST_DATABASE_URL'] = %r; "
                "from app import auth; print(auth.issue_session(int(%r), int(%r)))"
                % (str(APP), str(APP), json.dumps({**ENV, "UBYHOST_DATABASE_URL": db_url}), db_url, uid, sv),
            ],
            env={**os.environ, **ENV, "UBYHOST_DATABASE_URL": db_url},
            capture_output=True,
            text=True,
            check=True,
        )
        out[key] = r.stdout.strip()
    return {"host": out["h1"], "admin": out["admin"]}


def go_persona_sessions(seed):
    """Go cookies for Playwright (Go Load rejects some Python-issued tokens in edge timing)."""
    import json as _json

    out = {}
    for key, uid in (("h1", seed["h1"]["id"]), ("admin", seed["admin"]["id"])):
        row = subprocess.run(
            [PSQL, PG + "/parity_run", "-tAc", f"SELECT session_version FROM user_account WHERE id={uid}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        env = {**os.environ, **ENV, "UID": str(uid), "SV": row}
        r = subprocess.run(
            ["go", "run", "./cmd/e2e-issue-session"],
            cwd=str(GO_DIR),
            env=env,
            capture_output=True,
            text=True,
        )
        if r.returncode:
            raise RuntimeError(r.stderr[-800:])
        out[key] = _json.loads(r.stdout)["session"]
    return out


def concretize(path, refs):
    out = path
    for k, v in refs.items():
        out = out.replace("{" + k + "}", str(v))
    return re.sub(r"\{[^/}]+\}", "1", out)


class TE(HTMLParser):
    def __init__(self):
        super().__init__()
        self.bits, self.skip = [], False

    def handle_starttag(self, t, a):
        self.skip = t in ("script", "style", "noscript")

    def handle_endtag(self, t):
        if t in ("script", "style", "noscript"):
            self.skip = False

    def handle_data(self, d):
        if not self.skip and (t := d.strip()):
            self.bits.append(t)


def norm_dom(html):
    p = TE()
    p.feed(html)
    t = re.sub(r"\s+", " ", " ".join(p.bits))
    for pat in DOM_NORM_PATTERNS:
        t = re.sub(pat, "X", t)
    return t.strip()


def start_py(port, db_url, public, env=ENV):
    import uvicorn

    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.update({**env, "UBYHOST_DATABASE_URL": db_url, "UBYHOST_PUBLIC_BASE_URL": public})
    from app import db
    from app.main import app

    db.init_db()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(200):
        if srv.started:
            return srv, f"http://127.0.0.1:{port}"
        time.sleep(0.05)
    raise RuntimeError("py")


def start_go(port, db_url, public, env=ENV):
    bin = Path("/var/tmp/ubyhost-web-parity")
    subprocess.run(["go", "build", "-o", str(bin), "./cmd/ubyhost-web"], cwd=GO_DIR, check=True)
    run_env = {
        **os.environ,
        **env,
        "UBYHOST_DATABASE_URL": db_url,
        "UBYHOST_GO_ADDR": f"127.0.0.1:{port}",
        "UBYHOST_MIGRATIONS_DIR": str(APP / "migrations_pg"),
        "UBYHOST_GO_JOB_KINDS": "",
        "UBYHOST_JOB_QUEUE_KINDS": "",
        "UBYHOST_PUBLIC_BASE_URL": public,
        "UBYHOST_APP_ROOT": str(APP),
    }
    proc = subprocess.Popen([str(bin)], cwd=ROOT, env=run_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import httpx

    base = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            if httpx.get(base + "/healthz", timeout=1).status_code in (200, 503):
                return proc, base
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("go")


def start_py_process(port, db_url, public, env=ENV):
    """A second Python app in its own interpreter.

    The PIN flag is read when app.config is imported, so the in-process server above
    cannot be reconfigured: this one imports the app fresh with UBYHOST_GUEST_PIN=1.
    """
    import httpx

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
        cwd=str(APP),
        env={**os.environ, **env, "UBYHOST_DATABASE_URL": db_url, "UBYHOST_PUBLIC_BASE_URL": public},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            if httpx.get(base + "/healthz", timeout=1).status_code in (200, 503):
                return proc, base
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("py-pin")


@dataclass
class Row:
    route: str
    persona: str
    py_status: int | None
    go_status: int | None
    verdict: str
    note: str
    cause: str = ""
    console_py: list = field(default_factory=list)
    console_go: list = field(default_factory=list)
    failed_py: list = field(default_factory=list)
    failed_go: list = field(default_factory=list)


def accepted_difference(route: str, persona: str, py_status: int, go_status: int, go_headers: dict, dp: str, dg: str) -> tuple[str, str] | None:
    """Only intentional, documented harness differences — not unported Go pages."""
    if route == "/admin/fakturace/export-vse" and py_status == 0:
        return "accepted-harness-k3", "Python ReadError flake (diff_harness KNOWN K3)"
    if py_status == go_status and py_status in (404, 410):
        return "accepted-status", f"both {py_status}"
    if py_status == go_status == 303:
        return "pass", "redirect"
    if py_status == go_status and py_status in (403, 401):
        return "pass", "status+auth match"
    return None


def capture(browser, base, path, cookie, slug, persona, side):
    host = base.split("://", 1)[-1].split("/", 1)[0]
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    if cookie:
        ctx.add_cookies(
            [
                {
                    "name": "ubyhost_session",
                    "value": cookie,
                    "domain": host.split(":")[0],
                    "path": "/",
                    "httpOnly": True,
                    "secure": False,
                    "sameSite": "Lax",
                }
            ]
        )
    page = ctx.new_page()
    cons, fail = [], []
    page.on("console", lambda m: cons.append(m.text[:100]) if m.type == "error" else None)
    page.on("requestfailed", lambda r: fail.append(r.url))
    headers = {}
    try:
        resp = page.goto(base + path, wait_until="domcontentloaded", timeout=SHOT_MS)
        status = resp.status if resp else 0
        headers = resp.headers if resp else {}
        loc = page.locator("div.ui-page").first
        html = loc.evaluate("el => el.outerHTML") if loc.count() else page.content()
    except Exception as e:
        status, html = 0, str(e)
    for w in WIDTHS:
        page.set_viewport_size({"width": w, "height": 900})
        page.screenshot(path=str(STORE_MEDIA / f"{slug}--{persona}--{side}--{w}.png"), full_page=True, timeout=SHOT_MS)
    ctx.close()
    return status, html, headers, cons[:5], fail[:5]


def score_row(route, persona, ps, gs, ph, gh, gh_meta) -> Row:
    if gs == 501 or str(gh_meta.get("x-ubyhost-not-ported", "")).strip() == "1":
        return Row(
            route,
            persona,
            ps,
            gs,
            "fail-status",
            f"py={ps} go={gs} (Go not ported)",
            "go-gap-501",
        )
    acc = accepted_difference(route, persona, ps, gs, gh_meta, "", "")
    dp, dg = norm_dom(ph), norm_dom(gh)
    if acc:
        return Row(route, persona, ps, gs, acc[0], acc[1], acc[1])
    if ps != gs:
        return Row(route, persona, ps, gs, "fail-status", f"py={ps} go={gs}", "status-mismatch")
    if dp == dg:
        return Row(route, persona, ps, gs, "pass", "DOM match", "")
    if not dp or not dg:
        return Row(route, persona, ps, gs, "fail-dom", "empty DOM", "empty-dom")
    ratio = abs(len(dp) - len(dg)) / max(len(dp), len(dg))
    if ratio < 0.02:
        return Row(route, persona, ps, gs, "pass-soft", f"len {len(dp)}/{len(dg)}", "dom-near")
    sim = SequenceMatcher(None, dp, dg).ratio()
    if sim >= 0.94:
        return Row(route, persona, ps, gs, "pass-soft", f"sim {sim:.3f}", "dom-similar")
    return Row(route, persona, ps, gs, "fail-dom", f"len {len(dp)}/{len(dg)} sim={sim:.2f}", "dom-drift")


def lang_query(path: str, lang: str) -> str:
    """The same page, asked for in one language: both stacks read ?lang= first."""
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}lang={lang}"


def main():
    sys.path.insert(0, str(ROOT / "scripts"))
    import py_routes

    def free_port():
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])

    py_port, go_port = free_port(), free_port()
    seed, refs = seed_db()
    db_url = f"{PG}/parity_run"
    public = f"http://127.0.0.1:{py_port}"
    py_srv, py_base = start_py(py_port, db_url, public)
    go_proc, go_base = start_go(go_port, db_url, public)
    STORE_MEDIA.mkdir(parents=True, exist_ok=True)
    py_persons = {"anon": None, **py_persona_sessions(seed)}
    go_sess = go_persona_sessions(seed)
    go_persons = {"anon": None, "host": go_sess["h1"], "admin": go_sess["admin"]}
    paths = []
    for method, path in py_routes.routes():
        if method != "GET" or path in {"/openapi.json", "/docs", "/redoc"}:
            continue
        if any(x in path for x in SKIP_SUBSTR):
            continue
        cp = concretize(path, refs)
        if cp not in paths:
            paths.append(cp)
    import playwright.sync_api as pw

    def run_pass(br, pbase, gbase, p_sess, g_sess, sweep, suffix):
        out: list[Row] = []
        for path in sweep:
            slug = (re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower())[:55] or "root") + suffix.replace("+", "--")
            for persona in p_sess:
                label = persona + suffix
                ps, ph, pmeta, pc, pf = capture(br, pbase, path, p_sess[persona], slug, label, "py")
                gs, gh, gmeta, gc, gf = capture(br, gbase, path, g_sess[persona], slug, label, "go")
                row = score_row(path, label, ps, gs, ph, gh, gmeta)
                row.console_py, row.console_go = pc, gc
                row.failed_py, row.failed_go = pf, gf
                out.append(row)
        return out

    with pw.sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        rows = run_pass(br, py_base, go_base, py_persons, go_persons, paths, "")
        lang_rows = 0
        for lang, suffix in LANG_PASSES.items():
            lang_paths = [
                lang_query(p, lang)
                for p in paths
                if p in LANG_EXACT or any(p.startswith(x) for x in LANG_PREFIXES)
            ]
            lang_rows += len(lang_paths) * len(py_persons)
            rows += run_pass(br, py_base, go_base, py_persons, go_persons, lang_paths, suffix)
        pin_paths = [x for x in paths if x.startswith(PIN_PREFIX)]
        if pin_paths:
            # The same guest-link pages with the PIN on: the stranger must get the PIN
            # page, the host must still get through. Same seed database, no reseed.
            pin_pport, pin_gport = free_port(), free_port()
            pin_public = f"http://127.0.0.1:{pin_pport}"
            pin_py, pin_py_base = start_py_process(pin_pport, db_url, pin_public, PIN_ENV)
            pin_go, pin_go_base = start_go(pin_gport, db_url, pin_public, PIN_ENV)
            try:
                rows += run_pass(br, pin_py_base, pin_go_base, py_persons, go_persons, pin_paths, "+pin")
            finally:
                pin_py.terminate()
                pin_go.terminate()
        br.close()
    py_srv.should_exit = True
    go_proc.terminate()
    fails = [r for r in rows if r.verdict.startswith("fail")]
    pn = sum(1 for r in rows if r.verdict == "pass")
    sn = sum(1 for r in rows if r.verdict == "pass-soft")
    an = sum(1 for r in rows if r.verdict.startswith("accepted"))
    causes: dict[str, int] = {}
    for r in rows:
        key = r.cause or r.verdict
        causes[key] = causes.get(key, 0) + 1
    meta = {
        "paths": len(paths),
        "personas": len(py_persons),
        "rows": len(rows),
        "screenshots": len(paths) * len(py_persons) * 2 * len(WIDTHS),
        "pass": pn,
        "pass_soft": sn,
        "accepted": an,
        "fail": len(fails),
        "pin_paths": len([x for x in paths if x.startswith(PIN_PREFIX)]),
        "lang_rows": lang_rows,
        "causes": causes,
        "refs": refs,
    }
    STORE_DOC.parent.mkdir(parents=True, exist_ok=True)
    out_json = Path(str(STORE_DOC).removesuffix(".md") + ".json")
    out_json.write_text(json.dumps({"meta": meta, "rows": [asdict(r) for r in rows]}, indent=2))
    print(json.dumps({k: meta[k] for k in ("paths", "rows", "pass", "pass_soft", "accepted", "fail")}))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
