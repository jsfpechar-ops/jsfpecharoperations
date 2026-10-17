# 0041: paused draft handoff

Status: blocked — owner stopped implementation and requested a draft for another AI.
Branch: `task/host-design-staging`; PR [#338](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/338).

Full [handoff](../../.codex/handoffs/2026-10-10-233854-host-design-draft.md)
contains the design inventory, decisions, source references and ordered next steps.
No acceptance is claimed. The brief remains blocked until renewed owner instruction.

## Changes preserved

- Stays Copy visibility now follows `reservation.permalink_token`, replacing
  the awaiting-guest/incomplete-only restriction that hid available links.
- Dashboard replaces bespoke `> More` with shared ellipsis; Copy uses the same
  token guard. Open and ellipsis have reserved action widths.
- Shared Copy helper adds optional menuitem semantics. Shared menu JavaScript
  adds keyboard navigation, opening focus and manual-copy focus handling.
- Mixed-status Stays browser coverage and dashboard interaction checks updated.
- No backend access, expiry, reporting, calculations or deletion policy changes.

## Last executor validation

Required Chromium command from `App/`:
`.venv/bin/python -m pytest tests/test_host_stay_actions_browser.py tests/test_host_quiet_dashboard_browser.py -q`

**2 failed, 1 passed, 0 skipped; 30.24s.**

- Stays at 1280px: Send/Copy/ellipsis right edge is 1299.61, outside viewport
  (`test_host_stay_actions_browser.py:197`). Genuine Ready Send and status
  visibility checks passed before containment failed.
- Mobile dashboard menu closes after opening: expanded=false, scrollY=163,
  panel returned to row (`test_host_quiet_dashboard_browser.py:216`). First-item
  focus causing scroll is a hypothesis; no further patch was made after stop.

Test-source compilation passed earlier. No final full suite or final CI result
exists for this WIP. Historical 0040 results (3,030 passes, zero skips) predate
these changes and cannot be reused as acceptance. Prior ee3 CI exit 2 remains
undiagnosed; clean test collection does not explain its failure.

## Remaining work

Resolve action overflow and mobile menu behavior; test shared-menu regressions;
bump the stale 0040 asset cache version; run final browser/geometry/full coverage
and CI with zero skips; capture final evidence. The owner's other rejected
design choices await hand-picking. Legal address requiredness is not verified.

Local `generated_images/0041-evidence/` contains partial synthetic action
captures only and is not included in this commit. Earlier committed evidence
is under `docs/tasks/0040-evidence/`; it is historical, not current acceptance.

All executors and test processes are stopped. No staging deployment or merge
was performed. Owner/next AI reviews the draft; execution requires renewed scope.
