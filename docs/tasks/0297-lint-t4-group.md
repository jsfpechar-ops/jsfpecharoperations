# 0297: Design lint T4: two primaries with no container boundary between them

Status: todo
Depends on: 0296 | Base commit: 3a30859 | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

## 1. Objective

0296's T4 regex flags invoice_form.html (its one `<form>` holds the IČO lookup primary and the Issue primary, two different groups) and misses two bare sibling primaries (the drift fixture in `tests/test_design_lint.py`). New rule: two `ui-btn-primary` are in one group when no container tag opens or closes between them.

## 2. Context

`scripts/design_lint.py` lines 52-58 (verbatim):
```python
    # T4 (0291, owner 2026-10-24): one primary per button group. A group is a
    # run of buttons inside one element; two primaries in one tag's direct
    # children are flagged, a page may hold several groups.
    for m in re.finditer(r"<(div|form|p|td|li)\b[^>]*>((?:(?!</?\1\b).)*)</\1>", plain, re.S):
        if m.group(2).count("ui-btn-primary") > 1:
            out.append(f"{rel}: T4 more than one ui-btn-primary in one group")
            break
```

## 3. Files

| Path | Action | What |
|---|---|---|
| scripts/design_lint.py | edit | step 1 |

No other file may change.

## 4. Steps

1. Replace those 7 lines with:
```python
    # T4 (0291, owner 2026-10-24): one primary per button group. Two primaries
    # are in one group when no container tag opens or closes between them.
    if re.search(r"ui-btn-primary(?:(?!</?(?:div|form|p|td|li|section|fieldset|dialog)\b).)*?ui-btn-primary", plain, re.S):
        out.append(f"{rel}: T4 more than one ui-btn-primary in one group")
```

## 5. Do not touch

Everything else.

## 6. Commands

From `App/`:
```
.venv/bin/python ../scripts/design_lint.py 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_design_lint.py -q --tb=short 2>&1 | tail -15
```

## 7. Acceptance

- [ ] design lint OK; test_design_lint passes. If a template is still flagged, report the two lines and stop.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0297-report.md` (200 tokens max), `Status: review`. One commit `0297: lint T4 by group boundary`.
