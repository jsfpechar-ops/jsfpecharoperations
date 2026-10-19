# 0158: screenshot review fixes for cleaning cards and the properties guest links

Status: todo
Depends on: 0143 | Branch: claude/project-thread-5hw8cf
Executor: Sonnet 5.5 or Haiku 5.5 | Fits one session

## 1. Objective

The orchestrator reviewed the 0140 and 0143 screenshots (`checkpoint-3/properties`, `checkpoint-3/cleaning`) and found two problems:
1. On each cleaning card, "Edit cleaning" is a button but "Property instructions & codes" is a bare link next to it. They differ in size and style, which the owner flagged as "weird sizes".
2. On `/apartments` at 1280, the guest-link URL in "Guest links and reporting timing" wraps character by character into six lines.

## 2. Context

`App/app/templates/_cleaning_list.html` line 24 holds the card actions. `App/app/templates/apartments.html` line 87 renders the URL as `<code class="mono property-inline-url" ... title="{{ row.link_url }}">`. The copy button copies the element's text, so truncating it visually with an ellipsis keeps the copy correct. The host2.css key is in `base.html`. Bump it to `20261019-0158`.

## 3. Files

`App/app/templates/_cleaning_list.html`, `App/app/static/host2.css` (append), `App/app/templates/base.html`, `App/tests/static_versions.json`, `docs/tasks/0158-*`.

## 4. Steps

1. In `App/app/templates/_cleaning_list.html`, replace `<a href="/cleaning/properties/{{ item.propertyId }}">{{ ct('settings') }}</a>` with `<a class="ui-btn ui-btn-quiet ui-btn-compact" href="/cleaning/properties/{{ item.propertyId }}">{{ ct('settings') }}</a>`. The anchor occurs once; if it does not, stop.
2. Append to `App/app/static/host2.css`:

```
/* 0158: guest-link URLs stay on one line (full URL in the title and the copy button) */
.host-workspace .property-inline-url { display: block; max-width: 16rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; overflow-wrap: normal; word-break: normal; }
.host-workspace .cleaning-card-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
```

3. Bump host2.css in `base.html` to `20261019-0158`. From `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`. From the root: `python3 scripts/design_lint.py 2>&1 | tail -3`.
4. From `App/`, with `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`, run `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_cleaning_browser.py tests/test_design_cleaning.py tests/test_cleaning.py -q -rs 2>&1 | tail -8` (foreground, timeout 600000). Expected: all passed, 0 skipped. A cleaning test that pins the bare link's markup may be updated to the new class, and that is the only test edit allowed.
5. Commit by path: `0158: cleaning card actions match; guest-link URL on one line`. Do not push.

## 5. Do not touch

Anything else. Hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Guard passes, cleaning tests pass, lint OK, versions OK.

## 8. Stop and ask

A test fails twice.

## 9. Report

`docs/tasks/0158-report.md`, `Status: review`.
