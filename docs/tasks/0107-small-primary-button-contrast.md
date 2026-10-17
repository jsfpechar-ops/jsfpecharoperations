# 0107: Fix grey text on `.btn.small.primary` (Stay fee "Set up stay fee" and every small primary button)

Status: todo
Depends on: 0105 committed (same CSS file) | Base commit: head of branch `task/0105-restore-dashboard-stay-rows` | Branch: `task/0107-small-primary-button-contrast`
Executor: Haiku 5.5 sub-agent | Fits one session, 80k tokens at most

## 1. Objective

On the Stay fee page the coral "Set up stay fee" buttons show dark grey text on coral (unreadable, fails 4.5:1). Make every `.btn` keep its own text colour, and add a test that fails if a small primary button ever loses its contrast again.

## 2. Context

Cause (found by reading, confirm it in step 1): `App/app/static/host-design0123.css` line 21 (PR 397) recolours every element with class `small` inside the host shell:

```
body.host-workspace :is(.muted,.small,.hint,.help-tip-body,.lede,.dashboard-row-dates,.dashboard-row-property-context,.dashboard-row-task,.stay-col-source,.filter-applied-summary,.cal-control-label):not(.err-text):not(.warn-text) { color:var(--ink-secondary); }
```

Buttons are written `class="btn small primary"` (79 uses in 26 templates, e.g. `stay_fees.html` lines 49 and 56), so `.small` wins over `.btn.primary { color:var(--on-brand) }` (`app.css:1093`) by specificity. Production (`main`) does not have this rule, so production is fine; PR 397 introduces it.

Rules: AGENTS.md hard rules 6 and 7 (light mode only; browser tests with 0 skipped, screenshots in the report). WCAG: text contrast at least 4.5:1.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/host-design0123.css` | edit | Line 21: add `:not(.btn)` to the selector |
| `App/tests/test_host_button_contrast_browser.py` | new | Contrast test (step 3) |
| `docs/tasks/0107-report.md`, `docs/tasks/0107-screenshots/*.png` | new | §9, §7 |

No other file may change. If the selector bump needs a `?v=` change on the stylesheet link in `base.html`, STOP and ask.

## 4. Steps

1. `grep -n "\.small,\.hint" App/app/static/host-design0123.css` and confirm the excerpt in §2. Also run `git grep -n "btn" -- App/app/static/host-design0123.css` to check no other rule in that file recolours buttons.
2. Change the selector from `...:not(.err-text):not(.warn-text)` to `...:not(.err-text):not(.warn-text):not(.btn)`. Nothing else.
3. Add `App/tests/test_host_button_contrast_browser.py`: copy the fixture/app-startup pattern of `App/tests/test_host_list_layouts_browser.py` (same imports, same host login helper, same demo data, same skip rules). Open `/stay-fees` as the signed-in host (two demo properties, both "Not set up"), then for every `a.btn.small.primary` evaluate in the page `getComputedStyle(el).color` and `.backgroundColor`, compute the WCAG contrast ratio, and assert it is at least 4.5 and that there is at least one such button. Run it at widths 1280 and 360.
4. Run the commands in §6. Take screenshots of `/stay-fees` at 1280 and 360 px.

## 5. Do not touch

Any other stylesheet, template, JS, Python, i18n file; the `.dashboard-row*` rules (task 0105); the PR's other `:is(...)` entries (`.muted`, `.hint`, ...) stay as they are.

## 6. Commands

From `App/` (never set `PYTHONPATH=App`):

```
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_button_contrast_browser.py -q -rs
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests -q -rs -k "host_list_layouts or stay_fee or host_quiet_dashboard"
UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests -q
```

Before step 2, run the new test once against the unfixed CSS: it must FAIL (proves the test catches the bug). Known pre-existing failures: `test_feed_dns_pinning` (sandbox DNS) plus any listed in `docs/tasks/0105-report.md`. From the repo root: `python3 scripts/context_lint.py` (a `decisions.md` cap error is pre-existing).

## 7. Acceptance

- [ ] The new test fails before the fix and passes after, at 1280 and 360 px.
- [ ] Screenshots show white text on coral for "Set up stay fee" in `docs/tasks/0107-screenshots/`.
- [ ] No other visual change on the page; browser tests 0 skipped.

## 8. Stop and ask

Stop, and write the report, if: the excerpt is not found as shown; a test fails twice for another reason; a file outside §3 needs a change; you are about 75k tokens in; you need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/0107-report.md` (1,500 tokens at most), `Status: review`: files changed (`git diff --stat`), each command with the last 5 lines of output (including the failing run before the fix), §7 ticked honestly, deviations. Commit on the branch; never push.

## Owner steps

1. Push the branch into the PR 397 branch when 0105 and 0106 are also reviewed.
2. After CI, open `/stay-fees` on staging and check the button text is white.
