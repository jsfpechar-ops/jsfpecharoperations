# 1005: Photo reorder row without inline style, no-JS CSRF, booking sites on phone

Status: todo
Depends on: none (PR #803) | Base commit: 57f6799f | Branch: task/0999-property-rules-map (commit on the PR #803 branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Three small defects from the PR #803 review. (a) 1000 added a `style="display:flex;gap:4px;…"` row on `/apartments/<id>/page`; the layout lint fires `tight-side` (↑/↓ 4 px apart) at 390/768/1280 and the arrows are 42 px wide (44 px touch target). (b) The new `photo-move` forms (and the old `photo-delete` form) have no `_csrf` field, so they only work when `app.js` injects it; without JavaScript they end in "form expired". (c) 0995 added "Booking site" to the desktop sidebar only; the phone "More" menu (`_shell_tabbar.html`) has no entry, so on phone `/booking-sites` is unreachable from navigation.

## 2. Context

Rules: AGENTS.md 1-10; design-system.md rule 2 (no `style=""` in a template; a missing style becomes a class with tokens), rule 3 (12 px between neighbours), §3 (touch target 44 px); rules.md UX: "Preserve ordinary server forms without JavaScript". CSRF: `App/app/security.py` `_supplied_csrf_token` reads the `x-csrf-token` header or the `_csrf` form field; other host forms carry `<input type="hidden" name="_csrf" value="{{ csrf_token }}">`.

`App/app/templates/property_page_review.html`:
```
      <div style="display:flex;gap:4px;margin-top:4px;align-items:center;">
```
```
        <form method="post" action="/apartments/{{ apartment.id }}/page/photo-move">
          <input type="hidden" name="path" value="{{ p }}">
```
```
          <button class="ui-btn ui-btn-secondary ui-btn-compact" type="submit" aria-label="{{ t(key) }}"{% if (d == 'up' and first) or (d == 'down' and last) %} disabled{% endif %}>{{ glyph }}</button>
```
```
      <form method="post" action="/apartments/{{ apartment.id }}/page/photo-delete" data-confirm data-confirm-message="{{ t('payments.page.photo_delete_confirm') }}" style="position:absolute;top:4px;right:4px;">
        <input type="hidden" name="path" value="{{ p }}">
```
`App/app/templates/_shell_tabbar.html`:
```
      <a class="ui-menu-item" href="/payments">{{ icon('credit-card', 16) }}{{ t('nav.payments') }}</a>
```
If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/property_page_review.html | edit | class instead of inline style; `_csrf` in move and delete forms; regular-size arrows |
| App/app/static/host.css | edit | one class `.pp-photo-moves` (only if no existing class fits, step 1) |
| App/app/templates/_shell_tabbar.html | edit | "Booking site" menu item |
| App/tests/test_property_page_photos.py | edit | markup test |
| App/tests/test_booking_site_host.py | edit | phone menu test |

No other file may change.

## 4. Steps

1. Find the host rule for `.ui-btn-group`: `grep -rn "\.ui-btn-group" App/app/static/host*.css App/app/static/components.css | head -5`. If one applies to host pages (not only `body.v2`) with a gap of `var(--space-3)` or 12 px, use `class="ui-btn-group"` on the row. Otherwise add to `host.css`: `.pp-photo-moves { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-2); }` and use `class="pp-photo-moves"`; find the `host.css?v=` cache key with `grep -rn "host.css?v=" App/app/templates | head -3` and bump it (STOP if there are several different keys).
2. Replace the `<div style="display:flex;gap:4px;…">` line with the class from step 1.
3. Arrow buttons: drop `ui-btn-compact` from the ↑/↓ buttons (regular buttons are 44 px on phone).
4. Add `<input type="hidden" name="_csrf" value="{{ csrf_token }}">` as the first child of the `photo-move` form and of the `photo-delete` form.
5. `_shell_tabbar.html`: after the `/payments` line add `      <a class="ui-menu-item" href="/booking-sites">{{ icon('external-link', 16) }}{{ t('nav.booking_sites') }}</a>`.
6. Tests: (a) `test_property_page_photos.py`: GET `/apartments/<id>/page` with two photos; assert the page has `name="_csrf"` inside the photo-move form and no `gap:4px`. Then post `photo-move` with only `path`, `dir`, `_csrf` taken from the HTML (no header) and assert 303 and the order changed. (b) `test_booking_site_host.py`: any host page HTML contains `href="/booking-sites"` inside the tab-bar menu (`ui-menu-item`).

## 5. Do not touch

The rest of `property_page_review.html` (its older inline styles are known debt, not this brief), `routes/payments.py`, `property_page.py`, `_shell_sidebar.html`. Hard rules 6, 7, 10.

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_property_page_photos.py tests/test_booking_site_host.py tests/test_property_page.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py -q -rs --tb=short 2>&1 | tail -30
python3 ../scripts/design_lint.py 2>&1 | tail -10
```
The lint does not crawl `/apartments/<id>/page`: open it with 3+ photos at 390/768/1280 in a throwaway script, run `tests/layout_lint.js`, and confirm no `tight-side`/`tight-row` finding on the arrows (findings on the older header buttons Unpublish/Open the public page are known and listed in the review). Do not commit the script.

## 7. Acceptance

- [ ] No `style=` on the new reorder row; arrows at least 44x44 at 390.
- [ ] Reorder and delete work with JavaScript disabled (`browser.new_context(java_script_enabled=False)`).
- [ ] Phone "More" menu lists Booking site.
- [ ] 390 px screenshots of `/apartments/<id>/page` photo block and of the opened phone menu in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; a file outside §3 needs a change; the cache key is unclear.

## 9. Report

`docs/tasks/1005-report.md`, 600 tokens at most, `Status: review`.

## Risk list (for the reviewer)

`host.css` (if touched: cache key), `_shell_tabbar.html`.

## Owner steps

None.
