# 1597: Go onboarding part 4: load the demo dataset (POST /demo)

Status: blocked — three ports are written as briefs (1650, 1651, 1652) and the volume is decided (1640), but `demo.seed` still needs the guest claim functions and the code-list fetch, which have no brief that can run yet; see §2. Do not run.
Depends on: 1595, 1596, 1640 (writable `/data`, decided 2026-11-14), 1650, 1651, 1652, and the two ports of §2 that have no brief yet | Base commit: current branch (One big PR mode) | Branch: none
Executor: none until unblocked | Fits one session: not written
Tier: A (guest data, demo stays that must never be filed)

> **One big PR mode.** When this brief is rewritten, the executor works on the current branch: commit `1597 step k` after each step that changes a file, never create a branch, never push, never open a PR.

## 1. Objective

Serve `POST /demo` (`load_demo`, `App/app/routes/onboarding.py` 23-34) on Go. The route calls `demo.seed(owner)` (`App/app/demo.py` 755-877 with `_seed_apartment`, `_sync_sample_feed`, `_enrich_studio`, `_enrich_loft`, `_enrich_extras`, 217-752) and answers `/?msg=flash.demo.loaded` or `/?err=flash.error.demo_staging_only`.

## 2. Context: what is still missing (state 2026-11-14)

`demo.seed` only does anything while `UBYHOST_UBYPORT_ENV` is `mock` (production answers the `demo_staging_only` error at once), but on a mock install it builds two complete demo properties through the Python functions below. Checked on main (after PR #1021) with `grep -rn` under `go/internal`, sizes from `App/app`:

| Python call in demo.py | Go today | Size and plan |
|---|---|---|
| Writable `/data` for the photo write | decided 2026-11-14: option "Allow writable volume" | **brief 1640** (compose line) |
| `sample_calendar.sample_airbnb_ics` | no port | 59 lines, pure. **Brief 1650** (`ical.SampleAirbnbICS`) |
| `validation.mark_from_ws_user` | no port (the login pattern `wsUserRE` exists) | 20 lines, pure. **Brief 1651** (`validation.MarkFromWSUser`) |
| `property_page.publish_page` (with `slug_for`, `ensure_slug`, `publish`) | no port | about 70 lines. **Brief 1652** (`booking.PublishPage`) |
| `passport_photos.save_photo` (the Karlín sample passport photo: re-encode as JPEG q90, encrypt, write `<id>.jpg.enc`) | no port; Go can delete these files (`demoDeletePhoto`), not write them | medium. Needs the writable volume (1640), a q90 no-shrink variant next to `imgproc.Clean` (1641 only has the guide-photo pipeline: q82, 1600 px), and `secure` Fernet encryption of the blob. **No brief yet**; write it after 1640 and 1641 are merged, so the variant can reuse the package |
| `validation.normalise_guest` (every demo guest row) | no port (`validation.go` has completeness checks only, `GuestIssues`, `GuestIsComplete`) | not small: `normalise_name`, `normalise_document`, `normalise_birth_date`, `normalise_residence_part`, `normalise_note` and the transliteration they use sit in a 1,244-line module. Belongs with the guest registration pages (owner: last). **No brief** |
| `claim.start_claim`, `claim.confirm`, `claim.ensure_row`, `claim.lock_guest_access` (provisional and assigned claims, the claim mail in the outbox, locked access) | no port (only `reservation_claim` reads in `ical`, `retention`, `statemachine`) | not small: `claim.py` is 1,034 lines (`start_claim` 130, `confirm` 80, plus the mail and rate-limit helpers). Belongs with the guest registration pages (owner: last). **No brief** |
| `codelists.refresh_all(reporting.client_for(...))` | no port (no `INSERT INTO codelist`; `go/internal/ubyport` has no `code_list` SOAP call) | medium: a SOAP read in the Go client, the column mapping of `_code_and_texts`/`_extra`, and `store`. **No brief yet**; it is a good standalone brief in the UbyPort area (the Go service will need the code lists for filing anyway) |
| `icalsync.sync_feed`, `payment_request.create`, `reporting.check_deadlines`, `reporting.submit_for_apartment` (mock), `auth.new_permalink_token`, `db.encrypt_secret` | Go has counterparts (`ical.SyncFeed`, `payments`, `calendar`, `ubyport.SubmitForApartment`, `secure`) | none needed |

So the demo seed stays on Python until the two big ports (guest claim, guest normalisation) exist, i.e. with the guest registration pages, or until the owner accepts that `POST /demo` stays on Python for good (it only matters on a mock install; the production answer is a fixed error). A Go `POST /demo` that answers only the production branch would be wrong on every mock install once the path is switched, and a 501 for the mock branch repeats the 501 problem of owner item 1.

## To unblock

1. Run 1640, 1650, 1651, 1652 (any order; 1641 and 1447 are independent of them).
2. Port the guest claim functions and `normalise_guest` (guest registration pages, owner's order: last), or decide that `POST /demo` stays on Python.
3. Optional pieces with no brief yet: the passport photo save (after 1640 and 1641) and the code-list fetch. Write each as its own brief when the claim port is scheduled.
4. Then a tier A writer rewrites this brief (Opus): a Python golden of the seeded rows per table (ids, names, states, never the random tokens or PINs except the fixed demo PINs), with the mock UbyPort stubbed on both sides.

## 3. Files

None until unblocked.

## 4. Steps

None until unblocked.

## 5. Do not touch

Everything. `POST /demo` stays on Python.

## 6. Commands

None.

## 7. Acceptance

None.

## 8. Stop and ask

Do not run this brief.

## 9. Report

None.

## Risk list (for the reviewer)

Not applicable.

## Owner steps

Nothing now. `/demo` and `/demo/reset` stay on Python until this brief is done (brief 1596's owner steps switch them together). The data volume question is answered (brief 1640); the remaining blockers are code, not decisions.
