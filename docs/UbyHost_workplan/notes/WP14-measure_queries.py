"""Seed the demo data, or render host pages and count SQL statements.

usage: measure.py seed <db>   |   measure.py render <db> <outdir>
Run with cwd = <worktree>/App.
"""
import json, os, re, sqlite3, sys, tempfile
from pathlib import Path

mode, dbfile = sys.argv[1], sys.argv[2]
tmp = Path(tempfile.mkdtemp(prefix="wp14m-"))
os.environ["UBYHOST_DATA_DIR"] = str(tmp)
os.environ["UBYHOST_DB"] = dbfile
os.environ["UBYHOST_SECRET_KEY"] = "measure-secret-key-not-for-real-use"
os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
os.environ["UBYHOST_GUEST_PIN"] = "0"
os.environ["UBYHOST_BOOTSTRAP_ADMIN"] = "0"
os.environ["UBYHOST_UBYPORT_ENV"] = "mock"
os.environ["UBYHOST_MAIL_BACKEND"] = "console"
os.environ["UBYHOST_ICAL_ALLOW_PRIVATE"] = "1"
sys.path.insert(0, os.getcwd())

COUNT = {"stmts": 0, "queries": 0, "connects": 0}
_real_connect = sqlite3.connect

TRACE = []
def _trace(sql):
    TRACE.append(sql)
    COUNT["stmts"] += 1
    head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
    if head not in ("PRAGMA", "BEGIN", "COMMIT", "ROLLBACK"):
        COUNT["queries"] += 1

def counting_connect(*a, **k):
    conn = _real_connect(*a, **k)
    COUNT["connects"] += 1
    conn.set_trace_callback(_trace)
    return conn

sqlite3.connect = counting_connect

from app import auth, db, demo, config  # noqa

PASSWORD = "Measure-Password-123"
if mode == "seed":
    config.UBYPORT_ENV = "mock"
    db.init_db()
    owner = auth.create_account("measure-host", PASSWORD, "Measure", must_change_password=False)
    from app import acceptance
    demo.icalsync.fetch_feed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network"))
    print("seeded", demo.seed(owner))
    sys.exit(0)

from fastapi.testclient import TestClient
from app.main import app
from app import acceptance
acceptance.pending = lambda *a, **k: []  # as the test suite does
out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
stay = db.query_one(
    "SELECT r.id FROM reservation r JOIN guest g ON g.reservation_id = r.id "
    "GROUP BY r.id ORDER BY COUNT(g.id) DESC, r.id LIMIT 1")["id"]
stays = [r["id"] for r in db.query("SELECT id FROM reservation ORDER BY id")]
pages = {"dashboard": "/", "reservations": "/reservations", "stay": f"/reservations/{stay}",
         "stay_fees": "/stay-fees", "invoices": "/invoices"}
import datetime as _dt
_today = _dt.date.today()
pages["stay_fees_cur"] = f"/stay-fees?month={_today:%Y-%m}"
_prev = (_today.replace(day=1) - _dt.timedelta(days=1))
pages["stay_fees_prev"] = f"/stay-fees?month={_prev:%Y-%m}"
apt_ids = [r["id"] for r in db.query("SELECT id FROM apartment ORDER BY id")]
for aid in apt_ids:
    pages[f"fee_detail_{aid}"] = f"/stay-fees/{aid}?month={_today:%Y-%m}"
for sid in stays:
    pages[f"stay_{sid}"] = f"/reservations/{sid}"
with TestClient(app) as client:
    from app import security
    tok = re.search(r'<meta name="csrf-token" content="([^"]*)"', client.get("/l/does-not-exist").text).group(1)
    r = client.post("/login?lang=en", data={"username": "measure-host", "password": PASSWORD, security.CSRF_FIELD: tok},
                    follow_redirects=False)
    assert r.status_code == 303, r.status_code
    w = client.get("/", follow_redirects=False)  # warm-up
    assert w.status_code == 200, (w.status_code, w.headers.get("location"))
    result = {}
    for name, path in pages.items():
        for k in COUNT: COUNT[k] = 0
        TRACE.clear()
        resp = client.get(path, follow_redirects=False)
        result[name] = dict(COUNT, status=resp.status_code)
        if os.environ.get("MEASURE_TRACE") == name:
            import collections
            for q, n in collections.Counter(" ".join(t.split())[:150] for t in TRACE).most_common():
                print(n, q, file=sys.stderr)
        (out / f"{name}.html").write_text(resp.text)
print(json.dumps({k: v for k, v in result.items() if not k.startswith("stay_") or k.startswith("stay_fees")}, indent=1))
print("stay pages max queries", max(v["queries"] for k, v in result.items() if k.startswith("stay_") and not k.startswith("stay_fees")))
