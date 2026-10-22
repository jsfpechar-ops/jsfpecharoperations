# 0241: Stay list step label says "Step", not a bare count

Status: review
Depends on: main after PR #423 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 15 tool calls

## 1. Objective

Owner (Josef, 2026-10-22): on the stay list the reporting pill reads "5 of 5 · Reported", right next to the guest count "2 / 2", so it looks like a guest count. The pill must say "Step 5 of 5 · Reported" (CS "Krok 5 z 5", VI "Bước 5 / 5"), matching the stay page tracker ("Step 2 of 5: Guest form").

## 2. Context

The pill text comes from `workflow.step_of`, used only in `_components.html` `progress_pill`. Row-height rule (100 px) still holds; the geometry tests check it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | step 1 |
| `App/tests/test_workflow_strip_0232.py` | edit | step 2 |
| `docs/tasks/0241-report.md` | create | report |

## 4. Steps

1. Replace these exact lines (keep indentation):
   - `App/app/host_i18n.py`: `        "workflow.step_of": "%(n)s of %(total)s",` → `        "workflow.step_of": "Step %(n)s of %(total)s",`
   - same file: `        "workflow.step_of": "%(n)s z %(total)s",` → `        "workflow.step_of": "Krok %(n)s z %(total)s",`
   - `App/app/host_vi_i18n.py`: `    "workflow.step_of": "%(n)s / %(total)s",` → `    "workflow.step_of": "Bước %(n)s / %(total)s",`

   Commit `0241 step 1`.

2. `App/tests/test_workflow_strip_0232.py`, anchor (exact line) `    assert 'data-journey-step="2"' in listing.text` → insert directly after it (same indentation): `    assert "Step 2 of 5 · " in listing.text  # 0241: never a bare count next to the guest count`. Commit `0241 step 2`.

3. Run from `App/` (timeout 600000 ms):

```
UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw .venv/bin/python -m pytest tests/test_workflow_strip_0232.py tests/test_workflow_0230.py tests/test_status_colours.py tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -p no:cacheprovider 2>&1 | tail -8
```

Expected: all passed. (If only `test_host_i18n.py` tests fail with "no such table", rerun with that file last in the list.)

## 5. Do not touch

Everything outside section 3. Do not run screenshots or other browser tests (the orchestrator does).

## 6. Commands

As in section 4.

## 7. Acceptance

- [ ] Step 3 passes.

## 8. Stop and ask

A test fails twice: stop and report its last 30 lines.

## 9. Report

Write `docs/tasks/0241-report.md` (200 tokens at most): commits, step 3 last lines. Set `Status: review` in it and in this brief, commit both as `0241 report` (git add those two files only). Do not push.
