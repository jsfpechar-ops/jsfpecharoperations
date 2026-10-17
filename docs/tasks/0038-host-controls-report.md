# 0038 report: Host interaction and control polish

**Status:** review

0038 now covers consistent host hover/focus and action geometry, the Settings audit scope controls, CSV/PDF export dialogs, copy labels, and soft-archive confirmation copy. All changes are UI-only. Existing routes, query limits, required/optional date semantics, restore behavior and backend guards remain in place.

Scoped files changed: `App/app/static/host-controls.css`; `App/app/static/app.js` (CSV scope population and exact `/archive` confirmation label selection only); `App/app/templates/base.html` (CSV property summary and confirm labels only); `App/app/templates/_components.html` (optional server-derived CSV scope labels only); `App/app/templates/reservation_detail.html`; `App/app/templates/settings.html`; `App/app/templates/settings_archived.html`; `App/tests/test_host_controls_browser.py`; this brief and report. `housebook.html` remained under Filters ownership; its existing call site now passes the applied property label.

## Validation

- `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_CONTROLS=1 .venv/bin/python -m pytest -q tests/test_host_controls_browser.py` from `App/`: **1 passed, 1 warning in 18.59s**. Chromium ran with no browser skip using synthetic fixtures. Coverage includes 13 host pages at 360, 390 and 1280px in EN/CS; empty onboarding at 360px; 42px/44px action geometry; hover, keyboard focus, touch-visible actions; Settings' All/Support `aria-current` and preserved URLs; actual CSV and inspection dialogs at all three widths/languages; applied and All-property summaries; required native CSV dates; optional native inspection dates; selected property, 100-form warning; dialog bounds, aligned buttons and no overflow; and actual archive versus non-archive confirmation labels in EN/CS. The CSV submit was intercepted to assert the original `/reservations.csv?from=…&to=…&apartment=…` URL without downloading/exporting data.
- `python3 scripts/context_lint.py` from repository root: **context lint: OK**. It reports the existing warning that 10 App commits postdate the last `docs/context/status.md` update.

Earlier in this task, the required Chromium run exposed an intermediate 360px stay-fees filter overflow to x430; subsequent complete runs passed after shared CSS was updated. The original 360px onboarding overflow and all sampled export/settings layouts also pass.

## Screenshots

44 PNGs use synthetic fixtures under `/workspace/generated_images/host-design-application/controls/`. The set includes the empty onboarding page, dashboard, stay detail, Properties, Archived, Settings audit scopes, and open CSV/inspection dialogs in EN/CS. Examples: [CSV export at 360px, EN](/workspace/generated_images/host-design-application/controls/csv-export-360-en.png), [inspection export at 1280px, CS](/workspace/generated_images/host-design-application/controls/inspection-export-1280-cs.png), and [Settings audit at 360px, CS](/workspace/generated_images/host-design-application/controls/settings-audit-360-cs.png).

## Acceptance and owner steps

All §7 items are verified. Review the scoped CSS, selectors, scope-label wiring and confirmation-label behavior; the checked feature commit can then be deployed to staging without a production merge. This executor performed no commit, push, deployment or data export.

## Deviations and questions

None. Inspection date bounds remain optional to match the actual ZIP endpoint contract. CSV From/Until remain required. Only forms or buttons whose submitted action path ends exactly in `/archive` display Delete / Smazat; other confirmations retain Confirm / Potvrdit.
