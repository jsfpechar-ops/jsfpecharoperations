# 0289: Business table name width must not make the table scroll sideways

Status: todo
Depends on: 0288 | Branch: worktree /home/user/wt, local branch wip-0284 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 12 tool calls, 40k tokens

## 1. Objective

CI guest-browser fails `test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard`: at 1280 px with the sidebar open, the Business table (container 976 px) is 1038 px wide and scrolls sideways. Cause: the 0288 rule `td.col-name { min-width: calc(var(--space-12) * 4); }` applies from a 950 px container. Give the name that room only from a 1100 px container; the arrow rule already keeps the arrow on the name's line at any width.

## 2. Context

host2.css 0288 block (end of file):

```css
@container list-cards (min-width: 950px) {
  .host-workspace .lc-entities tbody td.ui-sub { display: table-cell; }
  .host-workspace .lc-entities tbody td.col-name { min-width: calc(var(--space-12) * 4); }
  ...
}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | edit | move the min-width line |
| App/app/templates/base.html | edit | host2.css key |
| App/tests/static_versions.json | regenerate | `--write` |

No other file may change.

## 4. Steps

1. host2.css: delete the line `  .host-workspace .lc-entities tbody td.col-name { min-width: calc(var(--space-12) * 4); }` from the 0288 block, and append at the very end of the file:

```css
@container list-cards (min-width: 1100px) {
  .host-workspace .lc-entities tbody td.col-name { min-width: calc(var(--space-12) * 4); }
}
```

2. Cache key, from the worktree root:

```
sed -i 's/host2.css?v=20261022-0288"/host2.css?v=20261022-0289"/' App/app/templates/base.html
grep -c 'host2.css?v=20261022-0289"' App/app/templates/base.html
cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5
```

Commit: `0289 step k` per step.

## 5. Do not touch

Everything not in section 3. AGENTS.md hard rules 6 and 7.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

```
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_0285_rows_browser.py tests/test_static_versions.py -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -5
git checkout -- docs/tasks/0102-evidence; git clean -fq docs/tasks/0102-evidence
```

Expected: all pass, 0 skipped; lint clean. Never commit App/.venv or docs/tasks/0102-evidence.

## 7. Acceptance

- [ ] The layout guard and test_0285 pass, 0 skipped.
- [ ] host2.css key `20261022-0289`; static_versions.json regenerated; design lint clean.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8. If test_0285's entities check fails (arrow not on the name line at 1280), stop and paste the assertion.

## 9. Report

`docs/tasks/0289-report.md` (300 tokens at most), set `Status: review`. Do not push.
