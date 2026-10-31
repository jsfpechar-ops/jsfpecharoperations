# 0443: dashboard first-paint attention polish (one demonstrated improvement)

Status: todo
Depends on: none | Base commit: 8b5317d0 | Branch: task/0443-dashboard-attention
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

One demonstrated dashboard improvement from the smoothness plan's revised order: give the dashboard's single attention area a cleaner first paint without touching the needs-you producer contract. The producer (`App/app/needs_you.py:177`) already sorts lines by tone rank; the template's first-item summary is correct and must not gain redundant aggregation.

## 2. Context

The rules that apply, pasted in. Exact code excerpts, each with its file path. If an excerpt isn't found verbatim, STOP (§8).

The producer sorts; the template renders that order as-is:

```python
# App/app/needs_you.py (line 177)
lines.sort(key=lambda line: _TONE_RANK.get(line["tone"], 1))
```

The browser fixture asserts the sorted order and a red first item (App/tests/test_host_quiet_dashboard_browser.py, assertions around lines 323-327): `ranks == sorted(ranks)`, first item `data-tone == "red"`.

Binding rules (docs/context/rules.md §UX and interaction, revised 2026-10-30):

- One attention surface per page; folding a banner preserves warning severity, action, dismissal and visibility; a badge cannot hide a blocking warning; the needs-you producer's tone ordering stays the contract the template renders.
- Reuse existing tokens/components (`tokens.css`, `components.css`, `ui_*` macros); no new stylesheet, no new design generation.
- Measure performance rather than promise it; no perf claims in the report without recorded samples.
- Changed host pages: `test_host_geometry.py` 0 skipped, before/after 390 px screenshots in the PR.
- Update the component catalog (`docs/design/`) if a component's look changes.

Relevant sources to read first (read ranges, do not audit):

- `App/app/templates/base.html` (shell and needs-you include point)
- `App/app/templates/dashboard.html` (attention area placement)
- `App/app/templates/_shell_topbar.html` (existing badge pattern)
- `docs/design/MASTER.md` (the needs-you component section)
- `docs/design/pages/dashboard.md` (the page add-on)

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/dashboard.html | edit | The scoped change decided in §4 step 1, within the existing attention area only |
| App/tests/test_dashboard_first_paint.py | create | Template/markup assertions for the change |
| docs/design/pages/dashboard.md | edit | Catalog/page add-on line for the changed component |
| docs/tasks/0443-report.md | create | The report per TEMPLATE §9 |

No other file may change.

## 4. Steps

1. Read the five sources in §2. Decide the smallest change that improves the dashboard's first paint inside the existing attention area (for example: reduce stacked summary tiles to at most 4 with a justified mapping to the needs-you card, or fold a redundant welcome/onboarding banner per the W2 rule). Do NOT add severity aggregation to the template; the producer contract already guarantees red-first ordering.
2. Write the exact template diff here (old/new markup), reusing `ui_*` macros only.
3. Apply the diff; run `python3 -m pytest tests/test_dashboard_first_paint.py tests/test_host_quiet_dashboard_browser.py -q --tb=short -x 2>&1 | tail -30` (the browser file needs Playwright chromium; if unavailable, record the skip in the report as a blocker, do not fake it).
4. Run `python3 -m pytest tests/test_host_geometry.py -q -rs 2>&1 | tail -30` and confirm 0 skipped.
5. Capture before/after 390 px screenshots (widths 360/1280 only if layout changed beyond the attention area) into `UBYHOST_SHOTS_DIR`.
6. If a component look changed, update `docs/design/pages/dashboard.md` and the catalog entry.

## 5. Do not touch

- `App/app/needs_you.py` (producer contract).
- `App/app/templates/base.html`, `_shell_sidebar.html`, `_shell_topbar.html` unless step 1 proves a defect there; if so, STOP and report (§8).
- Guest/marketing/auth/legal surfaces; `tokens.css`/`components.css` wholesale reorganization; any stylesheet deletion.
- The filing path (`ubyport/`, `reporting.py`, deadlines).

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

```
python3 -m pytest tests/test_dashboard_first_paint.py -q --tb=short -x
python3 -m pytest tests/test_host_quiet_dashboard_browser.py -q --tb=short -x
python3 -m pytest tests/test_host_geometry.py -q -rs
```

Expected: all pass, geometry 0 skipped.

## 7. Acceptance

- [ ] The dashboard shows exactly one attention surface with the producer's tone order unchanged.
- [ ] No template-side severity aggregation added; `needs_you.py` untouched.
- [ ] `test_host_geometry.py` passes 0 skipped; new test passes.
- [ ] Before/after 390 px screenshots attached in the PR.
- [ ] No perf claim without recorded samples (route, viewport, network, cache state, count).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0443-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/templates/dashboard.html` (attention-area diff)
- `App/tests/test_dashboard_first_paint.py` (new)
- `docs/design/pages/dashboard.md`

## Owner steps

1. Review the PR diff and the before/after 390 px screenshots.
2. Merge with `scripts/merge-pr-on-green.sh <pr>`; deploy when you choose.
