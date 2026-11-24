# 2040: V2 visual parity, part 1: environment, harness, and every host/admin page the seed already covers

Status: todo
Depends on: 2028 | Base commit: HEAD of the branch you start on | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 100k tokens (stop at 25 calls; see section 8)

## 1. Objective

Owner requirement: after production switches to Go-only, every page a logged-in host or an
admin sees must look exactly the same as in Python today. This brief builds the repeatable
setup, extends the pixel-comparison probe from 11 cases to every host and admin page whose
data the current seed already provides, runs it in cs and en at 390, 768 and 1280 px, and
reports. **It must not fix any visible difference.** Fixes come later in separate briefs.
Anonymous and public pages are out of scope (owner decision). Guest pages are brief 2042;
pages that need new seed data are brief 2041.

## 2. Context (verified in this checkout)

- A fresh cloud container has: Go 1.24 (`/usr/local/go/bin`, not always on PATH), Postgres 16
  binaries in `/usr/lib/postgresql/16/bin` (NOT on PATH, no server running), Python 3.13, Chromium
  in `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`. There is **no** `App/.venv` and the
  `playwright` Python package is not installed. Postgres refuses to run as root, so it starts with
  `runuser -u postgres`. Verified: initdb + `pg_ctl ... start` on port 5433 works.
- `scripts/e2e/page_parity_audit.py` reads `UBYHOST_E2E_PG` (default `postgresql://postgres@127.0.0.1:5433`)
  and `UBYHOST_E2E_PSQL`; `seed_db()` returns `(seed, refs)`.
  `seed["h1"|"admin"|"alfa"|...]` hold `id`/`session`; `seed["fee"]["a"]` is a stay-fee apartment id,
  `seed["host_invoices"]` the three host invoice ids. `refs` has `apartment_id`, `reservation_id`,
  `guest_id`, `invoice_id`, `token`.
- `scripts/e2e/page_parity_visual.py` has `cases(refs, py, go)` returning
  `(name, path, py_cookie, go_cookie)` tuples (11 today), `main()` loops them through
  `shots.run_case(...)` and returns 1 when a row is visible. `run_case` raises when either stack
  answers HTTP >= 400, which would stop the whole run.
- Language: `?lang=cs|en` is read first by both stacks (`host_i18n.resolve_language`).
- Both stacks share ONE database. Anything that fires once and marks itself done (the 2FA prompt,
  cleared by `PRE_SQL` in `page_parity_visual.py`) is consumed by whoever renders first.

## 3. Files

| Path | Action | What |
|---|---|---|
| `scripts/e2e/parity_env.sh` | new, then modified in step 0 | one `source`-able script: starts Postgres, builds the venv, exports the env |
| `scripts/e2e/parity_cases.py` | new | the page table (data only) |
| `scripts/e2e/page_parity_visual.py` | edit | read the table, add `lang`, `PARITY_GROUP`, error rows, `--report` markdown |
| `docs/tasks/2040-report.md` | write | the verdict table and the visible-row descriptions |

No other file may change. Never touch `App/app/**`, `go/**`, `scripts/e2e/seed.py`.

## 4. Steps

0. **Step 0 (re-run after the first attempt).** The first attempt stopped at step 1 (commit cd75988 already has `scripts/e2e/parity_env.sh`, with a broken install block). Run `rm -rf App/.venv`. In `scripts/e2e/parity_env.sh`, find the anchor line `if [ ! -x App/.venv/bin/python ]; then` and replace that whole block (through its closing `fi`, 4 lines) with exactly:
```
[ -x App/.venv/bin/python ] || python3 -m venv App/.venv
if ! App/.venv/bin/python -c "import playwright, uvicorn, psycopg, httpx" 2>/dev/null; then
  App/.venv/bin/pip install -q -r App/requirements.lock -r App/requirements-dev.txt
  App/.venv/bin/pip install -q playwright==1.63.0
fi
```
   Why: the hashed lock file turns on `--require-hashes`, which refuses the unhashed `playwright==1.63.0` in the same call (CI installs it separately), and the old guard skipped the install after a half-failed one. Then skip the file creation in step 1 (the file already exists; its text below is the corrected version) and run only step 1's Run command. Never pipe a `source` into `tail`: a pipe runs it in a subshell and the exports are lost.

1. Create `scripts/e2e/parity_env.sh` with exactly this content, then `chmod +x` it:
```
#!/usr/bin/env bash
# Usage (repo root):  source scripts/e2e/parity_env.sh
export PGBIN=/usr/lib/postgresql/16/bin
export PARITY_PG_DIR=/var/tmp/parity-pg
export UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433
export UBYHOST_E2E_PSQL=$PGBIN/psql
export PARITY_OUT=${PARITY_OUT:-/var/tmp/parity-visual}
export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome
export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
export PATH=/usr/local/go/bin:$PATH
mkdir -p /var/tmp/parity_data "$PARITY_OUT"
if ! $PGBIN/pg_isready -q -h 127.0.0.1 -p 5433; then
  if [ ! -d "$PARITY_PG_DIR/data" ]; then
    mkdir -p "$PARITY_PG_DIR" && chown postgres "$PARITY_PG_DIR"
    runuser -u postgres -- $PGBIN/initdb -D "$PARITY_PG_DIR/data" -A trust -U postgres >/dev/null
  fi
  runuser -u postgres -- $PGBIN/pg_ctl -D "$PARITY_PG_DIR/data" -w -l "$PARITY_PG_DIR/pg.log" \
    -o "-p 5433 -c listen_addresses=127.0.0.1 -c fsync=off -c unix_socket_directories=$PARITY_PG_DIR" start >/dev/null
fi
[ -x App/.venv/bin/python ] || python3 -m venv App/.venv
if ! App/.venv/bin/python -c "import playwright, uvicorn, psycopg, httpx" 2>/dev/null; then
  App/.venv/bin/pip install -q -r App/requirements.lock -r App/requirements-dev.txt
  App/.venv/bin/pip install -q playwright==1.63.0
fi
```
   Run (timeout 600000): `cd /home/user/jsfpecharoperations && source scripts/e2e/parity_env.sh > /var/tmp/parity_env.log 2>&1; tail -5 /var/tmp/parity_env.log; $PGBIN/pg_isready -h 127.0.0.1 -p 5433; ls App/.venv/bin/python; App/.venv/bin/python -c "import playwright, uvicorn, psycopg, httpx; print('ok')" 2>&1 | tail -3`
   Expected: `accepting connections`, the python path, `ok`. If `requirements.lock` fails to install,
   stop (section 8). Do NOT run `playwright install`. `git status --short | tail -5` must not list `App/.venv`.

2. Smoke-test the existing probe (no edits yet), to learn the baseline and timing:
   `source scripts/e2e/parity_env.sh; cd App && PARITY_ONLY=admin-home PARITY_WIDTHS=390 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -5`
   Expected: one row `admin-home 390 identical ...` and `{"rows": 1, "verdicts": {...}}`.
   If it does not run, stop and report the last 15 lines of output.

3. Create `scripts/e2e/parity_cases.py` with exactly this content (anchors for later briefs):
```
"""Page table for the visual parity run (briefs 2040-2042). Data only.

One row = (name, path template, persona, group). Persona is "host" (user h1) or "admin".
Anonymous pages are out of scope. Placeholders are filled by page_parity_visual.fill():
{apt} {res} {guest} {inv} {hinv} {fee_a} {alfa} {tok}
Groups: A account+admin, B host core, C money, D setup+cleaning+guide (empty states).
"""

CASES = [
    # A: account and admin
    ("home-host", "/", "host", "A"),
    ("2fa-setup", "/account/2fa/setup", "host", "A"),
    ("2fa-setup-moved", "/account/2fa/setup?moved=1", "host", "A"),
    ("admin-home", "/admin", "admin", "A"),
    ("admin-operations", "/admin/operations", "admin", "A"),
    ("admin-ops-alerts", "/admin/operations/alerts", "admin", "A"),
    ("admin-customers", "/admin/customers", "admin", "A"),
    ("admin-customers-overdue", "/admin/customers?state=overdue", "admin", "A"),
    ("admin-customers-trialing", "/admin/customers?state=trialing", "admin", "A"),
    ("admin-customer", "/admin/customers/{alfa}", "admin", "A"),
    ("admin-fakturace", "/admin/fakturace", "admin", "A"),
    ("privacy-requests", "/privacy-requests", "admin", "A"),
    ("dev-ui", "/dev/ui", "admin", "A"),
    # B: host core
    ("menu", "/menu", "host", "B"),
    ("settings", "/settings", "host", "B"),
    ("settings-archived", "/settings/archived", "host", "B"),
    ("predplatne", "/predplatne", "host", "B"),
    ("onboarding", "/onboarding", "host", "B"),
    ("entities", "/entities", "host", "B"),
    ("apartments", "/apartments", "host", "B"),
    ("apartments-new", "/apartments/new", "host", "B"),
    ("apartment-detail", "/apartments/{apt}", "host", "B"),
    ("reservations", "/reservations", "host", "B"),
    ("reservation-detail", "/reservations/{res}", "host", "B"),
    ("guest-form-new", "/reservations/{res}/guests/new", "host", "B"),
    ("guest-detail", "/guests/{guest}", "host", "B"),
    ("housebook", "/housebook", "host", "B"),
    ("submissions", "/submissions", "host", "B"),
    # C: money
    ("stay-fees", "/stay-fees", "host", "C"),
    ("stay-fee-detail", "/stay-fees/{fee_a}", "host", "C"),
    ("invoices", "/invoices", "host", "C"),
    ("invoices-new", "/invoices/new", "host", "C"),
    ("invoice-detail", "/invoices/{hinv}", "host", "C"),
    ("payments", "/payments", "host", "C"),
    ("payments-new", "/payments/new", "host", "C"),
    ("payments-consent", "/payments/consent", "host", "C"),
    ("booking-sites", "/booking-sites", "host", "C"),
    ("booking-site-setup", "/apartments/{apt}/booking-site", "host", "C"),
    ("property-page-review", "/apartments/{apt}/page", "host", "C"),
    # D: setup, cleaning, guide (empty states: no data is seeded for these yet)
    ("cleaning", "/cleaning", "host", "D"),
    ("cleaning-new", "/cleaning/new", "host", "D"),
    ("cleaning-properties", "/cleaning/properties", "host", "D"),
    ("cleaning-property", "/cleaning/properties/{apt}", "host", "D"),
    ("cleaning-shares", "/cleaning/shares", "host", "D"),
    ("havel", "/havel", "host", "D"),
    ("guide", "/guide", "host", "D"),
    ("apt-guide", "/apartments/{apt}/guide", "host", "D"),
    ("apt-guide-qr", "/apartments/{apt}/guide/qr", "host", "D"),
    ("apt-guide-questions", "/apartments/{apt}/guide/questions", "host", "D"),
    ("leon-settings", "/apartments/{apt}/leon", "host", "D"),
] + [
    (f"wizard-{s}", f"/apartments/{{apt}}/setup/{s}", "host", "D")
    for s in ("property", "calendar", "door_lock", "automation", "guest_link", "police", "stay_fee", "try_it", "done")
] + [
    (f"leon-setup-{s}", f"/apartments/{{apt}}/leon/setup/{s}", "host", "D")
    for s in ("cards", "import", "try", "switch_on", "done")
]
```
   Check: `python3 -c "import sys; sys.path.insert(0,'scripts/e2e'); import parity_cases as c; print(len(c.CASES))" | tail -3` -> `64`.
   (Wizard steps in `property_setup.RETIRED_STEPS` may redirect: that is fine, the redirect target is compared.)

4. Edit `scripts/e2e/page_parity_visual.py` (anchors: `def cases(`, `def main()`, `rows.append({`, `tally = {`):
   a. Add `import parity_cases` after the `import go_page_parity_screenshots as shots` line.
   b. Keep the old `cases()` as `legacy_cases()` (rename only) so the 11 old rows still exist as group `L`.
   c. Add `def fill(path, refs, seed)` that does `path.format(apt=refs["apartment_id"], res=refs["reservation_id"], guest=refs["guest_id"], inv=refs["invoice_id"], hinv=seed["host_invoices"][-1], fee_a=seed["fee"]["a"], alfa=seed["alfa"]["id"], tok=refs["token"])`.
   d. Add `def table_cases(refs, seed, py, go)` yielding, for each row of `parity_cases.CASES`, for `lang` in `("cs", "en")`: name `f"{name}-{lang}"`, path = filled path plus `("&" if "?" in path else "?") + "lang=" + lang`, cookies `(py["host"], go["h1"])` for persona host, `(py["admin"], go["admin"])` for admin, and the group. A file-top comment says the old `legacy_cases` rows are anonymous or lang-less and run only with `PARITY_GROUP=L`.
   e. `main()`: read `PARITY_GROUP` (comma list, default `A,B,C,D`); skip a case whose group is not selected; `PARITY_ONLY` still filters by name (exact, or prefix match when the value ends in `*`).
   f. Wrap the `shots.run_case(...)` call in `try/except Exception as exc`: on error append a row with `verdict="error"`, `width=0`, `note=str(exc)[:200]`, and continue. Add `"error"` to the `tally` keys; exit code is 1 when `visible` or `error` is non-zero.
   g. In each row store `side_png` and `diff_png` (from `r.side_png`, `r.diff_png`) and `group`.
   h. After the loop, write `OUT/report-<groups>.md` (groups joined by `-`): a table `| case | path | 390 | 768 | 1280 |` with the verdict word per width (`ERR` for error rows) plus, below it, a list of every non-identical row with its `side_png` path. Print its path.
   Check: `source scripts/e2e/parity_env.sh; python3 -m py_compile scripts/e2e/page_parity_visual.py scripts/e2e/parity_cases.py && echo compiled | tail -3`.

5. Run the groups, one command each (timeout 600000 each; if one hits the timeout, re-run it with `PARITY_WIDTHS=390,1280` and say so in the report; never skip a group silently):
   `source scripts/e2e/parity_env.sh; cd App && PARITY_GROUP=A .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12`
   then the same for `B`, `C`, `D`. Each ends with a line like `{"rows": N, "verdicts": {"identical": ..., "invisible": ..., "visible": ..., "error": ...}}`.
   Group A: 13 pages x 2 languages x 3 widths = 78 rows. B: 15x2x3 = 90. C: 11x2x3 = 66. D: 25x2x3 = 150.

6. For every row that is `visible` or `error`: open its `*-side.png` (Read tool, one image per row; the file is py on the left, go on the right) at 390 first, then look at 1280 only if 390 is identical. Group rows that share a cause (same component in several pages) and describe each cause once in plain words ("Go shows the filter chips on one line, Python wraps them", "Go page returns 404"). Budget: at most 12 image reads in total; if there are more distinct visible rows, describe the worst 12 by `diff_pixels` and list the rest as "not inspected" with their paths.
   For an `error` row, say which stack failed and with which status (the exception text names the URL).
   A visible row that only differs in a banner or counter that one stack consumed first: re-run it alone (`PARITY_ONLY=<name> PARITY_WIDTHS=390`) once; if it becomes identical, write "one-shot state" and name the state.

7. Write `docs/tasks/2040-report.md` (format of `docs/tasks/2028-report.md`): totals per verdict, then one table with every case (`name | path | lang | 390 | 768 | 1280`) taken from the generated reports, then "Visible differences" (one plain-words paragraph per cause, with the `*-side.png` path of one example), "Errors", "Not inspected", and "Environment notes" (what worked in `parity_env.sh`, wall time per group).
   Images stay in `/var/tmp/parity-visual/` (outside the repo, never committed; they vanish with the container, so the descriptions must be complete).

8. Run: `python3 scripts/context_lint.py 2>&1 | tail -3`; `cd App && .venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q --tb=short -x 2>&1 | tail -30` (the test-map row for `go_page_parity_screenshots.py`; this brief did not edit that file, so a failure is a pre-existing one: report it, do not fix it).
   Commit only the four files of section 3 with message `2040: parity harness and host pages (report)`.

## 5. Do not touch

`App/app/**`, `go/**`, `scripts/e2e/seed.py`, `scripts/e2e/page_parity_audit.py`, `App/scripts/go_page_parity_screenshots.py`, `PRE_SQL` (add a statement only if a visible row is proven one-shot state, and then only report it, do not add).

## 6. Commands

```
source scripts/e2e/parity_env.sh
cd App && PARITY_GROUP=A .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -12
python3 scripts/context_lint.py 2>&1 | tail -3
```

## 7. Acceptance

- [ ] `parity_env.sh` brings up Postgres, the venv and the env from a fresh container with one `source`.
- [ ] 64 table pages x 2 languages x 3 widths = 384 comparison rows exist (identical, invisible, visible or error), none silently skipped.
- [ ] `docs/tasks/2040-report.md` has the all-rows table and a plain-words description for every visible cause.
- [ ] No file outside section 3 changed (`git status --short | tail -10`); `context_lint` passes.

## 8. Stop and ask

- The venv install, Postgres start, or the step 2 smoke run fails: stop, report the last 15 lines.
- 25 tool calls used: stop, commit what exists, write the report with the groups done and say which are missing (the next chat re-runs `PARITY_GROUP=<missing>`).
- Never edit Python or Go to make a row identical. Never silence a row.

## 9. Report

`docs/tasks/2040-report.md`.
