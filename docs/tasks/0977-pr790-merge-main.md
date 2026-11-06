# 0977: PR #790: renumber colliding briefs, merge main, fix lint, wording and tests

Status: todo
Depends on: none | Base commit: origin/codex/ux-remediation-handoff | Branch: codex/ux-remediation-handoff (already exists, rides on PR #790, no new PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens. If you hit 25 calls, finish the step you are on, commit, write the report as `blocked` with `Done: steps 1 to k. Left: steps k+1 to 10.`, and stop.

## 1. Objective

Make PR #790 mergeable as ONE PR (owner decision). Five jobs, in this order:

1. The branch reuses brief numbers 0958 to 0964, which main already uses for other tasks. Renumber the branch's versions to 0978 to 0984.
2. `git merge origin/main` (conflicts in `app2.css` and the four cache-key files).
3. New cache keys, `static_versions.json` regenerated.
4. Re-measure the two `v2_mockup.py` 320 px widths.
5. Fix the layout lint (`table-squeezed` on the feed URL cell), revert the validation wording (UbyPort filing parity), add tests for the two stay-fee filing routes.

## 2. Context

Main's 0958 to 0964 are: guest-pay fixes (0958 to 0960), 0961 ruff, 0962 deploy image cleanup, 0963 access log kind, 0964 stay dates at 320 px. Do not touch those files. Both sides have `0958-report.md` to `0964-report.md`, so git sees add/add conflicts. Precedent: brief 0869 renumbered colliding briefs.

Renumber table (old -> new). Branch files only:

| Old | New |
|---|---|
| 0958-calendar-type-state.md, 0958-calendar-type-state.patch, 0958-cont-1.md, 0958-report.md | 0978-calendar-type-state.md, 0978-calendar-type-state.patch, 0978-cont-1.md, 0978-report.md |
| 0959-guest-draft-language.md, 0959-report.md | 0979-guest-draft-language.md, 0979-report.md |
| 0960-calendar-create-actions.md, 0960-report.md | 0980-calendar-create-actions.md, 0980-report.md |
| 0961-host-shell-forms.md, 0961a-guest-form-v2-shell.md, 0961b-invoice-form-v2-shell.md | 0981-host-shell-forms.md, 0981a-guest-form-v2-shell.md, 0981b-invoice-form-v2-shell.md |
| 0962-property-readiness.md, 0962-report.md, 0962-patches/ (3 files) | 0982-property-readiness.md, 0982-report.md, 0982-patches/ |
| 0963-property-wrappers.md, 0963-report.md | 0983-property-wrappers.md, 0983-report.md |
| 0964-connection-states.md, 0964-report.md | 0984-connection-states.md, 0984-report.md |

Branch has no `0961-report.md`; main's `0961-report.md` stays untouched. 0965 to 0976 are unique and keep their numbers; this brief is 0977.

What stays unchanged on purpose: cache keys such as `20261105-0958b`, branch names (`codex/0960-b02-...`), `/tmp/ubyhost-0958-worktree`, `calendar-0960-*` screenshot file names, `.patch` contents. The script in step 1 skips them (they are preceded by `-`, `codex/`, `task/`, `tmp/`, or followed by a letter/digit).

Why the renumber runs BEFORE the merge: before the merge every `0958` to `0964` in the tree belongs to the branch, so a mechanical replace is safe. After the merge, main's own `0964:` comments (`app2.css` 320 px block, `v2_mockup.py`) arrive and must NOT be renamed.

Static versions: `App/tests/static_versions.json` is written by `.venv/bin/python tests/test_static_versions.py --write` (from `App/`) and checked by `tests/test_static_versions.py`. Never edit it by hand.

Layout lint: `App/tests/layout_lint.js` line ~265, check 10a `table-squeezed`: a `td`/`th` with 4 to 30 characters of text (no `/ : ? =`) that wraps to 2 or more lines, where lines > words and the longest word is 4 or more letters. The branch's feed URL cell (`<td class="small feed-url">` in `App/app/templates/_property_calendars.html` lines 48 to 54: a `<details><summary>URL label</summary>`, the hidden `.feed-url-value`, and a copy button) has short text (summary plus copy-button label), so it trips the check when the table cell is narrow (22 findings in the 0984 report, before renumber: 0964-report). CSS today (`App/app/static/app2.css` ~line 2771 on the branch): `body.v2 .feed-table td.feed-url{min-width:0;max-width:none;white-space:normal}` (with `::before{display:none}`) and `.feed-url-details summary{...display:inline-flex;min-height:44px}`. Below 1024 px the table turns into stacked cards (lines ~2413 to 2422, `td{display:block;width:100%}`), so the squeeze happens at the widths where the table is still a real table (tablet and desktop).

Wording revert: main says `UbyPort web-service login is required for automatic reporting.` The branch changed it to `UbyPort web login required for automatic reporting.` UbyPort filing parity beats everything: Python and Go must agree, and `go/internal/validation/testdata/golden.json` is generated from Python by `App/scripts/validation_golden.py`.

New routes (commit 7b1eff2c, `App/app/routes/stay_fees.py` lines ~1015 to 1062): `POST /stay-fees/{apartment_id}/filings/{filing_id}/sent` sets `sent_at` once; `POST .../paid` sets `paid_at` and `sent_at` (keeps an existing `sent_at`), once. Both take form fields `_csrf` and `month` (e.g. `2026-08`), look up the filing with `_filing_for_month` (`id` and `apartment_id` must match, not superseded, `period_key` must be one of `stay_fee_filing.overlap_keys(cadence, month)`), and redirect (303) back to `/stay-fees/{apartment_id}?month=...`. Unknown apartment (`access.apartment` returns nothing for another host's property) redirects to `/stay-fees` with an error. Wrong filing_id for the apartment redirects with `flash.stay_fees.report_blocked`. Do not change route behaviour.

## 3. Files

| Path | Action |
|---|---|
| `docs/tasks/09{58..64}*` (table above) | `git mv` to 0978 to 0984 |
| text references listed by the script (step 1) in `App/app`, `App/tests`, `docs/tasks` | replace old number with new |
| `App/app/static/app2.css`, `App/app/templates/base.html`, `App/app/templates/guest/base.html`, `App/app/templates/_dashboard_calendar.html`, `App/tests/static_versions.json` | merge conflicts, cache keys |
| `App/tests/v2_mockup.py` | re-pin 2 widths |
| `App/app/static/app2.css` | feed URL cell fix |
| `App/app/templates/_property_calendars.html` | only if CSS alone cannot fix it |
| `App/app/validation.py`, `App/app/validation_i18n.py`, `App/app/host_vi_i18n.py`, `go/internal/validation/validation.go`, `go/internal/validation/testdata/golden.json` | wording revert |
| `App/tests/test_stay_fee_detail.py` | add tests |
| `docs/tasks/0977-report.md`, `docs/tasks/screenshots-0977/` | create |

No other file may change. If another file has a conflict, stop (section 8).

## 4. Steps

Work from `/home/user/jsfpecharoperations`, branch `codex/ux-remediation-handoff`. First: `git status --short | head -5 | tail -30` must be clean, and `git fetch origin main 2>&1 | tail -30`.

### Step 1: renumber and commit (before the merge)

1. Move the files (one command; `git mv` keeps history):
```
cd docs/tasks && git mv 0958-calendar-type-state.md 0978-calendar-type-state.md && git mv 0958-calendar-type-state.patch 0978-calendar-type-state.patch && git mv 0958-cont-1.md 0978-cont-1.md && git mv 0958-report.md 0978-report.md && git mv 0959-guest-draft-language.md 0979-guest-draft-language.md && git mv 0959-report.md 0979-report.md && git mv 0960-calendar-create-actions.md 0980-calendar-create-actions.md && git mv 0960-report.md 0980-report.md && git mv 0961-host-shell-forms.md 0981-host-shell-forms.md && git mv 0961a-guest-form-v2-shell.md 0981a-guest-form-v2-shell.md && git mv 0961b-invoice-form-v2-shell.md 0981b-invoice-form-v2-shell.md && git mv 0962-property-readiness.md 0982-property-readiness.md && git mv 0962-report.md 0982-report.md && git mv 0962-patches 0982-patches && git mv 0963-property-wrappers.md 0983-property-wrappers.md && git mv 0963-report.md 0983-report.md && git mv 0964-connection-states.md 0984-connection-states.md && git mv 0964-report.md 0984-report.md 2>&1 | tail -30
```
Expected: no output. Any `git mv` error: stop.

2. Create the script `"${TMPDIR:-/tmp}/renum.py"` with exactly this content (keep it outside the repo):
```python
import re, subprocess, sys
M = {"0958": "0978", "0959": "0979", "0960": "0980", "0961": "0981", "0962": "0982", "0963": "0983", "0964": "0984"}
rx = re.compile(r"(?<![A-Za-z0-9.-])(?<!codex/)(?<!task/)(?<!tmp/)(0958|0959|0960|0961|0962|0963|0964)([ab]?)(?![A-Za-z0-9])(?!\.\d)")
write = "--write" in sys.argv
files = subprocess.check_output(["git", "ls-files", "App/app", "App/tests", "docs/tasks", "docs/context"], text=True).split("\n")
n = 0
for f in files:
    if not f or f.endswith((".svg", ".png", ".json", ".lock", ".patch")):
        continue
    try:
        s = open(f, encoding="utf-8").read()
    except Exception:
        continue
    t, c = rx.subn(lambda m: M[m.group(1)] + m.group(2), s)
    if c:
        n += c
        print(c, f)
        if write:
            open(f, "w", encoding="utf-8").write(t)
print("total", n)
```
3. Dry run: `python3 "${TMPDIR:-/tmp}/renum.py" 2>&1 | tail -60`. Expected: `total` about 391 (a few more or fewer is fine), listing only files under `App/app`, `App/tests`, `docs/tasks`. No hit in `docs/context`. If the list contains a file outside those, or `docs/tasks/0950-*`, `0951-*`, `0948-*`, `0949-*`: stop (those carry `0960m`/`0960n` cache letters that must not change).
4. Apply: `python3 "${TMPDIR:-/tmp}/renum.py" --write 2>&1 | tail -3`.
5. Spot check (each must print what is stated): `grep -c "0960m" docs/tasks/0950-stays-current-pill-hover.md | tail -3` is 1 or more; `grep -rn "20261105-09[56]" App/app/templates | head -5 | cut -c1-140` still shows the old cache keys unchanged; `grep -n "def test_098" App/tests/test_guest_browser_e2e.py App/tests/test_dashboard_calendar_browser.py | head -8 | cut -c1-120` shows renamed tests (e.g. `test_0979_...`).
6. Quick import check: `cd App && .venv/bin/python -m pytest tests/test_host_property_controls_browser.py tests/test_guest_browser_e2e.py --collect-only -q 2>&1 | tail -5`. Expected: tests collected, no error.
7. Commit: `git add -A docs/tasks App && git commit -m "0977 step 1: renumber colliding briefs 0958-0964 to 0978-0984" 2>&1 | tail -30`.

### Step 2: merge main

1. `git merge origin/main 2>&1 | tail -30`. Expected conflicts in exactly these files and no others: `App/app/static/app2.css`, `App/app/templates/base.html`, `App/app/templates/guest/base.html`, `App/app/templates/_dashboard_calendar.html`, `App/tests/static_versions.json`, `App/tests/v2_mockup.py`. List them: `git diff --name-only --diff-filter=U | tail -30`. Any `docs/tasks/*` conflict, or any other file: run `git merge --abort 2>&1 | tail -3` and stop (section 8).
2. The cache-key files and `v2_mockup.py`: resolve by hand, never with `git checkout --ours`/`--theirs` (that takes the whole file and drops main's other edits). In each of `App/app/templates/base.html`, `App/app/templates/guest/base.html`, `App/app/templates/_dashboard_calendar.html` (1 block each), `App/tests/static_versions.json` (3 blocks) and `App/tests/v2_mockup.py` (1 block): keep the branch side (between `<<<<<<<` and `=======`), delete main's side and the three marker lines. Step 3 sets the final `?v=`/sha256 values; step 4 re-measures the `v2_mockup.py` widths. Check: `grep -c '^<<<<<<<\|^=======\|^>>>>>>>' <file>` prints 0 for each.
3. `app2.css`: `grep -n '^<<<<<<<\|^=======\|^>>>>>>>' App/app/static/app2.css | tail -30`. Expected 2 conflict blocks.
   - Block 1 (~line 667), the stay-dates rules. Branch side: `@media (max-width:1023px){body.v2 .host-stay-detail .stay-dates b{white-space:nowrap}}`. Main side: the 0964 block at 320 px (equal columns, 12 px cell padding, `.wd` screen-reader only). Keep BOTH: branch rule first, then main's block. Delete only the three marker lines.
   - Block 2 (~line 2759): branch side holds the 0983 archive/copy dialog, 0984 connection states and feed-url, 0968 stays filter, 0971 success pattern rules; main side holds the 0897 property save-bar pill, stay-fee-guest-fields and the tip-tail block. Keep BOTH sides in full (branch side first, then main side). Delete only the marker lines. No rule dropped.
   Check: `grep -c '^<<<<<<<\|^=======\|^>>>>>>>' App/app/static/app2.css | tail -3` prints 0. `grep -c "stay-dates" App/app/static/app2.css | tail -3` must be at least the sum of both sides (run `git show origin/main:App/app/static/app2.css | grep -c stay-dates | tail -3` and compare: merged is that number plus 1 or more).
4. Final check for markers anywhere: `git diff --check 2>&1 | tail -30` (trailing-whitespace warnings in `docs/tasks` are known and ignored; any `leftover conflict marker` is not).
5. Commit the merge: `git add -A App docs && git commit --no-edit 2>&1 | tail -30`.

### Step 3: cache keys and static_versions

New version string for all three files: `20261106-0977`.

1. Set the three keys (anchors found by name; each must change exactly once):
```
sed -i -E 's#(/static/app2\.css\?v=)[^"]*#\120261106-0977#' App/app/templates/base.html 2>&1 | tail -30
sed -i -E 's#(/static/guest\.css\?v=)[^"]*#\120261106-0977#' App/app/templates/guest/base.html 2>&1 | tail -30
sed -i -E 's#(/static/dashboard-calendar\.js\?v=)[^"]*#\120261106-0977#' App/app/templates/_dashboard_calendar.html 2>&1 | tail -30
grep -n "app2.css?v=\|guest.css?v=\|dashboard-calendar.js?v=" App/app/templates/base.html App/app/templates/guest/base.html App/app/templates/_dashboard_calendar.html | cut -c1-150 | tail -30
```
Expected: each shows `20261106-0977`. If a file has more than one match, or none: stop.
2. Regenerate the json: `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. The three templates keep this key while their sha256 is regenerated. Later steps change `app2.css` again (steps 5): after step 5 run this `--write` once more (the key stays `20261106-0977`; only the sha256 changes). Do not bump the key again.
3. `cd App && .venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short 2>&1 | tail -30`. Expected: pass.
4. Commit: `git add -A App && git commit -m "0977 step 3: cache keys 20261106-0977, static_versions regenerated" 2>&1 | tail -30`.

### Step 4: v2_mockup re-measure

Playwright and Chromium: `cd App && .venv/bin/pip install -q playwright==1.63.0 2>&1 | tail -3` if missing; always `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` in the same command line; never run `playwright install`.

1. Run: `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "stay" -q --tb=short -rs 2>&1 | tail -30`.
2. The two lines in `App/tests/v2_mockup.py` (find with `grep -n 'stay-dates small@320\|stay-dates b@320' App/tests/v2_mockup.py | tail -5`): `"stay:.stay-dates small@320": {"width": ...}` and `"stay:.stay-dates b@320": {"width": ..., "height": "28px"}`. Branch had `80.0156px`, main has `94px`. Equal columns plus 12 px cell padding make the value date-independent. If the test fails with `app=<N>px mockup=...` for these, write the measured `<N>px` into both lines (keep `"height": "28px"`; tolerance stays +-2 px; seed dates stay). Keep main's explanatory comment lines and add one line above them: `# 0977: re-measured after merging main (equal columns + 12px cell padding at 320px).` If the test already passes, change nothing and say so.
3. Rerun the command of 1.: all pass, 0 skipped. Then commit: `git add -A App && git commit -m "0977 step 4: re-pin stay-dates 320px widths" 2>&1 | tail -30` (skip the commit if nothing changed).

### Step 4b (orchestrator amendment after run 1): the three remaining mockup failures

Run 1 stopped here with 3 failures in `test_0710_v2_mockup_match_browser.py -k stay`: stays `.mh .big, .head h1` width at 320 and 390 (app 100.203px, mockup 77.0625px), and stay `.stay-dates .tot` width at 320 (app 238px, mockup 280px).

1. Check if they already fail on main: `git worktree add -q ../m0977 origin/main 2>&1 | tail -3`, then from `../m0977/App` run the same pytest command with this repo's venv: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers /home/user/jsfpecharoperations/App/.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k stay -q --tb=line -rs 2>&1 | tail -15`. Then `git worktree remove --force ../m0977`.
2. Stays h1 (both widths): the branch moved `page_help('stays')` out of the h1 in `reservations.html` on purpose. Add pins in `App/tests/v2_mockup.py` next to the other text-dependent h1 pins (~line 70): `"stays:.mh .big, .head h1@320"` and `@390` with the measured app width, comment `# text-dependent: the help button sits beside the stays title, not inside it (0968)`. Use the exact key format the existing `stay_fees:` / `invoices:` pins use.
3. `.stay-dates .tot` at 320: if it fails on main too (item 1), pin it the same way with comment `# 0964 (main): 320 px stay-dates layout`. If it passes on main, it is caused by the branch's `white-space:nowrap` rule meeting main's 320 px block: scope the branch rule to `@media (min-width:360px) and (max-width:1023px)` in `app2.css`, bump the app2.css cache key to `20261106-0977b` (template + `static_versions.json`, regenerate as in step 3), and rerun. If it still fails, pin it with comment `# 0977: nowrap stay dates` and say so in the report.
4. Rerun the step 4 command: 0 failed, 0 skipped. Commit `0977 step 4b: stays mockup pins`.

### Step 5: feed URL cell, layout lint

1. Run: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -rs 2>&1 | tail -30`. Expect `table-squeezed` findings on `td.feed-url` for the property calendars page at some widths (read the finding: it names the width). 0 skipped required.
2. Fix in `App/app/static/app2.css`, in the branch's 0984 feed-url block (`grep -n "td.feed-url" App/app/static/app2.css | tail -5`), CSS only. Concrete guidance, measure and adjust (do not guess numbers):
   - Keep the summary and the copy button on one line each: `body.v2 .feed-table td.feed-url summary, body.v2 .feed-table td.feed-url .copy-btn{white-space:nowrap}` (find the real copy button class in `grep -n "def copy_button\|macro copy_button" -r App/app/templates | tail -3`).
   - Give the cell a floor so it cannot be squeezed to a few letters while the table is a real table (min 1024 px): `@media (min-width:1024px){body.v2 .feed-table td.feed-url{min-width:150px}}`. Raise the number until the finding is gone; if the table then scrolls sideways at 1024, instead let the long URL value (`.feed-url-value`, already `overflow-wrap:anywhere`) stay hidden and the cell sit on its own row.
   - If a width between 768 and 1023 shows the finding: the stacked-card rule (`@media` around line 2413) should already apply there; if it starts at a different breakpoint, align the new rule to that breakpoint instead of adding a second one.
   Do not edit `layout_lint.js` and do not silence the finding. Change `_property_calendars.html` only if CSS cannot do it, and then only the `<td class="small feed-url">` cell.
3. Rerun the command of 1.: expected `passed`, 0 findings, 0 skipped. Also rerun step 4's command (the mockup test) to be sure `app2.css` did not move the stay page.
4. Regenerate the sha: `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` then `cd App && .venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short 2>&1 | tail -30`.
5. Commit: `git add -A App && git commit -m "0977 step 5: feed URL cell no longer squeezed" 2>&1 | tail -30`.

### Step 6: validation wording revert

1. Replace in the five files (anchor: `grep -rn "web login required" App go | cut -c1-120 | tail -30` must show 6 lines: `validation.py` 1, `validation_i18n.py` 1, `host_vi_i18n.py` 1, `validation.go` 1, `golden.json` 2):
```
sed -i 's/UbyPort web login required for automatic reporting\./UbyPort web-service login is required for automatic reporting./g' App/app/validation.py App/app/validation_i18n.py App/app/host_vi_i18n.py go/internal/validation/validation.go go/internal/validation/testdata/golden.json 2>&1 | tail -30
grep -rn "web login required" App go | tail -30
```
Expected: the second command prints nothing. If the new wording is also needed elsewhere (a test that expects the old string): `grep -rln "web login required" App/tests docs/context | tail -5`; any hit there: stop and ask.
2. Parity check, Python side regenerates the golden from `validation.py`: `cd App && .venv/bin/python scripts/validation_golden.py 2>&1 | tail -5; cd .. && git diff --stat -- go | tail -5`. Expected: `git diff --stat` shows only the sed-edited files for step 6 (golden.json differs from HEAD by the 2 lines, nothing more). If the regenerated golden has other differences, stop.
3. Tests: `cd go && go test ./internal/validation/... 2>&1 | tail -30` (expected `ok`), and `cd App && .venv/bin/python -m pytest tests/test_validation.py tests/test_validation_i18n.py tests/test_ubyport_*.py -q --tb=short -x 2>&1 | tail -30` (expected pass).
4. Commit: `git add -A App go && git commit -m "0977 step 6: restore web-service login wording (Python and Go parity)" 2>&1 | tail -30`.

### Step 7: tests for the filing sent/paid routes

File: `App/tests/test_stay_fee_detail.py` (has fixture `host` -> `(client, owner_id, entity_id)`, helpers `_property`, `_stay`, `_csrf`, `_cleanup` which deletes users named `stay-fee-detail-%`). Do not create a new test file. Read only lines 1 to 145 and 146 to 175 of that file (helpers and one cross-owner test) with `sed -n`.

1. Append helpers and four tests at the end of the file. Adapt names to the real helper signatures you read; keep the logic:
```python
def _filing(apartment_id, period_key="2026-08"):
    return db.insert("stay_fee_filing", {
        "apartment_id": apartment_id, "period_key": period_key, "cadence": "monthly",
        "rate_czk": 50, "liable_days": 4, "exempt_days": 0, "total_due_czk": 200,
        "total_collected_czk": 200, "pdf_enc": db.encrypt_blob(b"%PDF-1.4 x"),
        "csv_enc": db.encrypt_blob(b"a;b"), "payload_enc": db.encrypt_field("{}"),
        "created_at": db.utcnow(),
    })

def _mark(client, apartment_id, filing_id, action, month="2026-08"):
    page = client.get(f"/stay-fees/{apartment_id}?month={month}")
    token = page.text.split('name="csrf-token" content="')[1].split('"')[0]
    return client.post(f"/stay-fees/{apartment_id}/filings/{filing_id}/{action}",
                       data={"_csrf": token, "month": month}, follow_redirects=False)

def _row(filing_id):
    return db.query_one("SELECT sent_at, paid_at FROM stay_fee_filing WHERE id = ?", (filing_id,))
```
   - `test_filing_sent_sets_sent_at_once`: own property (use `_property(owner_id, entity_id, "Mark Demo")`), `fid = _filing(apt)`; first `_mark(..., "sent")` -> 303, `sent_at` set, `paid_at` None; remember `first = _row(fid)["sent_at"]`; second `_mark(..., "sent")` -> 303 and `_row(fid)["sent_at"] == first` (idempotent).
   - `test_filing_paid_sets_paid_at_and_sent_at`: fresh filing, `_mark(..., "paid")` -> both `paid_at` and `sent_at` set; a filing with `sent_at` already set keeps that `sent_at` (set it first via `"sent"` then `"paid"`, compare); second `"paid"` leaves `paid_at` unchanged.
   - `test_another_hosts_filing_cannot_be_marked`: create a second account `auth.create_account("stay-fee-detail-other@example.test", "Other Demo", role="host", username="stay-fee-detail-other")` with its own `legal_entity` and property (copy the pattern of the existing cross-owner test at line ~158), `other_fid = _filing(other_apt)`. As the logged-in first host, `client.post(f"/stay-fees/{other_apt}/filings/{other_fid}/sent"...)` and `.../paid` (use a CSRF token from the host's own page, `_mark` needs the apartment page so take the token from `/stay-fees/{own_apt}?month=...`): response is a redirect (303) and `_row(other_fid)` still has `sent_at` None and `paid_at` None.
   - `test_filing_id_from_another_apartment_is_rejected`: the host has two properties A and B; `fid_b = _filing(B)`; post to `/stay-fees/{A}/filings/{fid_b}/sent` and `/paid`: 303 and `_row(fid_b)` unchanged (both None).
2. Run: `cd App && .venv/bin/python -m pytest tests/test_stay_fee_detail.py -q --tb=short -x 2>&1 | tail -30`. Fix a failing test once (a test-writing mistake); if the route behaves differently from section 2, STOP and report (do not change the route).
3. Also run the row: `cd App && .venv/bin/python -m pytest tests/test_invoice_*.py tests/test_stay_fee*.py -q --tb=short -x 2>&1 | tail -30`.
4. Commit: `git add -A App && git commit -m "0977 step 7: tests for filing sent/paid routes" 2>&1 | tail -30`.

### Step 8: verification (no full suite)

Rows from `docs/context/test-map.md` for what changed, each from `App/`, all with `-rs`, 0 skipped for browser files:
```
cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -rs 2>&1 | tail -30
cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_host_stay_detail_layout_browser.py tests/test_host_property_controls_browser.py -q --tb=short -rs 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_stay_fee_detail.py tests/test_validation.py tests/test_validation_i18n.py -q --tb=short 2>&1 | tail -30
cd go && go test ./internal/validation/... 2>&1 | tail -30
cd /home/user/jsfpecharoperations && python3 scripts/context_lint.py 2>&1 | tail -30
```
`context_lint` failing on a renumbered brief (a Status line, a missing section, or two open briefs naming the same file): fix only what it names inside `docs/tasks/09{78..84}*`, once. Do not run the full suite.

Screenshots (rule 7 and 10 of AGENTS.md): from `/tmp/shots/layout-lint/` open, for the stay detail page and the property calendars/connection page, the `-390`, `-768`, `-1280` PNGs (`ls /tmp/shots/layout-lint | grep -i "stay\|propert\|calendar\|connect" | tail -30`). Copy those six files to `docs/tasks/screenshots-0977/`. Also copy the stay detail `-320` PNG if one exists, and in the report say whether the total row (`.stay-dates .tot`, pinned to 238 px in step 4b, main had 252 px) is centred, unclipped and on one line. Look at each once. Write in the report per page "390: ...; 768: ...; 1280: ..." (what you saw: no sideways scroll, feed URL cell readable, nothing closer than 12 px, stay dates on one line). Tick the design-system checklist (`docs/design/design-system.md` section 5) in the report. If no browser is available, say so: CI is then the check; Chromium missing means `blocked`.

### Step 9: report

Write `docs/tasks/0977-report.md` (600 tokens at most): `Status: review` (or `blocked`), files changed (`git diff --stat origin/main | tail -3`), each command of step 8 with its last 5 lines, section 7 ticked, per-page screenshot notes, deviations (the measured `v2_mockup` value or "unchanged"; the CSS fix chosen for the feed URL cell), questions, owner steps. Set `Status: review` in this brief's header line. Commit: `git add -A docs && git commit -m "0977 report" 2>&1 | tail -30`.

### Step 10: push

`git push origin codex/ux-remediation-handoff 2>&1 | tail -30`. Normal push only: never `--force`, never `main`. After a non-fast-forward rejection: stop and report (do not rebase or force). Retry only on a network error (2 s, 4 s, 8 s, 16 s). The PR #790 CI re-runs on the push; the owner merges with `scripts/merge-pr-on-green.sh` when green.

### Step 11 (orchestrator amendment after run 4): triage the remaining failures

Run 4 left 5 failures. For each, decide main vs branch, then act. Use one worktree: `git worktree add -q ../m0977 origin/main 2>&1 | tail -3`; run main's copy from `../m0977/App` with `/home/user/jsfpecharoperations/App/.venv/bin/python`; remove it at the end with `git worktree remove --force ../m0977`.

1. List the failures exactly on the branch (one call): `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_host_stay_detail_layout_browser.py tests/test_host_property_controls_browser.py "tests/test_invoice_autofill.py::test_invoice_buyer_block_spacing_0896" -q --tb=line -rfs 2>&1 | grep -E "FAILED|SKIPPED|passed|failed" | tail -30`.
2. Run the same command in the main worktree. A test that also fails on main: do not fix it; add one line to `docs/context/known-issues.md` (match the file's format) naming the test and the measured values, and list it in the report as "pre-existing on main".
3. A test that fails only on the branch:
   - `v2_mockup` width/height/margin pin where the branch changed the markup or text on purpose (find the commit with `git log --oneline origin/main..HEAD -S '<selector or class>' -- App/app/templates App/app/static | tail -5`): update the existing pin in `App/tests/v2_mockup.py` (edit the existing key, never add a duplicate key) with the measured app value and a comment naming the brief number from that commit.
   - Anything else (invoice buyer block layout findings, `.hl` margins 0 vs 8/28/8, a lint-style finding): do NOT pin or silence. Stop, and in the report give the test, the measured values, and the branch commit that caused it (`git log` as above).
4. Rerun item 1's command: target 0 failed, 0 skipped. Then rerun the invoice row with screenshots so the 2 skips run: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_invoice_autofill.py -q --tb=line -rs 2>&1 | tail -15`.
5. Commit `0977 step 11: triage remaining failures`, add a "Run 5" section to the report (per test: main or branch, action), push.

### Step 12 (orchestrator amendment after run 5): overview pin, invoice buyer block fix

1. Overview `.hl` margins (overview-320, overview-390, branch only): commit 551808e7 moved the h1 into `.ov-title-row` and moved the margin `0 8px 28px` from `h1.hl` to the row (`app2.css`, the `.ov-title-row` rule near line 922), so the page looks the same. Pin the `.hl` margins to the app value in `App/tests/v2_mockup.py`: edit the existing `overview:` key for `.hl` at 320/390 if one exists, otherwise add page-scoped keys in the same format as the `properties:` keys from run 5. Comment: `# 551808e7: the 0 8px 28px margin moved from h1.hl to .ov-title-row`. First confirm with `grep -n "ov-title-row{" App/app/static/app2.css | tail -3` that the row really has `margin:0 8px 28px`; if not, stop.
2. Invoice buyer block (`test_invoice_autofill.py::test_invoice_buyer_block_spacing_0896`, real finding on the branch: "guest at 320px: text 0.0 px from the edge of div.ui-choice-card (min 16)"; run 4 also saw `input#buyer_ico` controls 10.5 px apart and `p.hint` at 12 px). Fix the CSS, do not edit the test. Read the test's assertions first (`grep -n "min\|assert" App/tests/test_invoice_autofill.py | sed -n '/0896/,$p' | head -30`). Change only the `body.v2 .invoice-customer ...` rules in `App/app/static/app2.css` (near line 2016): give the choice card inner padding of at least 16 px, keep at least 16 px between the buyer IČO controls and 16 px above `p.hint` where the test asks for it. Bump the app2.css key to `20261106-0977c` (base.html and static_versions.json, regenerate as in step 3). Rerun only that test until it passes, at most 3 tries; still failing: stop and report the last message.
3. Rerun step 11 item 1 and item 4 commands, then `test_layout_lint_browser.py` (step 8 row 1) and `test_static_versions.py`. Target: 0 failed, 0 skipped everywhere.
4. Copy the invoice form `-390`, `-768`, `-1280` screenshots from the item 4 run's `UBYHOST_SHOTS_DIR` into `docs/tasks/screenshots-0977/` (names starting `invoice-`).
5. In `docs/context/known-issues.md`, the line run 5 added for the invoice test: change it to say only that origin/main's copy of the test errors with the Range TypeError and the branch fixes it in 0977.
6. Commit `0977 step 12: overview pin, invoice buyer block spacing`. Report: add a "Run 6" section; set the top Status to `review` only if item 3 is fully green. Push.

## 5. Do not touch

- main's own briefs, reports and screenshots (`0958` to `0964` files that came from main), main's `0964:` comments and CSS block.
- Any route behaviour in `stay_fees.py`; `layout_lint.js`; any dependency; any file outside section 3.
- `docs/tasks/0950-*`, `0951-*`, `0948-*`, `0949-*` (cache letters `0960m`/`0960n` are not brief numbers).

## 6. Commands

All in section 4. Never `pytest tests` or the full suite. Every command ends with `| tail -30` (or `tail -5`).

## 7. Acceptance

- [ ] `git ls-files docs/tasks | grep -E '^docs/tasks/09(5[89]|6[0-4])' | sort` shows only main's files (no `0958-calendar-type-state`, `0959-guest-draft-language`, `0960-calendar-create-actions`, `0961-host-shell-forms`, `0962-property-readiness`, `0963-property-wrappers`, `0964-connection-states` and no `0962-patches`).
- [ ] `git merge-base --is-ancestor origin/main HEAD` exits 0; `git diff --check` has no conflict marker.
- [ ] `app2.css` has both sides of both blocks; no `<<<<<<<`.
- [ ] The three templates and `static_versions.json` carry `20261106-0977`; `test_static_versions.py` passes.
- [ ] `test_0710_v2_mockup_match_browser.py` stay tests pass, 0 skipped.
- [ ] `test_layout_lint_browser.py` passes: 0 findings, 0 skipped.
- [ ] `grep -rn "web login required" App go` prints nothing; `go test ./internal/validation/...` ok; regenerated golden equals the committed file.
- [ ] 4 new tests in `test_stay_fee_detail.py` pass; route code unchanged (`git diff origin/main -- App/app/routes/stay_fees.py` shows only branch changes from before this brief).
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] Screenshots at 390, 768, 1280 for the stay detail page and the property calendars page with notes in the report; design-system checklist ticked.
- [ ] Pushed (normal push) to `codex/ux-remediation-handoff`.

## 8. Stop and ask

Stop, write the report (`blocked`), and do not guess if:

- a `git mv` fails, or the dry run lists files outside `App/app`, `App/tests`, `docs/tasks`;
- the merge conflicts in any file other than the five of step 2, or in any `docs/tasks/*` file;
- an anchor of section 4 is not found, or a `sed` changes no line or more lines than stated;
- a test fails twice, or a browser test is skipped;
- the lint finding cannot be removed by CSS (or a one-cell template edit) without touching `layout_lint.js`;
- the golden regeneration differs from the sed-edited file beyond the 2 lines;
- a stay-fee test needs a route change;
- you reach 25 tool calls or about 50k tokens;
- you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0977-report.md`, see step 9.

## Risk list (for the reviewer)

- The mechanical renumber touches about 390 references across 45 files; `.patch` files, cache keys, branch names and tmp paths are skipped by design. Check `git diff --stat HEAD~N` of step 1 for non-comment code changes (it should be comments, test names and screenshot names only).
- Conflict files are resolved block by block (step 2.2); no whole-file checkout.
- The feed URL fix is a measured CSS floor; check the property calendars page at 1024 px for sideways scroll.
- The wording revert reverses a branch change on purpose; the parity check is the golden regeneration.

## Owner steps

None. The PR #790 CI re-runs on the push; the owner merges with `scripts/merge-pr-on-green.sh` when green.
