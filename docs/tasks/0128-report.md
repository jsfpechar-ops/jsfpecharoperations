# 0128 report (executor: Haiku 5.5)

Status: blocked

## Files changed

- `App/app/templates/_ui.html` (new, step 1, committed as `0128 step 1`, commit b940931).
- `App/app/static/host2.css` (new, step 2, NOT committed: design lint fails, see below).

## Commands

- Step 1 macro render: `{% from "_ui.html" ... %}` output: `<button class="ui-btn ui-btn-primary" type="button"><span>Save</span></button><span class="ui-badge ui-badge-action ui-badge-overdue">! x</span>` (matches expected).
- Step 2 `python3 scripts/design_lint.py 2>&1 | tail -30`:
  - `DESIGN App/app/static/host2.css: S1 raw colour rgba(`
  - `DESIGN App/app/static/host2.css: S1 font-family outside tokens`
  - `design lint: FAIL` (brief expects `design lint: OK`).
- Steps 3 to 5 and the test commands were not run.

## Section 7

- [ ] Not ticked. Steps 2 to 5 not done.

## Deviations

Done: steps 1 to 1 (step 2 file written, uncommitted). Left: steps 2 to 5 and report sections 6 and 7.

## Questions

1. `host2.css` line 66: `.host-workspace .ui-mono { font-family: var(--font-mono); ... }` is flagged as "font-family outside tokens". Which token or rule is expected here?
2. `host2.css` line 84: `.host-workspace .ui-dialog::backdrop { background: rgba(32, 32, 30, 0.4); }` is flagged as "raw colour". Which token should the backdrop use (for example a scrim token in `docs/design/`)? I did not guess.

## Owner steps left

None.
