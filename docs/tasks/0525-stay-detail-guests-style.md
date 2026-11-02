# 0525: Stay detail redesign, part 2: guests as table rows, styling, tests
Status: todo
Depends on: 0524 | Base commit: the 0524 branch head | Branch: task/0525-stay-detail-style
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Finish the stay page from brief 0524 per the approved computer mockup: on computer widths each guest reads as one table row (name, document type, registration state, menu) inside one white card; the door code card shows the code large. The phone layout is not redesigned yet (owner has not approved a phone version): below 1024 px the guest cards keep today's look.

## 2. Context
- Guest cards: `<ul class="guest-cards">` / `<li class="guest-card">` with `guest-card-head`, `guest-card-who`, `guest-card-state` in `App/app/templates/reservation_detail.html` (from about line 214). Keep the markup and every badge, error list and menu; add only the doc cell in step 1.
- Document type labels exist: `t('guest.doc_type.' ~ code)`. Never print the document number (privacy, public repo screenshots).
- CSS: `App/app/static/host2.css` (linked in `base.html` as `host2.css?v=...`). Find current guest card CSS with `grep -n 'guest-card' App/app/static/*.css`.
- New classes from 0524: `stay-door-card`, and `data-stay-header-copy`. Every new class must be in `docs/design/catalog.json` (`classes` list and description map), else `scripts/design_lint.py` fails CI.

## 3. Files
Edit `App/app/templates/reservation_detail.html` (step 1 only), `App/app/static/host2.css`, `App/app/templates/base.html` (the `?v=` key only), `App/tests/static_versions.json` (only via `--write`), `docs/design/catalog.json`. Create `App/tests/test_0525_stay_detail.py`. Existing tests only under section 8. Screenshots in `docs/tasks/screenshots-0525/`. Report `docs/tasks/0525-report.md`.

## 4. Steps
1. **Doc cell.** In `guest-card-head`, between `guest-card-who` and `guest-card-state`, add `<span class="guest-card-doc">{{ t('guest.doc_type.' ~ guest.doc_type) if guest.doc_type else '—' }}</span>`. In the placeholder card (the `stay.detail.guests.placeholder` `<h3>`), add the same span with `—` if its head has the same structure; otherwise skip it there and say so in the report. Commit `0525 step 1`.
2. **CSS**, inside `@media (min-width: 1024px)` in `host2.css`: `.guest-cards` becomes one white card (existing card radius, border and surface tokens) with no gap; each `.guest-card` loses its own border and radius, gets a bottom border except the last; `.guest-card-head` is a grid `minmax(0,2fr) minmax(0,1fr) auto auto` (who, doc, state, menu) with `align-items:center`; error lists and other card body content stay full width below the head. `.stay-door-card #door-code-line` 18 px, weight 700, card padding 16 px. Use only existing custom properties. Commit `0525 step 2`.
3. **Catalog.** Add `guest-card-doc`, `stay-door-card` and `data-stay-header-copy` (if the lint covers data attributes) with one-line descriptions. `python3 scripts/design_lint.py 2>&1 | tail -10` from the repo root until clean. Commit `0525 step 3`.
3b. **Owner ask 2026-11-01 13:39: resend in the header.** Move (do not copy) the whole `{% if claim_resend.enabled %}<form ... /resend-claim ...>...</form>{% endif %}` from the guests section's claim line into the `secondary_actions` block, after the copy button, keeping the form, its `data-resend-claim` attribute, title and text (`stay.claim.resend`, cs "Poslat odkaz znovu"); drop `ui-btn-compact` there. Also set the `.guest-card-head` grid in host2.css to 3 tracks `minmax(0,2fr) minmax(0,1fr) auto` (the menu sits inside `guest-card-state`). Commit `0525 step 3b`.
4. **Test** `test_0525_stay_detail.py` (copy fixtures and login from `tests/test_design_stay_detail.py`): (a) `<h1>` is the lead guest's "First Surname"; a stay with no guests shows the property name; (b) the sub line holds the reporting pill and a link to `/apartments/<id>`; (c) no `stay-jump` in the page; (d) with an issued door code, `id="door-code"` section holds `door-code-line` and the "Now" panel does not; (e) a guest with `doc_type` "P" (or the first code in the doc type list) shows its label in `guest-card-doc`, and the document number does not appear in the page; (f) header has `data-stay-header-copy` for an active stay and not for an archived one; (h) for a claimed stay with resend enabled, `data-resend-claim` appears once, inside the page header, not in `#guests`; (g) the Send button still renders for a ready stay (copy the setup from an existing send test if one exists in `test_design_stay_detail.py`). Commit `0525 step 4`.
5. Bump `host2.css?v=` in `base.html`, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Screenshots of a stay page with three guests, `?lang=cs`, at 1280 and 390 px into `docs/tasks/screenshots-0525/`. Commit `0525 step 5`.

## 5. Do not touch
Any JS file, other templates, routes, the "Now" panel logic, reports and settings sections, the phone layout below 1024 px. No new dependency, no migration.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0525_stay_detail.py tests/test_design_stay_detail.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`, then browser: `tests/test_host_stay_detail_layout_browser.py tests/test_host_stay_actions_browser.py tests/test_onboarding_followup_browser.py tests/test_host_wide_geometry_browser.py tests/test_0199_phone_geometry_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. Diff against the 0524 head lists only section 3 files plus section 8 test edits.

## 8. Stop and ask
Standing rule: a browser test that asserts the jump tabs, the property line, the property name as the `<h1>`, or the door code inside the "Now" panel may be updated to the new place. Keep every geometry rule as strict as before. List each edited assertion in the report. Stop if a geometry rule itself fails, or if any send, fix, receipt or filing assertion changes result.

## 9. Report
`docs/tasks/0525-report.md`: Status, test and lint tails, diff stat, screenshot paths, deviations.
