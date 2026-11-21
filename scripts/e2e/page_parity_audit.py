#!/usr/bin/env python3
"""GET page parity: Python vs Go, Playwright 390+1280, 3 personas."""
from __future__ import annotations
import json, os, re, socket, subprocess, sys, threading, time
from dataclasses import asdict, dataclass
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
ENV = {"UBYHOST_SECRET_KEY": "e2e-secret-key-0123456789-abcdefghijkl", "UBYHOST_ENABLE_SCHEDULER": "0",
       "UBYHOST_BOOTSTRAP_ADMIN": "0", "UBYHOST_MAIL_BACKEND": "console", "UBYHOST_UBYPORT_ENV": "mock",
       "UBYHOST_DATA_DIR": "/var/tmp/parity_data", "UBYHOST_GUEST_PIN": "0", "UBYHOST_SIGNUP_ENABLED": "1",
       "UBYHOST_BILLING_ENABLED": "1", "UBYHOST_BILLING_IBAN": "CZ6503000000000123456789"}


def sql(stmt, db="postgres"):
    subprocess.run([PSQL, f"{PG}/{db}", "-qc", stmt], check=True, capture_output=True)


def seed_db():
    for stmt in ("DROP DATABASE IF EXISTS parity_tpl", "CREATE DATABASE parity_tpl"):
        sql(stmt)
    r = subprocess.run([sys.executable, str(HERE / "seed.py")], cwd=APP,
        env={**os.environ, **ENV, "UBYHOST_DATABASE_URL": f"{PG}/parity_tpl"}, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    seed = json.loads(r.stdout.strip())
    for stmt in ("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='parity_run' AND pid <> pg_backend_pid()",
                 "DROP DATABASE IF EXISTS parity_run", "CREATE DATABASE parity_run TEMPLATE parity_tpl"):
        sql(stmt)
    refs = {"apartment_id": sql_row("SELECT id FROM apartment WHERE permalink_token!='' LIMIT 1", "parity_run"),
            "reservation_id": sql_row("SELECT id FROM reservation LIMIT 1", "parity_run"),
            "guest_id": sql_row("SELECT id FROM guest LIMIT 1", "parity_run"),
            "invoice_id": sql_row("SELECT id FROM invoice LIMIT 1", "parity_run"),
            "platform_invoice_id": sql_row("SELECT id FROM platform_invoice LIMIT 1", "parity_run"),
            "token": sql_row("SELECT permalink_token FROM apartment WHERE permalink_token!='' LIMIT 1", "parity_run"),
            "slug": sql_row("SELECT permalink_token FROM apartment WHERE permalink_token!='' LIMIT 1", "parity_run"),
            "submission_id": "1", "request_id": "1", "item": "wifi", "action": "up", "group": "phone", "kind": "login", "id": "1", "code": "x"}
    return seed, refs


def sql_row(stmt, db):
    return subprocess.run([PSQL, f"{PG}/{db}", "-tAc", stmt], capture_output=True, text=True, check=True).stdout.strip()


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
    for pat in (r"\d{4}-\d\d-\d\d", r"nonce-[A-Za-z0-9_-]+", r'name="_csrf"\s+value="[^"]*"'):
        t = re.sub(pat, "X", t)
    return t.strip()


def start_py(port, db_url, public):
    import uvicorn
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    from app import db
    from app.main import app
    os.environ.update({**ENV, "UBYHOST_DATABASE_URL": db_url, "UBYHOST_PUBLIC_BASE_URL": public})
    db.init_db()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(200):
        if srv.started:
            return srv, f"http://127.0.0.1:{port}"
        time.sleep(0.05)
    raise RuntimeError("py")


def start_go(port, db_url, public):
    bin = Path("/var/tmp/ubyhost-web-parity")
    subprocess.run(["go", "build", "-o", str(bin), "./cmd/ubyhost-web"], cwd=GO_DIR, check=True)
    env = {**os.environ, **ENV, "UBYHOST_DATABASE_URL": db_url, "UBYHOST_GO_ADDR": f"127.0.0.1:{port}",
           "UBYHOST_MIGRATIONS_DIR": str(APP / "migrations_pg"), "UBYHOST_GO_JOB_KINDS": "", "UBYHOST_JOB_QUEUE_KINDS": "",
           "UBYHOST_PUBLIC_BASE_URL": public, "UBYHOST_APP_ROOT": str(APP)}
    proc = subprocess.Popen([str(bin)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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


@dataclass
class Row:
    route: str
    persona: str
    py_status: int | None
    go_status: int | None
    verdict: str
    note: str
    console_py: list
    console_go: list
    failed_py: list
    failed_go: list


def capture(browser, base, path, cookie, slug, persona, side):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    if cookie:
        ctx.add_cookies([{"name": "ubyhost_session", "value": cookie, "url": base + "/"}])
    page = ctx.new_page()
    cons, fail = [], []
    page.on("console", lambda m: cons.append(m.text[:100]) if m.type == "error" else None)
    page.on("requestfailed", lambda r: fail.append(r.url))
    try:
        resp = page.goto(base + path, wait_until="networkidle", timeout=SHOT_MS)
        status = resp.status if resp else 0
        html = page.content()
    except Exception as e:
        status, html = 0, str(e)
    for w in WIDTHS:
        page.set_viewport_size({"width": w, "height": 900})
        page.screenshot(path=str(STORE_MEDIA / f"{slug}--{persona}--{side}--{w}.png"), full_page=True, timeout=SHOT_MS)
    ctx.close()
    return status, html, cons[:5], fail[:5]


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
    py_srv, py_base = start_py(py_port, db_url, f"http://localhost:{py_port}")
    go_proc, go_base = start_go(go_port, db_url, f"http://localhost:{go_port}")
    STORE_MEDIA.mkdir(parents=True, exist_ok=True)
    persons = {"anon": None, "host": seed["h1"]["session"], "admin": seed["admin"]["session"]}
    paths = []
    for method, path in py_routes.routes():
        if method != "GET" or path in {"/openapi.json", "/docs", "/redoc"}:
            continue
        if any(x in path for x in SKIP_SUBSTR):
            continue
        cp = concretize(path, refs)
        if cp not in paths:
            paths.append(cp)
    rows = []
    import playwright.sync_api as pw
    with pw.sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        for path in paths:
            slug = re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower())[:55] or "root"
            for persona, cookie in persons.items():
                ps, ph, pc, pf = capture(br, py_base, path, cookie, slug, persona, "py")
                gs, gh, gc, gf = capture(br, go_base, path, cookie, slug, persona, "go")
                dp, dg = norm_dom(ph), norm_dom(gh)
                if ps != gs:
                    v, note = "fail-status", f"py={ps} go={gs}"
                elif dp == dg:
                    v, note = "pass", "DOM match"
                elif abs(len(dp) - len(dg)) / max(len(dp), 1) < 0.02:
                    v, note = "pass-soft", f"len {len(dp)}/{len(dg)}"
                else:
                    v, note = "fail-dom", f"len {len(dp)}/{len(dg)}"
                rows.append(Row(path, persona, ps, gs, v, note, pc, gc, pf, gf))
        br.close()
    py_srv.should_exit = True
    go_proc.terminate()
    fails = [r for r in rows if r.verdict.startswith("fail")]
    pn = sum(1 for r in rows if r.verdict == "pass")
    sn = sum(1 for r in rows if r.verdict == "pass-soft")
    meta = {"paths": len(paths), "personas": len(persons), "rows": len(rows), "screenshots": len(paths) * len(persons) * 2 * len(WIDTHS)}
    STORE_DOC.parent.mkdir(parents=True, exist_ok=True)
    Path(str(STORE_DOC) + ".json").write_text(json.dumps({"meta": meta, "rows": [asdict(r) for r in rows]}, indent=2))
    print(json.dumps(meta) + f" fail={len(fails)} pass={pn} soft={sn}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())