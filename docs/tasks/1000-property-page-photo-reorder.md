# 1000: Property page, reorder photos (up / down)

Status: todo
Depends on: 0999 (both edit `property_page_review.html`, `host_i18n.py` and `routes/payments.py`; run after it) | Base commit: 47640cf3 | Branch: task/1000-property-page-photo-reorder
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The host can move each page photo up or down with two buttons; the first photo is the hero on the public page. The cap stays `MAX_PAGE_PHOTOS = 10`; reordering rewrites only the order in `photos_json`.

## 2. Context

Owner decision 2026-11-07. Rules: 6 (forms work without JavaScript), 7 and 10 (browser, geometry, screenshots, UX gate), 9 (the buttons carry an aria-label, no extra sentence). `App/app/routes/payments.py` has `router = APIRouter(dependencies=[Depends(security.protect_host_post)])`, so CSRF is enforced for every POST on it; mirror the existing delete form, which sends the same fields.

The public page already shows `page.photos[:5]` with `loop.first` as `pp-photo-main`, and `_og` uses `photos[0]`, so order in `photos_json` is the only thing to change.

Anchors (verbatim, else STOP):

`App/app/property_page.py`:
```python
def delete_photo(apartment_id: int, path: str) -> None:
```
`App/app/routes/payments.py`:
```python
@router.post("/apartments/{apartment_id}/page/photo-delete")
```
`App/app/templates/property_page_review.html`:
```html
      <form method="post" action="/apartments/{{ apartment.id }}/page/photo-delete" data-confirm data-confirm-message="{{ t('payments.page.photo_delete_confirm') }}" style="position:absolute;top:4px;right:4px;">
```
`App/app/host_i18n.py` (en and cs):
```python
        "payments.page.photo_delete": "Delete photo",
```
and its cs line `"payments.page.photo_delete": ...` (find with `grep -n 'payments.page.photo_delete"' App/app/host_i18n.py`; two hits).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/property_page.py` | edit | `move_photo()` |
| `App/app/routes/payments.py` | edit | POST `/apartments/{id}/page/photo-move` |
| `App/app/templates/property_page_review.html` | edit | up / down buttons, "main" marker |
| `App/app/host_i18n.py` | edit | 3 keys en + cs |
| `App/tests/test_property_page_photos.py` | edit | reorder tests |

No other file may change. No migration, no retention line, no new dependency.

## 4. Steps

From `App/`; commit after each step as `1000 step k`.

1. `App/app/property_page.py`: insert directly before `def delete_photo` (anchor):
```python
def move_photo(apartment_id: int, path: str, direction: str) -> None:
    """Swap one photo with its neighbour; rewrites the order only (0 = hero)."""
    page = _page_row(apartment_id)
    if page is None or direction not in ("up", "down"):
        return
    photos = _json.loads(page["photos_json"] or "[]")
    if path not in photos:
        return
    i = photos.index(path)
    j = i - 1 if direction == "up" else i + 1
    if j < 0 or j >= len(photos):
        return
    photos[i], photos[j] = photos[j], photos[i]
    db.execute(
        "UPDATE property_page SET photos_json = ?, updated_at = ? WHERE apartment_id = ?",
        (_json.dumps(photos, ensure_ascii=False), db.utcnow(), apartment_id),
    )


```
   (Only paths already in `photos_json` can move; no file is touched, the list length never changes, so the cap holds.)

2. `App/app/routes/payments.py`: insert before the photo-delete route (anchor):
```python
@router.post("/apartments/{apartment_id}/page/photo-move")
async def property_page_photo_move(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    apartment = db.query_one(
        "SELECT id FROM apartment WHERE id = ? AND owner_user_id = ?",
        (apartment_id, owner_id),
    )
    if apartment is None:
        return Response(status_code=404)
    form = await request.form()
    from .. import property_page as pp

    pp.move_photo(apartment_id, str(form.get("path") or ""), str(form.get("dir") or ""))
    return _back(f"/apartments/{apartment_id}/page")


```
   Command: `.venv/bin/python -m pytest tests/test_property_page_photos.py -q --tb=short -x 2>&1 | tail -30`.

3. `App/app/templates/property_page_review.html`: inside the per-photo `<div style="position:relative">`, after the delete `</form>` and before that div's `</div>`, insert (no-JS forms, mirrored fields, native buttons):
```html
      <div style="display:flex;gap:4px;margin-top:4px;align-items:center;">
        {% if loop.first %}<span class="ui-sub">{{ t('payments.page.photo_main') }}</span>{% endif %}
        {% for d, glyph, key in (('up', '↑', 'payments.page.photo_up'), ('down', '↓', 'payments.page.photo_down')) %}
        <form method="post" action="/apartments/{{ apartment.id }}/page/photo-move">
          <input type="hidden" name="path" value="{{ p }}">
          <input type="hidden" name="dir" value="{{ d }}">
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit" aria-label="{{ t(key) }}"{% if (d == 'up' and loop.first) or (d == 'down' and loop.last) %} disabled{% endif %}>{{ glyph }}</button>
        </form>
        {% endfor %}
      </div>
```
   Careful: the inner `for` shadows `loop`. Before the inner loop add `{% set first = loop.first %}{% set last = loop.last %}` right after the outer `<div style="position:relative">` line... Jinja `set` inside a for is scoped to the iteration, which is fine here. Use `first`/`last` in the two `disabled` conditions and the "main" marker instead of `loop.first`/`loop.last`. If the template does not render, STOP.

4. `App/app/host_i18n.py`: after each `"payments.page.photo_delete": ...` line add: en `"payments.page.photo_up": "Move photo earlier",` `"payments.page.photo_down": "Move photo later",` `"payments.page.photo_main": "Main photo",`; cs `"payments.page.photo_up": "Posunout fotku dříve",` `"payments.page.photo_down": "Posunout fotku později",` `"payments.page.photo_main": "Hlavní fotka",`. Command: `.venv/bin/python -m pytest tests/test_flash_literals.py tests/test_i18n*.py -q --tb=short -x 2>&1 | tail -30`.

5. `App/tests/test_property_page_photos.py`: append tests using the existing `owner` fixture, writing `photos_json` directly with `db.execute("UPDATE property_page SET photos_json = ? WHERE apartment_id = ?", (json.dumps(["/photos/property/a.jpg","/photos/property/b.jpg","/photos/property/c.jpg"]), owner))`:
   - `test_move_photo_down_and_up`: `move_photo(owner, b, "up")` gives `[b, a, c]`; then `move_photo(owner, b, "down")` gives `[a, b, c]`.
   - `test_move_photo_edges_and_unknown_are_noops`: first "up", last "down", an unknown path and a bad direction leave the list unchanged and the length is 3.
   - `test_move_keeps_the_cap_and_the_files`: with 10 entries, after a move the length is still `<= property_page.MAX_PAGE_PHOTOS`; no file is created or deleted (assert `photos_dir()` listing is unchanged).
   Command: `.venv/bin/python -m pytest tests/test_property_page_photos.py -q --tb=short -x 2>&1 | tail -30`.

## 5. Do not touch

`store_photo`, `download_listing_photos`, `delete_photo`, `MAX_PAGE_PHOTOS`, `property_page.html` (the public page already honours the order), any CSS file, `tests/layout_lint.js`. Hard rules 3, 6, 7, 9, 10; no JavaScript added.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

- `.venv/bin/python -m pytest tests/test_property_slug.py tests/test_property_page.py tests/test_property_page_photos.py tests/test_property_page_meta.py tests/test_property_page_rules.py -q --tb=short -x`
- Browser, geometry, 0 skipped (`-rs`, `UBYHOST_REQUIRE_BROWSER=1`): `tests/test_property_page_buttons_browser.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py`
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` (0 skipped, zero host findings; the photo row must not overflow at 390 px with 10 photos).
- Repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] Up on the first photo and down on the last are disabled; the first photo shows "Main photo".
- [ ] Posting `photo-move` changes only the order in `photos_json`; the cap and the files are unchanged.
- [ ] The public page shows the new first photo as the hero (the `og:image` follows it).
- [ ] Section 6 tests green, browser files with 0 skipped.
- [ ] One 390 px screenshot of `/apartments/<id>/page` with several photos; 768 and 1280 read for the UX gate; the PR body has "390: ...; 768: ...; 1280: ..." and the ticked design-system checklist.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; 25 tool calls or about 50k tokens; the Jinja loop scoping in step 3 does not render; a layout finding appears that needs CSS (CSS is outside this brief: report it); a file outside section 3 needs a change; push, merge, secrets, SSH or deploy is needed.

## 9. Report

`docs/tasks/1000-report.md` (600 tokens at most): files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left. Set `Status: review`.

## Risk list (for the reviewer)

`App/app/templates/property_page_review.html` (layout at 390 px), `move_photo` (only reorders).

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh <PR number>` once CI is green.
2. Deploy as usual. No migration, no secret.
3. Open `/apartments/<id>/page`, move a photo up, and check it becomes the first picture on the public page.
