"""Records Python's answers to POST /admin/users/{id}/export (brief 1510).

Run from App/: .venv/bin/python scripts/auth_export_golden.py
"""
import base64
import io
import json
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))

import auth_routes_golden as base  # noqa: E402

from app import db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
import go_host_i18n  # noqa: E402

OUT = base.PKG / "testdata" / "workspace_export.json"
FIXED = datetime(2099, 3, 4, 5, 6, 7, 890123, tzinfo=timezone.utc)
ENV = dict(base.ENV)
PDF_RECEIPT = base64.b64encode(b"%PDF-1.4 receipt\n").decode()
PDF_INV = b"%PDF-1.4 invoice one"

EXTRA_TABLES = ["apartment", "reservation", "guest", "submission", "invoice"]


def seed():
    rows = base.base_seed()
    rows += [
        ["apartment", {"id": 201, "owner_user_id": 2, "internal_name": "Studio", "legal_entity_id": 1,
                       "created_at": base.OLD}],
        ["reservation", {"id": 2011, "apartment_id": 201, "source": "ical", "uid": "u2011",
                         "date_from": "2026-02-01", "date_to": "2026-02-03", "status": "confirmed",
                         "created_at": base.OLD, "updated_at": base.OLD}],
        ["guest", {"id": 20111, "reservation_id": 2011, "surname": "Export", "first_name": "Guest",
                   "nationality": "CZE", "submit_state": "sent", "created_at": base.OLD, "updated_at": base.OLD}],
        ["submission", {"id": 101, "apartment_id": 201, "created_at": base.OLD, "state": "ok",
                        "receipt_pdf": PDF_RECEIPT}],
        ["invoice", {"id": 201, "legal_entity_id": 1, "owner_user_id": 2, "kind": "invoice", "seq_year": 2026,
                     "seq_no": 1, "number": "2026-0001", "vs": "2026000100", "lang": "cs", "vat_status": "non_payer",
                     "issue_date": "2026-05-01", "seller_name": "S", "seller_seat": "Seat", "buyer_name": "B",
                     "total_haler": 100, "created_at": base.OLD, "pdf_blob": PDF_INV.decode("latin-1")}],
    ]
    return rows


def cases():
    a = {"uid": 1}
    fresh = {"uid": 1, "iat": -60}
    stale = {"uid": 1, "iat": -3600}
    h = {"uid": 2}
    imp = {"uid": 1, "as": 2, "ast": -60, "iat": -60}
    origin = {"origin": "http://testserver"}
    P = "POST"
    path = "/admin/users/{}/export".format
    return [
        {"name": "export", "method": P, "path": path(2), "session": fresh},
        {"name": "export_stale", "method": P, "path": path(2), "session": stale, "lang": "cs"},
        {"name": "missing_user", "method": P, "path": path(99), "session": fresh},
        {"name": "export_empty", "method": P, "path": path(3), "session": fresh},
        {"name": "bad_id", "method": P, "path": "/admin/users/abc/export", "session": fresh},
        {"name": "bad_id_signed_out", "method": P, "path": "/admin/users/abc/export"},
        {"name": "host", "method": P, "path": path(2), "session": h, "lang": "cs"},
        {"name": "signed_out", "method": P, "path": path(2)},
        {"name": "no_csrf_same_site", "method": P, "path": path(2), "session": fresh, "csrf": False,
         "headers": origin},
        {"name": "no_csrf_cross_site", "method": P, "path": path(2), "session": fresh, "csrf": False},
        {"name": "export_impersonating", "method": P, "path": path(3), "session": imp},
    ]


base.WATCH.clear()
base.WATCH.update({
    "audit": "SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id",
})
for table in ["invoice", "submission", "guest", "reservation", "apartment"]:
    if table not in base.TABLES:
        base.TABLES.insert(0, table)


def run(case, seed):
    now = time.time()
    base.load_seed(seed, case.get("seed", []), now)
    patched = case.get("py_config", {})
    from app import config  # noqa: WPS433
    saved = {k: getattr(config, k) for k in patched}
    for k, v in patched.items():
        setattr(config, k, v)
    try:
        from app import auth, security  # noqa: WPS433
        cookies = []
        token = base.session_cookie(case.get("session"), now)
        if token:
            cookies.append(f"{auth.SESSION_COOKIE}={token}")
        if case.get("csrf", True):
            cookies.append(f"{security.CSRF_COOKIE}={base.NONCE}")
        if case.get("lang"):
            cookies.append(f"ubyhost_lang={case['lang']}")
        headers = {"cookie": "; ".join(cookies)} if cookies else {}
        headers.update(case.get("headers", {}))
        pairs = [tuple(p) for p in case.get("form", [])]
        if case.get("csrf", True) and case["method"] == "POST":
            pairs.append(("_csrf", base.CSRF_TOKEN))
        client = TestClient(app, base_url="http://testserver")
        url = case["path"] + (("?" + case["query"]) if case.get("query") else "")
        headers["content-type"] = "application/x-www-form-urlencoded"
        response = client.post(url, content=urlencode(pairs), headers=headers, follow_redirects=False)
        ct = response.headers.get("content-type", "")
        want = {
            "status": response.status_code,
            "location": response.headers.get("location"),
            "content_type": ct.split(";")[0] if ct else ct,
            "cache_control": response.headers.get("cache-control"),
            "content_disposition": response.headers.get("content-disposition"),
            "body": None if 300 <= response.status_code < 400 else response.text,
            "cookies": [base.parse_cookie(line, now) for line in response.headers.get_list("set-cookie")],
            "db": base.dump(),
        }
        if response.status_code == 200 and ct.startswith("application/zip"):
            want["body"] = None
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                want["zip_names"] = zf.namelist()
                manifest = json.loads(zf.read("manifest.json"))
                manifest.pop("generated_at", None)
                want["manifest"] = manifest
    finally:
        for k, v in saved.items():
            setattr(config, k, v)
    out = dict(case)
    out["want"] = want
    return out


def main() -> int:
    db.init_db()
    rows = seed()
    recorded = [run(case, rows) for case in cases()]
    out = {"secret": base.SECRET, "nonce": base.NONCE, "env": ENV, "fixed": FIXED.isoformat(),
           "seed": rows, "cases": recorded}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(base.REPO)}")
    catalog = base.PKG / "i18n.json"
    catalog.write_text(go_host_i18n.render(go_host_i18n.read_keys(base.PKG / "i18n_keys.txt")), encoding="utf-8")
    print(f"wrote {catalog.relative_to(base.REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())