# 0912 report: stay-fee help copy and fee-register label

Status: blocked
Done: step 1 (help copy) and the orchestrator's fee-register change.
Left: steps 2 and 3 (guest-guide fact), and the 390 px fit fixes below.

## Files changed
- `App/app/host_i18n.py`: `how.stay_fees.1-3` (en, cs) now cover the guest-pay toggle, the rails and "UbyHost only shows the means". New key `stay_fees.label.obec_resident` (en "Resident of this municipality", cs "Obyvatel této obce").
- `App/app/host_vi_i18n.py`: same keys in vi. The vi text is my translation; a native check is advised.
- `App/app/templates/stay_fee_detail.html`: the grey hint is now a label plus `help_tip(...)` holding the existing explanation text (unchanged). `help_tip` added to the import.

## Commands
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`: 211 passed, 0 failed, 0 skipped.
- `python3 scripts/design_lint.py`: OK.
- `python3 scripts/context_lint.py`: OK (only pre-existing WARN lines).
- The 0898 test that checks the explanation text still passes, because that text stays in the help body.

## Screenshots (docs/tasks/screenshots-0912/)
- help-390.png: FAIL. The popover opens, but its panel runs past the right edge and steps 1 to 3 are cut off.
- help-768.png: OK. Fits; all three steps and "More in the guide" are readable.
- help-1280.png: OK. Fits and reads well.
- fee-row-390.png: OK. "Ada Guest", Exempt badge, "0 Kč  Resident of this municipality ?" on one line, the "?" inline.
- fee-row-tip-390.png: FAIL. The tooltip opens, but its left part is cut off at the left edge.
- fee-row-1280.png: OK. Label and "?" on one line.
- Cause: the popover and tooltip positioning is in the shared help CSS, which is not in the allowed files. Not fixed here.

## §5 checklist
- [x] Extends `host_page.html`; no own shell, `<style>`, `style=""` or raw colour.
- [x] Header action row and forms unchanged.
- [ ] No fine print; the "?" is inline, but the popover and tooltip overflow at 390 px (see above).
- [ ] 390, 768, 1280: scroll width is fine, but the 390 popover is clipped.
- [x] `test_layout_lint_browser.py` green, 0 skipped; screenshots opened and described above.
- [x] CS and EN keys added together, vi too; no em dash in UI copy.
- [ ] CI watched: no PR opened.

## Not done
- Guest-guide fact (brief §1.2, steps 2 and 3): `guide_facts.py`, guest guide route and template, editor screen, `guide_fact_stay_fee*` keys, `?v=` bump, guest e2e. Not in the orchestrator's scope or allowed files, and too large for this session. Decide: split into a 0912b brief, or drop it.
- 390 px fit of the help popover and the fee-row tooltip: needs a CSS change in the shared help component, a separate brief.
- Owner steps: none yet.
