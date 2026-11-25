# 2045: V2 parity harness fixes, then rerun the host pages (groups A to D)

Status: todo
Depends on: 2040 (files exist) | Base commit: HEAD of the branch you start on | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 100k tokens (stop at 25 calls; see section 8)

## 1. Objective

The 2040 run was noisy for harness reasons, not app reasons. Fix the harness, rerun A to D, report.
**Do not fix any app difference.** Only files under `scripts/e2e/` change.

Owner decisions (binding, 2026-11-24):
- Booking site (`/booking-sites`, booking-site setup, property-page review, public bookings) and payments (payment requests, `/pay`, payments consent, Stripe) are RETIRED. Remove them from the case lists. Do not touch app code.
- Every function Python has, Go must have. Where Go deliberately looks newer (the "External guide" link card on the apartment guide page), the row is ACCEPTED: listed separately with the reason, never counted as a failure.
- Goal: confidence that everything works after production goes all-Go.

## 2. Context (verified in this checkout)

- The "Add a second way in?" modal shows when `user_account.two_factor_prompted_at` is NULL and `totp_enabled` is 0 (Python `App/app/templating.py:684`, Go `go/internal/hostweb/layout/layout.go:170`, `TwoFactorDone` = prompted OR totp). It was shown in BOTH stacks on every host page, covering them. Fix: set the column, do not clear it. `PRE_SQL` in `scripts/e2e/page_parity_visual.py:42` currently clears it.
- Leon pages 404 in Python because `ai.enabled_for_property("leon", apt)` (`App/app/ai.py:107`) needs `UBYHOST_AI_FEATURES` containing `leon`, a key in `UBYHOST_ANTHROPIC_API_KEY` (provider default anthropic), the owner on `UBYHOST_AI_TEST_EMAILS` only while that list is set (leave it unset), and the owner's billing not `paused` while `UBYHOST_BILLING_ENABLED=1` (`seed.py:62` sets the host `active`, so entitled). Go reads the same three env names (`go/internal/web/ai/guide_index.go` `leonOffered`, `go/internal/palette/palette.go`). GET render of the Leon pages makes no API call: the Anthropic client is created lazily in `App/app/ai.py:_get_client`, only on a chat or generate call. A fake key is therefore safe.
- `audit.ENV` (`scripts/e2e/page_parity_audit.py:28`) is the default `env` argument of `audit.start_py`, `audit.start_go` and the seed, so mutating that dict before they run changes both stacks identically. Python runs in-process (`os.environ.update`), Go as a child with `{**os.environ, **env}`.
- `App/scripts/go_page_parity_screenshots.py` (shared with a test) stays UNCHANGED. Its `capture_png` raises on HTTP >= 400, which aborts the case. This brief therefore adds its own capture function inside `page_parity_visual.py` and keeps using `shots.compare_images`, `shots.write_side_by_side`, `shots.write_diff_image`, `shots._run_pre_sql` (import them from `shots`).
- QR images: `img.auth-setup-qr` (2FA setup, both stacks; setup key text is `.auth-setup-key` in Python, `#totp-setup-key` in Go; the open-app link is `a.auth-setup-open`), `img.guide-qr` (apartment guide QR page, both stacks; the guest URL text is `.ui-mono`), `img.ready-card-qr` (setup ready card). Python templates: `App/app/templates/two_factor_setup.html`, `guest_guide_qr.html`, `_setup_ready_card.html`. Go: `go/internal/web/auth/acct_templates/two_factor_setup.tmpl`, `go/internal/web/ai/guide/templates/guide_qr.tmpl`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/e2e/parity_cases.py` | edit | drop retired cases, add `MODAL_CASES`, `ACCEPTED`, `QR_PAYLOAD_CASES` |
| `scripts/e2e/page_parity_visual.py` | edit | PRE_SQL, AI env, own capture/compare, error and QR handling, report |
| `scripts/e2e/parity_env.sh` | edit | export the AI env too (so a manual server start matches) |
| `docs/tasks/2045-report.md` | write | counts and descriptions |

No other file may change. Never touch `App/**`, `go/**`, `scripts/e2e/seed.py`, `page_parity_audit.py`, `App/scripts/go_page_parity_screenshots.py`.

## 4. Steps

0. Setup: `git pull --ff-only origin claude/nice-hawking-fw98ct 2>&1 | tail -2`. Then `source scripts/e2e/parity_env.sh 2>&1 | tail -5` (never pipe a `source` into `tail` if you need the exports in the same shell: run it as `source scripts/e2e/parity_env.sh` alone, once per shell call, then the command after `;`). Check: `grep -c "" scripts/e2e/parity_cases.py scripts/e2e/page_parity_visual.py | tail -3` (both exist).

1. `scripts/e2e/parity_cases.py`: delete exactly these 6 lines (find each with `grep -nF`):
```
    ("payments", "/payments", "host", "C"),
    ("payments-new", "/payments/new", "host", "C"),
    ("payments-consent", "/payments/consent", "host", "C"),
    ("booking-sites", "/booking-sites", "host", "C"),
    ("booking-site-setup", "/apartments/{apt}/booking-site", "host", "C"),
    ("property-page-review", "/apartments/{apt}/page", "host", "C"),
```
   Then append at the end of the file:
```
# One case that shows the two-factor prompt modal on purpose in both stacks (PRE_SQL clears the prompt).
MODAL_CASES = [
    ("two-factor-modal", "/reservations", "host", "B"),
]

# Deliberate differences, kept as Go has them. Key = case name without "-cs"/"-en". Reported separately, not failures.
ACCEPTED = {
    "apt-guide": "Go keeps the newer External guide link card (Link (https) / Save link) above the Booking or Airbnb import; Python lacks it. Python import-title spacing differs as a consequence.",
}

# Cases with a QR image: its pixels are masked, and its payload text is compared separately.
QR_PAYLOAD_CASES = {
    "2fa-setup": {"mask": ["img.auth-setup-qr"], "texts": ["a.auth-setup-open@href", ".auth-setup-key|#totp-setup-key"]},
    "2fa-setup-moved": {"mask": ["img.auth-setup-qr"], "texts": ["a.auth-setup-open@href", ".auth-setup-key|#totp-setup-key"]},
    "apt-guide-qr": {"mask": ["img.guide-qr"], "texts": [".ui-mono"]},
}
```
   Check: `python3 -c "import sys; sys.path.insert(0,'scripts/e2e'); import parity_cases as c; print(len(c.CASES), len(c.MODAL_CASES), sorted(c.ACCEPTED))" 2>&1 | tail -3` expect `<n> 1 ['apt-guide']` with n = old count minus 6. Commit `2045 step 1`.

2. `scripts/e2e/page_parity_visual.py`, AI env and PRE_SQL. Anchor `PRE_SQL = ["UPDATE user_account SET two_factor_prompted_at = NULL"]`. Replace that one line with:
```
# Default: mark the prompt as shown so no modal covers a page. The modal case alone clears it.
PRE_SQL = ["UPDATE user_account SET two_factor_prompted_at = now() WHERE two_factor_prompted_at IS NULL"]
PRE_SQL_MODAL = ["UPDATE user_account SET two_factor_prompted_at = NULL"]
# Leon needs the feature, a key, and an entitled owner (the seed host is billing 'active'). Same for both stacks.
# The key is fake: a GET render never calls the AI provider (client is created lazily).
AI_ENV = {"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "parity-fake-key-not-used"}
```
   If `two_factor_prompted_at` is a TEXT column and `now()` fails, run `grep -rn "two_factor_prompted_at" App/migrations_pg | head -3` and use the matching type (`now()::text`). Then find `    seed, refs = audit.seed_db()` and insert immediately BEFORE it: `    audit.ENV.update(AI_ENV)` (also `audit.PIN_ENV.update(AI_ENV)`). Check: `cd App && .venv/bin/python -m py_compile ../scripts/e2e/page_parity_visual.py && echo ok | tail -3`. Commit `2045 step 2`.

3. `scripts/e2e/parity_env.sh`: append at the end `export UBYHOST_AI_FEATURES=leon UBYHOST_ANTHROPIC_API_KEY=parity-fake-key-not-used`. Commit `2045 step 3`. (No check needed beyond `bash -n scripts/e2e/parity_env.sh 2>&1 | tail -3`.)

4. `scripts/e2e/page_parity_visual.py`, own capture. Insert this block immediately before `def main() -> int:` (anchor `def main() -> int:`):
```
def _capture(playwright, base, path, width, dest, cookie, mask, texts):
    """One screenshot. Returns dict(status, error, texts). Never raises on HTTP >= 400; masks QR images."""
    from tests.browser_support import chromium_launch_kwargs, settle_motion

    out = {"status": None, "error": "", "texts": {}, "shot": False, "body": ""}
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    try:
        context = browser.new_context(viewport={"width": width, "height": 900})
        if cookie:
            context.add_cookies([{"name": "ubyhost_session", "value": cookie, "url": base + "/"}])
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
                out["texts"][spec] = value.replace(base, "<BASE>").strip()
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


def run_case2(name, base_name, path, out_dir, py_base, go_base, widths, py_cookie, go_cookie, pre_sql):
    import playwright.sync_api as sync_api

    cfg = parity_cases.QR_PAYLOAD_CASES.get(base_name, {"mask": [], "texts": []})
    slug = shots._slug(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_api.sync_playwright() as pw:
        for width in widths:
            f = {k: out_dir / f"{slug}-{width}-{k}.png" for k in ("py", "go", "side", "diff")}
            shots._run_pre_sql(pre_sql)
            a = _capture(pw, py_base, path, width, f["py"], py_cookie, cfg["mask"], cfg["texts"])
            shots._run_pre_sql(pre_sql)
            b = _capture(pw, go_base, path, width, f["go"], go_cookie, cfg["mask"], cfg["texts"])
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


```
   Check: py_compile as in step 2. Commit `2045 step 4`.

5. `scripts/e2e/page_parity_visual.py`, use it. (a) `table_cases` yields 5-tuples `(name, path, py, go, group)`. Add the modal cases: find `    jobs += list(table_cases(refs, seed, py, go))` and replace it with:
```
    jobs += list(table_cases(refs, seed, py, go))
    for name, path, persona, group in parity_cases.MODAL_CASES:
        for lang in ("cs", "en"):
            filled = fill(path, refs, seed)
            sep = "&" if "?" in filled else "?"
            pc, gc = (py["host"], go["h1"]) if persona == "host" else (py["admin"], go["admin"])
            jobs.append((f"{name}-{lang}", f"{filled}{sep}lang={lang}", pc, gc, group))
```
   (b) Replace the whole `try: ... except Exception as exc: ... print(f"{name:22} ERROR {note}")` block inside the `for name, path, py_cookie, go_cookie, group in jobs:` loop (from the line `        try:` to the line `            print(f"{name:22} ERROR {note}")`) with:
```
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
```
   (c) Find `tally = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("identical", "invisible", "visible", "error")}` and change the tuple to `("identical", "invisible", "visible", "accepted", "error")`. Leave `return 1 if tally["visible"] or tally["error"] else 0` as is (accepted does not fail). (d) In the markdown report, `Not identical:` loop prints everything not identical; change its condition to `r["verdict"] not in ("identical", "accepted")` and after that loop add:
```
    lines.append("")
    lines.append("Accepted (deliberate, not failures):")
    for r in rows:
        if r["verdict"] == "accepted":
            lines.append(f"- {r['case']} {r['width']} {r['note']}")
```
   Check: py_compile; then `cd App && PARITY_GROUP=B PARITY_ONLY=two-factor-modal-en,reservation-detail-en .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12`. Expect 6 rows; `two-factor-modal-en` rows may be identical or visible, `reservation-detail-en` shows no modal (open one side PNG to confirm, 1 image read). Commit `2045 step 5`.

6. Smoke the three fixes: `cd App && PARITY_ONLY=leon-settings-en,2fa-setup-en,apt-guide-qr-en .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12`. Expect: no `py=404` for `leon-settings-en` (if still 404: stop, see section 8); `2fa-setup-en` and `apt-guide-qr-en` have no QR diff (small residual only, plus a note if the payload differs). Commit `2045 step 6`.

7. Full rerun, each separately (timeout 600000): `cd App && PARITY_GROUP=A .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -8`, then `B`, `C`, `D`. Expected rows: A 78, B 90 + 6 (modal), C 62 minus 36 (6 removed cases x 6) = 26 plus 2 pay, D 126 (the 12 Leon rows now real rows, not 2 error rows, so 126 + 0 to 12). Say the actual numbers.

8. Inspect (cap 15 image reads in total, including steps 5 to 6). For every `visible` or `error` row, group by cause and open ONE side PNG per cause (Python left, Go right). Write what you see in plain words. List every row you did not inspect. Then copy the side PNGs of every visible row: `mkdir -p /var/tmp/parity-visual/_visible && cp <side_png> /var/tmp/parity-visual/_visible/` (read paths from `/var/tmp/parity-visual/probe.json`, rows with verdict visible; the file is rewritten per group run, so copy after each group).
   Known rows to describe with the cause already found (still confirm in one image): `reservation-detail` at 1280 (Go has no "Generate invoice" button and no back arrow in the header; brief 2046 fixes it, state this), `admin-customer` and `dev-ui` (a few anti-aliasing pixels: report as trivial).

9. Write `docs/tasks/2045-report.md` (up to 1200 tokens): table per group (rows, identical, invisible, visible, accepted, error), the rows list of every visible/error row with a plain-words description, accepted list with reason, uninspected rows, wall time per group, and the path `/var/tmp/parity-visual/_visible/`. Then `python3 scripts/context_lint.py 2>&1 | tail -3` and `cd App && .venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q --tb=short -x 2>&1 | tail -30`. Commit `2045: parity harness fixes and host rerun (report)`.

## 5. Do not touch

`App/**`, `go/**`, `scripts/e2e/seed.py`, `scripts/e2e/page_parity_audit.py`, `App/scripts/go_page_parity_screenshots.py`. No new dependency. Do not fix app differences. Do not delete directories.

## 6. Commands

```
source scripts/e2e/parity_env.sh
cd App && PARITY_GROUP=A .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -8
python3 scripts/context_lint.py 2>&1 | tail -3
cd App && .venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q --tb=short -x 2>&1 | tail -30
```

## 7. Acceptance

- [ ] No booking-site, property-page-review or payments case in `parity_cases.py`: `grep -c "booking\|payments" scripts/e2e/parity_cases.py | tail -1` prints 0 (comments excluded; if the count is above 0, name the lines).
- [ ] No host page in the rerun shows the modal except `two-factor-modal-*` (one image check).
- [ ] `leon-*` rows are real rows (verdict identical/visible), not 404 errors, or the reason is in the report.
- [ ] An error on one side is a `visible` row with both statuses and the message in the note.
- [ ] The 2FA and guide QR rows no longer differ because of the QR pixels; the payload check passed or its mismatch is in the report.
- [ ] `apt-guide-cs/en` rows are `accepted` and listed with the reason.
- [ ] `/var/tmp/parity-visual/_visible/` holds the side PNG of every visible row.
- [ ] `context_lint` passes; `git status --short | tail -10` shows only section 3 files.

## 8. Stop and ask

- An anchor is not found verbatim: stop. A `py_compile` error you cannot fix in one try: stop.
- `leon-settings-en` still 404 in Python after step 2: run `grep -n "def enabled_for_property" -A9 App/app/ai.py | tail -12` once, put the output in the report, stop. Do not change app code.
- Python still shows the 2FA modal: stop and report the `two_factor_prompted_at` column type.
- Postgres or the venv is down: run `source scripts/e2e/parity_env.sh` once; if still down, stop.
- 25 tool calls used: finish the step, commit, write the report with `Status: blocked` and `Done: steps 1 to k. Left: ...`.

## 9. Report

`docs/tasks/2045-report.md`, then `Status: review`.
