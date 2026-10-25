# 0403: import a Booking and an Airbnb link together, and put the import first

Status: review
Depends on: main (0347, 0348, 0396 merged) | Branch: claude/0403-leon-setup-wizard (checked out; commit here)
Executor: Haiku 5.5 | Reviewer: Opus | Fits one session: 30 tool calls, 80k tokens
Followed by: 0404 (Leon setup wizard), 0405 (try Leon). Same branch, one PR.

## 1. Objective

Owner (Josef, 2026-10-25): the "Import from Booking or Airbnb" box sits low on the Guest guide tab. He wants it **first**, and wants hosts to paste **both** their Booking.com and Airbnb links in one go so the drafts get the best of both listings. One link is enough.

1. `guest_guide_import.request_imports(apartment_id, raw_urls)` queues one row per link (at most one Booking and one Airbnb) in a single request. All checks happen before any row is written.
2. The import form has two optional fields, "Booking.com link" and "Airbnb link". A field is shown only while that platform has not been imported for this property. At least one must be filled.
3. On the Guest guide tab the import section moves to the top (right after the banners) while it still has work to offer: imports on and (imports left, or an import running, or drafts waiting). Otherwise it stays at the bottom, as today.
4. The merge prompt (rule 6) keeps details from both listings instead of keeping only the earlier text.

Caps stay as they are: one import per platform per property for good (failed runs do not count), and `UBYHOST_APIFY_MONTHLY_RUNS` counts each actor run (two links = two runs). A two-link request needs room for both runs, else it is refused with the budget message.

## 2. Context (read only these)

- `App/app/guest_guide_import.py`: `normalise_url`, `used_sources`, `imports_left`, `global_budget_left`, `runs_this_month`, `request_import` (~140-160).
- `App/app/guest_guide_merge.py`: `SYSTEM_RULES` rule 6 (~85).
- `App/app/routes/guest_guide.py`: `guide_index` (context `import_on`, `import_left`, `import_busy`, `imports`, `import_drafts`), POST `guide_import` (~205-218).
- `App/app/templates/guest_guide.html`: the `ui_section(t('guest_guide.import.title'), id='import')` block (~50-75).
- Copy: `App/app/host_i18n.py` en `guest_guide.import.*` (~8562) and cs (~8625). Vietnamese has no import keys (falls back to en); do not add vi.
- Tests: `App/tests/test_guest_guide_import.py` (`_post` helper posts the field `url`; tests near line 87-140), `App/tests/test_guest_guide_merge.py` (grep `rule 6` or `earlier_drafts`).
- Macros: `ui_field`, `ui_section`, `ui_button` in `App/app/templates/_ui.html`. **Exactly one primary button per page**: the import button stays `secondary`.

## 3. Files

| Path | Action |
|---|---|
| App/app/guest_guide_import.py | `request_imports`; `request_import` calls it |
| App/app/routes/guest_guide.py | POST import reads `booking_url`, `airbnb_url` (and legacy `url`); `next` target; guide context `import_sources_left`, `import_first` |
| App/app/templates/guest_guide.html | import section as a macro, rendered first or last; two fields |
| App/app/guest_guide_merge.py | rule 6 wording |
| App/app/host_i18n.py | copy (en, cs) |
| App/tests/test_guest_guide_import.py | new tests |
| App/tests/test_guest_guide_merge.py | rule 6 assertion if one exists |

## 4. Steps

1. `guest_guide_import.py`, replace `request_import` with:
   ```python
   def request_imports(apartment_id: int, raw_urls: List[str]) -> List[int]:
       """Queue one import per pasted link (0403: a Booking and an Airbnb link may come together).

       Every check runs before any row is written, so a refusal queues nothing.
       """
       if not enabled():
           raise GuideImportError("flash.error.guide_import_off")
       raws = [r for r in (raw_urls or []) if str(r or "").strip()]
       if not raws:
           raise GuideImportError("flash.error.guide_import_empty")
       links = [normalise_url(r) for r in raws]
       sources = [link["source"] for link in links]
       if len(set(sources)) != len(sources):
           raise GuideImportError("flash.error.guide_import_same")
       if db.query_one(
           "SELECT id FROM guide_import WHERE apartment_id = ? AND status IN ('queued', 'running')",
           (apartment_id,),
       ):
           raise GuideImportError("flash.error.guide_import_busy")
       if set(sources) & used_sources(apartment_id):
           raise GuideImportError("flash.error.guide_import_limit")
       limit = config.APIFY_MONTHLY_RUNS
       if limit > 0 and runs_this_month() + len(links) > limit:
           raise GuideImportError("flash.error.guide_import_budget")
       now = db.utcnow()
       return [int(db.insert("guide_import", {
           "apartment_id": apartment_id, "source": link["source"], "url": link["url"],
           "status": "queued", "created_at": now,
       }) or 0) for link in links]


   def request_import(apartment_id: int, raw_url: str) -> int:
       """Queue one import for a property the caller has checked; returns the row id."""
       return request_imports(apartment_id, [raw_url])[0]
   ```
   Also add, below `imports_left`:
   ```python
   def sources_left(apartment_id: int) -> List[str]:
       """0403: the platforms this property may still import, in form order."""
       used = used_sources(apartment_id)
       return [s for s in ("booking", "airbnb") if s not in used]
   ```
   The worker already runs up to 3 queued rows per minute and `guest_guide_merge.process_pending` merges oldest first, passing the first listing's drafts as `earlier` to the second. Do not change the worker.
2. `routes/guest_guide.py` POST `guide_import`:
   ```python
   form = await request.form()
   cap = guest_guide_import.MAX_URL_LENGTH
   urls = [str(form.get(name, ""))[:cap] for name in ("booking_url", "airbnb_url", "url")]
   target = f"/apartments/{apartment_id}/leon/setup/import" if form.get("next") == "leon" else f"{_base(apartment_id)}#import"
   try:
       guest_guide_import.request_imports(apartment_id, urls)
   except guest_guide_import.GuideImportError as exc:
       return back(target, err=flash(request, exc.key))
   return back(target, msg=flash(request, "flash.guest_guide.import_queued"))
   ```
   (`next=leon` is used by brief 0404; the target is fixed, never taken from the form.) In `guide_index` add `import_sources=guest_guide_import.sources_left(apartment_id)` and
   `import_first=guest_guide_import.enabled() and (guest_guide_import.imports_left(apartment_id) > 0 or guest_guide_import.in_progress(apartment_id) or guest_guide_merge.drafted_count(apartment_id) > 0)` (compute the three values once into locals and reuse them for `import_left`, `import_busy`, `import_drafts`).
3. `guest_guide.html`: move the whole import `{% call ui_section(... id='import') %} ... {% endcall %}` into `{% macro import_section() %} ... {% endmacro %}` defined at the top of `{% block body %}` (macros see the template context: `t`, `csrf_token`, `base_url`, the import values). Render `{{ import_section() }}` right after the `usage` paragraph when `import_first`, and at its old place (after the Leon section) when not. Inside, replace the single `ui_field('guide-import-url', ...)` with:
   ```jinja
   {% if 'booking' in import_sources %}{{ ui_field('guide-import-booking', t('guest_guide.import.booking_url'), name='booking_url', type='url', placeholder='https://www.booking.com/hotel/cz/...', attrs='maxlength="2048" inputmode="url" autocomplete="off"') }}{% endif %}
   {% if 'airbnb' in import_sources %}{{ ui_field('guide-import-airbnb', t('guest_guide.import.airbnb_url'), name='airbnb_url', type='url', placeholder='https://www.airbnb.com/rooms/...', attrs='maxlength="2048" inputmode="url" autocomplete="off"') }}{% endif %}
   ```
   No `required` (one of the two is enough; the server says so when both are empty). Keep the button, the running banner, the drafted line and the history table unchanged.
4. `guest_guide_merge.py` rule 6, replace its first two sentences with: `An earlier draft from the other platform may arrive inside <earlier_drafts> tags. Combine both: keep everything the earlier draft says and add any step, place or detail this listing has that the earlier draft lacks, so the card holds the best of both.` Keep the rest of rule 6 (the disagreement handling) word for word. Do not change any other rule.
5. Copy (en / cs) in `host_i18n.py`, next to the existing `guest_guide.import.*` keys:

   | key | en | cs |
   |---|---|---|
   | `guest_guide.import.help` (replace) | Paste the public links of your own listings. Add both if you have them: we combine Booking.com and Airbnb into one set of draft cards for you to check. One link is enough. | Vložte veřejné odkazy na své vlastní nabídky. Máte-li obě, vložte obě: z Booking.com i Airbnb připravíme jednu sadu návrhů karet ke kontrole. Stačí i jeden odkaz. |
   | `guest_guide.import.booking_url` | Booking.com link | Odkaz na Booking.com |
   | `guest_guide.import.airbnb_url` | Airbnb link | Odkaz na Airbnb |
   | `flash.error.guide_import_empty` | Paste at least one link: your Booking.com or your Airbnb listing. | Vložte aspoň jeden odkaz: na svou nabídku na Booking.com nebo na Airbnb. |
   | `flash.error.guide_import_same` | Paste one Booking.com link and one Airbnb link, not two from the same site. | Vložte jeden odkaz na Booking.com a jeden na Airbnb, ne dva ze stejného webu. |

   Keep `guest_guide.import.url` (other pages may still use it; grep before removing, remove only if unused).
6. Tests in `test_guest_guide_import.py` (reuse the `ws` fixture, `BOOKING`, `AIRBNB`; add a `_post2(ws, booking="", airbnb="")` helper posting `booking_url` / `airbnb_url` with the CSRF token the same way `_post` does):
   - both links in one post -> two `queued` rows (booking and airbnb), `imports_left == 0`, redirect has `msg=`.
   - both fields empty -> `err=`, no row.
   - two Airbnb links (one in each field) -> `err=` containing "not two from the same site", no row.
   - one platform already used + both links -> `err=` (limit), no new row.
   - `APIFY_MONTHLY_RUNS = 1` with 0 runs used and two links -> budget error, no row; one link -> queued.
   - guide page: with nothing imported both `name="booking_url"` and `name="airbnb_url"` are present and the `id="import"` section comes before `id="topic-` (compare `page.index`); after both are `used` and no drafts waiting, `name="booking_url"` is absent and `id="import"` comes after the last `id="topic-`.
   - `next=leon` post redirects to `/apartments/<id>/leon/setup/import` (only the path start; 0404 adds the page).
   - Update the existing tests that assumed the old single field: `test_one_import_per_listing_for_good` asserts `'name="url"' not in page` (now `name="booking_url"` / `name="airbnb_url"` absent), `test_off_without_a_token` the same.
   - `test_only_one_import_runs_at_a_time` stays valid (second post while one is queued is refused).
7. `test_guest_guide_merge.py`: if a test asserts the old rule 6 sentence, update it to the new text. Add one assertion that `"Combine both" in guest_guide_merge.SYSTEM_RULES`.

## 5. Do not touch

`normalise_url` and its allowlist, the worker (`process_queue`, `_run_one`, `_fetch`), retention, `guest_guide_merge.verify` / `_write`, other templates.

## 6. Commands

From `App/`:
```
.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5
.venv/bin/python -m pytest tests/test_guest_guide_import.py tests/test_guest_guide_merge.py tests/test_guest_guide.py tests/test_guest_guide_pages.py tests/test_design_*.py -q --tb=short 2>&1 | tail -30
```
From the repo root: `python3 scripts/design_lint.py | tail -5`.

## 7. Acceptance

- [ ] One post with a Booking and an Airbnb link queues both; refusals queue nothing.
- [ ] Only the platforms not yet imported get a field; empty, duplicate, used and over-budget requests are refused with their own message.
- [ ] The import section is first on the Guest guide tab while it has work to offer, last otherwise.
- [ ] Merge rule 6 combines both listings; disagreement handling unchanged.
- [ ] §6 passes.

## 8. Stop and ask

If a design test counts the import button as a second primary, or the macro cannot see a context value.

## 9. Report

`docs/tasks/0403-report.md` (600 tokens at most). Commit `0403 step k` after each step. Do not push.
