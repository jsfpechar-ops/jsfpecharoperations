# 0159: guard checks that table cells sit under their headers; fix the settings activity log

Status: done
Depends on: 0144 | Branch: claude/project-thread-5hw8cf
Executor: Sonnet 5.5 or Haiku 5.5 | Fits one session

## 1. Objective

At 1280 px the settings "Recent activity" table renders every cell stacked in the first column under a visible desktop header. Cause: `.host-workspace .ui-sub { display: block; }` (host2.css line 158) turns each `<td class="ui-sub">` into a block. This is the same bug class as the owner's dashboard screenshot (a card layout under a desktop header), and the layout guard missed it. Add a check to the guard, then fix the cause.

## 2. Context

The guard is `App/tests/design_guard.js`. MASTER 11.0 allows adding checks but never loosening them. The current host2.css key is `20261019-0144e`.

## 3. Files

`App/tests/design_guard.js`, `App/app/static/host2.css` (append), `App/app/templates/base.html`, `App/tests/static_versions.json`, `docs/design/MASTER.md` (one bullet), `docs/tasks/0159-*`.

## 4. Steps

1. In `App/tests/design_guard.js`, insert this block right before the line `  return out;`:

```js
  // 6. table cells sit under their header (catches card rules leaking onto a desktop table)
  for (const table of ws.querySelectorAll('table')) {
    const head = table.tHead;
    if (!head || !vis(head) || !head.rows.length || !table.tBodies.length) continue;
    const ths = [...head.rows[0].cells].filter(vis);
    for (const tr of table.tBodies[0].rows) {
      if (!vis(tr) || [...tr.cells].some((c) => c.colSpan > 1)) continue;
      const tds = [...tr.cells].filter(vis);
      for (let i = 0; i < Math.min(tds.length, ths.length); i++) {
        const a = tds[i].getBoundingClientRect(), b = ths[i].getBoundingClientRect();
        if (Math.abs(a.left - b.left) > 2 || a.top > tds[0].getBoundingClientRect().bottom) { out.push(['cell-not-under-header', name(tds[i]), name(ths[i])]); break; }
      }
      break;
    }
  }
```

2. From `App/` with the browser env, run `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q 2>&1 | tail -15`. Expected: it **fails** with `cell-not-under-header` on route `settings` (or `settings-account`) at 1280 and 2000. Record every finding it lists in the report.
3. Append to `App/app/static/host2.css`:

```
/* 0159: subtext class on a table cell keeps the cell a cell on desktop */
@media (min-width: 1024px) { .host-workspace .ui-table td.ui-sub, .host-workspace .ui-table th.ui-sub { display: table-cell; } }
```

   Bump the key to `20261019-0159`, then run versions `--write`, the version test and `scripts/design_lint.py`.
4. Rerun the guard. Expected: pass. If other routes show `cell-not-under-header`, find the rule that turns those cells into blocks and fix it the same way, scoped to `min-width: 1024px`. If that is not clear, stop and report the finding verbatim.
5. In `docs/design/MASTER.md` section 11.0 item 1, add the bullet `   - A table cell does not sit under its column header.` after the bullet that starts with `   - Content spills out of its table row.`
6. Run `.venv/bin/python -m pytest tests/test_host_controls_browser.py tests/test_shell_lane_browser.py tests/test_host_wide_geometry_browser.py -q -rs 2>&1 | tail -6` with the browser env. Expected: pass, 0 skipped.
7. Commit by path: `0159: guard checks table columns; settings activity table fixed`. Do not push.

## 5. Do not touch

Other checks in the guard. Hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] The new check exists, first failed on settings, and now passes everywhere.

## 8. Stop and ask

An unclear new finding, or a test fails twice.

## 9. Report

`docs/tasks/0159-report.md`, `Status: review`.
