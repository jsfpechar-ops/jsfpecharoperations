# 0253: Four red browser layout tests, fixed at the cause

Status: todo
Depends on: 0252 | Base commit: 09febf4 (tip of claude/project-thread-cjz5cc, PR #427) | Branch: claude/project-thread-kpgr9d
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Four browser tests fail on main and on PR #427. Two hide real layout bugs (the stay page's Next step panel content sits 13 px left of every other card's content on phone; the invoice Remove button is shorter than the inputs beside it on phone). The rest are stale tests: they measure things that changed on purpose. Fix the app where the layout is wrong and the test where it is stale. Never skip, loosen a tolerance, or delete an assertion.

## 2. Context

Run browser tests with the cloud workaround (team memory `browser-tests-cloud`): from `App/`, prefix every pytest command with
`PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/-home-user-jsfpecharoperations/7b34a644-d34a-5b7b-ba73-f85f9d98a14c/scratchpad/pw`. The venv already has playwright 1.63.0. Do not run `playwright install`.

Diagnosis (done by the orchestrator, reproduced on 09febf4):

**A. `test_0199_phone_geometry_browser.py::test_stay`, check A "panel content offset 118".**
`MEASURE` (line ~22) does `out.A = f(tl(panel) - tl(gh))`: text-left of the first text node in `.stay-command-panel` minus the Guests `h2`. Round 1 (0231) put a `<details class="journey">` progress bar at the top of the panel, so the first text node is now "Step 4 of 5…" after the dots (x ≈ 151). Stale measurement. But measured without the journey, the panel content is still wrong: Guests is a bordered card (`.ui-section`, 1 px border + 16 px padding, text at x 33), while `host-design0123.css` line ~130 (inside `@media (max-width:760px)`) still has the 0199 hack from before Guests became a card:
```
  /* 0199: A - the Next step panel content starts at the Guests heading edge. */
  body.host-workspace .host-stay-detail .stay-command-panel { padding-left:0; }
  body.host-workspace .host-stay-detail .stay-command-main { padding-left:4px; }
```
So the panel's content (and the journey bar) start at x 20, flush against the 4 px coloured stripe, 13 px left of the Guests text.

**B. Same test, check B "wrapped labels ['Copy this guest's ']".**
The button does not wrap. app.js upgrades `[data-copy]` buttons into `<span class="copy-label-stack"><span class="copy-label-default">…</span><span class="copy-label-confirmed">Link copied</span></span><span class="copy-state-icon" aria-hidden="true"><svg>…`. `lines(el)` takes `getClientRects()` of a range over the whole element, which includes the span boxes and the icon at different tops (728, 730, 720), so it counts 3 "lines". Stale measurement.

**C. `test_host_invoice_items_browser.py::test_invoice_item_geometry_and_localized_screenshots`: "Remove height differs from the first control at 360px (en): 48 vs 46.5".**
`host2.css` line ~423: `.invoice-items-grid .row-actions [data-remove-item] { min-height: 48px; }`; phone rule line ~102 sets `.ui-btn-compact { height: var(--control-h-phone) }` (44 px). Real bug: Remove must match the quantity input height at every width.

**D. `test_host_property_controls_browser.py::test_property_and_operator_controls_render_and_work_in_browser`: `assert labels.count() == 3` gets 4.**
`_property_address_fields.html` first `.property-address-grid` now holds street, house no., orientation no. and ZIP (4 fields, auto-fit grid in `host.css:824`). Intended layout. Stale count. The test may fail further down after this; fix each in the same way (find the cause first).

**E. `test_host_controls_browser.py::test_host_interactions_geometry_copy_and_archive_controls`: `assert requested_urls == [csv_request.value.url]` gets `[]`.**
PR #421 added `/static/sw.js`, whose fetch handler answers every same-origin GET navigation with `fetch(req)`. The CSV export is a GET form submit (a navigation), so the request reaches the server through the service worker, and Playwright's `page.route` never sees service-worker requests (documented Playwright limitation). The test is not about the service worker. Fix: create that test's browser context with `service_workers="block"`. Again, later failures in the same test: fix at the cause.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host-design0123.css | edit | A: replace the 0199 phone padding hack |
| App/app/static/host2.css | edit | C: Remove height |
| App/app/templates/base.html (+ any template referencing these two files) | edit | new `?v=20261022-0253` keys for both files |
| App/tests/static_versions.json | regenerate | `.venv/bin/python tests/test_static_versions.py --write` |
| App/tests/test_0199_phone_geometry_browser.py | edit | A and B measurement |
| App/tests/test_host_property_controls_browser.py | edit | D |
| App/tests/test_host_controls_browser.py | edit | E |
| docs/tasks/0253-report.md | create | report |

No other file may change. Do not change the invoice inputs, the journey markup, app.js or sw.js.

## 4. Steps

1. **A, app.** In `host-design0123.css`, replace the two 0199 lines quoted in §2 A (keep the comment, reworded) so that on phone the panel's content box starts exactly where the Guests card's content starts: panel `padding-left` = Guests card `border-left-width + padding-left` minus the panel's 4 px stripe (13 px today; write it as `calc(var(--space-4) + 1px - 4px)` only if `--space-4` is 16px in `tokens.css`, else a plain value with a comment), and drop the `.stay-command-main { padding-left:4px; }` line. Right padding must equal the Guests card's right inset too (check `padding-right` of both in the browser). The journey bar sits inside the panel, so it moves with it.
2. **A, test.** In `MEASURE`, compute `out.A` from the text-left of `.host-stay-detail .stay-command-panel .stay-command-main` (not the whole panel), and add `out.Aj = f(R(q('.stay-command-panel .journey')).left - R(q('.stay-command-panel .stay-command-main')).left)` when the journey exists. In `_check_stay` add: `if m.get("Aj") is not None: FAILS.append((abs(m["Aj"]) <= 1, f"{name}: A journey offset {m['Aj']}"))`. Keep `abs(m["A"]) <= 1`.
3. **B, test.** Rewrite `lines(el)` to count only visible text: walk text nodes with a TreeWalker, skip a node whose parent (or any ancestor up to `el`) has `aria-hidden="true"`, `visibility:hidden`, `opacity:0` or a zero-size box; take each remaining node's `range.getClientRects()`; count distinct line tops where two tops within 4 px are the same line. Then a real wrap (a second line ≥ ~14 px lower) still fails. Check: temporarily set `white-space:normal; width:120px` on the button via `page.evaluate` in a scratch run and confirm `lines` returns > 1, then remove the scratch code.
4. **C.** In the browser at 360 and 1280, read computed `height`, `min-height`, `box-sizing` of `[data-remove-item]` and `[name="item_quantity"]`. Change only the `host2.css` line ~423 rule so Remove's `height` and `min-height` equal the input's at every width (one rule, no `!important`).
5. **D.** Change `assert labels.count() == 3` to `== 4` with a one-line comment naming the four fields. Run the test; fix any next failure at its cause.
6. **E.** In `test_host_controls_browser.py`, add `service_workers="block"` to the `new_context(...)` call that owns the CSV check, with a comment: `# sw.js answers navigations itself; page.route cannot see service-worker requests.` Run; fix any next failure at its cause.
7. Bump `?v=` for host-design0123.css and host2.css to `20261022-0253` everywhere they are referenced (`grep -rn "host-design0123.css\|host2.css" app/templates`), then regenerate `static_versions.json`.
8. Run §6. Copy these screenshots into `/mnt/project-files/red-tests-safari/after/`: from `/mnt/project-files/design-reset/checkpoint-6/mobile/` the files `stay-incomplete-en-390.png`, `stay-failed-en-390.png`, `stay-ready-cs-390.png`, `stay-incomplete-vi-360.png`; plus a 390 px full-page screenshot of the invoice form with one "other" item (write it from the invoice test run or a scratch script; do not commit the script).

## 5. Do not touch

`App/app/static/sw.js`, `app.js`, `_workflow.html`, invoice input sizes, anything under `App/app/ubyport*`. Hard rules 6 (light mode), 7 (browser tests 0 skipped, 390 px screenshots), 8 (no push to main). Do not commit screenshots or scratch scripts.

## 6. Commands

From `App/` (prefix `PLAYWRIGHT_BROWSERS_PATH=…` as in §2):

```
.venv/bin/python -m pytest "tests/test_0199_phone_geometry_browser.py" tests/test_host_invoice_items_browser.py tests/test_host_property_controls_browser.py tests/test_host_controls_browser.py tests/test_host_stay_actions_browser.py tests/test_0252_touch_sweep_browser.py tests/test_0251_tablet_browser.py tests/test_static_versions.py -q --tb=short -p no:cacheprovider 2>&1 | tail -30
```
Expected: all pass, 0 skipped. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] The four named tests pass; no assertion removed or loosened; 0 skipped.
- [ ] At 360 and 390, Next step panel text-left equals Guests heading text-left (±1), journey bar aligned with it.
- [ ] Remove height equals the quantity input height at every tested width.
- [ ] `?v=20261022-0253` on both CSS files; static_versions test passes.
- [ ] Screenshots in `/mnt/project-files/red-tests-safari/after/`.

## 8. Stop and ask

Per TEMPLATE §8 (excerpt not found, a test fails twice after a fix attempt, 25 tool calls, file outside §3).

## 9. Report

Write `docs/tasks/0253-report.md` (600 tokens max), set `Status: review` here, commit with message `0253: red layout tests fixed at the cause`. Do not push.
