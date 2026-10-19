# 0149: stays and dashboard rows, part 1: card roles (data-card), old stays CSS out

Status: todo
Depends on: 0148 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part 2 (quiet setup strip, scrolling chips) is [0150](0150-stays-polish-2.md). Run this only after `docs/tasks/0148-report.md` says review. Commit each step as `0149 step k`. Never push, never open a PR. Rule book: MASTER 7.3 "Card roles" and 7.4 (`sed -n '/^### 7.3/,/^### 7.5/p' docs/design/MASTER.md`, read once).

## 1. Objective

The v2 stays list (`/reservations`) still carries three generations of stays-table CSS, so at 1280 px the header row is tall and tinted, every cell shows an inner bordered box, the date range is a coral underlined link that wraps, and the status and deadline badges make rows 65 px. At 390 px each cell becomes its own line, cards are 200 px tall and the menu sits bottom left. MASTER 7.3 now defines a generic card mechanism: each `<td>` declares its card role with `data-card`, and `host2.css` places the roles. This brief:

1. deletes the old stays CSS from `host.css` and `host-design0123.css` (scripted, with exact markers);
2. puts the role grid into `host2.css` (phone) and tightens the desktop cells;
3. adds `data-card` roles and the v2 row classes to `reservations.html` and `dashboard.html`;
4. proves it with the listed tests and four screenshots.

Decision made by the orchestrator (MASTER 7.3 rule 4): on phone the row's Send button stays in the card as a full-width 44 px secondary on its own line 4, shown only for stays that are ready; everything else is in the menu.

## 2. Context

Load order (`base.html`): `app.css`, `host.css`, `host-design0123.css`, `host2.css`. `host2.css` is scoped to `.host-workspace` and wins on equal specificity. `* { box-sizing: border-box }` is global, so a `td` height includes its padding.

Anchor A, `App/app/static/host2.css` lines 216-219 (inside `@media (max-width: 1023px) {` of the `/* ---- phone ---- */` block), copy exactly:
```
  .host-workspace .ui-table tr { display: grid; grid-template-columns: minmax(0, 1fr) auto; column-gap: var(--space-2); align-items: center; position: relative; background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); padding: var(--row-py) var(--row-px); min-height: calc(var(--row-h) + var(--space-6) + var(--space-1)); }
  .host-workspace .ui-table td { display: block; grid-column: 1; height: auto; padding: 0; border: 0; text-align: left; }
  .host-workspace .ui-table td:empty { display: none; }
  .host-workspace .ui-table td.ui-cell-acts { grid-column: 2; grid-row: 1 / span 4; }
```
Anchor B, `host2.css` line 155:
```
.host-workspace .ui-table td { height: var(--row-h); padding: 0 var(--row-px); border-bottom: 1px solid var(--line); vertical-align: middle; color: var(--ink-2); font-size: var(--body-size); }
```
Anchor C, `host2.css` lines 318-321 (the 0134 stacked-table rules; line 317, the `thead` rule, stays):
```
  .host-workspace .ui-table-stack tr { display: block; padding: var(--row-py) 0; border-bottom: 1px solid var(--line); }
  .host-workspace .ui-table-stack td { display: flex; gap: var(--space-3); padding: var(--space-1) 0; border: 0; }
  .host-workspace .ui-table-stack td[data-label]::before { content: attr(data-label); flex: 0 0 38%; color: var(--ink-3); font-size: var(--size-14); }
  .host-workspace .ui-table-stack td[data-label=""]::before, .host-workspace .ui-table-stack td:not([data-label])::before { content: none; }
```
Anchors D to M are single lines in `App/app/templates/reservations.html` (D line 149, E 152, F 154, G 156, H 165, I 168, J 169, K 176, L 178, M 204) and N to R in `App/app/templates/dashboard.html` (N line 26, O 28, P 29, Q 30, R 39). Each is quoted in step 3 and occurs once in its file.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host.css | edit | step 1 script removes two blocks (0091 and 0079 stays rules) |
| App/app/static/host-design0123.css | edit | step 1 script removes the stays rules (keeps the `.row-primary-link` line) |
| App/app/static/host2.css | edit | Anchors A, B, C; append (step 2) |
| App/app/templates/reservations.html | edit | Anchors D to M (step 3) |
| App/app/templates/dashboard.html | edit | Anchors N to R (step 3) |
| docs/tasks/0149-report.md | create | step 5 |

No other file may change. Tests are not edited in this brief.

## 4. Steps

1. Old CSS out. From `App/`, run exactly this (it asserts every marker is unique and prints what it removed):
   ```
   .venv/bin/python - <<'EOF' 2>&1 | tail -8
   from pathlib import Path
   def cut(path, start, end, after=0, keep=()):
       p = Path(path); lines = p.read_text(encoding="utf-8").split("\n")
       s = [i for i, l in enumerate(lines) if l.startswith(start)]
       e = [i for i, l in enumerate(lines) if l.startswith(end)]
       assert len(s) == 1 and len(e) == 1 and s[0] < e[0], (path, start, s, e)
       block = lines[s[0]:e[0] + 1 + after]
       kept = [l for l in block if any(l.startswith(k) for k in keep)]
       lines[s[0]:e[0] + 1 + after] = kept
       p.write_text("\n".join(lines), encoding="utf-8")
       print(path, "removed", len(block) - len(kept), "lines, kept", len(kept))
   cut("app/static/host.css",
       "/* 0091 — stays fit the content lane, not the viewport. .stays-view is a named",
       "  .row-menu-panel .row-menu-item { min-height: 44px; display: flex; align-items: center; }", after=1)
   cut("app/static/host.css",
       "/* 0079 — Dashboard and Stays share one action pair: Open, then an adjacent More",
       ".host-workspace .stays-view .stay-col-deadline .deadline.overdue { max-width: none; }")
   cut("app/static/host-design0123.css",
       "body.host-workspace .stays-view td { padding-top:0; padding-bottom:0; }",
       "body.host-workspace .stay-col-actions .row-menu-trigger { min-width:42px; min-height:42px; }",
       keep=("body.host-workspace .row-primary-link, body.host-workspace .stay-identity-link",))
   cut("app/static/host-design0123.css",
       "  body.host-workspace .stays-view table, body.host-workspace .stays-view tbody, body.host-workspace .stays-view tr, body.host-workspace .stays-view td { display:block; width:100%; }",
       "  body.host-workspace .stay-col-actions .row-action-pair { justify-content:flex-start; }")
   EOF
   ```
   Expected (the orchestrator dry-ran it): `host.css removed 150 lines, kept 0`, `host.css removed 49 lines, kept 0`, `host-design0123.css removed 17 lines, kept 1`, `host-design0123.css removed 7 lines, kept 0`. An AssertionError means a marker moved: stop and report it. Then `grep -c 'stays-view\|stay-col-\|stay-report-deadline' app/static/host.css app/static/host-design0123.css` prints `1` for each file (host.css: a comment near `.filters` that mentions `.stays-view`; host-design0123.css: the kept `.stay-identity-link` line), and `python3 -c "t=open('app/static/host.css').read();print(t.count('{')-t.count('}'))"` prints `0`. Commit `0149 step 1`.

2. `host2.css`. Replace Anchor A (four lines) with:
   ```
     .host-workspace .ui-table tr { display: grid; grid-template-columns: minmax(0, 1fr) auto var(--control-h-phone); column-gap: var(--space-3); row-gap: calc(var(--space-1) / 2); align-items: start; position: relative; background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); padding: var(--row-py) var(--space-2) var(--row-py) var(--row-px); min-height: calc(var(--row-h) + var(--space-6) + var(--space-1)); }
     .host-workspace .ui-table td { display: block; grid-column: 1; min-width: 0; height: auto; padding: 0; border: 0; text-align: left; }
     .host-workspace .ui-table td:empty { display: none; }
     .host-workspace .ui-table td.ui-cell-acts:not([data-card]) { grid-column: 3; grid-row: 1 / span 3; justify-self: end; }
     /* 0149: MASTER 7.3 card roles */
     .host-workspace .ui-table td[data-card="primary"] { grid-row: 1; font-size: var(--size-16); font-weight: 600; color: var(--ink); }
     .host-workspace .ui-table td[data-card="secondary"] { grid-row: 2; grid-column: auto; font-size: var(--size-15); color: var(--ink-2); }
     .host-workspace .ui-table td[data-card="meta"] { grid-row: 3; grid-column: auto; font-size: var(--size-13); color: var(--ink-3); }
     .host-workspace .ui-table td[data-card="meta"] + td[data-card="meta"] { justify-self: end; }
     .host-workspace .ui-table td[data-card="badge"] { grid-column: 2; grid-row: 1 / span 2; justify-self: end; display: flex; flex-direction: column; align-items: flex-end; gap: var(--space-1); }
     .host-workspace .ui-table td[data-card="hide"] { display: none; }
     .host-workspace .ui-table td[data-card] .ui-sub { display: inline; margin: 0 0 0 var(--space-1); font-size: var(--size-13); color: var(--ink-3); font-weight: 400; }
     .host-workspace .ui-table td[data-card="actions"] { display: contents; }
     .host-workspace .ui-table td[data-card="actions"] > .row-menu { grid-column: 3; grid-row: 1 / span 3; justify-self: end; align-self: start; }
     .host-workspace .ui-table td[data-card="actions"] > .row-action-form { grid-column: 1 / span 2; grid-row: 4; margin: var(--space-1) 0 0; }
     .host-workspace .ui-table td[data-card="actions"] .row-action-send { width: 100%; height: var(--control-h-phone); min-height: var(--control-h-phone); }
     .host-workspace .ui-table .row-menu-trigger { width: var(--control-h-phone); height: var(--control-h-phone); min-height: var(--control-h-phone); }
   ```
   Replace Anchor B with:
   ```
   .host-workspace .ui-table td { height: var(--row-h); padding: var(--space-1) var(--row-px); border-bottom: 1px solid var(--line); vertical-align: middle; color: var(--ink-2); font-size: var(--body-size); }
   ```
   Delete the four lines of Anchor C (line 317, `.ui-table-stack thead`, stays). Append to the end of the file:
   ```
   /* 0149: desktop list cells. The row is the link, so a link in a cell is plain ink. */
   .host-workspace .ui-table td > a { color: inherit; text-decoration: none; }
   .host-workspace .ui-table td > .ui-sub, .host-workspace .ui-table .stay-report-deadline { margin: var(--space-1) 0 0; }
   .host-workspace .ui-table .ui-cell-acts > .row-action-form, .host-workspace .ui-table .ui-cell-acts > .row-menu { display: inline-flex; vertical-align: middle; margin: 0; }
   .host-workspace .ui-table .ui-cell-acts > .row-action-form + .row-menu { margin-left: var(--space-2); }
   ```
   `python3 scripts/design_lint.py | tail -3` must print OK (run from the repo root). Commit `0149 step 2`.

3. Templates. `reservations.html`, one edit per anchor; each old string occurs once:
   - D `<tr class="clickable-row" data-href=` becomes `<tr class="ui-row clickable-row" data-href=`
   - E `<td class="stay-col-stay" data-label=` becomes `<td class="ui-cell-first stay-col-stay" data-card="primary" data-label=`
   - F `<div class="small muted stay-col-source">` becomes `<div class="ui-sub stay-col-source">`
   - G `<td class="nowrap stay-col-dates" data-label=` becomes `<td class="nowrap stay-col-dates" data-card="secondary" data-label=`
   - H `<td class="stay-col-property" data-label=` becomes `<td class="stay-col-property" data-card="meta" data-label=`
   - I `<td class="num stay-col-guests" data-label=` becomes `<td class="num stay-col-guests" data-card="meta" data-label=`
   - J `<td class="stay-col-reporting" data-label=` becomes `<td class="stay-col-reporting" data-card="badge" data-label=`
   - K `<td class="nowrap row-actions stay-col-actions" data-label="">` becomes `<td class="ui-cell-acts row-actions stay-col-actions" data-card="actions" data-label="">`
   - L delete the line `          <span class="row-action-pair">` and M delete the line `          </span>` that sits right after `{{ row_menu_end() }}` (line 204; the only `</span>` on a line of its own in the file).

   `dashboard.html`:
   - N `<td class="ui-cell-first dashboard-row-copy">` becomes `<td class="ui-cell-first dashboard-row-copy" data-card="primary">`
   - O `<td>{{ property_identity(reservation.apartment_id, stay_label, true) }}</td>` becomes `<td data-card="secondary">{{ property_identity(reservation.apartment_id, stay_label, true) }}</td>`
   - P `<td class="ui-cell-r ui-num">` becomes `<td class="ui-cell-r ui-num" data-card="meta">`
   - Q `<td class="dashboard-row-task">` becomes `<td class="dashboard-row-task" data-card="badge">`
   - R `<td class="ui-cell-acts dashboard-row-actions">` becomes `<td class="ui-cell-acts dashboard-row-actions" data-card="actions">`

   `python3 scripts/design_lint.py | tail -3` OK. From `App/`: `.venv/bin/python -m pytest tests/test_design_stays.py tests/test_host_quiet_dashboard.py -q --tb=short -x 2>&1 | tail -5` passes. Commit `0149 step 3`.

4. Browser run, from `App/`, with `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0149`:
   `.venv/bin/python -m pytest tests/test_host_list_layouts_browser.py tests/test_host_stay_actions_browser.py tests/test_host_list_cards_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_quiet_dashboard_browser.py -q --tb=line -rs 2>&1 | tail -12`. Expected: all pass, 0 skipped, including `test_stays_pills_and_deadlines_stay_on_one_line` (rows ≤ 72 px at 1280 and 1440).
   Then the screenshots: `UBYHOST_CAPTURE_0079=1 UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_list_layouts_browser.py -k share_compact_row_menu -q --tb=line 2>&1 | tail -3`, then from the repo root:
   ```
   mkdir -p /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0149 && cp docs/tasks/0079-evidence/stays-390-cs.png docs/tasks/0079-evidence/stays-1280-cs.png docs/tasks/0079-evidence/dashboard-390-cs.png docs/tasks/0079-evidence/dashboard-1280-cs.png /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0149/ && git checkout -- docs/tasks/0079-evidence && git status --short docs/tasks/0079-evidence | head -3
   ```
   (the last command must print nothing).

5. Open the four files in `/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0149/` with the Read tool and tick each line by eye; write the result in the report:
   - stays 1280: header row is a plain 40 px line of grey 13 px labels (no tinted fill); cells have no inner boxes or lines; each date range is one line of plain dark text, "2 noci" under it in small grey; status badge with the deadline badge under it; the Send button and the ⋯ sit side by side in the last cell; rows are about 48 to 60 px, all the same style.
   - stays 390: each card is one white box about 90 px tall: line 1 stay label (bold) with the source after it in small grey, the status badge at the right; line 2 dates with "2 noci" after them, the deadline badge at the right under the status; line 3 property dot and name left, guests count right; the ⋯ is a 44 px square at the top right edge; only the ready stays have a full-width "Odeslat tento pobyt" line under the card text.
   - dashboard 1280: unchanged from before (table rows about 48 px, ⋯ at the right).
   - dashboard 390: each card: line 1 dates bold with "do ... " after them (when present) and the task badge at the right; line 2 property; line 3 guests; ⋯ top right.
   Run ruff: `App/.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 App/ | tail -3`. Write `docs/tasks/0149-report.md` (Status review or blocked, what each test run printed, the by-eye list, the screenshot paths). Commit `0149 report`.

## 5. Do not touch

Tests, `catalog.json`, `_components.html`, `app.css`, `components.css`, `tokens.css`, JS, Python, the chips and the setup strip (0150), anything under `docs/design/`.

## 6. Commands

As in steps 1 to 5. Every command ends with `| tail -N`.

## 7. Acceptance

- [ ] Step 1 printed the four "removed" lines and no AssertionError.
- [ ] `design_lint.py` OK after steps 2 and 3.
- [ ] Step 4: every listed browser test passes, 0 skipped.
- [ ] Step 5: all four by-eye lists confirmed; `docs/tasks/0079-evidence` clean.

## 8. Stop and ask

Stop if a marker in step 1 is not unique, if a test fails twice, or if a screenshot still shows a bug from section 1. Report the assertion or the file verbatim. Do not add page CSS (`.stays-view`, `.stay-col-*`, `.dashboard-row-*`) to fix a card: the roles must do it; say which role fails instead.

## 9. Report

As in step 5.
