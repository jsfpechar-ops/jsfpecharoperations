# 0237: Round 1 polish (quiet stay list, one arrow, heading size, lock shots)

Status: todo
Depends on: 0236 | Branch: claude/project-thread-kbrf7w
Executor: Haiku 5.5 | Fits one session: 25 tool calls

## 1. Objective

Close the last browser failure and three visual nits found in the 0235 screenshots:
1. The "On guest link from <date>" line in the stay list adds a third text line to a row (row 122 px, rule 100 px, `test_stays_pills_and_deadlines_stay_on_one_line`). Decision: the stay list stays quiet; the stay page keeps the line, the "?" and the "Copy this guest's own link" button.
2. The stay tracker shows two arrows: the app-wide `summary::before` chevron (app.css) plus 0230's own `::after`. Keep the app-wide one only.
3. The "No smart lock / Yes" choice card (a `<summary>`) must not get the app-wide chevron.
4. "How each stay works" renders as a large page h2 in the wizard; it should read as a section label (text-md).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservations.html` | edit | step 1 |
| `App/tests/test_guest_link_window_0231.py` | edit | step 2 |
| `App/app/static/workflow.css` | edit | step 3 |
| `App/app/templates/_workflow.html` | edit | step 4 |
| `App/app/templates/base.html` | edit | step 5 |
| `/mnt/project-files/foolproof-round1/lock-question/` | create | step 7 shots |
| `docs/tasks/0237-report.md` | create | report |

## 4. Steps

1. `App/app/templates/reservations.html`: delete these exact lines (they follow the `stay-report-deadline` block):

```jinja
          {% if reservation.status == 'active' and progress.status in ('awaiting_guest', 'incomplete') %}
            {% set lw = link_window(reservation) %}
            {#- 0236: quiet when fine; only a stay not yet on the link says so. -#}
            {% if lw and lw.state == 'from' %}<div class="link-window is-later" data-link-window="from">{{ t('workflow.link.from', date=lw.opens.isoformat() | date_short) }}</div>{% endif %}
          {% endif %}
```

Check: `grep -c "link_window" App/app/templates/reservations.html` → `0`. Commit `0237 step 1`.

2. `App/tests/test_guest_link_window_0231.py`: anchor (these two exact lines):

```python
    listing = host.get("/reservations?lang=en")
    assert 'data-link-window="from"' in listing.text
```

Replace with:

```python
    # 0237: the stay list stays quiet; the stay page carries the date.
    listing = host.get("/reservations?lang=en")
    assert 'data-link-window=' not in listing.text
```

Commit `0237 step 2`.

3. `App/app/static/workflow.css`:
   - Anchor (exact line): `.journey > summary::after { content: ""; width: 8px; height: 8px; margin-left: auto; border-right: 2px solid var(--ink-muted); border-bottom: 2px solid var(--ink-muted); transform: rotate(45deg); }` → delete the line.
   - Anchor (exact line): `.journey[open] > summary::after { transform: rotate(-135deg); }` → delete the line.
   - Anchor (exact line): `.lock-choice-option::-webkit-details-marker { display: none; }` → replace with `.lock-choice-option::-webkit-details-marker, .lock-choice-yes > summary::before { display: none; }`
   - Anchor (exact line): `.workflow-block > h2 { margin: 0 0 var(--space-3); font-size: var(--text-md); }` → replace with `.workflow-block > h2.workflow-title { margin: 0 0 var(--space-3); font-size: var(--text-md); line-height: 1.3; }`

   Commit `0237 step 3`.

4. `App/app/templates/_workflow.html`: anchor (exact text): `<h2 id="workflow-title">` → replace with `<h2 id="workflow-title" class="workflow-title">`. Commit `0237 step 4`.

5. `App/app/templates/base.html`: anchor (exact line): `  <link rel="stylesheet" href="/static/workflow.css?v=20261022-0230">` → replace with `  <link rel="stylesheet" href="/static/workflow.css?v=20261022-0237">`. Commit `0237 step 5`.

6. Run (timeout 600000 ms):

```
cd App && UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/pw .venv/bin/python -m pytest tests/test_host_list_layouts_browser.py tests/test_onboarding_wizard_browser.py tests/test_host_stay_detail_layout_browser.py tests/test_design_guardrails_browser.py tests/test_guest_link_window_0231.py tests/test_workflow_strip_0232.py -q --tb=short -rs 2>&1 | tail -15
```

Expected: all passed, 0 skipped. A failure: quote the last 30 lines in the report and stop.

7. The wizard browser test writes lock-step shots into `docs/tasks/0102-evidence/` (tracked old evidence). Save the new ones and restore the folder:

```
mkdir -p /mnt/project-files/foolproof-round1/lock-question/ && cp docs/tasks/0102-evidence/30-lock-instructions-*.png /mnt/project-files/foolproof-round1/lock-question/ 2>&1 | tail -3; ls /mnt/project-files/foolproof-round1/lock-question/ | head; git checkout -- docs/tasks/0102-evidence/ && git clean -fq docs/tasks/0102-evidence/ && git status --short | head -5
```

(run from the repo root). Then look once (Read tool) at one 390 px lock shot and write one line about it in the report.

## 9. Report

Write `docs/tasks/0237-report.md` (400 tokens at most): commits, step 6 last lines, step 7 file list and your one line. Set `Status: review`, commit both as `0237 report` (git add those two files only). Do not push or open a PR.
