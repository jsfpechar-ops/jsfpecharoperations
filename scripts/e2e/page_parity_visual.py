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
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "App"
OUT = Path(os.environ.get("PARITY_OUT", str(Path.home() / ".local/parity/visual")))

sys.path.insert(0, str(ROOT / "scripts" / "e2e"))
sys.path.insert(0, str(APP / "scripts"))
import page_parity_audit as audit  # noqa: E402
import go_page_parity_screenshots as shots  # noqa: E402
import parity_cases  # noqa: E402

# One-shot state both stacks clear on first use (the security prompt banner).
# Default: mark the prompt as shown so no modal covers a page. The modal case alone clears it.
PRE_SQL = ["UPDATE user_account SET two_factor_prompted_at = now()::text WHERE two_factor_prompted_at IS NULL"]
PRE_SQL_MODAL = ["UPDATE user_account SET two_factor_prompted_at = NULL"]
# Leon needs the feature, a key, and an entitled owner (the seed host is billing 'active'). Same for both stacks.
# The key is fake: a GET render never calls the AI provider (client is created lazily).
AI_ENV = {"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "parity-fake-key-not-used"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# The old 11 rows. They are anonymous or lang-less, so they run only with PARITY_GROUP=L.
def legacy_cases(refs: dict, py: dict, go: dict) -> list[tuple[str, str, str | None, str | None]]:
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


def fill(path: str, refs: dict, seed: dict, extra: dict | None = None) -> str:
    return path.format(
        apt=refs["apartment_id"], res=refs["reservation_id"], guest=refs["guest_id"],
        inv=refs["invoice_id"], hinv=seed["host_invoices"][-1], fee_a=seed["fee"]["a"],
        alfa=seed["alfa"]["id"], tok=refs["token"], **(extra or {}),
    )


def run_extra_seed(seed: dict, refs: dict) -> dict:
    """Brief 2041: synthetic populated data on parity_run. Skipped blocks are echoed from stderr."""
    env = {**os.environ, **audit.ENV, "UBYHOST_DATABASE_URL": f"{audit.PG}/parity_run"}
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/e2e/seed_parity_extra.py"), str(seed["h1"]["id"]),
         str(refs["apartment_id"]), str(refs["reservation_id"])],
        cwd=APP, env=env, capture_output=True, text=True, check=True,
    )
    for line in r.stderr.splitlines():
        print(line)
    return json.loads(r.stdout.strip().splitlines()[-1])


def table_cases(refs: dict, seed: dict, py: dict, go: dict, extra: dict | None = None):
    for name, path, persona, group in parity_cases.CASES + parity_cases.EXTRA_CASES:
        try:
            filled = fill(path, refs, seed, extra)
        except KeyError as exc:
            print(f"SKIPPED (seed block missing): {name} needs {exc}")
            continue
        if persona == "host":
            py_cookie, go_cookie = py["host"], go["h1"]
        elif persona == "anon_invite":
            py_cookie, go_cookie = None, None
        else:
            py_cookie, go_cookie = py["admin"], go["admin"]
        for lang in ("cs", "en"):
            sep = "&" if "?" in filled else "?"
            yield (f"{name}-{lang}", f"{filled}{sep}lang={lang}", py_cookie, go_cookie, group)


def _capture(playwright, base, path, width, dest, cookie, mask, texts, extra_cookies=None):
    """One screenshot. Returns dict(status, error, texts). Never raises on HTTP >= 400; masks QR images."""
    from tests.browser_support import chromium_launch_kwargs, settle_motion

    out = {"status": None, "error": "", "texts": {}, "shot": False, "body": ""}
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    try:
        context = browser.new_context(viewport={"width": width, "height": 900})
        if cookie:
            context.add_cookies([{"name": "ubyhost_session", "value": cookie, "url": base + "/"}])
        if extra_cookies:
            context.add_cookies([{"name": n, "value": v, "url": base + "/"} for n, v in extra_cookies])
        page = context.new_page()
        try:
            response = page.goto(base.rstrip("/") + path, wait_until="networkidle")
            out["status"] = response.status if response else None
            if out["status"] and out["status"] >= 400:
                out["error"] = (page.inner_text("body") or "")[:200].replace("\n", " ")
            settle_motion(page)
            for sel in mask:  # hidden keeps the layout; only the QR pixels disappear
                page.evaluate("s => document.querySelectorAll(s).forEach(e => e.style.visibility = 'hidden')", sel)
            for spec in texts:
                value = ""
                for alt in spec.split("|"):
                    sel, _, attr = alt.partition("@")
                    el = page.query_selector(sel)
                    if el:
                        value = (el.get_attribute(attr) if attr else el.inner_text()) or ""
                        break
                out["texts"][spec] = re.sub(r"https?://127\.0\.0\.1:\d+", "<BASE>", value.replace(base, "<BASE>")).strip()
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(dest), full_page=True)
            out["shot"] = True
        except Exception as exc:  # timeout, navigation error: record the message, no screenshot
            out["error"] = (out["error"] or str(exc))[:200]
        context.close()
    finally:
        browser.close()
    return out


def _shape(text: str) -> str:
    """A TOTP secret is random per render: compare its shape (length, groups), with the secret= value blanked."""
    import re
    text = re.sub(r"secret=[A-Za-z0-9]+", "secret=X", text)
    return re.sub(r"[A-Z2-7]", "X", text)


def run_case2(name, base_name, path, out_dir, py_base, go_base, widths, py_cookie, go_cookie, pre_sql, extra_cookies=None):
    import playwright.sync_api as sync_api

    cfg = parity_cases.QR_PAYLOAD_CASES.get(base_name, {"mask": [], "texts": []})
    slug = shots._slug(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_api.sync_playwright() as pw:
        for width in widths:
            f = {k: out_dir / f"{slug}-{width}-{k}.png" for k in ("py", "go", "side", "diff")}
            shots._run_pre_sql(pre_sql)
            a = _capture(pw, py_base, path, width, f["py"], py_cookie, cfg["mask"], cfg["texts"], extra_cookies=extra_cookies)
            shots._run_pre_sql(pre_sql)
            b = _capture(pw, go_base, path, width, f["go"], go_cookie, cfg["mask"], cfg["texts"], extra_cookies=extra_cookies)
            sa, sb = a["status"], b["status"]
            msg = f"py={sa} go={sb}" + (f" py_err={a['error']}" if a["error"] else "") + (f" go_err={b['error']}" if b["error"] else "")
            if a["shot"] and b["shot"]:
                shots.write_side_by_side(f["py"], f["go"], f["side"])
                shots.write_diff_image(f["py"], f["go"], f["diff"])
                verdict, max_delta, diff_px, _total, note = shots.compare_images(f["py"], f["go"])
            else:
                one = f["py"] if a["shot"] else (f["go"] if b["shot"] else None)
                if one:
                    shutil.copy(one, f["side"])
                verdict, max_delta, diff_px, note = ("error", None, None, "no screenshot on either side")
                if one:
                    verdict, note = "visible", "one side failed to load"
            if (sa or 0) >= 400 or (sb or 0) >= 400 or not a["shot"] or not b["shot"]:
                if sa != sb:                      # error on one side only: a status mismatch, always a visible row
                    verdict = "visible" if (a["shot"] or b["shot"]) else "error"
                note = (note + " | " + msg).strip(" |")
            for spec in cfg["texts"]:             # QR payload text: must match (secret compared by shape)
                x, y = a["texts"].get(spec, ""), b["texts"].get(spec, "")
                if x != y and _shape(x) != _shape(y):
                    verdict = "visible" if verdict in ("identical", "invisible") else verdict
                    note += f" | QR payload differs [{spec}] py={x[:60]!r} go={y[:60]!r}"
            results.append({"width": width, "verdict": verdict, "max_delta": max_delta, "diff_pixels": diff_px,
                            "note": note, "side_png": str(f["side"]), "diff_png": str(f["diff"])})
    return results


def main() -> int:
    only = {x for x in os.environ.get("PARITY_ONLY", "").split(",") if x}
    groups = {g for g in os.environ.get("PARITY_GROUP", "A,B,C,D").split(",") if g}
    widths = tuple(int(w) for w in os.environ.get("PARITY_WIDTHS", "390,768,1280").split(","))

    def selected(name: str) -> bool:
        if not only:
            return True
        return any(name == pat or (pat.endswith("*") and name.startswith(pat[:-1])) for pat in only)

    audit.ENV.update(AI_ENV)
    audit.PIN_ENV.update(AI_ENV)
    seed, refs = audit.seed_db()
    extra = run_extra_seed(seed, refs)
    py_port, go_port = free_port(), free_port()
    db_url = f"{audit.PG}/parity_run"
    public = f"http://127.0.0.1:{py_port}"
    _, py_base = audit.start_py(py_port, db_url, public)
    go_proc, go_base = audit.start_go(go_port, db_url, public)
    try:
        py, go = audit.py_persona_sessions(seed), audit.go_persona_sessions(seed)

        jobs = [(name, path, py_c, go_c, "L") for name, path, py_c, go_c in legacy_cases(refs, py, go)]
        jobs += list(table_cases(refs, seed, py, go, extra))
        for name, path, persona, group in parity_cases.MODAL_CASES:
            for lang in ("cs", "en"):
                filled = fill(path, refs, seed)
                sep = "&" if "?" in filled else "?"
                pc, gc = (py["host"], go["h1"]) if persona == "host" else (py["admin"], go["admin"])
                jobs.append((f"{name}-{lang}", f"{filled}{sep}lang={lang}", pc, gc, group))

        rows = []
        for name, path, py_cookie, go_cookie, group in jobs:
            if group not in groups or not selected(name):
                continue
            out_dir = OUT / name
            if out_dir.exists():
                shutil.rmtree(out_dir)
            base_name = name.rsplit("-", 1)[0]
            pre = PRE_SQL_MODAL if name.startswith("two-factor-modal") else PRE_SQL
            for r in run_case2(name, base_name, path, out_dir, py_base, go_base, widths, py_cookie, go_cookie, pre):
                verdict = r["verdict"]
                accepted = verdict == "visible" and base_name in parity_cases.ACCEPTED
                if accepted:
                    verdict = "accepted"
                    r["note"] = parity_cases.ACCEPTED[base_name]
                rows.append({"case": name, "path": path, "group": group, "width": r["width"], "verdict": verdict,
                             "max_delta": r["max_delta"], "diff_pixels": r["diff_pixels"], "note": r["note"],
                             "side_png": r["side_png"], "diff_png": r["diff_png"]})
                print(f"{name:22} {r['width']:5} {verdict:9} diff_px={r['diff_pixels']} {r['note'][:120]}")
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "probe.json").write_text(json.dumps({"db": "parity_run", "rows": rows}, indent=1))

        # Markdown report: one line per case, verdict per width, then the non-identical rows with their side image.
        case_order: list[str] = []
        cell: dict[str, dict[int, str]] = {}
        for r in rows:
            if r["case"] not in cell:
                case_order.append(r["case"])
                cell[r["case"]] = {}
        path_of = {r["case"]: r["path"] for r in rows}
        lines = ["| case | path | 390 | 768 | 1280 |", "|---|---|---|---|---|"]
        for r in rows:
            word = "ERR" if r["verdict"] == "error" else r["verdict"]
            if r["width"]:
                cell[r["case"]][r["width"]] = word
        for case in case_order:
            cols = [cell[case].get(w, "-") for w in (390, 768, 1280)]
            lines.append(f"| {case} | {path_of[case]} | {cols[0]} | {cols[1]} | {cols[2]} |")
        lines.append("")
        lines.append("Not identical:")
        for r in rows:
            if r["verdict"] not in ("identical", "accepted"):
                lines.append(f"- {r['case']} {r['width']} {('ERR' if r['verdict'] == 'error' else r['verdict'])} {r['side_png']}")
        lines.append("")
        lines.append("Accepted (deliberate, not failures):")
        for r in rows:
            if r["verdict"] == "accepted":
                lines.append(f"- {r['case']} {r['width']} {r['note']}")
        report = OUT / f"report-{'-'.join(sorted(groups))}.md"
        report.write_text("\n".join(lines) + "\n")
        print(f"report: {report}")

        tally = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("identical", "invisible", "visible", "accepted", "error")}
        print(json.dumps({"rows": len(rows), "verdicts": tally}))
        return 1 if tally["visible"] or tally["error"] else 0
    finally:
        go_proc.terminate()
        try:
            go_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            go_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
