# 0950 report: Stays current pill stays dark on hover

Status: review

## Files changed
- `App/app/static/app2.css` line 1938 (step 1, commit 628ce250)
- Browser test for the current pill state on Stays and archive (step 2, commit ccbf8375)
- `docs/tasks/screenshots-0950/reservations-{390,768,1280}.png` (step 3, commit 6cb87991)
- `docs/tasks/0950-report.md`, `docs/context/status.md` (step 4)

No decision or known-issues line: one-selector bug fix (brief §4 step 4).

## Tests
- `test_layout_lint_browser.py`, `test_static_versions.py`, `test_host_pill_state_browser.py`: 13 passed, 0 skipped (run before this session, not re-run).
- `python3 scripts/context_lint.py`: `context lint: OK` (only WARN lines about other briefs; no error).

## Per-page UX note (AGENTS.md rule 10)
- **Stays `/reservations`, 390 px:** current pill "Upcoming & current" is dark with white text and a visible red focus ring. Other pills are light grey. The pill strip is cut at the right edge ("Pas" visible), so the strip scrolls sideways inside itself. The page itself does not scroll sideways.
- **Stays `/reservations`, 768 px:** same dark current pill with white text and focus ring. Other pills light grey. Nothing clipped. This screenshot was first opened by the executor for this report, not by the orchestrator.
- **Stays `/reservations`, 1280 px:** same dark current pill with white text and focus ring. Layout intact, nothing clipped.

The screenshots show the current pill as already dark. Hover is confirmed by the browser test (computed background equals `--ink`), not by a visible change in the screenshot.

## Design-system checklist (design-system.md §5)
- [x] Page extends `host_page.html`; no CSS change to the shell (step 1 is one selector).
- [x] Header action row unchanged.
- [x] No Save form or heading change.
- [x] No help "?" change.
- [x] No spacing change.
- [ ] 390/768/1280 "no sideways scroll": the 390 pill strip scrolls sideways inside itself (see above). Pre-existing; not in this brief. Owner or orchestrator to decide.
- [x] `test_layout_lint_browser.py` green, 0 skipped.
- [x] Screenshots at 390/768/1280 exist; 390 and 1280 opened by the executor; 768 opened by the executor.
- [x] No copy change, so CS/EN keys and em-dash check do not apply.
- [ ] CI watched to the end: not yet (no push in this session).

## Deviations
Done: steps 1 to 4. Left: none. No push (per owner instruction). To meet the 700-token status cap, shortened the billing line in status.md (dropped "Deploy manual.") and the Production line's "Next" tail.

## Questions
- Should the 390 pill strip be fully visible or stay a scroller? Not changed here.

## Owner steps left
- Review the PR, then merge with `scripts/merge-pr-on-green.sh` after CI is green. Push the branch when ready (not done here).
