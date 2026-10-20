# 0175 report

Status: review

## Files changed
- App/app/templates/_icons.html: new icon `invoice-slip` (old pre-redesign invoice glyph, see below)
- App/app/templates/_shell_sidebar.html, _shell_tabbar.html: Invoices uses `invoice-slip` and `nav.invoices_fees`
- App/app/host_i18n.py: `nav.invoices_fees` in en ("Invoices and stay fees") and cs ("Faktury a poplatky z pobytu")
- App/app/static/host2.css: 0175 badge border rules (appended)
- App/app/templates/base.html: host2.css key `-0175`; App/tests/static_versions.json regenerated
- App/tests/test_design_shell.py: one string, `receipt` to `invoice-slip`
- App/docs/tasks/0175-screenshots/ (390 and 1280 px, /reservations and /invoices), docs/tasks/0175-report.md

## Old icon
Found in commit 912a5a6, App/app/templates/_components.html `nav_icon('invoice')`: a receipt slip inline SVG (20 px viewBox, stroke 1.5). Re-added as `invoice-slip` with the same paths scaled 1.2 to the 24 px Lucide grid.

## Commands (last lines)
- design_lint.py: `design lint: OK`
- test_static_versions.py: `3 passed`
- test_design_shell, test_host_redesign, test_host_i18n: `23 passed` (after the one-string fix)
- Browser guards (test_design_guardrails_browser, test_a11y_guard_browser, test_host_controls_browser): `8 passed, 1 warning`, 0 skipped
- 0102-evidence cleanup: ran, not refused
- shots.py: `6 shots, 0 with problems`

## Acceptance (section 7)
- [x] Old icon and "Invoices and stay fees" in sidebar and More sheet; pills bordered; tests pass with 0 skipped.

## Deviations
- Badge CSS: the brief's one-line rule would drop the `-overdue` border (no `--ui-dot` on overdue), so the rule uses `var(--ui-dot, var(--st-action-dot))` and `box-sizing: border-box` so the height stays `--badge-h`.
- Screenshots: the shots command in the brief captures pages only. The open More sheet was not captured; the 390 px invoices shot shows the bordered pills. Sidebar label at 1024 px not checked visually.
- Not pushed, no PR opened (orchestrator said never push).

## Questions
- Commit trailer: the brief's trailers name Claude Sonnet 5.5; the session's attribution note names Claude Haiku 5.5. I used the Sonnet 5.5 trailer as briefed.

## Owner steps left
- Review the branch, then merge via `scripts/merge-pr-on-green.sh`. Push is not done.
