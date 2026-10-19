# 0150: stays and dashboard rows, part 2: quiet setup strip, chips scroll on phone

Status: todo
Depends on: 0149 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

Part 1 is [0149](0149-stays-polish.md); run this only after `docs/tasks/0149-report.md` says review. Commit each step as `0150 step k`. Never push, never open a PR.

## 1. Objective

1. **Setup strip.** `onboarding_banner` renders a coral `btn primary` "Pokračovat v nastavení" in a tinted box. On the stays list that is a second coral primary next to "Přidat pobyt" (MASTER 4 and 7.1: one primary per screen). It becomes one quiet line: a `secondary compact` Continue link, a `quiet compact` Skip, white surface, hairline, no tint. Same macro on every page, so the dashboard gets the same strip.
2. **Chips on phone.** At 390 px the four stays chips wrap and "Archivované" sits alone on a line. Below 1024 the chip row scrolls sideways instead (no visible scrollbar); the page never scrolls sideways.

## 2. Context

Anchor A, `App/app/templates/_components.html` (inside `{% macro onboarding_banner(onboarding) %}`, two lines):
```
      <a class="btn primary onboarding-banner-setup-link" href="{{ onboarding.setup_url }}">
```
```
        <button class="btn ghost" type="submit">{{ t('onboarding.skip') }}</button>
```
Anchor B, `App/tests/test_onboarding_wizard_browser.py` line 1424:
```
        assert "primary" in continue_button.get_attribute("class").split()
```
Old strip CSS that the new rules override (not deleted; other legacy banners share them): `app.css` `.onboarding-banner { display: grid; ... }`, `host.css` lines 138 (`background: #fbeae2`) and 1505-1508 (`.onboarding-banner-setup`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_components.html | edit | Anchor A (step 1) |
| App/tests/test_onboarding_wizard_browser.py | edit | Anchor B (step 1) |
| App/app/static/host2.css | edit | append (step 2) |
| docs/tasks/0150-report.md | create | step 4 |

No other file may change.

## 4. Steps

1. Anchor A: the first line becomes
   `      <a class="ui-btn ui-btn-secondary ui-btn-compact onboarding-banner-setup-link" href="{{ onboarding.setup_url }}">`
   and the second
   `        <button class="ui-btn ui-btn-quiet ui-btn-compact" type="submit">{{ t('onboarding.skip') }}</button>`.
   Anchor B becomes `        assert "ui-btn-secondary" in continue_button.get_attribute("class").split()`.
   From `App/`: `.venv/bin/python -m pytest tests/test_setup_banner.py tests/test_design_stays.py -q --tb=short -x 2>&1 | tail -5` passes. Commit `0150 step 1`.

2. Append to the end of `App/app/static/host2.css`:
   ```
   /* 0150: setup strip is one quiet line; chips scroll sideways on phone */
   .host-workspace .onboarding-banner-setup { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-2) var(--space-3); margin: 0 0 var(--space-4); padding: var(--space-2) var(--row-px); background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); box-shadow: none; overflow: visible; }
   .host-workspace .onboarding-banner-setup form { margin: 0; }
   .host-workspace .onboarding-banner-setup-link { min-height: var(--control-h-compact); margin: 0; }
   @media (max-width: 1023px) {
     .host-workspace .ui-toolbar .ui-chips { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; padding-bottom: 1px; }
     .host-workspace .ui-toolbar .ui-chips::-webkit-scrollbar { display: none; }
     .host-workspace .ui-chip { flex: none; }
   }
   ```
   `python3 scripts/design_lint.py | tail -3` OK. Commit `0150 step 2`.

3. Browser run, from `App/`, with `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0150`:
   `.venv/bin/python -m pytest tests/test_host_list_layouts_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_quiet_dashboard_browser.py "tests/test_onboarding_wizard_browser.py::test_phone_guest_sharing_and_clear_setup_actions" -q --tb=line -rs 2>&1 | tail -12`. Expected: pass, 0 skipped.
   Screenshots: `UBYHOST_CAPTURE_0079=1 UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_list_layouts_browser.py -k share_compact_row_menu -q --tb=line 2>&1 | tail -3`, then from the repo root:
   ```
   mkdir -p /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0150 && cp docs/tasks/0079-evidence/stays-390-cs.png docs/tasks/0079-evidence/stays-1280-cs.png docs/tasks/0079-evidence/dashboard-390-cs.png docs/tasks/0079-evidence/dashboard-1280-cs.png /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0150/ && git checkout -- docs/tasks/0079-evidence && git status --short docs/tasks/0079-evidence | head -3
   ```
   (the last command prints nothing). The stays fixture may show no setup strip; the onboarding test above writes `docs/tasks/0102-evidence/28-continue-setup-*.png` (untracked files; never `git add` that folder). Copy one: `cp docs/tasks/0102-evidence/28-continue-setup-cs-390.png /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0150/ 2>&1 | tail -1` (if that exact name is missing, `ls docs/tasks/0102-evidence | grep 28-continue | head -3` and copy the first).

4. By eye (Read tool), write what you saw in the report:
   - stays 1280: the only coral button is "Přidat pobyt"; the setup strip (when shown) is one white line with a bordered "Pokračovat v nastavení" and a plain "Přeskočit průvodce nastavením" at the right.
   - stays 390: the chips are one row cut off at the right edge (scrollable), no chip on a second line; the Filtry button below; no horizontal page scroll.
   - 28-continue-setup: the Continue button is white with a border, 32 px tall, text on one line.
   Run ruff (`App/.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 App/ | tail -3`). Write `docs/tasks/0150-report.md` (Status review or blocked, test output, by-eye list, screenshot paths). Commit `0150 report`.

## 5. Do not touch

`reservations.html`, `dashboard.html`, the role grid of 0149, `app.css`, `host.css`, `catalog.json`, any Python, other tests.

## 6. Commands

As in steps 1 to 4.

## 7. Acceptance

- [ ] Step 1 tests pass; `design_lint.py` OK after step 2.
- [ ] Step 3: every listed test passes, 0 skipped; `docs/tasks/0079-evidence` clean.
- [ ] Step 4 confirmed.

## 8. Stop and ask

Stop if a test fails twice or a screenshot still shows a coral setup button or wrapped chips. Report the assertion verbatim.

## 9. Report

As in step 4.
