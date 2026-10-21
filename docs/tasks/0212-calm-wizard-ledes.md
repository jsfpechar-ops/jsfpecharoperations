# 0212: Calm, readable wizard ledes

Status: review
Depends on: 0209 | Base commit: e5d5a47 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

0206 made every wizard lede two to four sentences of "why". They still use the old short-lede style (17 px bold; the stay-fee one copies the 26 px page heading), which at 390 px is a wall of bold text. Ledes become regular weight (GOV.UK lead-paragraph style) and the stay-fee lede drops its heading look, so every step reads the same.

## 2. Context

`App/app/static/host.css` (legacy, do not edit): `.setup-wizard-lede { ... font-size: 17px; font-weight: 700; ... }`, `.setup-wizard-instruction { ... font-weight: 600; ... }`.
`App/app/static/host2.css` (verbatim):
```
.host-workspace .setup-wizard-lede.setup-wizard-fee-intro { font-size: var(--size-26); font-weight: 600; letter-spacing: -0.01em; line-height: 1.2; }
@media (max-width: 1023px) { .host-workspace .setup-wizard-lede.setup-wizard-fee-intro { font-size: var(--size-22); } }
```
`App/app/templates/setup_wizard/stay_fee.html` (verbatim): `<p class="setup-wizard-lede setup-wizard-fee-intro">{{ t('why.stay_fee') }} {{ t('why.stay_fee_skip') }}</p>`

Two browser pins in `App/tests/test_onboarding_wizard_browser.py` encode the old look (around lines 1335 and 1474).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/setup_wizard/stay_fee.html | edit | drop `setup-wizard-fee-intro` |
| App/app/static/host2.css | edit | delete the two fee-intro rules, add one rule |
| App/app/templates/base.html | edit | host2 key |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_onboarding_wizard_browser.py | edit | two pins |
| docs/design/catalog.json | edit | only if design lint asks (Step 5) |

No other file may change.

## 4. Steps

1. `stay_fee.html`: `<p class="setup-wizard-lede setup-wizard-fee-intro">` → `<p class="setup-wizard-lede">`.
2. `host2.css`: delete the two lines quoted in §2. Append at the end of the file:
```
/* 0212: the why-ledes are 2-4 sentences; regular weight reads better than bold (GOV.UK lead paragraph). */
.host-workspace .setup-wizard-lede, .host-workspace .setup-wizard-instruction { font-weight: 400; }
```
3. `base.html`: replace the current `host2.css?v=` value (grep it; it is `20261021-0207`) with `20261021-0212`. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
4. `test_onboarding_wizard_browser.py`:
   a) replace
```
        assert page.locator(".setup-wizard-fee-intro").evaluate(typography) == page.locator(
            ".ui-ph h1"
        ).evaluate(typography)
```
   with
```
        # 0212: the fee lede looks like every other step's lede.
        assert page.locator(".setup-wizard-lede").first.evaluate(typography)[1:4] != page.locator(
            ".ui-ph h1"
        ).evaluate(typography)[1:4]
```
   b) replace `        assert int(lede.evaluate("(el) => getComputedStyle(el).fontWeight")) >= 700` with `        assert int(lede.evaluate("(el) => getComputedStyle(el).fontWeight")) == 400  # 0212`
5. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -10`. If it reports `setup-wizard-fee-intro` as stale in the catalog or in a template's legacy list, remove it from that list (JSON edit with `python3 -I`, `ensure_ascii=False, indent=2`, trailing newline) and re-run until `OK`.
6. Commit `0212 calm wizard ledes` (only §3 files, trailers from your prompt, never PNGs).

## 5. Do not touch

`host.css`, every template except `stay_fee.html` and `base.html`, filing code. AGENTS hard rules 1, 3, 6, 7, 8.

## 6. Commands

1. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_design_setup_wizard_browser.py -q --tb=line -rs 2>&1 | tail -20` (0 skipped)
2. From `App/`: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py -q --tb=line 2>&1 | tail -10`
3. Restore evidence PNGs the browser run rewrote: `git checkout -- docs/tasks/*-evidence` and delete untracked PNGs under `docs/tasks/`.

## 7. Acceptance

- [ ] Ledes and instructions render at weight 400 on every wizard step; the stay-fee lede matches the others. §6 passes.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0212-report.md`, as in TEMPLATE.md §9.
