# 1302: Go port of property and business details lists

Status: todo
Depends on: 1301 (incl. 1301-fix-1), 1380 (PR #985) | Base commit: d25f8b6 | Branch: task/1302-go-property-lists
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Port two host GET pages of `App/app/routes/admin.py` to Go in `go/internal/web/properties/`: `GET /entities` (the business details list with the add form) and `GET /apartments` for a workspace with no live property (the empty state). Same status, `Location`, `<title>` and page content (every tag, attribute and text run inside `div.ui-page`) as Python, proven by a golden file the Python test writes and the Go test replays on Postgres; every branch not ported answers `501` instead of a different page, and the routes stay switched off (nothing is added to `UBYHOST_GO_PATHS`).

## 2. Context

Every file was written and run green in a dry run by the brief writer, on SQLite and on Postgres; the finished files are in `docs/plans/1302-files/` (flat bundle). You do not write code: step 1 copies them, step 2 checks their sha256, steps 3-4 generate the two derived files, the rest are checks. **Do not open the bundle files**; the reviewer reads them.

Python sources ported (read-only, for the reviewer):

- `admin.py` `entities` (~858), `_entities_page` (~903, the branch with no `edit_entity`), `_entities_list_context` (~1091); `entities.html` lines 1-18 and 74-162; `_entity_business_fields.html` `business_form_body('new_', none)` (inlined; `phone_form_parts('')` is empty); `partials/settings_back_header.html` (inlined). `account_email` is the signed-in account's email (the admin inside a workspace); the lists are the workspace's.
- `admin.py` `apartments_list` (~1344) and `apartments.html` `{% else %}` branch: `has_operator` = the workspace has a non-archived business (`access.entities`).
- The `onboarding_banner(onboarding)` both pages call: `onboarding.progress` reduced to `is_dismissed` (`settings` key `onboarding_dismissed_<workspace>` = `"1"`), `wizard_step` (no live property: `name`; `_address_complete`; `_bookings_complete`: active feeds, else a count of active manual reservations, no guest fields read) and `setup_url`. Private copy in `lists.go`.
- `_host_alerts.html` is inside the `/entities` body; its open-alert query is `alerts.open_alerts(workspace)` (own alerts plus `SYSTEM_ALERT_KINDS`).

Not ported; Go answers **501** (`not served by Go yet: ...`), a golden case pins each:

- `/entities?edit=N` (`edit` all ASCII digits, or any non-ASCII value, since Python's `isdigit` takes those): the business editor with Invoice details (billing, signature).
- `/entities` when the workspace has an open alert (or an open system alert): host alerts come with brief 1381.
- `/apartments` when the workspace has a live property: the setup chips read filing state (`_apartment_issues`, `ubyport_auth_failed` alerts), calendars, the lock and the guest link.
- Left out entirely: every POST (1300 did the archive/restore/delete ones), the "fill from register" (ARES) flow (the button is static markup of the add form; its POST is not here). No guest personal data is read.

Go code reused (read-only): `hostweb.Login`, `hostweb.Lang`, `layout.Render`, `layout.Page`, `layout.Env` and the macros `icon`, `help_tip`, `tip_label`, `row_menu_begin/end`, `page_help`, `empty_state` (only constant hrefs); from 1300/1301: `catalog`, `pages`, `Pages`, `Wrap`, `fail`, `safeLocalPath`, `pyStrip`, `accountEmailSQL`, and in the test `testPool`, `seedWorld`, `readJSON`, `sqlValue`, `testEnv`, `pageCase`, `pageGolden`, `extractItems`, `squash`, `titleRE`. Links built from DB ids (`/entities?edit=N`, `row_open`, the banner's `setup_url`) are written in `lists.tmpl` with html/template escaping, never passed to a layout macro (until 1381). `RegisterLists` is a new function, so 1301's `RegisterPages` is unchanged; `register_web_properties.go` gains one line. The new keys are appended to `i18n_keys.txt`, so one `i18n.json` serves 1300, 1301 and 1302.

Golden cases (17): en/cs/vi on each page; the admin inside workspace 132001 and in his own workspace (different businesses and has_operator, so an account/workspace mix-up fails); archived rows with and without linked properties; an empty list; banners for steps name and bookings and a dismissed one; `next` kept and an unsafe `next` dropped; `edit=abc` (not digits, list shown); signed out; the three 501 cases. Python holds open system alerts of other tests while it runs (restored after).

Rules that apply: AGENTS.md hard rule 2 (no outbound request, no new personal-data field), 3 (seed has only made-up names and `example.test` addresses), 4 (no new dependency), 5 (Postgres SQL in Go, no schema change). Rules 7/10 do not apply yet: nothing is served and no Python template changes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/lists.go` | create | `RegisterLists`, `/entities`, `/apartments`, banner copy, 501 branches |
| `go/internal/web/properties/lists_test.go` | create | golden replay on Postgres, register test, helper tests |
| `go/internal/web/properties/templates/lists.tmpl` | create | entities.html (list) and apartments.html (empty) as Go templates |
| `go/internal/web/properties/i18n_keys.txt` | replace | 1301's keys plus 40 list keys (bundle copy) |
| `go/internal/web/properties/i18n.json` | regenerate (step 3) | catalog from `App/app/host_i18n.py` |
| `go/internal/web/properties/testdata/lists_cases.json` | create | seed rows and 17 cases |
| `go/internal/web/properties/testdata/lists_golden.json` | create (generated, step 4) | what Python rendered per case |
| `go/cmd/ubyhost-web/register_web_properties.go` | replace | one added line: `properties.RegisterLists(...)`, comment |
| `App/tests/test_go_properties_lists.py` | create | Python render; writes and checks the golden |
| `docs/tasks/1302-go-property-lists.md` | edit | `Status:` line only |
| `docs/tasks/1302-report.md` | create | report |

No other file may change.

## 4. Steps

1. Check you are on the branch, then copy the seven bundle files (run from the repo root):

```bash
git branch --show-current
B=docs/plans/1302-files P=go/internal/web/properties
cp $B/lists.go $P/lists.go && cp $B/lists_test.go $P/lists_test.go && cp $B/lists.tmpl $P/templates/lists.tmpl
cp $B/lists_cases.json $P/testdata/lists_cases.json && cp $B/i18n_keys.txt $P/i18n_keys.txt
cp $B/register_web_properties.go go/cmd/ubyhost-web/register_web_properties.go
cp $B/test_go_properties_lists.py App/tests/test_go_properties_lists.py
```

Expected first line: `task/1302-go-property-lists`. Anything else: stop (§8).

2. Check the copied files:

```bash
sha256sum -c <<'SUMS' 2>&1 | tail -10
d632a86a66638b316ed81f16e5f74a5c03a5e7edd1c9ebe693559fb8c8c6d0ed  go/internal/web/properties/lists.go
9e9f17ab7cf79bcb653708115dcdbf5ee8a32a32edee881bbf2e6c1100646583  go/internal/web/properties/lists_test.go
81133c6bf9dd6c9027d5a4a0687866000e0b381574971bc854e9e1a5c984a00c  go/internal/web/properties/templates/lists.tmpl
cd372e03bcfd0d6d71257e01ef9d35acde869d7db3a77d8b2aaa61395346a04b  go/internal/web/properties/testdata/lists_cases.json
4e806bfb1dd434275699a1e261893f9c207838aa0cb7877a6aa409b766f60f84  go/internal/web/properties/i18n_keys.txt
d50960bf8b6ec8fcdcef8683ab0c1c85421cf2ca29f09b2db4b327decb533d31  go/cmd/ubyhost-web/register_web_properties.go
09df1f661c7eb82a2af34d19a01a0357054349c187b76af6bdfd1972d60c5a33  App/tests/test_go_properties_lists.py
SUMS
```

Expected: 7 lines ending `OK`. Any `FAILED`: stop (§8).

3. Regenerate the catalog:

```bash
cd App && .venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -3 && sha256sum ../go/internal/web/properties/i18n.json
```

Expected: `wrote .../go/internal/web/properties/i18n.json`, then `36ee3c588177a52d875551018049a49e57a3f5d2a39f6e4cac492a693b6d57dd  ../go/internal/web/properties/i18n.json`. Another `wrote` line for a different package: stop (§8).

4. Generate the golden (Python on the fixture database) and check it:

```bash
cd App && UBYHOST_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_go_properties_lists.py -q --tb=short -x 2>&1 | tail -5 && sha256sum ../go/internal/web/properties/testdata/lists_golden.json
```

Expected: `2 passed`, then `7b1ea759f3942fcd44d3d7b3328cf26790809a91837c04a19d05c0dd3ffbbb20  ../go/internal/web/properties/testdata/lists_golden.json`. A different sum: stop (§8); never edit the golden by hand.

5. Run the checks in §6. Then commit:

```bash
git add go/internal/web/properties go/cmd/ubyhost-web/register_web_properties.go App/tests/test_go_properties_lists.py && git commit -q -m "1302: Go port of property and business details lists" && git show --stat HEAD | tail -15
```

6. Set `Status: review` in this brief, write `docs/tasks/1302-report.md` (§9), commit both.

## 5. Do not touch

- Read-only: `go/internal/hostweb/` (including `layout/`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/palette/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, 1300's and 1301's files (`properties.go`, `localpath.go`, `slug.go`, `pages.go`, `properties_test.go`, `pages_test.go`, `templates/guide.tmpl`, `testdata/actions_*`, `testdata/pages_*`, `App/tests/test_go_properties_actions.py`, `App/tests/test_go_properties_pages.py`), `App/tests/conftest.py`, every file under `App/app/` and `App/scripts/`.
- `docs/ENVIRONMENT.md`, `docs/context/status.md`, `test-map.md`, `decisions.md`, `known-issues.md`.
- Nothing is added to `UBYHOST_GO_PATHS` anywhere. No bare `GET /` route.
- Do not edit the copied files, `docs/plans/1302-files/` or the golden by hand. No new dependency, no `go get`, no `go mod tidy`.
- Hard rules 3, 4, 5, 8 of AGENTS.md. Never push to `main`; never merge.

## 6. Commands

From the repo root, with the test database the environment gives (`export UBYHOST_TEST_DATABASE_URL=postgresql://...`; unset means the Go replay skips, which is a stop (§8), not a pass):

```bash
cd go && test -z "$(gofmt -l .)" && go vet ./... 2>&1 | tail -5 && go test -count=1 -v ./internal/web/properties/ ./internal/hostweb/... ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- (FAIL|SKIP)|ok|FAIL)|Lists|Pages' | tail -30 && go build -o /dev/null ./cmd/ubyhost-web && echo BUILD OK
```

Expected: no `SKIP` or `FAIL`; `--- PASS: TestListsMatchPython`, `--- PASS: TestListsRegisterDoesNotTouchThePool`, `--- PASS: TestPagesMatchPython`; `ok` for properties, hostweb, hostweb/layout and cmd/ubyhost-web; `BUILD OK`.

```bash
cd App && .venv/bin/python -m pytest tests/test_go_properties_lists.py tests/test_go_properties_pages.py tests/test_go_properties_actions.py -q --tb=short -x 2>&1 | tail -5
cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -3; echo "check exit $?"
python3 scripts/context_lint.py 2>&1 | tail -3
git status --short | tail -20
```

Expected: `6 passed`; no `stale:` line; `context lint: OK`; after the commit, a clean tree.

## 7. Acceptance

- [ ] Step 2: 7 `OK`; steps 3 and 4: the sha256 sums given there.
- [ ] `go vet ./...` clean, `gofmt -l .` empty, `go build ./cmd/ubyhost-web` OK.
- [ ] `TestListsMatchPython` ran (not skipped) and passed; 1300's and 1301's tests still pass.
- [ ] Python: 6 passed; `go_host_i18n.py --check` prints no `stale:`.
- [ ] `git diff --stat d25f8b6..HEAD` lists only §3 paths, this brief and `docs/plans/1302-files/`.
- [ ] `grep -rn UBYHOST_GO_PATHS go/internal/web go/cmd/ubyhost-web/register_web_properties.go` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- you are not on `task/1302-go-property-lists`, a `cp` fails, or a sum in steps 2-4 differs;
- `TestListsMatchPython` is skipped or a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, or `go` wants to change `go.mod`/`go.sum`;
- a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1302-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat d25f8b6..HEAD`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left, and one line naming the three 501 branches of §2 as not ported.

## Risk list (for the reviewer)

Read these against the Python sources in §2:

- `go/internal/web/properties/lists.go`: login first; lists, has_operator and the banner read `host.Workspace.ID`, `account_email` reads `host.Account.ID`; `edit` and `next` take the last query value (Starlette); the 501 tests (`editAsked`, open-alert count incl. system kinds, live-property count) run before anything renders; `onboardingBanner` matches `progress`/`wizard_step`/`setup_url` (`ORDER BY a.id`, archived properties skipped, a dismissed value other than `"1"` still shows the banner).
- `templates/lists.tmpl`: same tags, attributes and text as entities.html (no editor) and the apartments.html empty branch; DB ids only in hrefs written there; layout macros get constant hrefs only.
- `lists_test.go` / `test_go_properties_lists.py`: Go checks status 501 on the three not-ported cases and full items on the rest; Python's hold-and-restore of open system alerts touches only rows it put back.

Known differences left on purpose: the shell around `div.ui-page` is not compared (layout's test; 1381). `dateCZ` reads the first ten bytes as `YYYY-MM-DD` (Python `strptime` also takes one-digit months; stored values are ISO). `addressComplete` counts `unicode.IsDigit` (Nd) where Python's `isdigit` also counts superscript digits.

## Owner steps

1. Wait for the draft PR's CI to go green (the `go` job runs the Postgres replay).
2. Nothing to deploy or configure: the routes stay off until a later brief adds them to `UBYHOST_GO_PATHS`, after 1381 and after the 501 branches are ported.
