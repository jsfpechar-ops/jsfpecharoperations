# 0090 report: lock setup feedback stays in its section

Base: `8b9df17` (0089 at review). Result: `0764a86`. Executor: Claude (owner-authorized).

## What changed

- `admin.py`:
  - Added `_SMART_LOCK_SECTIONS` (how / share / add-more / list) and `_smart_locks_url(return_to, section)`. Every lock-page redirect now goes to `/smart-locks?return_to=<encoded, sanitized>#<real section>`.
  - Added `_smart_locks_section(form, has_locks)`, which accepts only `share`, `add-more` or `list` from the form. Any other posted value falls back to a server default.
  - Added `_lock_property_return`, which builds `/apartments/{id}#door-code` only when `access.apartment` authorizes that id.
- Setup:
  - Terms, rate-limit and provider errors go to `#smart-locks-how`, and the terms box is never pre-ticked.
  - Success goes to `#smart-locks-share`.
- Refresh:
  - Budget, reauth and failed errors stay on the section the host acted in.
  - No lock or plain-key-only goes to `#smart-locks-share`, because with no locks that is the section the page shows.
  - Found locks: an authorized property return goes to `#door-code` (nothing is assigned or enabled); otherwise `#smart-locks-list`.
- Remove: same lifecycle and confirmation. It lands on `#smart-locks-how` with the existing local-only message when the provider fails.
- `smart_locks.html`:
  - The share block shows three essentials (EN/CS as specified) plus a `?` link to `/guide#door-codes-share`.
  - It keeps the receiver Copy, the "owner only" warning, the eKey warning, the terms checkbox and the terms link.
  - Each refresh form posts its constrained `section`.
- `guide.html`: the eight-step list moved, verbatim from the `smart_locks.s1–s8` keys, under `<h3 id="door-codes-share">` in the door-codes section. Nothing was removed from the detailed guide steps.
- `apartment_form.html`: the "connect" link targets `#smart-locks-how` and the "no locks" link targets `#smart-locks-share`. The property lock section still has one guide link.
- `app.js`: `openTarget` replaced with the supplied version. It opens every ancestor `<details>` and scrolls with `behavior:"auto"`, so reduced motion is respected. Added a `hashchange` listener. The existing link handlers and the initial call are kept, and no autofocus was added.
- `host_i18n.py`:
  - Added a `# 0090` block with the 3 essentials in EN/CS.
  - `smart_locks.name_label` changed "paste it in step 6" to "paste it in TTLock", because step 6 is no longer on the page.

## Anchors (old → new)

All matched: `/smart-locks?return_to={quote(...)}`, `_back(return_to, …)` errors, `range(1, 9)`, `#door-code` property links, and `openTarget` checking only the target. `admin_helpers.back` is unchanged; it already puts the query before the hash. `safe_local_path` drops fragments, so the property hash is rebuilt on the server.

## Commands (from App/, staging/mock env, pinned Chromium)

```
pytest tests/test_smart_locks_page.py tests/test_lock_navigation_browser.py -q -rs
  17 passed, 1 warning in 20.92s   (0 skipped)
per-file run of every test file mentioning smart-locks/ttlock/door-code/guide: all pass except
  baseline test_host_wide_geometry_browser (3) and test_host_i18n (first test lacks init_db when
  run alone; 44 passed when run after another file).
ruff check app tests tools --select E9,F63,F7,F82,F401,F841  ->  All checks passed!
python3 scripts/context_lint.py  ->  context lint: OK
```

## §7 checklist

- [x] Setup, check and error actions stay in their lock section. A property-started discovery returns to the expanded `#door-code`, where the browser test chooses the lock and saves, and nothing is assigned automatically. Foreign, external and `//` return paths and forged `section` values never escape.
- [x] Three essentials on the page, full provider steps in the Guide. Terms, admin sharing, ownership and PIN lifecycle are untouched. The tests patch `ttlock._call` and `_post` to fail, which proves no provider call is made.
- [x] Browser:
  - Starts deep in a property with the mock banner and a long title, in EN and CS: connect, accept, check with no lock, discover one lock, expanded `#door-code`, save.
  - The target is in the viewport after each step, and `scrollY > 0` on the share section.
  - Many locks: list and add-more at 360/390/1280. The add-more `<details>` reopens after an error.
  - No-JS share at 360/390, plus back navigation.
- [x] No schema, dependency or outbound call. Data is synthetic.
- [ ] CI on the task head: not run here (no push).

## Evidence

`docs/tasks/0090-evidence/`: `how-1280-*`, `share-1280-*`, `property-door-code-1280-*`, `list-{360,390,1280}-*`, `add-more-{360,390,1280}-*`, `share-nojs-{360,390}-*`. Captured with `UBYHOST_CAPTURE_0090=1`.

## Deviations / open points

- `App/app/static/host.css`: added a `/* 0090 */` block for the `?` link style, which is outside §3. 0093 should replace that link with the shared help component. It currently also has a `title` attribute, so it is not tooltip-only.
- Without JS, `#door-code` on the property page is a closed `<details>` and the hash cannot open it. Opening it would need server-side `open` from a query flag, which is not in the brief, so it is left as is.
- I did not bump `app.js?v=` in `base.html`, which is outside §3. On staging a browser could keep the old `openTarget` until its cache expires. The coordinator should bump the version once for the combined branch.
- "No lock found" and "plain key only" go to `#smart-locks-share` even when posted from add-more. After a check that finds nothing, the page shows only the share section.

## Owner steps

1. Review the screenshots in `docs/tasks/0090-evidence/`.
2. Let the coordinator run the full suite and CI, and bump the `app.js` cache version.
3. On staging, with test-mode TTLock, connect from a property and check that you land back on Digital door lock.
