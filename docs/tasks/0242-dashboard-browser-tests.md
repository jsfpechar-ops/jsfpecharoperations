# 0242: Move the dashboard browser tests to "What needs you"

Status: todo
Depends on: 0241 | Base commit: after 0241 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

0241 replaced the dashboard's count tiles, setup banner, alert stack and "Needs action now" table with one card, "What needs you" (`section.needs-you#needs-action`, one `li.needs-you-item` per line). The browser tests that measured the old blocks now point at the card, so CI keeps guarding the dashboard's geometry. No app code changes here.

## 2. Context

- Card markup (`dashboard.html`): `<div data-dashboard-refresh="stats"><section class="needs-you" id="needs-action" data-needs-you-card>`, lines are `li.needs-you-item[data-tone][data-needs-you="stay|alert|setup|paste"]`, stay lines carry `data-needs-you-stay="<stay id>"`, a dismissible alert line carries `data-notification` and a `form[data-notification-dismiss]`. The first 5 lines are visible, the rest sit in `details.needs-you-more` ("Show N more"). With no lines the card shows `p.needs-you-calm`.
- On `/` the alert stack (`.notification-stack`) is hidden; every other page still has it.
- A stay line's subject is the stay's label (the typed label of a hand-made stay) and its button links to `/reservations/<id>?return_to=/#...`.
- Browser tests need `export PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw` and `UBYHOST_REQUIRE_BROWSER=1` so they cannot skip.
- `ruff --select F401,F841` runs in CI: do not leave an unused variable.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_host_wide_geometry_browser.py` | edit | step 1 |
| `App/tests/test_dashboard_calendar_browser.py` | edit | step 2 |
| `App/tests/test_dashboard_phone_browser.py` | edit | step 3 |
| `App/tests/test_host_geometry.py` | edit | step 4 |
| `App/tests/test_dashboard_rows_browser.py` | edit | step 5 |
| `App/tests/test_host_list_layouts_browser.py` | edit | step 5 |
| `App/tests/test_host_list_page_layout_browser.py` | edit | step 5 |
| `App/tests/test_onboarding_followup_browser.py` | edit | step 5 |
| `docs/tasks/0242-report.md` | create | report |

No other file may change. `test_host_quiet_dashboard_browser.py` is brief 0243; do not touch it.

## 4. Steps

### Step 1. `test_host_wide_geometry_browser.py`

1a. Command: `cd App && sed -i 's/"\.dashboard-stats"/".needs-you"/g' tests/test_host_wide_geometry_browser.py && grep -c '"\.needs-you"' tests/test_host_wide_geometry_browser.py` → `3`.

1b. Anchor (exact line): `    alert_probe = probe.get("/?lang=en")` → replace with `    alert_probe = probe.get("/reservations?lang=en")`.

1c. Anchor (these exact lines, in the route loop):

```python
                    alert_stack = geometry["alertStack"]
                    assert alert_stack and geometry["alertLink"], (
                        f"synthetic persistent date-change alert not rendered on {name}/{lang}/{width}"
                    )
                    assert geometry["alertPosition"] == "static", geometry
                    assert geometry["alertDismissCount"] == 0, (
                        "dates_changed_resign alerts are filing gates and must remain non-dismissible"
                    )
                    for edge in ("left", "right"):
                        if abs(alert_stack[edge] - geometry["hostLane"][edge]) > 2:
                            mismatches.append({"route": name, "locale": lang, "width": width,
                                "lane": f"alertStack.{edge}", "result": geometry["hostLane"],
                                "candidate": alert_stack})
                    feedback_region = geometry["feedbackRegion"]
                    assert feedback_region and alert_stack["bottom"] <= feedback_region["top"] + 1, (
                        f"persistent alert overlaps feedback region on {name}/{lang}/{width}: "
                        f"alert={alert_stack}, feedback={feedback_region}"
                    )
```

Replace with:

```python
                    feedback_region = geometry["feedbackRegion"]
                    assert feedback_region, f"feedback region missing on {name}/{lang}/{width}"
                    if name == "dashboard":
                        # 0241: on the dashboard the alert is a line in "What needs you".
                        card_alert = page.locator('.needs-you [data-needs-you="alert"]')
                        assert card_alert.count() >= 1, f"date-change alert missing from the card at {lang}/{width}"
                        assert card_alert.first.locator("[data-notification-dismiss]").count() == 0, (
                            "dates_changed_resign alerts are filing gates and must remain non-dismissible"
                        )
                        assert geometry["alertStack"] is None, geometry["alertStack"]
                    else:
                        alert_stack = geometry["alertStack"]
                        assert alert_stack and geometry["alertLink"], (
                            f"synthetic persistent date-change alert not rendered on {name}/{lang}/{width}"
                        )
                        assert geometry["alertPosition"] == "static", geometry
                        assert geometry["alertDismissCount"] == 0, (
                            "dates_changed_resign alerts are filing gates and must remain non-dismissible"
                        )
                        for edge in ("left", "right"):
                            if abs(alert_stack[edge] - geometry["hostLane"][edge]) > 2:
                                mismatches.append({"route": name, "locale": lang, "width": width,
                                    "lane": f"alertStack.{edge}", "result": geometry["hostLane"],
                                    "candidate": alert_stack})
                        assert alert_stack["bottom"] <= feedback_region["top"] + 1, (
                            f"persistent alert overlaps feedback region on {name}/{lang}/{width}: "
                            f"alert={alert_stack}, feedback={feedback_region}"
                        )
```

1d. Anchor (these exact lines, in `test_dashboard_760_header_and_actions_remain_in_the_shared_lane`):

```python
            assert geometry["alertPosition"] == "static" and geometry["alertDismissCount"] == 0, {
                "alert": geometry["alertStack"], "body": page.locator("body").inner_text()[:500],
                "title": page.title(), "url": page.url,
            }
            assert geometry["alertStack"]["bottom"] <= geometry["feedbackRegion"]["top"] + 1
```

Replace with:

```python
            # 0241: the alert is a line in "What needs you", never a second stack.
            assert geometry["alertStack"] is None, geometry["alertStack"]
            card_alert = page.locator('.needs-you [data-needs-you="alert"]')
            assert card_alert.count() >= 1, page.locator("body").inner_text()[:500]
            assert card_alert.first.locator("[data-notification-dismiss]").count() == 0
```

Command: `cd App && .venv/bin/python -c "import ast,sys; ast.parse(open('tests/test_host_wide_geometry_browser.py').read())" && echo ok`. Commit `0242 step 1`.

### Step 2. `test_dashboard_calendar_browser.py`

2a. Anchor (exact line): `                    boxes = page.evaluate("""() => ['.dashboard-stats', '#calendar', '#needs-action'].map(selector => {`
Replace `['.dashboard-stats', '#calendar', '#needs-action']` with `['.needs-you', '#calendar']` on that line only.

2b. Delete this exact line (directly below the `boxes` evaluate): `                    assert boxes[2]["top"] >= boxes[1]["bottom"], boxes`

2c. Delete these exact four lines:

```python
                        pill_heights = page.locator(".dashboard-stat").evaluate_all(
                            "nodes => nodes.map(node => node.getBoundingClientRect().height)"
                        )
                        assert max(pill_heights) <= 40, pill_heights
```

2d. In `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place`, replace everything from the line
`        attention_before = int(page.locator('[data-dashboard-refresh="stats"] .dashboard-stat.action strong').inner_text())`
through the line `            assert row.is_visible()` (the last line of the `if row_rendered:` block, just before the blank line and `# Dashboard has no dismissible banner`) with:

```python
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/reservations")) as stay_result:
            page.locator("[data-cal-save]").click()
        created_stay = stay_result.value.json()
        assert stay_result.value.status == 201
        assert page.evaluate("location.pathname") == pathname
        # 0241: the new stay arrives today with no guest form, so "What needs you" gains its line.
        line = page.locator(
            f'[data-dashboard-refresh="stats"] .needs-you-item[data-needs-you-stay="{created_stay["id"]}"]'
        )
        line.wait_for(state="attached")
        assert "Popup row refresh" in line.text_content()
        line_button = line.locator(".ui-btn")
        assert line_button.count() == 1
        assert line_button.get_attribute("href").startswith(f"/reservations/{created_stay['id']}?")
        # Re-delivering the scoped update must not double-bind imported controls.
        page.evaluate("""() => {
            const root = document.querySelector('[data-dashboard-refresh="stats"]');
            document.dispatchEvent(new CustomEvent("ubyhost:content-updated", {detail: {root}}));
            document.dispatchEvent(new CustomEvent("ubyhost:content-updated", {detail: {root}}));
        }""")
        assert line.count() == 1
```

2e. Anchor (these exact lines, near the end of the same test):

```python
        if row_rendered:
            with page.expect_navigation():
                row.focus()
                row.press("Enter")
            assert page.url.split("?")[0].endswith(f"/reservations/{created_stay['id']}")
```

Replace with:

```python
        if not line_button.is_visible():
            page.locator('[data-dashboard-refresh="stats"] .needs-you-more > summary').first.click()
        with page.expect_navigation():
            line_button.click()
        assert page.url.split("?")[0].endswith(f"/reservations/{created_stay['id']}")
```

2f. Command (three occurrences each, in `test_dashboard_committed_stay_refresh_retry_does_not_post_twice`):

```
cd App && sed -i -e "s#'\[data-dashboard-refresh=\"work\"\] .dashboard-row')\].filter(row => !row.closest(\"noscript\")).map(row => ({#'[data-dashboard-refresh=\"stats\"] .needs-you-item[data-needs-you=\"stay\"]')].map(row => ({#" -e 's#id: row.getAttribute("data-stay-id"),#id: row.getAttribute("data-needs-you-stay"),#' tests/test_dashboard_calendar_browser.py && grep -c 'needs-you-item\[data-needs-you="stay"\]' tests/test_dashboard_calendar_browser.py && grep -c 'data-dashboard-refresh="work"\] .dashboard-row\|data-stay-id\|row_rendered\|dashboard-stat' tests/test_dashboard_calendar_browser.py
```
→ `3` then `0`. If the second number is not 0, show the remaining lines with `grep -n` and stop.

2g. In the same retry test, replace the two comment lines

```python
        # The work list is intentionally capped at five rows. Change an existing visible
        # synthetic manual label so the successful retry proves it replaced stale HTML.
```

with

```python
        # Change an existing stay's label so the successful retry proves it replaced stale HTML.
```

and the message `"fixture should render work rows before the committed save"` with `"fixture should show stay lines before the committed save"`.

Commit `0242 step 2`.

### Step 3. `test_dashboard_phone_browser.py`

3a. First line: replace the docstring with `"""Phone dashboard (0147, 0148, 0241): dots instead of bars, reduced controls, one PIN line, one short line per setup gap."""`

3b. Anchor (these exact lines):

```python
                pin_cards = page.locator("[data-notification]", has_text="PIN")
                assert pin_cards.count() == 1
                assert pin_cards.first.get_attribute("data-notification-group") == "guest_pin_rotated"
                for name in names:
                    assert name in pin_cards.first.inner_text(), name
                assert pin_cards.first.locator('a[href="/apartments"]').count() == 1
                short = page.locator(".dashboard-missing-short")
                assert short.is_visible()
                assert short.inner_text().strip() == "3 properties need setup", short.inner_text()
                assert not page.locator(".dashboard-missing-list").first.is_visible()
                assert page.locator(".ui-banner-attention .ui-btn").count() == 1
                shot(page, "phone-390-alert")
                pin_cards.first.locator("[data-notification-dismiss] button").click()
```

Replace with:

```python
                # 0241: the three PIN alerts are one line in "What needs you", linking to the property list.
                assert page.locator(".notification-stack").count() == 0
                pin_lines = page.locator('.needs-you [data-needs-you="alert"]', has_text="PIN")
                assert pin_lines.count() == 1
                assert pin_lines.first.locator('a[href="/apartments"]').count() == 1
                assert len(names) == 3
                # One short line per property with missing police details: no field list.
                setup_lines = page.locator('.needs-you [data-needs-you="setup"]')
                assert setup_lines.count() == 3
                for index in range(3):
                    assert setup_lines.nth(index).locator(".ui-btn").count() == 1
                    assert "Police details are missing" in setup_lines.nth(index).text_content()
                if not pin_lines.first.is_visible():
                    page.locator(".needs-you-more > summary").first.click()
                shot(page, "phone-390-alert")
                pin_lines.first.locator("[data-notification-dismiss] button").click()
```

3c. Anchor (these exact lines, in the `else:` branch):

```python
                assert page.locator(".dashboard-missing-list").first.is_visible()
                assert not page.locator(".dashboard-missing-short").is_visible()
                assert page.locator(".dashboard-missing-line").count() == 3
```

Replace with:

```python
                assert page.locator('.needs-you [data-needs-you="setup"]').count() == 3
```

Commit `0242 step 3`.

### Step 4. `test_host_geometry.py`

Anchor (exact lines):

```python
                stats: rect(document.querySelector('.ui-stats')),
```

Replace with `                stats: rect(document.querySelector('.needs-you')),`. Then replace the two messages `"the stat tiles must span the header card exactly"` → `"What needs you must span the header card exactly"` and `"the stat tiles must align with the content below"` → `"What needs you must align with the content below"`. Commit `0242 step 4`.

### Step 5. Row tests: the dashboard has no table rows any more

5a. `test_dashboard_rows_browser.py`: delete this exact line from `PATHS`: `    (f"/?lang={LANG}", "#needs-action table.ui-table", "dashboard"),`. Replace the first docstring line `"""Dashboard and stay-list rows (0194): one clean box per row at every width, sidebar open or collapsed.` with `"""Stay-list rows (0194; the dashboard has no table since 0241): one clean box per row at every width, sidebar open or collapsed.`

5b. `test_host_list_layouts_browser.py`: delete these exact lines:
- `    dash_cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)`
- `                    ("dashboard", base, dash_cookie, ".dashboard-row"),`
- `    for key, per_page in heights.items():`
- `        assert per_page["dashboard"] == per_page["stays"], (key, per_page)`

and replace the first docstring line `"""0102: Dashboard and Stays use one compact menu, with Open inside it."""` with `"""0102: Stays use one compact menu, with Open inside it (the dashboard has no rows since 0241)."""`.

5c. `test_host_list_page_layout_browser.py`: delete this exact line from `ROWS`: `    "dashboard": ("/", ".dashboard-row.clickable-row"),`.

5d. `test_onboarding_followup_browser.py`: replace these exact lines

```python
        dashboard_row = page.locator(".dashboard-row").first
        assert dashboard_row.is_visible()
        assert dashboard_row.locator(".dashboard-open").count() == 0
        dashboard_row.locator(".row-menu-trigger").click()
        menu = page.locator(".row-menu-panel.is-open")
        assert menu.get_by_role("menuitem", name=_t(lang, "common.open"), exact=True).is_visible()
        page.keyboard.press("Escape")
```

with

```python
        assert page.locator(".needs-you").is_visible()
```

Command: `cd App && .venv/bin/ruff check tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -10` (if `ruff` is not in the venv, use `python3 -m ruff`; if neither exists say so in the report). Commit `0242 step 5`.

## 5. Do not touch

Everything outside §3. No app code, no CSS, no template. `test_host_quiet_dashboard_browser.py` is 0243.

## 6. Commands

Run from `App/` with `export PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1` and `tests/test_alert_stack.py` first:

1. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_dashboard_calendar_browser.py tests/test_dashboard_phone_browser.py tests/test_host_geometry.py tests/test_dashboard_rows_browser.py -q --tb=short -x 2>&1 | tail -20`
2. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_list_layouts_browser.py tests/test_host_list_page_layout_browser.py tests/test_onboarding_followup_browser.py -q --tb=short -x 2>&1 | tail -20`
3. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_wide_geometry_browser.py -q --tb=short -x 2>&1 | tail -20` (slow; allow 10 minutes).

A failure caused by the old dashboard blocks that this brief did not foresee: report the file, line and message and stop. Do not change the app to make a test pass.

## 7. Acceptance

- [ ] The three §6 commands pass with 0 skipped.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls; a file outside §3 needs a change; a step is unclear.

## 9. Report

Write `docs/tasks/0242-report.md` (600 tokens at most) with the last lines of each §6 command, and set `Status: review`. Do not push or open a PR.

## Risk list (for the reviewer)

Test rewrites only: steps 1c, 2d and 3b change what the tests assert.

## Owner steps

None.
