# 1597: Go onboarding part 4: load the demo dataset (POST /demo)

Status: blocked — `demo.seed` needs five Python modules that have no Go port yet (claims, code lists, passport photo save, property page publish, guest normalisation), and its photo write needs a writable data volume for Go (owner item 4); see §2. Do not run.
Depends on: 1595, 1596, the ports listed in §2, owner decision on the `/data` mount | Base commit: current branch (One big PR mode) | Branch: none
Executor: none until unblocked | Fits one session: not written
Tier: A (guest data, demo stays that must never be filed)

> **One big PR mode.** When this brief is rewritten, the executor works on the current branch: commit `1597 step k` after each step that changes a file, never create a branch, never push, never open a PR.

## 1. Objective

Serve `POST /demo` (`load_demo`, `App/app/routes/onboarding.py` 23-34) on Go. The route calls `demo.seed(owner)` (`App/app/demo.py` 755-877 with `_seed_apartment`, `_sync_sample_feed`, `_enrich_studio`, `_enrich_loft`, `_enrich_extras`, 217-752) and answers `/?msg=flash.demo.loaded` or `/?err=flash.error.demo_staging_only`.

## 2. Context: why it is blocked

`demo.seed` only does anything while `UBYHOST_UBYPORT_ENV` is `mock` (production answers the `demo_staging_only` error at once), but on a mock install it builds two complete demo properties through these Python functions. Checked on go-wave3 at 859d114d5 with `grep -rn` under `go/internal`:

| Python call in demo.py | Go today |
|---|---|
| `claim.start_claim`, `claim.confirm`, `claim.ensure_row`, `claim.lock_guest_access` (provisional and assigned claims, a claim mail in the outbox, locked access) | no port (only `reservation_claim` reads in `ical`, `retention`, `statemachine`); the guest claim flow belongs to the guest registration pages, which the owner keeps last |
| `codelists.refresh_all(reporting.client_for(...))` (fetches the code lists from the mock UbyPort) | no port (no `INSERT INTO codelist` in Go) |
| `passport_photos.save_photo` (the Karlín sample passport photo, encrypted under `/data/passport_photos`) | no port; the Go service mounts `/data` read-only (`deploy/lightsail/docker-compose.yml`), the same blocker as brief 1447 (owner item 4) |
| `property_page.publish_page` (the published Vinohrady page with a paid site booking) | no port (`publish_page` / `PublishPage` absent) |
| `validation.normalise_guest`, `validation.mark_from_ws_user` (every demo guest row, the zkratka) | no port in `go/internal/validation` |
| `icalsync.sync_feed(feed, ics_text=sample_airbnb_ics())`, `payment_request.create`, `reporting.check_deadlines`, `reporting.submit_for_apartment` (mock), `auth.new_permalink_token`, `db.encrypt_secret` | Go has counterparts (`ical.SyncFeed`, `payments` requests, `calendar` deadlines, `ubyport.SubmitForApartment`, `secure`), but `sample_calendar.sample_airbnb_ics` would need a Go twin too |

A Go `POST /demo` that only answers the production branch (`demo_staging_only`) would be wrong on every mock install the moment the path is switched, and a 501 for the mock branch repeats the 501 problem of owner item 1. So the route stays on Python.

## To unblock

1. Port the guest claim functions above (they come with the guest registration pages, owner's order: last).
2. Port `codelists.refresh_all`, `property_page.publish_page`, `validation.normalise_guest` and `mark_from_ws_user`, and add a Go twin of `sample_calendar.sample_airbnb_ics`.
3. Owner item 4: make `/data` writable for `ubyhost-go`, or keep `POST /demo` on Python for good (it only matters on a mock install).
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

Decide owner item 4 (writable `/data` for Go, or keep the demo buttons on Python). Until then `/demo` and `/demo/reset` stay on Python (brief 1596's owner steps switch them together).
