# 0722: compact phone Overview (owner: "much more compact with phone")
Status: todo
Depends on: 0720, 0721 merged into claude/project-thread-50hyv5 | Branch: task/0722-v2-phone-compact
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Owner, 2026-11-01 18:56: "we have to be much more compact with phone". Below 1024 px, `/` shows only what the phone mockup's Dnes screen shows (`docs/design/mockup/ubyhost-phone-v1.html`, `data-s="dnes"`): greeting and date, "Potřebuje vás" with its cards, "Dnes" with the horizontal stay cards, and the month line at the bottom. Everything else is hidden on phone and stays on desktop.

## 2. Context and decisions (orchestrator)
- Shared utility: add `body.v2 .ph-hide` to app2.css (`display:none !important` below 1024 px, nothing above). Page threads will use the same class. Add it to `docs/design/catalog.json` (design lint).
- Below 1024 px, hide with `.ph-hide`: the help `<details data-how>`, the header quiet links (Cleaning is in Menu; "Clear demo data" stays on desktop), the alerts stack cards that duplicate needs-you (alerts without a needs-you card stay visible), and any onboarding/finish card except the one-line strip.
- Needs-you on phone: show the first 2 cards (mockup shows 2), and put the rest behind the existing "Show N more" `<details>`. Desktop keeps 4 (0717 decision). Do it with CSS where possible (e.g. `.todo > .card.need:nth-child(n+3)` hidden below 1024 unless the details is open), or move the threshold logic into the template. Keep one markup.
- Needs-you card text, as in the mockup: bold line = the problem, short (e.g. "Police deadline passed", "2 guests not registered"); small line = property · dates. Today the bold line is "Property · dates" and the problem is the small line. Swap them for every card type, using the existing i18n text for the problem. If a problem text is long, use the short title key if one exists (grep `needs_you` keys in host_i18n.py); add short keys in en/cs/vi only where none exists. The desktop uses the same markup, which is fine (the desktop mockup reads the same way).
- Mock-environment banner (only on non-production): on phone, one line, with the title only, and the explanation behind a `<details>` (no JS). Desktop unchanged. It sits in `_shell_v2.html` or base.html; change only its phone CSS and wrap the explanation if needed.
- Month line: on phone it goes last, after "Dnes" (mockup order). Use CSS `order` in a flex column or move it in the template if the desktop order is the same there.
- Never remove a feature from desktop. On phone, everything hidden must still be reachable: Cleaning via Menu, help via Menu → Help, demo-data clearing on desktop.
- Update `App/tests/v2_mockup.py` only if a phone selector changes. Bump the app2.css key to `20261101-0722` and `--write` the manifest.

## 3. Files
`App/app/static/app2.css`, `App/app/templates/dashboard.html`, `App/app/templates/_shell_v2.html` (env banner wrapper only), `App/app/host_i18n.py`/`host_vi_i18n.py` (short keys only if missing), `docs/design/catalog.json`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `App/tests/v2_mockup.py` (if needed), screenshots `docs/tasks/screenshots-0722/` (overview 390 and 768, before and after), report `docs/tasks/0722-report.md`.

## 4. Steps
1. `.ph-hide` plus hiding plus env banner. Commit.
2. Needs-you 2-on-phone plus card text swap plus month line order. Commit.
3. Tests, key, screenshots (Read them, compare with the mockup Dnes at 390), report. Commit.

## 5. Do not touch
`app.js`, routes, other pages' templates.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`)
`.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_design_dashboard.py tests/test_dashboard_queue_copy.py tests/test_0520_overview_today.py tests/test_0375_needs_you_and_open.py tests/test_needs_you_dashboard_0241.py tests/test_dashboard_missing_banner.py tests/test_dashboard_order.py tests/test_onboarding.py tests/test_page_help_0277.py tests/test_environment_banner.py tests/test_static_versions.py tests/test_0252_touch_sweep_browser.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped). Ruff subset as in CI. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
At 390 the Overview reads like the mockup Dnes screen: no help block, no quiet links, at most 2 needs cards before "Show more", a one-line env banner, and the month line last. Desktop is unchanged. All listed tests pass, 0 skipped.

## 8. Stop and ask
Stop if a hidden item would become unreachable on phone, or if a needs-you type has no short problem text and no obvious wording.

## 9. Report
`docs/tasks/0722-report.md`: status, test tails, screenshots before/after, every phone-only hide listed.
