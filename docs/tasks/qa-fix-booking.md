# qa-fix-booking: booking flow QA fixes (P1 and P2 subset)

Status: ready | Base: main @ pull | Branch: task/qa-fix-booking
Executor: Haiku 5.5 | Source: QA findings booking-flow-v2 (01, 02, 03) plus the 404 pages
Follow AGENTS.md and docs/context/executor.md. No new dependency, no migration, no deploy.

## 1. Objective
1. A guest name over 120 characters is refused with a friendly message; the host booking list wraps long text (no horizontal scroll). [finding 01]
2. A failed checkout (bad name, bad e-mail, terms not ticked, name too long) keeps the typed name and e-mail. [finding 02]
3. The booking site cannot be published without at least one photo and a description; the message says what to add. [finding 03]
4. 404 on `/p/...` and `/pay/...` is a proper HTML page with a Content-Type, not a blank body. [owner request]

Verified in code: all four are real. Finding 01: `maxlength=120` exists only in the HTML (property_page.html:126, property_page_book.html:21); `property_page_checkout` only checks `len(name) < 3`. Finding 02: `_book_error` redirects and the form has no `value=`. Finding 03: `booking_setup.can_publish` ignores the `page` step. 404s: `Response(status_code=404)` has an empty body, while `http_error_handler` in `app/main.py` already renders `error.html` for an `HTTPException` when the client sends `Accept: text/html`.
Dropped as false alarm: `/signup` 404 (staging mode). Finding 12 (port 8080) is likely the QA environment.

## 3. Files (touch only these)
`App/app/routes/property_page.py`, `App/app/routes/payments.py`, `App/app/booking_setup.py`, `App/app/host_i18n.py`, `App/app/templates/property_page.html`, `App/app/templates/property_page_book.html`, `App/app/static/app2.css`, tests named below, `docs/tasks/qa-fix-booking-report.md`.

## 4. Steps (commit after each: `qa-fix-booking step k`)

### Step 1: name length (server)
In `property_page.py`:
- Add `"name_too_long"` to the `BOOK_ERRORS` tuple.
- In `property_page_checkout`, directly after the `len(name) < 3` check add:
  `if len(name) > 120: return _book_error(slug, "name_too_long", lang, form)`
In `host_i18n.py` add next to `pp.book.err.bad_name` (en block, about line 1748 and cs block, about line 3882):
- en `"pp.book.err.name_too_long": "That name is too long. Use at most 120 characters."`
- cs `"pp.book.err.name_too_long": "Jméno je příliš dlouhé. Použijte nejvýše 120 znaků."` (write it with the same escape style the neighbouring cs lines use)
Do not add any other message field; checkout has none.

### Step 2: keep typed name and e-mail (no personal data in URLs)
Do NOT put name or e-mail in the redirect query (URLs reach access logs). Re-render instead, only for the four field errors.
In `property_page.py`:
- Move the body of `property_page_view` from `page = _page_context(apartment_id)` to the final `return render(...)` into a new helper `_render_page(request, slug, apartment_id, params, book_error="", values=None)`. `params` replaces `request.query_params` inside the helper (use `params.get(...)`); `page["book_error"]` is `book_error or params.get("book", "")` still checked against `BOOK_ERRORS`; add `page["form_values"] = values or {}`; `lang` stays `_page_lang(request)` except when `params` has `lang` in cs/en, then use that. `property_page_view` calls the helper with `request.query_params` and keeps its rate limit, resolve and redirect code unchanged (`_page_context(...) is None` still gives 404).
- In `property_page_checkout`, for the errors `bad_name`, `name_too_long`, `bad_email`, `terms` (the two checks plus the terms-version check stays a redirect), return
  `_render_page(request, slug, apartment_id, {"date_from": ..., "date_to": ..., "guests": ..., "lang": lang}, book_error=<kind>, values={"name": name[:120], "email": email[:254]})` using the form's date_from/date_to/guests values (each `str(form.get(x) or "")[:10]`). Add `response.headers["Cache-Control"] = "no-store"` and `X-Robots-Tag: noindex` on that response. Never prefill the terms box.
- Other errors keep using `_book_error` unchanged.
In both templates add `value="{{ page.form_values.name if page.form_values else '' }}"` to the `guest_name` input and the e-mail equivalent to `guest_email` (property_page_book.html has no `page.form_values`; leave that file untouched except nothing, it is the quote page: skip it entirely, only `property_page.html` changes; keep `maxlength=120` as is). Jinja autoescapes; do not use `|safe`.

### Step 3: publish needs photos and description
In `booking_setup.py` change `can_publish` to `return bool(done["pay"] and done["price"] and done["page"])` and fix the docstring ("... and photos plus a description").
In `payments.py` `booking_site_save` (about line 602): when publish is requested and `can_publish` is false, pick the message: if the `page` step is not done, `err=_flash(request, "bsite.err.publish_need_page")`, else the existing `publish_not_ready`. Use `{r["key"]: r["done"] for r in rows}`.
In `host_i18n.py` next to `bsite.err.publish_not_ready` (about lines 1647 and 3781):
- en `"bsite.err.publish_need_page": "Add at least one photo and a description before you publish."`
- cs `"bsite.err.publish_need_page": "Před zveřejněním přidejte alespoň jednu fotku a popis."` (escape style as neighbours)
Check the setup template (`booking_site_setup.html`) for a publish button guarded by `can_publish`; if it is disabled there, nothing else to do. Existing tests that publish with no photos will now fail: fix each once by giving the fixture a photo and description (grep `publish` in `tests/test_booking_site*.py`); that is the only allowed test repair.

### Step 4: host list wraps long text
In `app2.css` append one rule after the line containing `body.v2 dl.ui-facts>div>dt{min-width` (about 2324):
`body.v2 .bsite-bookings dt,body.v2 .bsite-bookings dd{min-width:0;overflow-wrap:anywhere}`
and `body.v2 .bsite-bookings>div{max-width:100%}`. Bump the CSS cache key the way `test_static_versions.py` expects (read that test's failure if it fails; fix once).

### Step 5: 404 as HTML
In `property_page.py` (all `Response(status_code=404)` in the file) and in `payments.py` only inside the two `/pay/{request_id:int}/{token}` handlers (about lines 754-790) replace `return Response(status_code=404)` by `raise HTTPException(status_code=404)` (import `from fastapi import HTTPException` if absent). Do not touch other routes in payments.py. Do not change `main.py`: its handler already renders `error.html` with the right Content-Type for browsers (`Accept: text/html`); scripts get the JSON 404 body. Grep the tests for `status_code == 404` plus `content == b""` and fix only assertions that break.

### Step 6: tests (add to existing files)
- `tests/test_booking_site_page.py`: (a) POST `/p/SLUG/checkout` with a 121-char name: 303 with `book=name_too_long`; 120 chars passes the name check. (b) bad e-mail: response 200, body contains the typed name, and the Location/URL has no e-mail; terms unticked also keeps both values; HTML-escape check with name `"><b>x` shows `&gt;`. Copy the setup helper used by the neighbouring checkout tests.
- `tests/test_booking_site_host.py`: publish without photos gets the `publish_need_page` text flashed and the page stays unpublished; with photo and description it publishes.
- `tests/test_property_page.py`: `GET /p/nope` with header `Accept: text/html` gives 404, `text/html` content type and non-empty body; same for `/pay/999/xxxx`.
- Optional if a host browser test exists (`test_booking_site_host_browser.py`): a booking with a 300-char unbroken name at 390 px has `document.documentElement.scrollWidth <= 390`.

## 6. Commands (from `App/`, each ends `-q --tb=short -x 2>&1 | tail -30`)
Test-map rows: Booking site, Public property pages, Host pages, Static files.
1. `.venv/bin/python -m pytest tests/test_booking_site.py tests/test_booking_site_page.py tests/test_booking_site_host.py tests/test_property_page.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_copy_cleanup.py tests/test_no_em_dashes.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -30`
3. Browser, 0 skipped (`-rs`): `tests/test_booking_site_page_browser.py tests/test_booking_site_host_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py`
4. Repo root: `python3 scripts/context_lint.py | tail -30`

## 7. Acceptance
- [ ] Commands 1 to 4 green, browser tests 0 skipped
- [ ] One 390 px screenshot each: `/apartments/<id>/booking-site` with a 300-char name in the list (no horizontal scroll); `/p/<slug>` after a failed checkout with name and e-mail kept (error beside the form)
- [ ] No em dashes in new copy; cs and en keys both added
- [ ] No name or e-mail in any URL (grep the diff for `urlencode` additions)
- [ ] Per host page UX gate: PR text states per page what the 390/768/1280 screenshots show; design-system checklist ticked
- [ ] One PR, no push to main

## 8. Stop and ask
Step 2 helper extraction changes behaviour of existing `/p/SLUG` tests you cannot fix once; `HTTPException` 404 breaks a test you cannot fix by editing the assertion; any anchor not found.

## 9. Deferred (not in this brief)
- 04 empty "Show price" message and button state; 05 localised dates and money on booking page; 06 booking horizon and year in summary; 07 buttons on request states; 08 "Declined" label, "Mark paid and confirm", list date and money formats; 09 tap targets on legal pages; 10 lang=cs after /book error (note: `property_page_book` hard-codes `lang: "en"`); 11 host modals in guest template; 12 port 8080 and small rails controls.
Owner steps after merge: deploy by hand.
