"""Screenshot parity for the pages a signed-in person uses (brief 2028).

The audit (page_parity_audit.py) compares DOM text and markup; this compares
pixels, at the three widths the design rules care about. Both stacks run from
this checkout against the audit's seed database, and each gets the session
cookie *it* signed: Python and Go have separate session secrets, so one token
never authenticates both.

    python3 scripts/e2e/page_parity_visual.py                 # 390, 768, 1280
    PARITY_ONLY=home-host,admin-home python3 scripts/e2e/page_parity_visual.py
    PARITY_WIDTHS=390 python3 scripts/e2e/page_parity_visual.py

Run it with the audit's own interpreter and environment, the way the audit runs:

    source ~/.local/parity/env.sh          # PSQL, PATH, UBYHOST_E2E_PG
    cd App && .venv/bin/python ../scripts/e2e/page_parity_visual.py

Needs a Postgres at $UBYHOST_E2E_PG with the audit's privileges (the seed drops
and recreates parity_tpl / parity_run), Playwright with Chromium, and the Go
toolchain. Artifacts land in $PARITY_OUT (default ~/.local/parity/visual).
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "App"
OUT = Path(os.environ.get("PARITY_OUT", str(Path.home() / ".local/parity/visual")))

sys.path.insert(0, str(ROOT / "scripts" / "e2e"))
sys.path.insert(0, str(APP / "scripts"))
import page_parity_audit as audit  # noqa: E402
import go_page_parity_screenshots as shots  # noqa: E402

# One-shot state both stacks clear on first use (the security prompt banner).
PRE_SQL = ["UPDATE user_account SET two_factor_prompted_at = NULL"]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def cases(refs: dict, py: dict, go: dict) -> list[tuple[str, str, str | None, str | None]]:
    tok, res, guest = refs["token"], refs["reservation_id"], refs["guest_id"]
    return [
        ("home-anon", "/", None, None),
        ("home-host", "/", py["host"], go["h1"]),
        ("reservations-host", "/reservations", py["host"], go["h1"]),
        ("guest-detail-host", f"/guests/{guest}", py["host"], go["h1"]),
        ("guest-form-host", f"/reservations/{res}/guests/new", py["host"], go["h1"]),
        ("booking-sites-anon", "/booking-sites", None, None),
        ("login-en", "/login?lang=en", None, None),
        ("link-hub-anon", f"/l/{tok}", None, None),
        ("link-hub-host", f"/l/{tok}", py["host"], go["h1"]),
        ("link-stay-host", f"/l/{tok}/{res}", py["host"], go["h1"]),
        ("admin-home", "/admin", py["admin"], go["admin"]),
    ]


def main() -> int:
    only = {x for x in os.environ.get("PARITY_ONLY", "").split(",") if x}
    widths = tuple(int(w) for w in os.environ.get("PARITY_WIDTHS", "390,768,1280").split(","))
    seed, refs = audit.seed_db()
    py_port, go_port = free_port(), free_port()
    db_url = f"{audit.PG}/parity_run"
    public = f"http://127.0.0.1:{py_port}"
    _, py_base = audit.start_py(py_port, db_url, public)
    _, go_base = audit.start_go(go_port, db_url, public)
    py, go = audit.py_persona_sessions(seed), audit.go_persona_sessions(seed)

    rows = []
    for name, path, py_cookie, go_cookie in cases(refs, py, go):
        if only and name not in only:
            continue
        out_dir = OUT / name
        if out_dir.exists():
            shutil.rmtree(out_dir)
        for r in shots.run_case(
            name=name, path=path, out_dir=out_dir, py_base=py_base, go_base=go_base,
            widths=widths, cookie_name="ubyhost_session",
            py_cookie_value=py_cookie, go_cookie_value=go_cookie, pre_sql=PRE_SQL,
        ):
            rows.append({
                "case": name, "path": path, "width": r.width, "verdict": r.verdict,
                "max_delta": r.max_delta, "diff_pixels": r.diff_pixels, "note": r.note,
            })
            print(f"{name:22} {r.width:5} {r.verdict:9} max_delta={r.max_delta} "
                  f"diff_px={r.diff_pixels} {r.note}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "probe.json").write_text(json.dumps({"db": "parity_run", "rows": rows}, indent=1))
    tally = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("identical", "invisible", "visible")}
    print(json.dumps({"rows": len(rows), "verdicts": tally}))
    return 1 if tally["visible"] else 0


if __name__ == "__main__":
    sys.exit(main())
