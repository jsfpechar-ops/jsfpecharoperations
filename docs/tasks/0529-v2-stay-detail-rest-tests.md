# 0529: Stay page v2, part 2: police card, door code, payment, action bar, settings, tests
Status: todo
Depends on: 0528 | Base commit: task/0528-v2-stay-detail head | Branch: task/0529-v2-stay-detail-rest
Executor: Haiku 5.5 | Fits one session: 30 tool calls (a continuation session is normal)

## 1. Objective
Finish the stay page from 0528 1:1 with the mockups (computer `data-v="stay"`, phone `data-s="pobyt"`, `pobyt-anna`, `pobyt-marco` in the two files under `docs/design/mockup/`) and prove it with the shared design test at six widths.

## 2. Context and decisions (orchestrator)
- Filing logic is untouchable: forms, conditions, hidden fields, receipts and the file-by-hand flow keep their behaviour; only wrappers, classes and placement change.
- **Police card:** `<h2>` (phone `h2.sec`) "Hlášení cizinecké policii" (computer) / "Hlášení policii" (phone; use the existing `host.reporting` key for both if the texts differ only slightly, and note it) + `.card`: `<b>` the old "Now" note text (the `stay-command-note` logic from 0528), a grey line with the deadline (`deadline_badge` text). Failed stay: the card gets the mockup's red look (`pobyt-anna`: `background:var(--bads)`, title in `--bad`) with the refusal reason. Under the card keep the submissions table (as `.card` > `table`) and the file-by-hand `details` (as a `.card`), unchanged inside.
- **Door code:** `h2` + `.card` with `<div class="code">` PIN (issued) and `<small>` validity, key `.ic.acc` on the right (phone), as in the mockup. Other door-code states: the existing text in the card. Keep `id="door-code"` and `id="door-code-line"`.
- **Reported stay with nothing to do:** show the mockup's `.allgood` line above the door code (existing "all reported" key if any).
- **Request payment:** `.list` with `a.link` → `/payments?reservation_id={id}#new-request` (`stays.row.request_payment`), active stays only.
- **Phone action bar:** `<div class="actbar">` (0718's name for the mockup `.bar`) with one `.btn`: the same primary CTA the computer header shows (send / fix / receipt), else the resend-claim form's button when enabled, else no bar. Same forms, not copies with new logic: render the form once and place it with CSS if possible; if it must render twice, both copies must be identical forms.
- **Settings:** keep the whole settings section as a collapsed `details.card` at the bottom ("Nastavení pobytu"), inside unchanged.
- Remove leftover dead markup/CSS from the old layout (lean rule); new CSS only for what app2.css lacks (`.code`, red card), in the `/* 0528 stay page */` block. Key `20261101-0529`, `--write` manifest.
- **Tests:** add a `PAGES` entry in `App/tests/v2_mockup.py`: name `stay`, path = a seeded active stay with three guests (see how the shared test seeds data; add a fixture there only if needed), view `stay`, phone_view `pobyt`; selectors `.crumb`, `.head h1`, `.head .sub`, `.head .btn`, `.head .btn.ghost`, `main h2`, `main .card`, `main table th`, `main table td`, `main .pill`, `.code`; phone_selectors `.tabs`, `.top .round`, `.big`, `.sub`, `.facts`, `.facts b`, `.facts small`, `h2.sec`, `.list .row`, `.row .ic`, `.row .t b`, `.row .t small`, `.card`, `.code`, `.list .link`, `.actbar .btn`; data-dependent ones to `missing_ok` with a reason. Fix mismatches by copying mockup values, never by loosening the test. Update old stay-page tests only where they assert removed markup (`guest-card`, `#now`, `stay-command`), keeping their intent; `test_0525_stay_detail.py` follows the new markup. `test_design_stay_detail.py::test_no_raw_style_or_legacy_control_in_the_template` predates v2: keep the no-`style="` rule, drop the `class="btn`/`class="pill`/`ui-btn-primary`/`ui-table-stack` asserts (v2 uses the mockup classes; one coral `.btn` in the header is the new rule, assert that instead). Facts have no check-in time (no variable for it): accepted departure.

## 3. Files
`App/app/templates/reservation_detail.html`, `App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `docs/design/catalog.json`, `App/tests/v2_mockup.py`, stay-page tests named in section 6, screenshots `docs/tasks/screenshots-0529/` (app at 320, 390, 768, 1024, 1280, 1440; mockup stay 1280, pobyt 390), report `docs/tasks/0529-report.md`.

## 4. Steps
1. Police card, door code, allgood, payment link. Commit.
2. Action bar, settings details, dead CSS removal, key, manifest. Commit.
3. PAGES entry, shared test green, old tests updated. Commit.
4. Screenshots (Read the 390 and 1280 pairs once), commands, report. Commit.

## 5. Do not touch
Shared test checks/tolerances, `_shell_v2.html`, JS, routes, the stays list.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, `UBYHOST_REQUIRE_BROWSER=1`)
`.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k stay -q --tb=short -rs 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_0525_stay_detail.py tests/test_design_stay_detail.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_host_stay_detail_layout_browser.py tests/test_host_stay_actions_browser.py tests/test_onboarding_followup_browser.py tests/test_host_wide_geometry_browser.py tests/test_0199_phone_geometry_browser.py tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -30`. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All pass, 0 skipped; every filing form still present with the same action and fields.

## 8. Stop and ask
Stop if any send, fix, receipt or file-by-hand test changes result, or if a geometry rule fails in the shared shell.

## 9. Report
`docs/tasks/0529-report.md`: status, test tails, edited assertions, screenshots, remaining visual differences.
