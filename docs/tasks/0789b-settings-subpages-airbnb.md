# 0789b: settings sub-page contents + companies, data requests, archive (part B of 0789)

Status: todo. Executor: Haiku 5.5, alone, branch `claude/project-thread-umes84`, after 0789a2. Look: brief 0789 §1 items 2-4; refs /mnt/project-files/settings-area/airbnb-ref/IMG_2200.png, IMG_2201.png (sub-page rows and toggles), IMG_2198-value-cards.png (value cards), IMG_2197-pill-tabs.png (pills). Same layout at 390, 768 and 1280 in the 720 lane.

## Steps

1. **Shared partials** in `App/app/templates/partials/`: `settings_toggle_row.html` (label left with help `?` 8 px after it, switch right), `settings_value_card.html` (small label, big bold value, optional chevron link), `settings_pills.html` (list of {label, href, current}). CSS in the 0789 block of `app2.css`.
2. **Toggles:** `#settings-onboarding-emails` and `#settings-stay-fee-emails` (and any other checkbox + Save forms on the sub-pages) become toggle rows: the checkbox styled as a 51x31 switch (ink when on), same form, same POST target, same `name`/`value`. Add `data-toggle-submit` to the checkbox. The Save button moves inside `<noscript>` so the form still works without JS. Authorised `app.js` change, this only: in `initAutoFilters` also bind `input[type=checkbox][data-toggle-submit]` inside any form (not only `form[data-auto-submit]`) to submit on change. Add a test that the form posts with JS off (button in noscript) and with JS on (change submits).
3. **Value cards:** read-only values become value cards: retention period, cutoff date, expired records (`#settings-retention`), 2FA state and passkey count on security, app version on technical. Keep the purge form and its button under the cards.
4. **Link rows:** a row whose action is "go somewhere" becomes a bordered card (1 px, radius 12, padding 20) with a chevron, label left.
5. **Pills:** `/settings/archived` type chips become `settings_pills.html` (44 px tall, grey fill, active black with white text, `aria-current="page"`, 12 px gap, horizontal scroll on phone, no wrap). Same for the support/all filter on the audit section (`?audit=support`).
6. **`/entities`, `/privacy-requests`, `/settings/archived`:** use `settings_back_header.html` (back to `/settings`, big h1); lists keep their data, as bordered cards; no descriptions (move to the help `?` or drop).
7. Rules from brief 0789 §1.4: no fine print, `?` small and inline after its label, >= 12 px between neighbours, nothing at a card edge.
8. Extend the 0789 test: the toggle switch is right-aligned in its row and vertically centred with the label within 1 px; value cards have a big value (font-size >= 20 px, bold); pill checks on /settings/archived. Run the brief 0789 §6 set plus `tests/test_0789_settings_subpages.py` and the entities/privacy-requests/archived tests (`grep -l "entities\|privacy-requests\|settings/archived" App/tests/*.py`), fix what this part broke.
9. Cache key bump (base.html, login.html if it loads app2.css/app.js), `tests/test_static_versions.py --write`. `python3 scripts/design_lint.py` and `context_lint.py` pass (add new classes to `docs/design/catalog.json`).
10. Screenshots at 390, 768 and 1280 of /settings, each /settings/<group>, /entities, /privacy-requests, /settings/archived, logged in with demo data, to `/mnt/project-files/settings-area/airbnb/<page>-<width>.png` (trailing slash on the folder path; never search the whole mount).

## Report

Append "Part B" to `docs/tasks/0789-report.md`: commits, test lines, screenshot list. Commit, do not push.
