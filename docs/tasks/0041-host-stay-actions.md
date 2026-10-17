# 0041: Guest-link availability and consistent stay menus

Status: blocked
Report: docs/tasks/0041-host-stay-actions-report.md
Depends on: 0040 completed local checks; execute only after its frozen owners.
Base commit: ee3a85cbf77037a5f01e837bd67fc9e9c02f6100
Branch: task/host-design-staging
Executor: owner-authorized Luna executor; Codex coordinates/reviews.

Owner pause: implementation stopped; preserve unfinished work as draft PR #338.
Read [handoff](../../.codex/handoffs/2026-10-10-233854-host-design-draft.md) before resuming.
Acceptance below remains unchecked; renewed owner instruction is required.

## 1. Objective

The owner reauthorized these two corrections after stopping broader design work:
find/fix the missing Copy guest form link on some Stays rows, and replace the
dashboard's > More control with the shared three-dot control. No wider redesign.

## 2. Context

Read AGENTS.md, status, the session exception and host-design action geometry.
Confirmed Stays anchor in App/app/templates/reservations.html:

```jinja
{% if progress.status in ('awaiting_guest', 'incomplete') and reservation.permalink_token %}
```

It hides Copy on ready/reported/preview/other rows despite their existing link.
Dashboard uses the same progress gate around menu copying, plus independent
`<details class="dashboard-more">` / `<summary class="btn">` markup. The shared
_components.html row_menu_begin/row_menu_end already supply the SVG ellipsis,
More actions accessible name and shared JS dismissal/keyboard behavior.
Copy should follow the existing Open guest form link's token availability;
retain canonical slug/token URL, permissions, expiry and server guards. Never
mint or enable missing links, change filing state or broaden guest access.

## 3. Files

- App/app/templates/reservations.html: Copy availability and action-group markup.
- App/app/templates/dashboard.html: shared menu integration, scoped row geometry.
- App/app/static/host.css: only Stays action-slot geometry if three controls need it.
- App/app/templates/base.html: asset cache token only if host.css or app.js changes.
- App/app/templates/_components.html: read shared menu/copy helpers; edit only if
  a small backwards-compatible optional hook is needed for dashboard copy/menu semantics.
- App/app/static/app.js: read existing row-menu/copy behavior; edit only if a
  reproduced shared-menu bug prevents Copy keyboard/focus behavior, report exact region.
- App/tests/test_host_quiet_dashboard_browser.py: menu selectors/assertions, keyboard.
- App/tests/test_host_filter_panels_browser.py and test_host_feedback_browser.py:
  relevant row-copy controls where needed.
- App/tests/test_host_wide_geometry_browser.py: applicable containment selectors.
- App/tests/test_host_stay_actions_browser.py: add focused mixed-status regression if clearer.
- docs/tasks/0041-host-stay-actions-report.md and 0041-evidence/: commands,
  unmodified synthetic captures only; no real data.

Validation adjunct: Luna validation may read focused 0041 logs and its named
test files to assist failure diagnosis; Luna executor retains all App edits.
Luna validation may also inspect the prior failed PR CI through
GitHub metadata/logs and reproduce collection in an isolated temporary archive
of the merge tree. Read-only diagnosis only; no additional App fixes or worktree.
Record whether CI failure is related, and exact evidence. Codex does not run it.

## 4. Steps

1. Reproduce the status-dependent disappearance on mixed-status fixtures with
   valid tokens, and record the exact cause. Verify absent-token rows don't
   generate invalid copy/open controls.
2. Replace the Stays gate with token availability, matching Open guest form.
   Remove the dashboard Copy progress gate for the same valid-link consistency.
3. Integrate row_menu_begin/row_menu_end into dashboard rows. Use the same SVG
   three-dot trigger and shared interaction behavior as Stays/Properties. Retain
   Open, menu actions, canonical Copy, confirm/Delete and existing return_to.
   Remove obsolete details marker/custom-menu styles instead of duplicating them.
4. Reserve a compact same-position ellipsis slot beside Open; use shared action
   heights, 44px mobile targets, no > marker or visible More text. Accessible
   localized More actions name remains. Every dashboard row uses the same slot.
5. Preserve Send on ready rows alongside newly visible Copy and More. Verify all
   three controls fit in a straight line at audited widths in EN/CS; minimally
   adjust their scoped tracks/card breakpoint if necessary. Don't hide or move
   Copy into a menu to conceal overflow. No unrelated columns or layout redesign.
6. Test mixed statuses (waiting, incomplete, ready/scheduled, reported, preview,
   failed where applicable), actual copy URLs and absent tokens; no assertion
   that every row must have a link when the server supplies none. Check mouse,
   Enter/Space, Escape, outside click, focus return, Copy feedback and Delete guard.
7. Run focused required-Chromium modules and geometry, capture 360,390,1280,1920
   EN/CS states including Send+Copy+More. Run the full CI-equivalent coverage
   command from 0040 validation after final App freeze; use CI tools PATH,
   required system Chromium, mock/staging, scheduler off, and unset smoke-only
   no-login/bootstrap variables. Preserve exit status/logs. No screenshots masks.

## 5. Do not touch

No other design changes, filters, statuses, dashboards caps, address validation,
police filing, guest permissions, deletion semantics, new dependencies or deploys.
Don't merge main. Prior rejected designs remain open for owner selection.

## 6. Commands

Focused browser checks and complete application coverage suite with zero skips;
EN/CS actions contained and aligned; actual clipboard URL correct. Report exact
commands and final output lines, baseline failure and final checks. Root runs
context lint only and reviews screenshots/diffs; Luna runs App checks.

Read-only prior-CI diagnosis: the ee3 test job failed with exit 2; Actions logs
were inaccessible. Its committed tree collected 3,030 tests cleanly, and the
current-main merge snapshot collected 3,051. The two earlier UI modules passed
42 tests. No collection cause or relationship to these fixes was established;
the final pushed commit still requires its own CI result.

## 7. Acceptance

- [ ] Copy is present wherever the existing guest form link is available, across statuses.
- [ ] Missing-token guard retained; canonical guest URL and permission/expiry unchanged.
- [ ] Dashboard uses the same ellipsis/menu component and interaction as other pages.
- [ ] Send/Copy/ellipsis and Open/ellipsis fit and align on desktop/mobile in EN/CS.
- [ ] Keyboard/dismissal/copy/Delete behavior verified; no unrelated design changes.
- [ ] Required browser/geometry and full coverage checks pass with zero skips.

## 8. Stop and ask

Stop only for a missing exact anchor, new access/filing requirement, or out-of-scope
change; send the concrete finding to Codex. Routine menu/CSS choices are authorized.

## 9. Report

Write the explicit Report path above (maximum 1,500 tokens), include changed
files, exact results, screenshot links, deviations and limitations, and set
Status: review. Root reviews, updates PR #338 and hands staging redeploy to owner.

## 10. Owner steps

Review PR #338 and screenshots, then redeploy staging if desired. No production
merge or deployment is authorized.
