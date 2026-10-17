# 0065: Review fixes for 0061, 0055, 0048

Status: todo
Depends on: none | Branch: task/0065-review-fixes
Executor: Cursor local agent | Fits one session

## 1. Objective
Three bugs found in review: a fill button can issue an invoice; ARES failures are cached for 24 h; the platform logos use the uncropped owner files.

## 2. Context
- `App/app/routes/invoices.py` `invoice_issue` (POST /invoices) ~line 674: the `fill_from_guest` branch returns only when a guest exists. With no complete guest it falls through to `invoices.issue`. The buttons in `invoice_form.html` (lines ~57, ~89) post to /invoices.
- `App/app/ares.py` `lookup`: `_CACHE[text] = (now, data)` runs for timeouts, 5xx and bad JSON too. The cache is unbounded.
- `App/app/templating.py` ~214–230: the logo map points to `airbnb-icon.svg`, `booking-icon.svg`, `logo-echalupy-cz-2.svg`, `Vrbo.svg`, `Trip.com_logo.svg.webp`. The approved cropped icons are in `docs/plans/new_plan/platforms/` (airbnb.svg, booking.svg, echalupy.svg).

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/routes/invoices.py | edit | the fill buttons never issue |
| App/app/ares.py | edit | cache only success and 404; cap the size |
| App/app/templating.py | edit | logo map: airbnb.svg, booking.svg, echalupy.svg only; vrbo and trip get no logo (text label) |
| App/app/static/platforms/ | edit | add the 3 cropped files from docs/plans/new_plan/platforms/; delete the 5 old files |
| App/tests/test_invoice_autofill.py, test_ares.py, test_source_badge.py | edit | tests below |
| App/app/host_i18n.py | edit | EN + CS `invoice.fill_guest.none` ("No checked-in guest on this stay yet." / "U tohoto pobytu zatím není vyplněný host.") |

## 4. Steps
1. invoices.py: replace the fill_from_guest branch with:
   guest = _lead_guest(stay["reservation"]); state = _form_state(request, form, entity)
   if guest: _merge_guest_fill(state, guest)
   context = _form_context(request, entities, entity, values=state, stay=stay)
   if not guest: context["errors"] = [host_i18n.translate(_lang(request), "invoice.fill_guest.none")]
   return render(request, "invoice_form.html", context)
   Also add, before `_draft(...)`: if any posted key starts with "fill_", re-render without issuing (defence in depth).
2. ares.py: a 404 is cached as None; a successful mapped result with a name is cached; every other outcome returns None **without caching**. When `len(_CACHE) > 1000`, clear it before inserting.
3. templating.py and static: as in the table. Check that each SVG has no <script>, no on* attributes and no external href.
4. Tests: POST /invoices with fill_from_guest=1 on a stay with no complete guest → status 200, **0 invoice rows created**, error shown; a timeout followed by a success on the next call → the second call returns data; 404 cached; the vrbo and trip sources render text only; the e-chalupy badge points to echalupy.svg.

## 5. Do not touch
Invoice numbering or issue logic, other ARES behaviour, migrations.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] The no-guest fill test proves that no invoice is issued.
- [ ] Screenshots of the stays list with the Airbnb, Booking and e-chalupy badges at 360, 390 and 1280 px.

## 8. Stop and ask
1. Any other button on invoice_form.html posts to /invoices without being an intended issue action.

## 9. Report
Files, test tail, screenshots.
