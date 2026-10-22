# 0238: Status-colour test reads pills with a step prefix

Status: todo
Depends on: 0237 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 8 tool calls

## 1. Objective

CI fails `tests/test_status_colours.py::test_the_stay_pill_is_blue_on_the_stays_list`: since 0232 the stay-list pill starts with `<span class="ui-badge-step" data-journey-step="4">Step 4 of 5 · </span>` before the label, so the test's `PILL` regex (`([^<]*)</span>`) no longer matches. The pill is right; the test parser must allow the optional step span.

## 2. Context

See section 1. The step prefix is intended (round 1, idea B+Q).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_status_colours.py` | edit | step 1 |
| `docs/tasks/0238-report.md` | create | report |

## 4. Steps

1. In `App/tests/test_status_colours.py`, anchor (exact line):

```python
    r'<span class="ui-badge ui-badge-[a-z]+(?: ui-badge-overdue)?" data-tone="([a-z]+)"(?: title="([^"]*)")?>(?:! )?([^<]*)</span>',
```

Replace with:

```python
    r'<span class="ui-badge ui-badge-[a-z]+(?: ui-badge-overdue)?" data-tone="([a-z]+)"(?: title="([^"]*)")?>(?:! )?(?:<span class="ui-badge-step"[^>]*>[^<]*</span>)?([^<]*)</span>',
```

Commit `0238 step 1`.

2. Run from `App/`: `.venv/bin/python -m pytest tests/test_status_colours.py -q --tb=short 2>&1 | tail -15`. Expected: all passed.

## 5. Do not touch

Everything outside section 3.

## 6. Commands

As in section 4.

## 7. Acceptance

- [ ] Step 2 passes.

## 8. Stop and ask

A test fails twice: stop and report its last 20 lines.

## 9. Report

Write `docs/tasks/0238-report.md` (200 tokens at most): commit, step 2 last lines. Set `Status: review`, commit both as `0238 report` (git add those two files only). Do not push.
