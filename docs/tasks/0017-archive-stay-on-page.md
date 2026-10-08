# 0017: Archive keeps you on the same page

Status: todo
Depends on: none | Base commit: current `main` | Branch: task/0017-archive-stay-on-page
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Archiving a stay or a property must leave the host on the page they pressed the button on. Today a stay archive redirects to `/reservations?range=archive`, and a property archive from the property form redirects to `/apartments`.

## 2. Context

Rule: "write 'no tracking cookies'", light mode, host UI geometry tests must pass with 0 skipped (AGENTS.md rules 6 and 7). No new dependency.

Archive buttons and where each lands today:

| Button | Template | Route | Lands today | Wanted |
|---|---|---|---|---|
| Stay, stays list | `reservations.html` ~187 | `reservation_archive` | `/reservations?range=archive` (BUG) | the list the host was on |
| Stay, dashboard | `dashboard.html` ~33 | same | same (BUG) | `/` |
| Stay, stay page menu | `reservation_detail.html` ~108 | same | same (BUG) | the stay page |
| Property, list | `apartments.html` ~52 | `archive_apartment` | `/apartments` (ok) | `/apartments` |
| Property, form | `apartment_form.html` ~385 | same | `/apartments` (BUG) | `/apartments/{id}` |
| Guest, house book / stay page | `housebook.html`, `reservation_detail.html` | `guest_archive` | return_to (ok) | no change |
| Business | `entities.html` ~114 | `archive_entity` | `/entities` (ok) | no change |

Anchor 1, `App/app/routes/admin.py` (stay archive; must be found verbatim):

```python
    form = await request.form()
    return_to = _form_return_to(form, _redirect_path_from_referer(request, "/reservations"))
    db.update("reservation", reservation_id, {"archived_at": db.utcnow(), "updated_at": db.utcnow()})
    db.audit("reservation_archived", f"id={reservation_id}")
    target = (
        f"/reservations?range=archive&undo_stay={reservation_id}"
        f"&undo_return={quote(return_to, safe='')}"
    )
    return _back(target, msg=_flash(request, "archive.stay_moved"))
```

`base.html` already shows an Undo toast when the URL has `undo_stay=<id>` and posts to `/reservations/<id>/unarchive` with `return_to` = `undo_return`. Keep that toast; only the destination changes.

Anchor 2, `App/app/routes/admin.py` (property archive):

```python
@router.post("/apartments/{apartment_id}/archive")
def archive_apartment(apartment_id: int, request: Request):
```
and its last line `return _back("/apartments", msg=_flash(request, "flash.apartments.archived", name=apartment["internal_name"]))`.

Anchor 3, `App/app/templates/apartment_form.html` ~385:

```html
          <button class="btn small" type="submit" formmethod="post"
                  formaction="/apartments/{{ apartment.id }}/archive"
                  data-confirm data-confirm-message="{{ t('confirm.archive_property') }}">{{ t('common.archive') }}</button>
```
This button sits inside the big property form. A submit button's `name` and `value` are posted only when it is the submitter, so `name="return_to" value="..."` on the button is safe.

Anchor 4, `App/app/templates/reservation_detail.html` ~111:

```html
            <input type="hidden" name="return_to" value="{{ return_to }}">
            <button class="row-menu-item" type="submit" role="menuitem">{{ t('stay.detail.menu.archive') }}</button>
```
Here `return_to` is the list the host came from (back link), not this page.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/admin.py` | edit | stay archive redirect; property archive reads `return_to`; one helper; import line |
| `App/app/templates/reservation_detail.html` | edit | archive form returns to the stay page |
| `App/app/templates/apartment_form.html` | edit | archive button posts `return_to` |
| `App/app/templates/apartments.html` | edit | archive form posts `return_to=/apartments` |
| `App/tests/test_archive_stays_on_page.py` | create | the new tests |
| `App/tests/test_destructive_confirm.py`, `App/tests/test_accounts.py` | edit only if an assertion on the old redirect fails | update the expected location |

No other file may change.

## 4. Steps

1. In `admin.py` line ~17 change `from urllib.parse import quote, urlencode, urlparse` to `from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlsplit, urlunsplit`. If `quote` is then unused, drop it.
2. Add below `_redirect_path_from_referer` in `admin.py`:

```python
def _with_undo(return_to: str, reservation_id: int) -> str:
    """return_to plus the query that makes base.html show the stay Undo toast."""
    parts = urlsplit(return_to)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in ("undo_stay", "undo_return", "msg", "err")
    ]
    clean = urlunsplit(("", "", parts.path, urlencode(query), ""))
    query += [("undo_stay", str(reservation_id)), ("undo_return", clean)]
    return urlunsplit(("", "", parts.path, urlencode(query), ""))
```
3. In `reservation_archive` replace the `target = (...)` block and the `return` with:

```python
    return _back(
        _with_undo(return_to, reservation_id),
        msg=_flash(request, "archive.stay_moved"),
    )
```
   Leave the already-archived early return above it as it is.
4. Make `archive_apartment` `async def`, read the form after the already-archived check, and redirect:

```python
    form = await request.form()
    return_to = _form_return_to(form, "/apartments")
    ...
    return _back(return_to, msg=_flash(request, "flash.apartments.archived", name=apartment["internal_name"]))
```
5. `reservation_detail.html`: change the hidden input to `value="/reservations/{{ reservation.id }}?return_to={{ return_to | urlencode }}"`.
6. `apartment_form.html`: add `name="return_to" value="/apartments/{{ apartment.id }}"` to the archive button (Anchor 3). Do not touch the Restore button.
7. `apartments.html`: inside the archive form add `<input type="hidden" name="return_to" value="/apartments">` before the button.
8. Create `App/tests/test_archive_stays_on_page.py`. Log in with `login_as` from `tests/conftest.py` (CSRF is added to test posts automatically by its session fixture). Seed a host, property and stay the way `tests/test_accounts.py` does (copy the pattern; do not import its private `_login`). Post with `follow_redirects=False`. Tests, each asserting status 303 and the `location` header:
   - stay archive with `return_to=/reservations?range=upcoming` lands on a location that starts with `/reservations?range=upcoming&undo_stay=<id>` and does not contain `range=archive`;
   - stay archive with `return_to=/` lands on a location starting with `/?undo_stay=<id>`;
   - stay archive with `return_to=/reservations/<id>?return_to=%2Freservations` lands on `/reservations/<id>?return_to=%2Freservations&undo_stay=...`;
   - `_with_undo("/reservations?undo_stay=9&undo_return=x&msg=old", 5)` contains exactly one `undo_stay=`, its value is `5`, and no `msg=old` (an old flash must not come back);
   - property archive with `return_to=/apartments/<id>` lands on `/apartments/<id>`; with no `return_to` lands on `/apartments`;
   - an evil `return_to=https://evil.example/` lands on the default.

## 5. Do not touch

`guest_archive`, `archive_entity`, every `unarchive` route, `settings_archived.html`, `base.html`, migrations, i18n files. UbyPort code.

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_archive_stays_on_page.py tests/test_destructive_confirm.py tests/test_accounts.py -q` → all pass.
- `.venv/bin/python -m pytest tests -q` → 0 failed, 0 skipped in the browser and geometry tests.

From the repo root: `python3 scripts/context_lint.py` → clean.

## 7. Acceptance

- [ ] Archive a stay from the stays list, the dashboard and the stay page: the URL path does not change and the Undo toast shows. Screenshots at 360, 390 and 1280 px of the stay page after archiving.
- [ ] Undo restores the stay and returns to the same page.
- [ ] Archive a property from the property form: you stay on `/apartments/{id}` and the Restore button shows.
- [ ] `grep -n "range=archive" App/app/routes/admin.py` finds nothing in the archive routes.
- [ ] Full test suite green.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found, a test fails twice, a file outside §3 needs a change, or you need push, merge or deploy (hand those to the owner).

## 9. Report

Write `docs/tasks/0017-report.md` (1,500 tokens at most) per the template and set `Status: review`.

## Risk list (for the reviewer)

`App/app/routes/admin.py` (the `_with_undo` helper and both routes): open-redirect safety rests on `_form_return_to` → `security.safe_local_path`; confirm nothing bypasses it.

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh <pr>` when CI is green.
2. Deploy when you want it live.
