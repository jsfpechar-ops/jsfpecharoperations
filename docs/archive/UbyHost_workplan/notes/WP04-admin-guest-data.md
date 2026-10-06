# WP04: Admin access to guest data (HIGH RISK)

Commit `215cbd8` on branch `wp04`, based on `wpbase` (492e2b1). Not stacked on any other WP.
Patch: `WP04-admin-guest-data.patch`.

## Summary

- Opening a host's workspace (`POST /admin/users/{id}/impersonate`) now needs a reason of 5 to 300 characters. Whitespace is folded to single spaces. The reason goes into the `impersonation_started` detail: `admin=<username> reason=<text>`.
- The session payload now carries `ast` (start time, epoch seconds) next to `as`. `auth.workspace_user`, the one place `as` is read, checks it on every request. After 60 minutes (`auth.IMPERSONATION_MAX_AGE`) it returns the admin's own account and flags the request. `auth.require_login` then writes `impersonation_stopped` with detail `expired` to the host's workspace and the admin's, swaps the cookie for a plain admin session, and redirects to `/admin/users` with a notice. A payload with `as` but no `ast` (issued before this change) counts as expired.
- Exiting by hand writes `impersonation_stopped` with detail `exit` to the host's workspace and the admin's.
- `access.identity_visible(request, guest_id=None)` is the one helper. It returns True when the admin is not impersonating. While impersonating it returns True only for a guest revealed in this session, and always False with no guest id (bulk downloads). `access.mask_identifier` keeps the last 3 characters (`•••567`). Jinja gets `identity_visible()`, `guest_identifier(value, guest_id)` and `impersonation_minutes_left()`.
- Reveal: `POST /guests/{id}/reveal-identity` with a reason. It writes `guest_identity_revealed` (`guest_id=<id> reason=<text>`) to the host's audit, and adds the guest id to the session payload (`rv`, at most 50 ids). The start time is kept, so a reveal does not extend the 60 minutes. Reveals end with the impersonation.
- The impersonation bar in `base.html` is kept and now shows the minutes left.
- Settings audit: the reason is shown in the existing Detail column. A new "All activity / Support sessions" filter (`/settings?audit=support`) shows start, stop and expiry, reveals, and every row written as an admin (`impersonator_user_id` set).

## Inventory: what outputs identity data, and what happens now

Pages (masked while impersonating, full for the host):

| Route | Template | Data | While impersonating |
|---|---|---|---|
| `GET /reservations/{id}` (`admin.py reservation_detail`) | `reservation_detail.html` | doc number, visa number (signature shown only as signed / not signed) | last 3 characters |
| `GET /housebook` (`admin.py housebook_view`) | `housebook.html` | doc number, visa number per row | last 3 characters |
| `GET /submissions/{id}` (`admin.py submission_detail`) | `submission_detail.html` | doc number per guest | last 3 characters |
| `GET /guests/{id}` (`admin.py guest_edit`, also the error re-render of `POST /guests/{id}`) | `guest_form_admin.html` | doc and visa inputs, signature pad and its hidden value, passport photo `<img>`/`<iframe>` | doc and visa read-only and masked, no input names; signature pad and photo replaced by "Hidden while supporting" with a Reveal button; reveal banner with reason field |
| `POST /guests/{id}` (`admin.py guest_update`) | | writes doc, visa, signature | stored values kept, so a masked value can never overwrite the real one |

Downloads and images:

| Route | Data | While impersonating |
|---|---|---|
| `GET /guests/{id}/passport-photo` (`admin.py`) | passport image | 403 text, unless that guest is revealed |
| `GET /guests/{id}/form.pdf` (`exports.py`, `housebook.registration_form_pdf`) | doc, visa, signature | blocked with message, unless revealed |
| `GET /guests/{id}/export.json` (`exports.py`, `dsr.guest_export`) | doc, visa (decrypted) | blocked, unless revealed |
| `GET /housebook.csv` (`housebook.iter_housebook_csv_rows`) | doc, visa | blocked |
| `GET /housebook/pdfs.zip` (`housebook.build_housebook_pdfs_zip`) | doc, visa, signatures | blocked |
| `POST /settings/workspace-export` (`workspace_export.build_workspace_zip`) | everything | blocked |
| `POST /admin/users/{id}/export` (`admin_accounts.py`, same ZIP) | everything | blocked if the admin is inside a workspace (see open issues for the admin's own view) |
| `GET /stay-fees/{id}/csv` (`stay_fee.register_rows`, evidenční kniha) | doc number | blocked |
| `GET /submissions/{id}/request.xml`, `response.xml` | request envelope has `cDocN`, `cVisN` | blocked |
| `GET /submissions/{id}/receipt.pdf`, `errors.pdf`, `/submissions/receipts.zip` | police Doručenka PDFs, cannot be masked | blocked (see deviations) |

Checked and not changed (no identity data): `/reservations.csv` (`stays_export`: dates, counts, e-mail), `/stay-fees/{id}/pdf` (remittance PDF; the signature there is the host's own entity signature), `/stay-fees/{id}` detail, `/api/command-palette`, `/privacy-requests`, `entities.html` (host signature, not guest). Guest pages under `/l/...` are reached with the guest link and PIN, not through the admin session, so they are out of scope.

## Files changed

- `App/app/auth.py`: `IMPERSONATION_MAX_AGE`, `ast`/`rv` in `issue_session`, expiry check in `workspace_user`, `impersonation_expired`, `impersonating` (cached per request), `impersonation_started_at`, `impersonation_minutes_left`, `revealed_guest_ids`, `support_reason`, `end_expired_impersonation`, hook in `require_login`.
- `App/app/access.py`: `identity_visible`, `mask_identifier`, `identifier_for`.
- `App/app/templating.py`: Jinja globals `identity_visible`, `guest_identifier`, `impersonation_minutes_left`.
- `App/app/routes/admin_accounts.py`: reason on impersonate, stop row to host and admin, admin ZIP blocked while impersonating.
- `App/app/routes/admin.py`: guest form masking, masked save keeps stored identity, passport photo gate, reveal route, Support sessions audit filter.
- `App/app/routes/exports.py`: `_identity_hidden` gate on every identity download.
- `App/app/routes/stay_fees.py`: register CSV gate.
- `App/app/host_i18n.py`: new EN and CS strings.
- `App/app/templates/base.html`: minutes left in the impersonation bar.
- `App/app/templates/users.html`: reason field on "Open workspace".
- `App/app/templates/guest_form_admin.html`: masked fields, placeholders, reveal banner and form.
- `App/app/templates/reservation_detail.html`, `housebook.html`, `submission_detail.html`: masked numbers.
- `App/app/templates/settings.html`: audit filter links.
- `App/tests/test_admin_guest_data.py`: new.
- `App/tests/test_accounts.py`, `test_legal_acceptance.py`, `test_access_audit.py`: pass a reason; the impersonated-export audit test now uses `/reservations.csv` because the Doručenka is blocked.

## Tests added

`tests/test_admin_guest_data.py` (14 tests):
- impersonation without a reason (empty, blank, 4 chars, 301 chars) is refused and writes no start row; a valid reason is stored, folded to one line;
- the bar shows 60 minutes left;
- a payload without a start time counts as expired;
- after 60 minutes (time patched with `monkeypatch.setattr(auth.time, "time", ...)`, as `test_move_to_new_phone.py` does) the next request redirects to `/admin/users` with the notice, writes `expired` to host and admin audits, and the next request is the admin's own view with no second row;
- at 58 minutes the impersonation holds and shows 2 minutes left;
- manual exit writes `exit` to host and admin audits;
- the host sees full data on every page and gets 200 on every download in the list;
- while impersonating every page in the list contains no full number but the last 3 characters, the form has no signature, pad, photo or doc input, every download is a 303 with an error (photo: 403), the stay-fee CSV and admin ZIP are blocked;
- saving a masked guest keeps the stored doc, visa and signature;
- reveal without a valid reason is refused; with one it writes the audit row (with the admin as impersonator) and unmasks only that guest (page, photo, form PDF), the other guest stays masked, bulk downloads stay blocked, the clock is not reset;
- reveals end with the impersonation;
- a reveal at 50 minutes does not extend the limit;
- helper unit checks for masking and reason length;
- the host sees start (with reason), stop, reveal and "as admin" in Settings, and the Support sessions filter hides ordinary rows.

## Test commands and results

From `/tmp/wp/wp04/App`:
- `python -m pytest -q tests/test_admin_guest_data.py tests/test_access_audit.py tests/test_accounts.py tests/test_legal_acceptance.py tests/test_host_guest_form.py`: 74 passed.
- Whole suite in chunks: `test_[a-c]*` 298 passed, 2 skipped; `test_[d-f]*` 316 passed; `test_g*` 299 passed, 4 skipped; `test_[h-o]*` 475 passed, 1 failed; `test_[p-r]*` 276 passed; `test_[s-z]*` 514 passed. Total 2178 passed, 7 skipped, 1 failed.
- The 1 failure is `test_host_geometry.py::test_the_month_filter_shares_its_page_edges`: Chromium cannot launch in this sandbox (`TargetClosedError`). It fails the same way on `wpbase` without this change.
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: all checks passed.
- The guest browser e2e was not run with `UBYHOST_REQUIRE_BROWSER=1` (no working Chromium here). No guest page (`templates/guest/`, guest CSS or JS) was changed.

## Deviations from the spec and why

- Doručenka PDFs (`receipt.pdf`, `errors.pdf`, `receipts.zip`) and the submission XML are blocked while impersonating. The spec names only the register exports and the ZIP, but its step 1 covers every route that outputs document numbers. The request XML holds `cDocN`/`cVisN` for certain. The police PDFs cannot be masked, and I assumed they list document numbers. If the owner confirms that a Doručenka holds no document numbers, remove the three `_identity_hidden` calls on receipts in `exports.py`.
- The stay-fee register CSV (`/stay-fees/{id}/csv`) is blocked too. It lists document numbers. The spec does not name it.
- The review says `identity_visible(request)`. The WP says `identity_visible(request, guest_id)`. I implemented the WP signature with `guest_id` optional: no id means a bulk check, which is always False while impersonating.
- Stop-row details are the bare words `expired` and `exit`. The admin's name is already in the `actor` column. The expiry row also has `impersonator_user_id` set, so the host's list shows "as admin X".
- Reveals are stored in the signed session cookie (`rv`), not looked up in the audit table. This keeps the check cheap and ends reveals when the session ends. At most 50 ids are kept; past that the oldest reveal drops.
- The admin's own `/admin/users/{id}/export` (not impersonating) is unchanged. The spec only covers impersonation (see open issues).

## What Cursor must verify or adapt when applying on the real main

- Re-run the inventory grep on main. New routes or templates that print `doc_number`, `visa_number`, `signature_png`, `/passport-photo`, or call `registration_form_pdf`, `iter_housebook_csv_rows`, `build_housebook_pdfs_zip`, `build_workspace_zip`, `register_rows`, `dsr.guest_export` or `request_xml` must use `access.identity_visible` or `guest_identifier`.
- The tests in `test_accounts.py`, `test_legal_acceptance.py` and `test_access_audit.py` that impersonate now send a reason. Any other test on main that posts to `/impersonate` needs `data={"reason": ...}`. Without one, the route returns a 303 with `err=` and silently stays in the admin's own view.
- `users.html`: the reason input sits inside the row menu. Check it renders and is usable on mobile (the schedule-deletion form uses the same pattern).
- The duplicated "Download PDF" link in `guest_form_admin.html` (two identical lines) was already there. Noticed, not changed.
- List these HIGH RISK hunks for hand review in the PR: `auth.workspace_user` and `require_login` (expiry), `access.identity_visible`, `admin.guest_update` (masked save keeps stored values), `admin.guest_reveal_identity`, and each `_identity_hidden` call in `exports.py`.
- After deploy, every admin who is currently impersonating is sent back to their own view on their next request, because old cookies have no `ast`. This is intended.

## Manual steps for the owner

- None on the server.
- Confirm whether the UbyPort Doručenka and error PDF contain document numbers. If they do not, the receipts can be unblocked (see deviations).
- Decide whether the admin's own workspace ZIP (`/admin/users/{id}/export`, outside impersonation) should also need a reason. Today it gives the full data with only a `workspace_exported` audit row.
