# 0038: Host interaction and control polish

Status: review
Report: docs/tasks/0038-host-controls-report.md
Depends on: 0037 | Base commit: 6545d094f41b717e33ca053cb74e022fa291f5d6 | Branch: task/host-design-staging
Executor: Luna authorized owner | Fits one session

## 1. Objective

Add consistent hover and keyboard-focus feedback to interactive host rows and cards, keep grouped actions within the viewport, and finish the Settings audit and export-dialog controls. Clarify the copied guest-form URL and existing soft-archive actions without changing archive, restore, export or deletion behavior.

## 2. Context

`docs/DESIGN.md`, “Action geometry”: “Controls that sit in the same action group share one height (`--action-height`, 42px), one gap (`--action-gap`, 8px), and the same baseline.”

`docs/DESIGN.md`, “Interaction feedback: default everywhere”: “interactive rows, cards, links and controls must respond consistently to pointer hover and keyboard focus throughout the app.” It also says static panels must not suggest clickability and essential actions stay available without hover.

`docs/DESIGN.md`, “Delete action: move to Archived”: “label existing host archive actions **Delete** (Czech: **Smazat**). Keep their existing archive operation and move records to **Archived**; this is a copy change, not permission to permanently erase data.” The confirmation is “This item will move to Archived.” / “Tato položka se přesune do archivu.”

`docs/DESIGN.md`, “Copy and action confirmations”: in a stay's More menu, use **Copy guest form link**, meaning the guest registration URL, never the internal host stay-detail URL.

Current tokens and selectors: `App/app/static/host.css` defines `--action-height: 42px` (44px at mobile), and `--surface-hover`; clickable rows use `.clickable-row` (for example `App/app/templates/reservations.html`). The source issue was the onboarding intro's fixed two-column geometry at 360px, where its action crossed the viewport edge.

`docs/plans/host-filter-audit.md` selects “Two labelled, directly selectable controls in the same segmented family” for Settings' All/Support scopes. It requires export dialogs to retain explicit date/property scope, matching field/label/button geometry, and existing endpoint, required bounds, limits, warning and output.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/host-controls.css` | Add | Scoped host interaction feedback and responsive action/onboarding geometry |
| `App/app/templates/reservation_detail.html` | Edit | Guest-form copy labels and Delete / move-to-Archived confirmation on existing stay and guest soft-archive forms |
| `App/app/templates/settings_archived.html` | Edit | Accessible class and group label for archived-item filters |
| `App/app/templates/settings.html` | Edit | Direct accessible segmented controls for the All/Support audit scopes |
| `App/app/templates/base.html` | Edit | CSV scope summary and confirm-button labels only |
| `App/app/templates/_components.html` | Edit | Optional server-derived scope label attributes on CSV triggers only |
| `App/app/static/app.js` | Edit | Populate CSV scope summary and label only exact `/archive` confirmations |
| `App/tests/test_host_controls_browser.py` | Add | Authenticated Chromium coverage for interactions, settings scopes, export dialog fields and geometry, copy/archive text, and overflow across host pages |
| `docs/tasks/0038-host-controls.md` | Add | This execution brief |
| `docs/tasks/0038-host-controls-report.md` | Add | Validation evidence and reviewer handoff |

## 4. Steps

1. Add host-workspace-scoped focus-visible outlines, interactive-row/card hover and focus-within feedback, and action-group/onboarding wrapping constraints to `host-controls.css`. Use existing tokens, keep control tracks 42px desktop / 44px mobile, and do not add click affordance to static panels.
2. In `reservation_detail.html`, use `host.copy_guest_form_link` for controls copying the guest registration URL. On the stay and per-guest `/archive` forms only, use `host.delete` and `host.delete_to_archived.confirm`; keep their existing routes, CSRF and return targets, and restore branches.
3. Add the `archive-type-filters` class and accessible group label to the existing filter control in `settings_archived.html`; preserve filter destinations and archived restore actions. In `settings.html`, render All/Support as directly selectable quiet segments with `aria-current`, preserving `/settings#settings-audit` and `/settings?audit=support#settings-audit`.
4. Extend only the approved export regions: add an optional server-derived property-scope label to the CSV menu macro and display/populate it in the shared CSV dialog with `textContent`. Add host-workspace scoped dialog styles; preserve CSV's required native dates and current query scope, plus the inspection bundle's optional dates, property selection, endpoint, warning and limit.
5. In the shared confirm dialog, add localized default and archive labels. Use the Delete label only when the pending form action or button formaction path ends in `/archive`; restore the default proceed label for every other confirmation. Preserve native POST forms, bypass and submit behavior.
6. Add required-browser checks using synthetic records, the shared Chromium launch helper, and `UBYHOST_REQUIRE_BROWSER`. Check EN/CS at 360, 390 and 1280px, page/dialog overflow, settings selected states, visible applied property scope, required CSV date fields, optional inspection date fields, native inputs, aligned controls and action tracks. Open actual archive and non-archive confirmations in EN/CS. Capture settings and open-dialog screenshots.
7. Run `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_CONTROLS=1 .venv/bin/python -m pytest -q tests/test_host_controls_browser.py` from `App/` and record results in `0038-host-controls-report.md`.

## 5. Do not touch

Do not edit shared `App/app/static/host.css` or `App/app/host_i18n.py`. Shared `app.js` and `base.html` edits are limited to the CSV export and shared confirmation regions in §3. Do not edit `housebook.html` or change archive/unarchive route handlers, backend eligibility or legal-entity guards, permanent deletion, filing/reporting readiness, required-field validation, Undo/Restore, export endpoints/limits, or guest/public pages. Do not commit, push, create a worktree, PR, or deploy.

## 6. Commands

From `App/`, run:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_CONTROLS=1 .venv/bin/python -m pytest -q tests/test_host_controls_browser.py
```

Expected: the test executes with Chromium (no browser skip), passes, and reports one or more tests while capturing synthetic screenshots. Run `python3 scripts/context_lint.py` from the repository root as final documentation validation.

## 7. Acceptance

- [x] Actual signed-in host pages and open export dialogs have no horizontal overflow at 360, 390 or 1280px in EN and CS.
- [x] Empty onboarding dashboard actions fit the viewport; grouped actions remain visibly usable without hover and share the host action-height tracks.
- [x] Interactive rows/cards have quiet hover and keyboard focus context; controls have visible focus; static panels do not become pointer-clickable.
- [x] Stay guest-form copy buttons are labeled “Copy guest form link” / “Kopírovat odkaz na formulář hosta”; stay and guest soft-archive actions say Delete / Smazat and explain movement to Archived.
- [x] All/Support audit controls are directly selectable and expose the correct `aria-current` state while preserving their URLs.
- [x] CSV dialog shows the server-derived property scope and required native date bounds; inspection dialog shows current property/date scope and preserves optional native date semantics and its limits.
- [x] Actual `/archive` confirmations show localized Delete / Smazat while other confirmations retain the localized default proceed label.
- [x] Existing archive, restore and permanent-deletion flows retain their distinct behavior; archived filters are grouped accessibly.
- [x] Required-browser validation passes and screenshots cover both export dialogs and Settings at 360, 390 and 1280px with synthetic fixtures.

## 8. Stop and ask

Stop and report if a required-browser check fails twice, a required selector or token differs from the cited source, a needed file outside §3 must change, or any route/guard/validation behavior would need to change. Do not request deployment, commit, push or PR actions; hand those to the owner if later needed.

## 9. Report

Write `docs/tasks/0038-host-controls-report.md` (1,500 tokens at most), summarize changed files and commands with results, tick §7 only for demonstrated outcomes, record deviations and questions, and list owner steps left. Keep report status at review only after tested completion.
