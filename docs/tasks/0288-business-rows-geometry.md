# 0288: Business table rows: contact cell and Open arrow geometry

Status: todo
Depends on: 0285, 0287 | Branch: worktree /home/user/wt, local branch wip-0284 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 40k tokens

## 1. Objective

The final geometry review of PR #431 found two faults on the Business & legal details table (`/entities`) at wide widths (container at least 950 px), now that its rows are bordered cards (0285):
- The Contact cell is `td.ui-sub`, and `.ui-sub { display: block }` (host2.css line 167) turns it into a block, so its border and hover break away from the row.
- The name column is narrow (about 120 px), so the name wraps and the Open arrow drops under it, tight against the name: the same fault the owner reported on Guest links.

## 2. Context

- host2.css ends with the 0285/0286 blocks. The Guest links fix (0285) reads:
  `.host-workspace .property-summary-table td:first-child .row-primary-link { display: inline-block; max-width: calc(100% - var(--space-12)); vertical-align: middle; }`
- entities.html: `<div class="panel tight scroll-x entities-page list-cards lc-entities">`, name cell `td.col-name` with `row-primary-link` then `row_open()`. Below 950 px the rows are cards (host.css 0281); leave those alone.
- Lint on host2.css: no raw colours, no bare px except 0 and 1. `--space-12` is 3rem.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | append | the 0288 block |
| App/app/templates/base.html | edit | host2.css key |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_0285_rows_browser.py | edit | add the entities check |

No other file may change.

## 4. Steps

1. host2.css: append at the very end:

```css

/* 0288: Business rows (wide): the contact cell stays a table cell so the row
   card is whole, and the name gets room so the Open arrow sits on its line. */
@container list-cards (min-width: 950px) {
  .host-workspace .lc-entities tbody td.ui-sub { display: table-cell; }
  .host-workspace .lc-entities tbody td.col-name { min-width: calc(var(--space-12) * 4); }
  .host-workspace .lc-entities tbody td.col-name .row-primary-link { display: inline-block; max-width: calc(100% - var(--space-12)); vertical-align: middle; }
  .host-workspace .lc-entities tbody td.col-name .row-primary-link + .row-open { margin-left: var(--space-3); }
}
```

2. Cache key, from the worktree root:

```
sed -i 's/host2.css?v=20261022-0286c"/host2.css?v=20261022-0288"/' App/app/templates/base.html
grep -c 'host2.css?v=20261022-0288"' App/app/templates/base.html
cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5
```

3. test_0285_rows_browser.py: directly after the line `            assert gap["sameLine"] and gap["gap"] >= 11, (width, gap)` insert (same indentation):

```python
            page.goto(base + "/entities?lang=en")
            rows = page.evaluate(
                """() => [...document.querySelectorAll('.lc-entities tbody tr')].map(tr => {
                const a = tr.querySelector('.row-primary-link'), o = tr.querySelector('.row-open');
                const ra = a.getBoundingClientRect(), ro = o.getBoundingClientRect();
                const sub = tr.querySelector('td.ui-sub');
                return {gap: ro.left - ra.right, sameLine: ro.top < ra.bottom && ro.bottom > ra.top,
                        contact: sub ? getComputedStyle(sub).display : 'table-cell'}; })"""
            )
            assert rows, width
            for row in rows:
                assert row["sameLine"] and row["gap"] >= 11 and row["contact"] == "table-cell", (width, row)
```

Commit: `0288: Business rows keep the contact cell and the Open arrow on the name line`.

## 5. Do not touch

Everything not in section 3. Do not change host.css, entities.html or the card rules below 950 px. AGENTS.md hard rules 6 and 7.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

```
.venv/bin/python -m pytest tests/test_0285_rows_browser.py tests/test_static_versions.py tests/test_0284_states_browser.py -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -5
git checkout -- docs/tasks/0102-evidence; git clean -fq docs/tasks/0102-evidence
```

Expected: all pass, 0 skipped; lint clean. Never commit App/.venv or docs/tasks/0102-evidence.

## 7. Acceptance

- [ ] test_0285 passes at 1280 and 2000 with the entities check, 0 skipped.
- [ ] host2.css key `20261022-0288`; static_versions.json regenerated; design lint clean.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8. If the entities check fails twice, stop and paste the assertion message.

## 9. Report

`docs/tasks/0288-report.md` (300 tokens at most), set `Status: review`. Do not push.
