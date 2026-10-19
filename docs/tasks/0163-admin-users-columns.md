# 0163: admin users page, column tops line up and manage fields stay readable

Status: done
Depends on: 0162 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

The orchestrator's review of the `/admin/users?manage=1` shots at 1280 and 2000 px found two faults:
1. The "Create a host" column on the right starts about 65 px lower than the users table on the left. Both columns of `.split.wide` should start on one line.
2. The Manage section's e-mail and reason fields stretch across the whole 1080 px lane. Cap the section at the form width.

## 2. Context

`users.html` puts the table in `<section>` and the create form in `<aside class="ui-section">` inside `<div class="split wide">`. The aside's top spacing (the section margin, plus the first `h2`'s margin) pushes it down. `host2.css` loads last, so equal-specificity rules win. S2 lint: no bare px in margin, padding, gap or font-size.

## 3. Files

`App/app/static/host2.css` (append), `App/app/templates/base.html` (host2.css key), `App/tests/static_versions.json`, `App/tests/test_design_guardrails_browser.py` (append one test), `docs/tasks/0163-*`.

## 4. Steps

1. Append to the end of `App/app/static/host2.css`:

```
/* 0163: split columns start on one line; the manage form keeps a readable width */
.host-workspace .split.wide > section, .host-workspace .split.wide > aside { margin-top: 0; padding-top: 0; }
.host-workspace .split.wide > section > .ui-section:first-child, .host-workspace .split.wide > aside > :first-child { margin-top: 0; padding-top: 0; }
.host-workspace #user-manage { max-width: 40rem; }
```

   From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2`. Expected: OK.
2. Find the host2.css key: `grep -rn "/static/host2.css?v=" App/app/templates | tail -3`. Change it to `20261019-0163`. Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`. Expected: passed.
3. Append to `App/tests/test_design_guardrails_browser.py` a test named `test_admin_users_columns_start_on_one_line`. Copy the setup (server, admin login, browser launch) from `test_admin_pages_pass_the_layout_guard` in the same file. At width 1280, go to `/admin/users?manage=<the admin user's id>` exactly as that test does. Then assert:
   - `page.evaluate("() => { const s = document.querySelector('.split.wide'); const a = s.children[0].getBoundingClientRect().top, b = s.children[1].getBoundingClientRect().top; return Math.abs(a - b); }") <= 2`
   - `page.locator('#user-manage input[type=email]').first.bounding_box()['width'] <= 660`

   If the manage page shows no e-mail input, use the first visible `#user-manage input` that is not hidden.
4. Tests from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q -rs 2>&1 | tail -6` (foreground, timeout 600000). Then from the repo root: `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence`. Expected: all passed, 0 skipped. If the new test fails on the first assertion, report the measured difference and stop; do not change the numbers.
5. Commit: `git add App/app/static/host2.css App/app/templates/base.html App/tests/static_versions.json App/tests/test_design_guardrails_browser.py docs/tasks/0163-* && git commit -m "0163: admin users columns line up, manage form width"`.

## 5. Do not touch

Anything else; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Block appended, key bumped, new test passes, guard file passes with 0 skipped.

## 8. Stop and ask

An anchor is missing, or a test fails twice.

## 9. Report

`docs/tasks/0163-report.md`, short; `Status: review`.
