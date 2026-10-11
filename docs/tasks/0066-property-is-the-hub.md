# 0066: No sub-bar: each property page is the only place for its settings

Status: todo
Depends on: none (if a 0064 automation-card PR exists, close it unmerged) | Branch: task/0066-property-is-the-hub
Executor: Cursor local agent | Fits one session

## 1. Objective
Remove the Properties / Business & legal details / Guest links / Automation & UbyPort / Digital door lock bar. Police timing, guest link and door lock are edited only on the property page. Old URLs redirect, so links in sent e-mails keep working. There are no duplicate forms left to maintain.

## 2. Context
- `App/app/templates/_host_navigation.html` lines 5–25: the bar for nav in apartments/entities/guest_links/automation/smart_locks.
- `App/app/templates/apartment_form.html` ~367–385: the `#automation` section shows a summary + "open" button linking to /automation. The property update handler in `routes/admin.py` (~1129) already saves `automation_mode`, `submit_after_hours`, `default_purpose` when posted. `#communication` = guest link section; `#door-code` links to /smart-locks (account connection; keep that page).
- `App/app/routes/admin.py`: GET /guest-links (~408), GET /automation (~1763), POST /automation/{id} (~1790), `_save_automation_form`, `_automation_payload`, the `form_source == "automation"` branch in `test_connection` (~1960).
- Other links: `reservation_detail.html` lines ~127 and ~414 (/guest-links); `mail_notify.py` ~1055; `routes/api.py` ~42–43 (search entries); `seo.py` ~37–39.
- 18 test files mention /automation or /guest-links (grep). Change only what this brief changes.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/templates/_host_navigation.html | edit | no local nav for that nav group |
| App/app/templates/apartment_form.html | edit | the #automation section becomes editable: mode select + hours (only for scheduled; reuse `data-automation-mode`) + default purpose; remove the links to /automation; the operator line gets "Business & legal details" → /entities |
| App/app/templates/settings.html | edit | one link "Business & legal details" → /entities |
| App/app/routes/admin.py | edit | GET /automation and GET /guest-links redirect (303): exactly one active property → `/apartments/{id}#automation` or `#communication`, otherwise `/apartments`; delete POST /automation/{id}, `_save_automation_form`, `_automation_payload` (if unused), the automation branch in test_connection |
| App/app/templates/automation.html, guest_links.html | delete | after moving anything unique (see §8.1) |
| App/app/templates/reservation_detail.html | edit | guest-link links → `/apartments/{{ reservation.apartment_id }}#communication` |
| App/app/routes/api.py | edit | the two search entries point to /apartments |
| tests that reference the removed pages | edit | assert the redirects instead |
| App/tests/test_property_hub.py | new | tests |

## 4. Steps
1. Before deleting guest_links.html, list every function it has (copy link, language variants, PIN rotation, preview, per-stay links) and confirm each exists in the property #communication section; move any that doesn't.
2. Make the property page timing editable; keep the help line "Automatic modes do not wait for ID verification…" from automation.html.
3. Redirects as in the table; keep `#anchor` targets matching the section ids.
4. Tests: the bar is absent on /apartments, /apartments/{id}, /entities and /smart-locks; GET /automation and /guest-links redirect correctly for 1 and 2 properties; saving the property page changes the mode/hours/purpose; the test-connection button on the property page still works; /entities is reachable from the property page and from /settings; no template references /automation or /guest-links except via the redirects.

## 5. Do not touch
UbyPort submission, door-code logic, /smart-locks behaviour, migrations.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Screenshots: /apartments without the bar; a property page with the editable timing and the guest-link section, at 360, 390 and 1280 px (demo data only).

## 8. Stop and ask
1. /guest-links has a function the property page can't host without a larger redesign.
2. Removing the bar breaks a geometry test baseline in a way that needs a new baseline image.

## 9. Report
Files, the list from step 1, test tail, screenshots.
