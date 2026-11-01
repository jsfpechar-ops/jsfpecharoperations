# 0723: Overview polish after 0722 (phone gaps, demo link, quiet links row, dead keys)
Status: done
Depends on: 0722 | Base commit: claude/project-thread-50hyv5 | Branch: task/0723-v2-overview-polish
Executor: Haiku 5.5 | Fits one session: 20 tool calls

## 1. Objective
Fix what the orchestrator saw in `docs/tasks/screenshots-0722/overview-390.png` and `overview-1280.png` (Read both first), and remove the i18n keys 0722 left unused.

## 2. Context and decisions (orchestrator, 2026-11-01 19:20)
1. Phone (below 1024): "Clear demo data" still shows under the date. Hide it with `.ph-hide` like the other quiet links (desktop keeps it).
2. Phone: there are large empty gaps under the date block, under "Show 3 more" and above "Today". Margins or padding of hidden elements, or of their wrappers, still take space. Find them with one evaluate call: list every element in `main` that has zero height but a non-zero margin/padding, or a wrapper whose children are all hidden. Then remove the gaps in the phone block so the spacing matches the mockup Dnes rhythm: 24-28 px between sections, as in `h2.sec` margins.
3. Desktop: the header quiet links ("How does this work?", "+ Cleaning", "Clear demo data") still sit on three lines. Put them in one wrapping flex row (`display:flex; flex-wrap:wrap; gap:4px 14px; align-items:center`), as brief 0715 item 1 and 0720 step 0 asked. Check which wrapper holds them; the help `<details>` may sit outside `p.ov-links`, in which case wrap both in one container in dashboard.html.
4. Dead keys: 0722 switched needs_you.py to `needs_you.short.*`. For each of `needs_you.stay.failed`, `needs_you.stay.overdue`, `needs_you.stay.ready`, `needs_you.stay.no_form`, `needs_you.stay.forms_missing`, `needs_you.setup`, `needs_you.paste`, run `grep -rn "<key>" App/app App/tests --include=*.py --include=*.html --include=*.js`. If the key is used only in the i18n dicts, delete it from host_i18n.py (en, cs) and host_vi_i18n.py. Keep any key that is still used. If a test checks for a removed key, read why first; if the test only checks that the text exists, point it at the short key.
5. Bump the app2.css key to `20261101-0723` if app2.css changed, then `--write` the manifest.

## 3. Files
`App/app/static/app2.css`, `App/app/templates/dashboard.html`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, tests only per item 4, screenshots `docs/tasks/screenshots-0723/overview-390.png` and `overview-1280.png`, report `docs/tasks/0723-report.md`.

## 4. Steps
1. Items 1-3. Commit.
2. Item 4. Commit.
3. Key, tests, screenshots (Read them), report. Commit.

## 5. Do not touch
`app.js`, `needs_you.py`, routes, other pages.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`)
`.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_design_dashboard.py tests/test_dashboard_missing_banner.py tests/test_dashboard_order.py tests/test_needs_you_dashboard_0241.py tests/test_signed_in_chrome.py tests/test_host_language.py tests/test_i18n*.py tests/test_static_versions.py tests/test_0252_touch_sweep_browser.py -q --tb=line -rs 2>&1 | tail -20` (0 skipped). Screenshots: `UBYHOST_SHOTS_V2=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q`, copy the two PNGs to screenshots-0723, then `git checkout -- docs/tasks/screenshots-0710` and remove the untracked files that run created. Ruff subset as in CI. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
At 390 there is no demo link and no large gaps; at 1280 the quiet links sit in one row; dead keys are gone; all listed tests pass, 0 skipped.

## 8. Stop and ask
Stop if a "dead" key turns out to be used by an email, push or PDF template.

## 9. Report
`docs/tasks/0723-report.md`: status, test tails, screenshots, removed keys.
