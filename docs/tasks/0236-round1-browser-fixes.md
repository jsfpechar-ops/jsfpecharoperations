# 0236: Round 1 browser fixes (lock choice in wizard tests, quiet stay list)

Status: todo
Depends on: 0235 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 20 tool calls

## 1. Objective

0235 found 18 browser failures. 17 are wizard tests that still press the old "Skip this step" footer button on the lock step; 0234 replaced it (on purpose) with the "No smart lock" choice card, so the tests follow the new UX. 1 is the stay-list row height: 0231's "On guest link now" line adds a text line to every waiting row. Owner rule: silent when things are fine, so the list shows only the "On guest link from <date>" case (the stay page keeps both).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_onboarding_wizard_browser.py` | edit | steps 1, 2 |
| `App/app/templates/reservations.html` | edit | step 3 |
| `docs/tasks/0236-report.md` | create | report |

## 4. Steps

1. In `App/tests/test_onboarding_wizard_browser.py`, the two-line block below occurs twice (around lines 197 and 1079). Replace BOTH occurrences:

```python
        page.wait_for_url("**/setup/door_lock**")
        page.locator(".setup-wizard-foot form.setup-wizard-skip button").click()
```

with:

```python
        page.wait_for_url("**/setup/door_lock**")
        page.locator('button[data-lock-choice="no"]').click()
```

Check: `grep -c 'data-lock-choice="no"' App/tests/test_onboarding_wizard_browser.py` → `2`. Commit `0236 step 1`.

2. Same file, anchor (exact line): `        assert page.locator(".setup-wizard-foot button[value=skip]").count() == 1` → replace with `        assert page.locator('button[data-lock-choice="no"]').count() == 1`. Then anchor (exact line): `        page.locator(".setup-wizard-foot button[value=skip]").click()` → replace with `        page.locator('button[data-lock-choice="no"]').click()`. Check: the grep from step 1 → `4`. Commit `0236 step 2`.

3. In `App/app/templates/reservations.html`, anchor (exact line):

```jinja
            {% if lw %}<div class="link-window{{ ' is-later' if lw.state == 'from' }}" data-link-window="{{ lw.state }}">{{ t('workflow.link.now') if lw.state == 'now' else t('workflow.link.from', date=lw.opens.isoformat() | date_short) }}</div>{% endif %}
```

Replace with:

```jinja
            {#- 0236: quiet when fine; only a stay not yet on the link says so. -#}
            {% if lw and lw.state == 'from' %}<div class="link-window is-later" data-link-window="from">{{ t('workflow.link.from', date=lw.opens.isoformat() | date_short) }}</div>{% endif %}
```

Commit `0236 step 3`.

4. Run (timeout 600000 ms):

```
cd App && UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_host_list_layouts_browser.py tests/test_guest_link_window_0231.py -q --tb=short -rs 2>&1 | tail -30
```

Expected: all passed, 0 skipped. A failure: fix nothing else; quote the last 30 lines in the report and stop.

## 9. Report

Write `docs/tasks/0236-report.md` (400 tokens at most): commits, the step 4 result lines, deviations. Set `Status: review`, commit both as `0236 report` (git add those two files only). Do not push or open a PR.

## 2. Context

See section 1 and the parent brief.

## 5. Do not touch

Everything outside section 3.

## 6. Commands

As in section 4.

## 7. Acceptance

- [x] The section 4 commands pass.

## 8. Stop and ask

A test fails twice, or a step is unclear: stop and report.
