# 0178: the property setup checklist is not pink and has the page's spacing

Status: todo
Depends on: 0177 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

On a property's Overview tab (`/apartments/<id>`), the "Setup checklist" section is a full-bleed pink block with its heading touching the left edge (owner: "what is this? why is it so pink"). It should be a normal section: white card, thin border, the same padding as other cards, heading inside the padding.

## 2. Context

The element is `<section class="panel host-checklist" data-setup-status>` with `<header class="setup-status-head">` and `<ul class="setup-status-grid">`. Old rule in `App/app/static/host.css` line 1487: `.host-workspace .host-checklist[data-setup-status] { margin-top: 28px; background: var(--canvas-subtle); border-style: dashed; }` gives the pink tint and a dashed border; the redesign removed the `.panel` padding, so the content touches the edge. Do not edit `host.css` (old file): override in `host2.css`, which loads last. S1 forbids raw colours, S2 forbids bare px in margin, padding, gap and font-size. Tokens: `--surface`, `--line`, `--card-radius`, `--card-p`, `--space-N`.

## 3. Files

`App/app/static/host2.css` (append `/* 0178 */`), `App/app/templates/base.html` (host2.css key ending `-0178`), `App/tests/static_versions.json`, `App/tests/test_design_guardrails_browser.py` (one new test), `docs/tasks/0178-*`.

## 4. Steps

1. Append to `host2.css`:
```
/* 0178: the setup checklist is a normal card, not a tinted dashed block */
.host-workspace .host-checklist[data-setup-status] { margin-top: var(--space-6); padding: var(--card-p); background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); }
.host-workspace .host-checklist[data-setup-status] .setup-status-head { margin-bottom: var(--space-4); }
```
   Check the result in a browser: heading inside the padding, tiles inside the card with the card's padding left and right equal, no pink. If the tiles inside need a different look, only change what is needed; no raw colours.
2. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2`. Expected: OK.
3. Bump the host2.css key (`-0178`) in `base.html`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
4. Add `test_setup_checklist_is_a_padded_card` to `test_design_guardrails_browser.py` (copy the fixture and page-open pattern of the other tests; open `/apartments/{property_id}` at 1280 where `property_id` is `wide_host["apartments"][0]`; skip the test body with an assert-free `return` only if no `[data-setup-status]` element exists after waiting 2 s, and print why). Assert: the element's computed `background-color` is not tinted (equals the computed background of a `.ui-card` or is `rgb(255, 255, 255)`), `border-top-style` is `solid`, and the left edge of `.setup-status-head h2` is at least 12 px right of the section's left edge.
5. Browser tests from `App/` (foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`): `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs 2>&1 | tail -6`. Then from the repo root `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused). Expected: all passed, 0 skipped.
6. One 1280 px screenshot of `/apartments/<id>`: from `App/`, `.venv/bin/python /mnt/project-files/design-reset/tools/shots.py --new-app $PWD --out ../docs/tasks/0178-screenshots --pages "/apartments" --widths 1280 2>&1 | tail -2` (property list page; if the harness has no property-detail option, take it with a short Playwright script outside the repo).
7. Commit: `git add App docs/tasks/0178-* && git commit` with message "0178: setup checklist is a normal card" and the two trailers given by the orchestrator.

## 5. Do not touch

`host.css`, templates, copy; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] No pink or dashed block; heading inside padding; test passes; guards pass with 0 skipped.

## 8. Stop and ask

An anchor is missing, or a test fails twice.

## 9. Report

`docs/tasks/0178-report.md`, short; `Status: review`.
