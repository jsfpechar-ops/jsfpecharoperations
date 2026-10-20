# 0183 report

Status: review

## Files changed
- App/app/static/host2.css: `/* 0183 */` block. Search row gets `var(--surface)`, 1 px `var(--input-border)`, `var(--input-radius)`. Collapsed search is a square of `var(--control-h-phone)`. `.ui-chip` (filter chips) gets a 1 px `var(--input-border)`.
- App/app/templates/base.html: host2.css key `20261020-0183a-0183` (plain `-0183` was refused after the CSS changed).
- App/tests/static_versions.json: regenerated.
- App/tests/test_design_guardrails_browser.py: `test_sidebar_search_has_a_border`.
- docs/tasks/0183-screenshots/: 10 shots at 390, 1280 and 2000 for `/` and `/reservations`, plus collapsed at 1280 and 2000.

## Commands (last lines)
- `python3 scripts/design_lint.py` -> `design lint: OK`
- `App/.venv/bin/python tests/test_static_versions.py --write` -> wrote 32 files; `pytest tests/test_static_versions.py -q` -> `3 passed`
- `pytest -k sidebar_search` (guardrails browser) -> `1 passed`
- Browser set (guardrails, a11y guard, host-wide geometry), `-rs`: `19 passed, 0 skipped` (267 s)
- Evidence cleanup on docs/tasks/0102-evidence: done.

## Audit (step c)
Searched `background: var(--surface-2)` in host2.css.
- Changed: `.ui-search-row` (sidebar search), `.ui-chip` (filter chips; grey fill at rest, no border).
- Left alone: hover states (`.ui-btn-secondary:hover`, `.ui-btn-quiet:hover`, `.ui-menu-item:hover`, `.ui-nav a:hover`, `.row-menu-item:hover`, table row hover), `.ui-bone` skeleton, `.ui-swatch` demo chip, `.invoice-items-grid thead` header.
- Not checked: `.ui-toolbar-search` and `.ui-select` do not use `surface-2`, so the grep did not flag them. Not verified visually.

## Deviations
- Key: plain `20261020-0183` was refused after the CSS changed under it, so the fallback `20261020-0183a-0183` is used.
- Brief §6/§7/§8 were missing. The coordinator's message supplied the commands.
- Trailer: the commit uses `Co-Authored-By: Claude Sonnet 5.5` as the orchestrator asked. The system attribution reminder says Haiku 5.5. Flagged for owner.

## Questions
- Is the chip border the right scope (filter chips), or should the audit also cover toolbar search and selects?

## Owner steps left
- Review the PR, then merge with `scripts/merge-pr-on-green.sh`. Do not push to main. Production deploy is manual.
