# 0154: Save buttons visible on phone, host alerts as one quiet list

Status: todo
Depends on: 0153 | Base commit: c340b7f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of the host design reset. Commit once at the end as `0154 step 6`. Never push, never open a PR. Runs before 0138.

## 1. Objective

1. **Bug:** below 1024 px `host2.css` hides every `.ui-form-actions` row. No page has the `.ui-sticky-actions` copy that was meant to replace it, so on a phone the add-stay dialog loses "Create stay", and the stay detail loses its quick-edit Save, its hand-filing confirm button and its add-guest link. Delete the hiding rule.
2. **Alerts:** with demo data, the host alert stack (`_host_alerts.html`, included on every signed-in page) shows five floating cards of about 80 px each with heavy shadows above every page title. Restyle it as one quiet list card in the lane: hairline, radius 12, one row per alert, no shadows, MASTER status dots (coral for errors, amber for warnings). Every alert and every action stays visible (tests in `test_alert_stack.py` forbid collapsing), markup and JS hooks do not change.

## 2. Context

`App/app/static/host2.css` line 107, inside `@media (max-width: 1023px) {`:

```
  .host-workspace .ui-form-actions { display: none; }
```

Stylesheet order in `base.html`: `app.css`, `components.css`, `host.css`, `host-controls.css`, `host-design0123.css`, `host2.css`. The current alert look comes from `host.css` lines 231 to 264 and 447 to 451 (`.host-workspace .notification-*`, same specificity), so rules appended to the end of `host2.css` win. `scripts/design_lint.py` rule S2 forbids bare px in margin, padding, gap, border-radius and font-size (0 and 1px allowed); use tokens.

Anchor A, `App/app/templates/base.html` line 19:

```
  <link rel="stylesheet" href="/static/host2.css?v=20261019-v2a">
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/host2.css` | edit | delete one line (step 1); append a block (step 2) |
| `App/app/templates/base.html` | edit | host2.css version key (step 3) |
| `App/tests/static_versions.json` | regenerate | step 3 |
| `App/tests/test_design_alerts_phone.py` | create | step 4 |

No other file may change.

## 4. Steps

1. In `App/app/static/host2.css` delete exactly the line `  .host-workspace .ui-form-actions { display: none; }` (the one inside `@media (max-width: 1023px)`). Command: `grep -c "ui-form-actions { display: none; }" App/app/static/host2.css`. Expected: `0`.

2. Append this block to the end of `App/app/static/host2.css`:

```
/* 0154: host alerts as one quiet list card in the lane; every alert and action stays visible */
.host-workspace .notification-stack { gap: 0; max-width: none; margin: 0 0 var(--space-6); background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); overflow: hidden; }
.host-workspace .notification-stack .notification-bubble { border: 0; border-radius: 0; background: transparent; box-shadow: none; animation: none; }
.host-workspace .notification-stack .notification-bubble + .notification-bubble { border-top: 1px solid var(--line); }
.host-workspace .notification-stack .notification-link { align-items: flex-start; gap: var(--space-3); padding: var(--space-3) var(--space-12) var(--space-3) var(--row-px); }
.host-workspace .notification-stack .notification-link .grow { min-width: 0; }
.host-workspace .notification-stack .notification-icon { width: var(--space-5); height: var(--space-5); margin-top: 0.125rem; border-radius: 50%; background: var(--st-action-dot); color: var(--surface); font-size: var(--size-12); }
.host-workspace .notification-stack .notification-bubble.warning .notification-icon,
.host-workspace .notification-stack .notification-bubble.info .notification-icon { background: var(--st-attention-dot); }
.host-workspace .notification-stack .notification-bubble strong { font-size: var(--size-14); font-weight: 600; color: var(--ink); }
.host-workspace .notification-stack .notification-bubble small { display: inline; margin: 0; font-size: var(--size-13); color: var(--ink-3); }
.host-workspace .notification-stack .notification-bubble small:not(.notification-action) { display: inline; -webkit-line-clamp: unset; }
.host-workspace .notification-stack .notification-bubble small + small::before { content: " · "; color: var(--ink-4); }
.host-workspace .notification-stack .notification-bubble .notification-action { color: var(--accent-ink); font-weight: 600; }
.host-workspace .notification-stack .notification-bubble form { top: 50%; right: var(--space-2); transform: translateY(-50%); }
```

   Command: `python3 scripts/design_lint.py 2>&1 | tail -5`. Expected: OK.

3. In `App/app/templates/base.html` replace Anchor A's key `20261019-v2a` with `20261019-0154` (that line only; `grep -rn "/static/host2.css?v=" App/app/templates` must show no other template; if it does, change those too and list them in the report). Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -5`. Expected: passed.

4. Create `App/tests/test_design_alerts_phone.py`:

```python
"""0154: form actions stay visible on phone; the alert stack is one quiet card."""
from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "app" / "static" / "host2.css").read_text(encoding="utf-8")


def test_form_actions_are_never_hidden_on_phone():
    assert not re.search(r"\.ui-form-actions\s*\{\s*display:\s*none", CSS)


def test_alert_stack_is_one_card_without_shadows():
    block = CSS.split("/* 0154:", 1)[1]
    assert ".notification-stack { gap: 0;" in block
    assert "box-shadow: none" in block
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_alerts_phone.py tests/test_alert_stack.py tests/test_notification_copy.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -10`. Expected: passed.

5. Browser: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py tests/test_dashboard_phone_browser.py tests/test_shell_lane_browser.py tests/test_host_stay_detail_layout_browser.py -q -rs --tb=short 2>&1 | tail -15`. Expected: passed, 0 skipped. If the executable path does not exist, run `ls -d /opt/pw-browsers/*/chrome-linux/chrome` and use that path. The orchestrator takes the screenshots; attach none.

6. Commit: `git add App/app/static/host2.css App/app/templates/base.html App/tests/static_versions.json App/tests/test_design_alerts_phone.py docs/tasks/0154-* && git commit -m "0154 step 6: phone form actions visible, quiet alert list"`.

## 5. Do not touch

`_host_alerts.html`, `app.js`, `host.js`, `host.css`, alert logic and copy; hard rules 1, 3, 8.

## 6. Commands

Steps 2 to 5 as written.

## 7. Acceptance

- [ ] No `.ui-form-actions { display: none` in host2.css.
- [ ] Alert block appended; lint OK; host2.css key is `20261019-0154`; static versions test passes.
- [ ] Step 4 and step 5 pass, 0 skipped.

## 8. Stop and ask

Stop and write the report if an anchor is not found, a test fails twice, a file outside section 3 needs a change, or you reach 25 tool calls.

## 9. Report

Write `docs/tasks/0154-report.md` (600 tokens at most) and set `Status: review`.
