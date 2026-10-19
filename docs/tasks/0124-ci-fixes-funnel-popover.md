# 0124: CI fixes before the design switch (funnel window, create popover reclamp)

Status: review
Depends on: none | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0124 step k`. Never push, never open a PR.

## 1. Objective

Fix two pre-existing CI failures on the branch so the design briefs start from green: the funnel test counts hosts created after its last bucket, and the dashboard create popover is clamped against its old height after the type switch. Neither is caused by the design work.

## 2. Context

Failure 1: `test_weekly_buckets_hosts_in_window` queries hosts with only a lower bound, so accounts created by earlier tests at the real date (after the last bucket ending Monday 2026-10-19) are counted while the series stops at that Monday.

Anchor A, `App/tests/test_admin_funnel.py`:

```
    since = first.isoformat()
    in_window = db.query(
        "SELECT COUNT(*) AS n FROM user_account WHERE role = 'host' AND created_at >= ?",
        (since,),
    )[0]["n"]
```

Failure 2: `test_create_popover_reclamps_when_switching_to_taller_stay_form[1280]` (Chrome 153, Playwright 1.63): after `setCreateKind("stay")` the dialog is re-placed in the next animation frame, but `getBoundingClientRect()` still returns the shorter cleaning-form height at that moment, so `top` is clamped for 516 px and the 646 px stay form ends at y 1118 in a 1000 px viewport. Root cause: the reclamp runs once, on a frame, instead of whenever the dialog's size changes. Fix: observe the dialog's size and re-run `placeCreate` on every change (the function is idempotent and already handles the phone branch).

Anchor B, `App/app/static/dashboard-calendar.js`:

```
    if (createDialog.open) requestAnimationFrame(() => placeCreate(createAnchor));
  }
  let createAnchor = null, createAnchorDate = "";
  function placeCreate(anchor) {
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_admin_funnel.py` | edit | upper bound on the in-window query |
| `App/app/static/dashboard-calendar.js` | edit | ResizeObserver re-places the create dialog |
| `App/app/templates/base.html` | edit | cache-bust the calendar script version string only if the file is linked there (see step 3) |

No other file may change.

## 4. Steps

1. In `App/tests/test_admin_funnel.py`, replace Anchor A with:

```
    since = first.isoformat()
    until = (admin_funnel._monday(NOW.date()) + timedelta(weeks=1)).isoformat()
    in_window = db.query(
        "SELECT COUNT(*) AS n FROM user_account WHERE role = 'host' AND created_at >= ? AND created_at < ?",
        (since, until),
    )[0]["n"]
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_admin_funnel.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed. Then run the whole file together with a test that creates hosts at the real date to prove the fix: `cd App && .venv/bin/python -m pytest tests/test_signed_in_chrome.py tests/test_admin_funnel.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed.

2. In `App/app/static/dashboard-calendar.js`, replace Anchor B with:

```
    if (createDialog.open) requestAnimationFrame(() => placeCreate(createAnchor));
  }
  let createAnchor = null, createAnchorDate = "";
  // The create form changes height when its kind switches (cleaning to stay)
  // and when a field shows or hides; a one-off frame can measure the old
  // height. Re-place on every size change so the popover never leaves the
  // viewport. placeCreate is idempotent and no-ops when the dialog is closed.
  if (typeof ResizeObserver === "function") {
    new ResizeObserver(() => { if (createDialog.open) placeCreate(createAnchor); }).observe(createDialog);
  }
  function placeCreate(anchor) {
```

   Command: `cd App && node -e "new Function(require('fs').readFileSync('app/static/dashboard-calendar.js','utf8'))" && echo syntax-ok` (if `node` is missing, skip and rely on the browser test). Expected: `syntax-ok`.

3. Cache bust: `grep -n 'dashboard-calendar.js' App/app/templates/*.html`. If a `?v=` version string is on that script tag, bump its last character by one (for example `0123d` to `0123e`) in that one place; if the script is linked without a version, change nothing. Command: the grep again. Expected: one line, new version.

4. Browser proof: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest "tests/test_dashboard_calendar_browser.py::test_create_popover_reclamps_when_switching_to_taller_stay_form" -q --tb=short -x 2>&1 | tail -30`. Expected: `2 passed` (both widths), 0 skipped.

5. Commit: `git add App/tests/test_admin_funnel.py App/app/static/dashboard-calendar.js App/app/templates/base.html && git commit -m "0124 step 5: funnel window upper bound; create popover reclamps on resize"` (leave base.html out of `git add` if step 3 changed nothing).

## 5. Do not touch

Any other test; `placeCreate` itself; the funnel query in `app/admin_funnel.py`; hard rules 1, 3, 8.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_admin_funnel.py -q --tb=short -x 2>&1 | tail -30` expected: passed.
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -q --tb=short -x 2>&1 | tail -30` expected: all passed, 0 skipped.
- `cd App && .venv/bin/python -m pytest tests/test_skeleton_loaders.py -q --tb=short -x 2>&1 | tail -30` expected: passed (base.html still valid).

## 7. Acceptance

- [ ] Both named tests pass locally with the browser required.
- [ ] `git diff df8b842 --stat` lists only the files in section 3.
- [ ] The report quotes the popover test's bounding box line from a `-s` run or the screenshot `create-popover-reclamp-1280` from `UBYHOST_SHOTS_DIR`.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0124-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/static/dashboard-calendar.js` (observer added once; placeCreate unchanged).

## Owner steps

None.
