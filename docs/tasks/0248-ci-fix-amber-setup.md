# 0248: CI fix, missing setup is amber, card guard test

Status: done
Depends on: 0247 | Base commit: 0e27895 | Branch: claude/project-thread-0io75h
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

## 1. Objective

PR #425 CI has two failures:

1. `test_status_colours.py::test_the_property_readiness_is_not_a_red_pill`: the property page health badge is red when police or business details are missing. Missing setup is a warning (amber), not a rejection. Calendar sync error and refused police login stay red.
2. `test_design_no_bang.py::test_needs_action_section_is_guarded_by_rows`: asserts the old dashboard section text that 0241 replaced with the "What needs you" card.

## 2. Context

`property_health.checks` sets each row's state; `_property_overview.html` makes the badge red when any row is `bad`.

## 3. Files

| Path | Action |
|---|---|
| `App/app/property_health.py` | edit (step 1) |
| `App/tests/test_property_health_0244.py` | edit (step 1) |
| `App/tests/test_design_no_bang.py` | edit (step 2) |
| `docs/tasks/0248-report.md` | create |

No other file may change.

## 4. Steps

### Step 1. Amber for missing details

In `App/app/property_health.py`:
- the line `rows.append(_row("police", "send", "bad", "health.police.missing", ...` : change `"bad"` to `"warn"`.
- the block `"business", "receipt", "bad", "health.business.missing", ...` : change `"bad"` to `"warn"`.
Leave `health.calendar.error` and `health.police.login` as `"bad"`.

In `App/tests/test_property_health_0244.py`, in `test_each_problem_gets_one_button_to_the_exact_setting`, after the line `assert rows["police"]["href"] == ...` add `assert rows["police"]["state"] == "warn"`, and after the business href line add `assert rows["business"]["state"] == "warn"`.

### Step 2. Card guard test

In `App/tests/test_design_no_bang.py` replace the body of `test_needs_action_section_is_guarded_by_rows` (keep the name) with:

```python
    """0241: the "What needs you" card replaced the needs-action table; one empty state for no property."""
    text = (T / "dashboard.html").read_text(encoding="utf-8")
    assert "{% if not apartments %}" in text
    assert "data-needs-you-card" in text
```

## 5. Do not touch

Everything outside §3.

## 6. Commands

From `App/`, `export PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw UBYHOST_REQUIRE_BROWSER=1`:

1. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_status_colours.py tests/test_design_no_bang.py tests/test_property_health_0244.py -q --tb=short 2>&1 | tail -10` → pass.
2. `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_onboarding_followup_browser.py -q --tb=short -rs 2>&1 | tail -10` → pass, 0 skipped. (If that file does not exist, run `ls tests | grep -i health` and the browser file it shows instead.)
3. `.venv/bin/ruff check --select F401,F841 app tests 2>&1 | tail -5` → clean.

## 7. Acceptance

- [ ] §6 commands pass, 0 skipped.

Commit once: `0248: missing setup is amber; dashboard guard test follows the card`.

## 8. Stop and ask

Stop and write the report if an anchor is missing, a test fails twice, or another file needs a change.

## 9. Report

Write `docs/tasks/0248-report.md` (300 tokens at most) with the tail of each command, set `Status: review`, commit. Do not push.
