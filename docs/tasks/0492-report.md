# 0492 report: Admin Today, System with Incidents, four tabs

Status: blocked
Branch: task/0492-admin-today-system (commit 34b1a488 on top of brief commit 6c39318f)

## Files changed
- App/app/templating.py: four admin tabs (today, customers, money, system) and path mapping.
- App/app/routes/admin_customers.py: admin_home passes `ops` and `review_alerts`.
- App/app/templates/admin_home.html: System problems section (only blocks with count > 0, linking to `#ops-<block>` or `#incidents`); "All clear" when nothing needs the owner; header buttons removed.
- App/app/templates/admin_operations.html: each health block is a `<details>` with its heading in `<summary>`, open only with problems; Incidents section (`id="incidents"`) at the end; workspace links point to `/admin/customers/<id>`.
- App/app/routes/admin_accounts.py: `/admin/operations` passes incident rows, review alerts and owners; `GET /admin/incidents` is a 303 to `/admin/operations#incidents`; incident POSTs redirect to `#incidents` via `_back_incidents`.
- App/app/templates/admin_incidents.html: deleted (markup moved).
- docs/design/catalog.json: template entry removed; `checkline` added to the operations template class map.
- App/app/auth.py (stop_impersonating redirect), App/app/templates/settings.html, App/app/routes/api.py (palette): `/admin/users` replaced by `/admin/customers`.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: admin.tab.today/money/system, admin.today.system, admin.today.clear (en, cs, vi).
- App/tests/test_design_admin.py: TEMPLATES list.
- App/tests/test_admin_section_tabs.py: four tabs; new tests for the clear state, a late job showing as a system problem, collapsed blocks, and the incidents redirect.
- App/tests/test_host_account_navigation.py: settings and palette links now expect `/admin/customers`.

## Tests
- Admin set (`test_admin_operations`, `test_admin_section_tabs`, `test_admin_customers`, `test_accounts`, `test_incident_register`, `test_host_account_navigation`, `test_umami_guard`, `test_design_admin`): 111 passed in the non-browser run, 0 failed after the fixes above. Last lines: `...... 111 passed` (browser test in that file failed only because the Chromium path was not set; it passes below).
- Browser set with `UBYHOST_BROWSER_EXECUTABLE` set (`test_host_account_navigation`, `test_design_guardrails_browser`, `test_design_shell_browser`, `test_havel_gap_list_browser`): `44 passed in 119.80s`, 0 skipped.
- `python3 scripts/design_lint.py`: OK.
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: All checks passed.
- Not run: `test_admin_customers` browser geometry for /admin (no separate browser file named in the brief for these pages beyond the set above).

## Diff stat (origin/main, App and docs/design)
15 files changed, 242 insertions(+), 160 deletions(-).

## Deviations
- Done: steps 1 to 7. Left: 390 px screenshots of `/admin` and `/admin/operations` (rule 7). Not taken because the executor tool-call cap was reached.
- Translation keys used only by the old incidents page header were left in place (no removal check was done within the cap).
- `App/app/routes/admin_accounts.py` impersonate redirect (about line 847) still points to `/admin/users`; the brief did not name it. It redirects through the 0490 route, so it works.
- Settings still links the incidents action to `/admin/incidents`, which now redirects to System. Works, not changed.
- Test run modified `docs/tasks/screenshots-0331/admin-havel-390.png`; restored with git checkout, not committed.

## Owner steps left
- None for merge. A fresh session should take the two 390 px screenshots and then set this brief to `review`.
