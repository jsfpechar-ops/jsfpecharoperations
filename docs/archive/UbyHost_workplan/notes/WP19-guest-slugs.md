# WP19: Readable guest links (HIGH RISK)

Patch: `WP19-guest-slugs.patch` (one commit, `WP19: Readable guest links`, on `wpbase`; not stacked on any other WP).

## Summary
Every property now has a readable guest link `/l/{readable}-{code}`, for example `/l/vinohrady-studio-k7m2qx`, next to the old `/l/{token}`. The old token link keeps working forever. One resolver in `routes/guest.py` (`_open_link`, built on `_resolve_key`) runs first in all 11 `/l/...` routes. It accepts the token or any slug. An earlier slug, or the current slug in other letter case, gets a 301 to the current slug on GET and HEAD. A POST on an earlier slug is served where it is, because a redirect would drop the form body. A key that matches nothing (including a slug with a wrong code) gets the existing "bad link" page with status 404.

The PIN cookie, `pin_fingerprint`, `pin_matches`, the per-IP PIN counter, the per-link lockout key, the guest POST throttle and the claim throttles are all keyed on the apartment's permanent `permalink_token`, resolved from the slug. They are never keyed on the URL segment. A guest who switches between links is not asked for the PIN again, and switching links does not reset the lockout. Pages keep building their own links in the form the guest arrived on: the token for token visitors, the current slug for slug visitors.

The host can edit the readable part in property settings (Guest links section). The code never changes. "Generate a new link" also deletes every slug and issues one with a new code.

## Files changed
- `App/app/guest_slug.py` (new): folding, 40-character cut at a word boundary, reserved words, code generation, lookup, `ensure`, `rename`, `rotate`, `backfill`.
- `App/app/db.py`: `apartment_slug` table and the partial unique index from review 8.3; `init_db` backfills a slug for every apartment that has none.
- `App/app/routes/guest.py`: the single resolver; every route uses it; PIN, lockout and rate-limit keys use the permanent token; `_form_context` takes the link key.
- `App/app/auth.py`: `PERMALINK_ALPHABET` constant (the slug code uses the same letters); docstring on `pin_fingerprint`.
- `App/app/routes/admin.py`: Guest links page, property page and stay detail copy the slug link; create makes a slug; the property form saves `guest_link_name`; regenerate-link rotates slugs; the stays list query adds `permalink_slug`.
- `App/app/routes/api.py`: the command-palette "copy property link" uses the slug.
- `App/app/onboarding.py`: the finish card link and its preview use the slug.
- `App/app/retention.py`, `App/app/demo.py`: delete slug rows explicitly before an apartment is deleted (the cascade does it too).
- `App/app/host_i18n.py`: 5 new strings in EN and CS (field label, hint, 3 flash errors).
- `App/app/templates/apartment_form.html`: the readable-part field, shown as `/l/ [input] -code`.
- `App/app/templates/guest_links.html`, `_components.html`, `reservations.html`: preview and copy links use the slug.
- `docs/SECURITY.md`: one sentence on the guest-access row.
- Tests: `tests/test_guest_slugs.py` (new); `test_guest_browser_e2e.py` (slug variant); expectations updated in `test_onboarding.py`, `test_overhaul.py`, `test_guest_links_bilingual.py` and `test_guest_links_preview.py`, which asserted that the copied link was the token.

## Tests added
`tests/test_guest_slugs.py`, 25 tests:
- Czech names folded correctly (`Příliš žluťoučký kůň...`, `ŘEČNÍ Ťulpas`, `ß`, `Ł`, `Ø`), cut at a word boundary, a single long word cut hard.
- Reserved words rejected (pin, claim, party, privacy, another, new, edit, save, confirm), in any letter case. An empty result is rejected. A name that folds to a reserved word or to nothing gets the fallback `stay`.
- The code is 6 characters from the token alphabet. The migration backfills a slug, a second run is idempotent, and deleting an apartment removes its slugs.
- Routing:
  - the old token URL works and keeps its own links on the token;
  - the current slug works;
  - sub-routes resolve the slug;
  - an old slug gets a 301 to the current one, keeping the sub-path and query, with `Cache-Control: no-store`;
  - renaming back to an earlier name reuses its row;
  - an upper-case slug gets a 301 to lower case;
  - a wrong code, a wrong readable part, a bare readable part or an extra character gets 404 (also on `/privacy`);
  - an archived property gets 404;
  - a POST on an old slug is served in place.
- PIN continuity: a PIN entered on the token URL is valid on the slug URL and the other way round, and the cookie carries the token and its fingerprint.
- Lockout: wrong PINs entered on the token, the slug and the upper-case slug count against one per-IP counter and one per-link counter, and nothing is counted under the slug. A link locked through the token is also locked through the slug.
- Host side:
  - the Guest links page, the stay detail page and the stays list show the slug link;
  - the host renames the readable part and the code stays the same;
  - reserved and empty names are refused;
  - "Generate a new link" makes all old slugs and the old token return 404.

`tests/test_guest_browser_e2e.py`: new `test_the_readable_link_takes_the_group_through_the_same_flow` at 320, 360 and 390 px. It runs the full group-of-three flow from `/l/{slug}`. The claim e-mail still links to the token, so the test also checks that switching links mid-flow works.

## Test commands and results (exact counts)
All run from `App/` with `/tmp/pr230/App/.venv/bin/python -m pytest -q`.
- WP19 set: `tests/test_guest_slugs.py`, `test_guest_pin.py`, `test_guest_rate_limits.py`, `test_guest_links_bilingual.py`, `test_guest_links_preview.py`, `test_onboarding.py`, `test_overhaul.py`, `test_security.py`, `test_db_upgrade.py`, `test_guest_pin_a11y.py`, `test_guest_csrf.py` and `test_guest_browser_e2e.py`: 140 passed, 7 skipped. The 7 skipped are all in `test_guest_browser_e2e.py`, because Chromium is missing.
- Full suite in chunks (before the commit; the commit adds nothing more):
  - `test_[a-f]*`: 600 passed, 2 skipped.
  - `test_[g-o]*`: 799 passed, 8 skipped, 1 failed. The failure is `test_host_geometry.py::test_the_month_filter_shares_its_page_edges`. Chromium cannot start in this sandbox (`libXdamage.so.1` missing), and the test fails the same way on `wpbase`.
  - `test_[p-s]*`: 637 passed, 1 failed. The failure is `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`. It also fails in this chunk on `wpbase` without the patch, and passes when run alone. It depends on test order and is not related to WP19.
  - `test_[t-z]*`: 152 passed.
- Lint: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: all checks passed.
- The guest browser e2e did not run here. Chromium cannot launch in the sandbox (`libXdamage.so.1` missing), so all its tests were skipped.

## Deviations from the spec and why
- The route path parameter is still named `{token}`, not `{key}`. `security.protect_guest_post` and `csrf_expired_page` read `path_params["token"]`, and the access log logs the route template. Inside each route, `token` is rebound to the resolved link key. Behaviour is as specified.
- The 301 carries `Cache-Control: no-store`. Without it, a browser caches the 301 forever. If the host later renames back to an earlier name, that cached redirect would point the current slug at the old one and loop.
- "Generate a new link" deletes all slugs and issues a new code. The spec says "the code never changes", but that button exists to kill a leaked link. If the old slugs still redirected, they would hand the new link to whoever holds the leaked one. Renaming keeps the code, as specified.
- Reserved words apply to the readable part. A full slug always ends in `-code`, so it can never equal a route segment.
- A name that folds to nothing or to a reserved word gets the readable part `stay` (my choice; the spec names no fallback).
- Slugs are also created lazily (`guest_slug.ensure`) the first time a host page needs one. This covers apartments inserted by the demo seed, by test fixtures or by any future insert path.
- The redirect for an old slug happens before the PIN check. It reveals the current slug, which is no more secret than the old one.
- Not changed: claim and reminder e-mails (`claim.py`), the dashboard "open guest form" menu item and the privacy-policy text still use the token form. They work forever, and the spec does not list them.

## What Cursor must verify or adapt when applying on the real main
- Run the guest browser e2e with a working Chromium: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_browser_e2e.py -q -rs`. It must report 0 skipped, including the new slug test at 320, 360 and 390 px. Also run `tests/test_host_geometry.py`, which needs Chromium too.
- Run the full suite in one process, as CI does.
- If later WPs added new `/l/{token}/...` routes or new callers of `_apartment_by_token`, those routes must start with `apartment, token, early = _open_link(request, token, lang)`. Their rate-limit or PIN keys must use `apartment["permalink_token"]`. Check with `grep -n "@router" App/app/routes/guest.py`.
- If WP14 (connection handling) changed `db.immediate()` or `init_db`, check `guest_slug.backfill(conn)` and the `with db.immediate()` blocks in `guest_slug.py`. Each block is small, with no network inside.
- If a Postgres backend is in sight: the partial unique index (`WHERE is_current = 1`) and `ON DELETE CASCADE` are portable. `sqlite3.IntegrityError` is caught in `ensure` and `rename` and would need the backend's equivalent exception.
- HIGH RISK hunks to review by hand: `_resolve_key`, `_open_link`, `_lock_token`, `_pin_page`, `_link_challenged`, `_require_pin`, and the key lines in `verify_pin`, `_throttle_guest_post`, `claim_confirm` and `set_party_size` in `routes/guest.py`; `regenerate_link` and `_save_apartment_form` in `routes/admin.py`.

## Manual steps for the owner
- Deploy to staging first. Open an old `/l/{token}` link, enter the PIN, then open the slug link from Guest links: no second PIN prompt. Rename the readable part in property settings and open the old slug: it should redirect.
- No server, DNS or AWS change. The migration runs at startup and gives every existing property a slug.
- Hosts can keep the old links in their Airbnb and Booking messages. Copying the new message from Guest links is optional.
