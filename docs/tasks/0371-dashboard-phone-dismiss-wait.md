# 0371: Phone dashboard test: wait for the dismiss request, not a fixed 500 ms

Status: review
Depends on: none | Base commit: f311d3b | Branch: task/0371-dashboard-phone-dismiss-wait
Executor: Haiku 5.5 | Fits one session: 12 tool calls, 30k tokens

## 1. Objective

`App/tests/test_dashboard_phone_browser.py::test_phone_dashboard_compact` failed once in CI (browser shard 4, PR #467) at line 78: after clicking dismiss on the PIN line and sleeping 500 ms, the reload still showed the PIN notification. The dismiss is an async `fetch` POST; on a slow runner it had not reached the server (or was aborted by the reload) before 500 ms passed. Replace the sleep with a wait on the POST response and on the line leaving the page, so the test checks the same thing without racing.

## 2. Context

Root cause. `App/app/static/app.js` `initNotifications()` intercepts the form submit, calls `fetch(form.action, {method: "POST", headers: {"X-Requested-With": "fetch"}})`, and only on `response.ok` adds `.leaving` and removes the node 230 ms later. `page.reload()` after a fixed wait can run before the POST lands, and a reload aborts an in-flight fetch.

`App/app/routes/admin.py` `dismiss_alert` (`POST /alerts/{alert_id}/dismiss`): for `guest_pin_rotated` it resolves every PIN alert of the owner, then returns `Response(status_code=204)` when `x-requested-with == "fetch"`.

The repo already uses this pattern, `App/tests/test_cleaning_browser.py:435`:

```python
        with page.expect_response(lambda response: response.request.method == "POST" and
```

Current code, `App/tests/test_dashboard_phone_browser.py` lines 75-78 (must match verbatim, else STOP):

```python
                pin_lines.first.locator("[data-notification-dismiss] button").click()
                page.wait_for_timeout(500)
                page.reload()
                assert page.locator("[data-notification]", has_text="PIN").count() == 0
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_dashboard_phone_browser.py` | edit | Replace lines 75-76 as in §4 |
| `docs/tasks/0371-dashboard-phone-dismiss-wait.md` | edit | `Status: review` |
| `docs/tasks/0371-report.md` | create | Report (§9) |

No other file may change.

## 4. Steps

1. In `App/tests/test_dashboard_phone_browser.py`, replace these two lines:

```python
                pin_lines.first.locator("[data-notification-dismiss] button").click()
                page.wait_for_timeout(500)
```

with:

```python
                # 0371: wait for the async dismiss POST and for the line to leave, not a fixed sleep.
                with page.expect_response(lambda response: response.request.method == "POST" and
                                          response.url.split("?")[0].endswith("/dismiss")) as dismissed:
                    pin_lines.first.locator("[data-notification-dismiss] button").click()
                assert dismissed.value.status == 204
                pin_lines.first.wait_for(state="detached")
```

Keep `page.reload()` and the assertion on line 78 exactly as they are.

2. Set up the browser once (skip parts already installed): from `App/`, `pip install -q -r requirements.txt -r requirements-dev.txt playwright==1.63.0`. If `python -m playwright install chromium` fails or is slow, set `UBYHOST_BROWSER_EXECUTABLE` to the `chrome` binary under `/opt/pw-browsers/chromium-*/` instead (find it with `ls /opt/pw-browsers/chromium-*/chrome-linux*/chrome`).

3. Run §6 three times in a row; all three must pass with 0 skipped.

## 5. Do not touch

`App/app/` (the app is right), every other test file, CI workflows. Do not loosen, remove or reorder any assertion. No `wait_for_timeout` anywhere in the new code.

## 6. Commands

From `App/`:

```
UBYHOST_REQUIRE_BROWSER=1 python -m pytest tests/test_dashboard_phone_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```

Expected: `1 passed`, no `skipped`.

```
grep -n "wait_for_timeout" tests/test_dashboard_phone_browser.py
```

Expected: no output.

## 7. Acceptance

- [ ] §6 passes 3 times in a row, 0 skipped.
- [ ] No `wait_for_timeout` left in the file.
- [ ] `git diff --stat` shows only the files in §3.

## 8. Stop and ask

Stop, and write the report, if: the excerpt is not found; a test fails twice; you reach 12 tool calls; a file outside §3 needs a change; you need push, merge or secrets.

## 9. Report

Write `docs/tasks/0371-report.md` (300 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations. Do not commit or push; the orchestrator does that.

## Risk list (for the reviewer)

`App/tests/test_dashboard_phone_browser.py`.

## Owner steps

None. The PR auto-merges when CI is green.
