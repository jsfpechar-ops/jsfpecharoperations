# 2059: parity harness: JSON endpoints, PIN focus, door-code stay seed, reruns, full gate, guest browser tests

Status: todo
Depends on: 2058 merged (precondition: `git log --oneline -40 | grep -c '2058'` is at least 1, else STOP) | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step)
Run order: 2058 (Go code) first, then this brief. This brief changes no app code.

## 1. Objective

Make the parity run trustworthy and run it: (1) JSON endpoints compared by parsed equality, (2) PIN page focus ring no longer a false visible row, (3) a stay where the door-code card is really shown, compared in the new case `g-stay-issued-done`, (4) rerun the changed cases, then the full gate once, (5) guest browser and geometry tests with 0 skipped.

## 2. Context

- Classification of the 2057 visible rows (done by the orchestrator, read-only):
  - `g-guide-apt`, `g-guide-stay` cs/en, 3 widths: REAL, fixed by 2058 (Go titles, headings, Leon block, QR host name and property name).
  - `g-leon-apt`, `g-leon-stay`: HARNESS. Both sides return the same JSON `{"messages":[],"open_questions":0,"answering":false}`; only key order differs. Fix: compare parsed JSON.
  - `g-pin-hub-cs` 390 and 1280: HARNESS (timing, not a code difference). Both templates have `autofocus` on the first PIN box (`App/app/templates/guest/pin.html:14`, `go/internal/web/guest/templates/pin.tmpl:12`) and load the same `guest-enhancements.js`. At 390 Python shows the focus ring, at 1280 Go shows it: the ring depends on when the screenshot fires. Fix: blur the active element before the screenshot on both sides,.
- The current `g-stay-issued` case (`scripts/e2e/parity_cases.py:136`) shows "Person 1 not filled in" on both sides, so the door-code card was never compared. Door code card shows only when (Python `App/app/door_codes.py` `view()` line 216, Go `go/internal/doorcodes/view.go:115` `View`): `apartment.lock_provider = 'ttlock'`; stay source is not `demo`; (`config.DOOR_CODES_LIVE` or source `manual`; the seed stays use source `manual`); a `door_code` row for the reservation with state `issued` and a non-empty `pin_enc` (encrypted with `db.encrypt_field`, `App/app/db.py:2477`; an empty `pin_enc` shows "preparing"); `valid_from`/`valid_to` for the "works from/until" lines. The stay page itself only reaches that card when the claim is confirmed and at least one guest exists (Go `stay_claim.go:200-220`). The seed `issued()` in `scripts/e2e/seed_parity_guest.py:83-98` has no `pin_enc`, the apartment is not `ttlock`, and the guest row misses required fields.
- Guest completeness: `reporting.guest_is_complete(guest, reservation)` = no error-level item in `reporting.guest_issues(guest, reservation)` (`App/app/reporting.py:447`). Use that function to find what is missing.
- Files: `scripts/e2e/page_parity_visual.py` `_capture` (line 127) and `run_case2` (line 175), `scripts/e2e/seed_parity_guest.py`, `scripts/e2e/parity_cases.py`, `scripts/e2e/parity_gate.sh`, `scripts/e2e/parity_env.sh`.

## 3. Files

| Path | Action |
|---|---|
| `scripts/e2e/page_parity_visual.py` | `_capture`: blur + JSON; `run_case2`: JSON equality |
| `scripts/e2e/parity_cases.py` | new case `g-stay-issued-done` |
| `scripts/e2e/seed_parity_guest.py` | `issued()`: lock provider, complete guest, door code with PIN |
| `docs/tasks/2059-report.md` | report |

## 4. Steps

1. JSON compare and blur, `page_parity_visual.py`. `grep -nF 'page.evaluate("window.scrollTo(0, 0)")' scripts/e2e/page_parity_visual.py` (once). Insert before it, same indentation:
```
            page.evaluate("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
```
   `grep -nF 'out = {"status": None, "error": "", "texts": {}, "shot": False, "body": ""}'` (once): add `"json": None` to that dict. After the line `out["status"] = response.status if response else None` insert:
```
            ctype = (response.headers.get("content-type", "") if response else "")
            if "json" in ctype:
                try:
                    out["json"] = json.loads(page.inner_text("body"))
                except Exception:
                    out["json"] = None
```
   In `run_case2` after the line `verdict, max_delta, diff_px, _total, note = shots.compare_images(f["py"], f["go"])` is inside the `if a["shot"] and b["shot"]:` block; add AFTER that whole if/else (before the line starting `if (sa or 0) >= 400`):
```
            if a["json"] is not None and b["json"] is not None and (sa or 0) < 400 and (sb or 0) < 400:
                if a["json"] == b["json"]:
                    verdict, note = "identical", "JSON equal after parsing (key order ignored)"
                else:
                    verdict, note = "visible", "JSON differs after parsing"
```
   Check: `python3 -c "import ast;ast.parse(open('scripts/e2e/page_parity_visual.py').read())" 2>&1 | tail -3`. Commit `2059 step 1`.
2. PIN autofocus: no harness change. A text spec cannot tell a present `autofocus` from an absent one, so the report states: both templates carry `autofocus` (pin.html:14, pin.tmpl:12), checked by `grep -c autofocus App/app/templates/guest/pin.html go/internal/web/guest/templates/pin.tmpl 2>&1 | tail -3` (expect 1 and 1). No commit.
3. Seed. In `seed_parity_guest.py` `issued()` keep the existing `res_issued` (case `g-stay-issued` stays as "one person not filled in" control). Add a second stay below it, same function:
```
    out["res_issued_done"] = stay(apt, "e2e-guest-issued-done")
    set_claim(out["res_issued_done"], state="claimed", claimed_at=now, token_version=1, declared_guests=1,
              token_hash=None, updated_at=now)
    db.execute("UPDATE apartment SET lock_provider = 'ttlock' WHERE id = ?", (apt,))
    db.execute("UPDATE reservation SET registration_completed_at = ? WHERE id = ?", (now, out["res_issued_done"]))
    gid = db.insert("guest", {
        "reservation_id": out["res_issued_done"], "first_name": "Parity", "surname": "Done",
        "birth_date": "01011990", "nationality": "DEU", "signature_png": SIG,
        "created_at": now, "updated_at": now,
    })
```
   Then make the guest complete: add a throwaway check at the end of the function (not committed in the final seed) by running, from `App/` with the parity env: `.venv/bin/python -c "..."` is NOT possible without the parity DB; instead extend the seed with this guarded debug print to stderr (keep it, it is harmless): after the insert, `from app import reporting` then `row = db.query_one("SELECT * FROM guest WHERE id = ?", (gid,))`, `res = db.query_one("SELECT * FROM reservation WHERE id = ?", (out["res_issued_done"],))`, `print(json.dumps({"issued_done_issues": [str(i)[:80] for i in reporting.guest_issues(row, res)]}), file=sys.stderr)`. Run the seed through the harness narrowed run (step 5 command with `PARITY_ONLY=g-stay-issued-done`, see below) and read the stderr line; add every missing required column to the `db.insert("guest", {...})` dict until the list has no error-level item (column names: `grep -n 'def guest_issues' -A40 App/app/reporting.py | head -60`, and the `guest` table in `App/migrations_pg/` via `grep -ln 'CREATE TABLE.*guest' App/migrations_pg/*.sql | head -2`). Use only synthetic values (`Prague`, `CZ`, `E2E` document number `E2E000000`). Maximum 3 iterations; if still not complete, STOP and report the list. Door code row: after the guest, insert
```
    pin_enc = db.encrypt_field("246810")
    db.insert("door_code", {
        "reservation_id": out["res_issued_done"], "apartment_id": apt, "lock_id": "e2e-lock-parity",
        "code_kind": "random", "state": "issued", "attempts": 0, "issued_at": now, "pin_enc": pin_enc,
        "valid_from": f"{d_from}T14:00:00", "valid_to": f"{d_to}T11:00:00",
        "next_attempt_at": now, "created_at": now, "updated_at": now,
    })
```
   where `d_from`/`d_to` are read back with `db.query_one("SELECT date_from, date_to FROM reservation WHERE id = ?", (out["res_issued_done"],))`. Also give the older `door_code` insert of `res_issued` a `pin_enc` the same way (so both show the card). Column list of `door_code`: `grep -n 'door_code' App/migrations_pg/*.sql | head -5` and match the types of `valid_from`/`valid_to` (ISO text vs ms) with Python `door_codes._iso_to_ms` (`grep -n 'def _iso_to_ms' -A6 App/app/door_codes.py`); use the format that function parses. Check: `python3 -c "import ast;ast.parse(open('scripts/e2e/seed_parity_guest.py').read())" 2>&1 | tail -3`. Commit `2059 step 3`.
4. Case. In `parity_cases.py` line 136 area add right after the `g-stay-issued` entry: `("g-stay-issued-done", "/l/{tok}/{res_issued_done}", ["claim"], "H"),`. Check how `{res_issued}` is exposed to `fill()` (`sed -n 76,83p scripts/e2e/page_parity_visual.py`); the seed JSON key `res_issued_done` must be reachable the same way as `res_issued`; if `fill` uses an allow-list, add the key there (one line). Also the claim cookie must cover the new stay: in `cookies()` (`seed_parity_guest.py:101`) add `str(out["res_issued_done"]): 1` to the dict signed as `claim_cookie`. Commit `2059 step 4`.
5. Narrow run, proof of the door-code card: `cd /home/user/jsfpecharoperations && source scripts/e2e/parity_env.sh && cd App && PARITY_ONLY=g-stay-issued-done PARITY_WIDTHS=390,1280 PARITY_GROUP=H .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30`. Open `/var/tmp/parity-visual/g-stay-issued-done-cs/g-stay-issued-done-cs-390-side.png` and the `-en-` one (the folder name may differ: `ls /var/tmp/parity-visual | grep issued-done`). BOTH sides must show the door-code card with the PIN `246810` (the PIN is synthetic). If a side shows "preparing", "waiting" or no card: STOP with the stderr line and the Go log tail (`UBYHOST_DATA_KEY`-style encryption keys differ between Python and Go in `parity_env.sh`: `grep -n 'KEY\|SECRET' scripts/e2e/parity_env.sh | cut -c1-80`, never print values). If the card shows but the rows differ, that is a REAL finding: report it, do not fix app code.
6. Rerun only the changed cases (H and P), all widths. H: `cd App && PARITY_GROUP=H PARITY_WIDTHS=390,768,1280 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30`. P: `PARITY_PIN=1 PARITY_GROUP=P PARITY_WIDTHS=390,768,1280 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30` (run with `source scripts/e2e/parity_env.sh` first in the same shell call). Expected: g-leon-* identical (JSON), g-pin-hub-cs identical, g-guide-* identical or a new REAL row listed (report it). Open at most 8 side PNGs of rows still visible (cs 390 first), one plain line per row in the report: what differs.
7. Full gate once: `cd /home/user/jsfpecharoperations && bash scripts/e2e/parity_gate.sh 2>&1 | tail -30` (takes long; run it in the background if the tool allows, then read the tail). Record per group the last line; list every visible row by name only. Do not rerun it. If it fails on rows outside this brief, report them; never silence a row.
8. Guest browser and geometry tests (test-map guest row, rules "Guest pages"). From `App/`: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30`. Then the guest unit row: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test .venv/bin/python -m pytest tests/test_guest_*.py -q -rs --tb=short -x 2>&1 | tail -30`. 0 skipped in the first command (`-rs` lists skips); a skip is a failure, STOP. A test fails: fix once only if the cause is the harness files of this brief, else STOP and report. The per-page 390 px screenshots are the parity side PNGs of step 6 (hub claimed, stay, guide, PIN): one plain-words line each.
9. `python3 scripts/context_lint.py 2>&1 | tail -3` from the repo root. Write `docs/tasks/2059-report.md` (600 tokens): totals H and P after the rerun, full gate result per group, visible rows with cause, the door-code proof line, test counts with skipped = 0. Set `Status: review`, open one PR (draft). Do not push to `main`.

## 5. Do not touch

`App/app/**`, `go/**`, `scripts/e2e/page_parity_audit.py`, `go_page_parity_screenshots.py`, other cases and seeds. A visible row is reported, never silenced.

## 6. Commands

Steps 1 to 9 only. Not `pytest tests` and not the parity tool outside steps 5 to 7.

## 7. Acceptance

- [ ] `g-leon-apt` and `g-leon-stay` rows identical with note "JSON equal after parsing".
- [ ] `g-pin-hub-cs` identical at all widths (or only a real, named difference remains).
- [ ] `g-stay-issued-done` shows the door-code card with a PIN on both sides at 390 and 1280; row verdict stated.
- [ ] Full gate run once; every visible row named with a cause.
- [ ] Guest browser and geometry tests green, 0 skipped.
- [ ] `context_lint` OK.

## 8. Stop and ask

Precondition fails; anchor not found; guest cannot be made complete in 3 tries; door-code card missing on a side; a test skipped; 25 tool calls (commit, report what is left; a fresh Haiku continues with steps k+1 to 9).

## 9. Report

`docs/tasks/2059-report.md`, 600 tokens at most. Trailers on every commit:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf
```
