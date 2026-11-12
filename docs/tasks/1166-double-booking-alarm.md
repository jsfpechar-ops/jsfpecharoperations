# 1166: double-booking alarm from the iCal calendars (e-mail + in-app alert)

Status: todo
Depends on: none | Base commit: 07d7328c | Branch: task/1166-double-booking-alarm
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When two active stays of one apartment overlap in dates after an iCal sync, the host gets
one in-app alert per overlapping pair plus one e-mail per pair while it stays open. The idea
was raised by the owner: two OTA calendars (e.g. Airbnb + Booking.com) can both show a
booking for the same nights, and today nothing tells the host — the booking site prevents its
own clashes (`site_booking.mail.host_clash_*`, `booking_webhook.py:223`) and manual stay
creation warns (`calendar.overlap`, `routes/admin.py:3889`), but feed-vs-feed overlaps are
silent.

## 2. Context

Rules that apply: AGENTS.md hard rules 1–6 and 9 (no new personal-data column, no new
outbound request — detection reads existing `reservation` rows only; no schema change, the
`alert` and `email_outbox` tables are reused); rules.md §Mail (service mail about stays);
mail rule from `mail.py:107-109`: a new kind goes into `KINDS` and exactly one of
`GUEST_KINDS`/`HOST_KINDS` (`test_mail.py` fails otherwise).

Key excerpts (verbatim, with paths):

Overlap predicate already used for manual stays — `App/app/routes/dashboard_calendar.py:54-61`:
```python
def overlapping_count(apartment_id: int, start: str, end: str) -> int:
    """Called only after the canonical create handler checks apartment access."""
    return int(db.query_one(
        "SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ? "
        "AND status = 'active' AND archived_at IS NULL "
        "AND date_from < ? AND date_to > ?",
        (apartment_id, end, start),
    )["n"])
```
(`date_to` is exclusive: check-out day = next check-in is NOT an overlap.)

Alert raise/resolve pattern — `App/app/icalsync.py` (feed_incomplete branch):
```python
alerts.raise_alert(
    "warning", "feed_incomplete",
    host_i18n.translate(host_i18n.DEFAULT_LANGUAGE, "notification.feed_incomplete.title", property=...),
    host_i18n.translate(host_i18n.DEFAULT_LANGUAGE, "notification.reason.feed_incomplete"),
    dedupe_key=f"feed_incomplete:{feed['id']}",
    apartment_id=feed["apartment_id"],
)
...
alerts.resolve(f"feed_incomplete:{feed['id']}")
```
Alert cards render from `notification.<kind>.title` / `.reason.<kind>` keys via
`alerts._present_stored` for kinds not in `_COMPUTED_ALERT_KINDS`; a `reservation_id` on the
alert makes `alerts.action_for` fall back to an "Open stay" button (`/reservations/{id}`).

Mail pattern — `App/app/mail_notify.py:1143-1205` (`cancelled_with_guests`): look up
apartment, `to_email = _entity_contact_email(apartment["legal_entity_id"])`, build
text+html via `_shell`, then:
```python
return mail.enqueue(
    kind="cancelled_with_guests",
    idempotency_key=f"cancelled_with_guests:{reservation_id}:{variant}",
    to_email=to_email, subject=subject,
    payload={"text": text, "html": html, "lang": lang},
    apartment_id=apartment_id, owner_user_id=apartment["owner_user_id"],
)
```
Kinds list — `App/app/mail.py:45` `KINDS = (...)` and `mail.py:123` `HOST_KINDS = (...)`.

Go side (the live path since the Go cutover; `go/cmd/ubyhost-web/main.go:268` calls
`ical.SyncAll`). The alert+mail+push trio for one event —
`go/internal/ical/reconcile.go:393-404`:
```go
if err := ubyport.RaiseAlert(ctx, pool, "warning", "cancelled_with_guests",
    title, detail, fmt.Sprintf("cancelled_with_guests:%d", res.ID), &aid, &rid, nil,
    ubyport.AlertParams{"date": res.DateFrom, "variant": variant}); err != nil {
...
if _, err := ubyport.QueueCancelledWithGuestsMail(ctx, pool, getenv, apartmentID, res.ID, variant); err != nil {
...
if _, err := ubyport.QueueCancelledWithGuestsPush(ctx, pool, getenv, apartmentID, res.ID); err != nil {
```
Signatures — `go/internal/ubyport/effects.go:85`
`func RaiseAlert(ctx, pool, level, kind, message, detail, dedupeKey string, apartmentID, reservationID, ownerUserID *int64, params AlertParams) error`
and `effects.go:148` `func ResolveAlert(ctx, pool, dedupeKey string) error`;
queue helpers in `go/internal/ubyport/cancelled_notify.go:30`
(`QueueCancelledWithGuestsMail`) and `:103` (`QueueCancelledWithGuestsPush`), with the HTML
builder in `go/internal/mail/cancelled_with_guests.go` (`BuildCancelledWithGuests`).

Mail Go/Python byte parity: golden cases are written by `App/scripts/mail_golden.py`,
pinned by `App/tests/test_mail_golden.py`, and compared byte-for-byte by
`go/internal/mail/cancelled_with_guests_test.go` (`TestCancelledWithGuestsMatchesPython`
reads `cancelled_cases.json` from the golden dir).

Sync entry points: Go `SyncFeed` (`go/internal/ical/syncfeed.go:258`, called per feed from
`SyncAll` at `syncall.go:61`); Python fallback `sync_feed` (`App/app/icalsync.py:854`,
called from `sync_all` and `sync_owner_if_stale`). Reconciliation itself lives in
`go/internal/ical/reconcile.go` / `App/app/icalsync.py`.

i18n: host copy keys live in `App/app/host_i18n.py` (en block ~line 671, cs block ~line
2833) and vi in `App/app/host_vi_i18n.py`; examples:
`host_i18n.py:671-674` `"notification.feed_duplicate_uid.title": "%(property)s: ..."` /
`"notification.reason.feed_duplicate_uid": "..."`, and mail keys
`host_i18n.py:698-700` `"notification.mail_kind.cancelled_with_guests"`,
`"mail.cancelled_with_guests.subject"`, `"mail.cancelled_with_guests.action"`.
`test_*_i18n.py` enforces key parity across en/cs/vi.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ical/doublebooking.go` | new | `checkDoubleBookings(ctx, pool, getenv, apartmentID)`: pair query, raise/resolve `double_booking` alerts, queue mail per new pair |
| `go/internal/ical/doublebooking_test.go` | new | Go tests with the same test pool pattern as `reconcile_test.go` |
| `go/internal/ical/syncfeed.go` | edit | call `checkDoubleBookings` at the end of `SyncFeed` (skip the not_modified/unchanged early returns) |
| `go/internal/mail/double_booking.go` | new | `BuildDoubleBooking(...)` mirroring `cancelled_with_guests.go` |
| `go/internal/mail/double_booking_test.go` | new | golden parity test reading `double_booking_cases.json` |
| `go/internal/ubyport/double_booking_notify.go` | new | `QueueDoubleBookingMail` (and `...Push` only if kept) mirroring `cancelled_notify.go` |
| `App/app/icalsync.py` | edit | `_check_double_bookings(apartment_id)` called at the end of `sync_feed` (Python fallback parity) |
| `App/app/mail_notify.py` | edit | `double_booking(...)` + `build_double_booking(...)` mirroring `cancelled_with_guests` |
| `App/app/mail.py` | edit | add `"double_booking"` to `KINDS` and `HOST_KINDS` |
| `App/app/host_i18n.py` | edit | en + cs keys: `notification.double_booking.title`, `notification.reason.double_booking`, `notification.mail_kind.double_booking`, `mail.double_booking.*` |
| `App/app/host_vi_i18n.py` | edit | vi twins of the same keys |
| `App/scripts/mail_golden.py` | edit | emit `double_booking_cases.json` |
| `App/tests/test_ical_double_booking.py` | new | Python fallback-path tests (alert + outbox row raised, resolved on cancel, no alert on touching ranges, `ignored` not counted) |

No other file may change. No migration, no new column, no new dependency.

## 4. Steps

1. **Detection core (shared semantics, Go then Python).** Pair query, same filters and
   overlap predicate as `dashboard_calendar.overlapping_count` (`status='active'`,
   `archived_at IS NULL`, `date_from < other.date_to AND date_to > other.date_from`),
   self-join with `r2.id > r1.id` on one `apartment_id`, ordered by `r1.id`. For each pair:
   dedupe key `double_booking:{apartment_id}:{min_id}:{max_id}`; raise alert level
   `warning`, kind `double_booking`, `reservation_id` = the newer row's id (so the card's
   default action opens a stay), params `{"property": …, "dates": <fmt_date_range of r1>,
   "other_dates": <fmt range of r2>, "other_source": <r2.source>}`; message/detail = English
   log copy via `notification.double_booking.title` / `reason.double_booking` at
   `DEFAULT_LANGUAGE`. Then list open `double_booking` alerts for the apartment and
   `ResolveAlert` every key whose pair is no longer overlapping. Queue the e-mail only for
   pairs that have no open alert yet (i.e. on raise, not on refresh), idempotency key =
   the same dedupe key, so one mail per pair while open.
2. **Hook points.** Go: end of `SyncFeed` after reconcile succeeds (not on the
   not_modified/unchanged/error early returns). Python: end of `sync_feed` after the
   cancellation sweep, before the final `db.update("ical_feed", ...)`; skip the `suspect`
   early return.
3. **Go alert/mail/push.** Implement `ubyport.QueueDoubleBookingMail` (builder in
   `go/internal/mail/double_booking.go`) following `cancelled_notify.go` +
   `cancelled_with_guests.go` exactly: to the apartment's legal-entity contact e-mail,
   subject `mail.double_booking.subject` (property + both date ranges), body names both
   stays with source labels and dates, button to `/reservations/{newer_id}`, kind
   `double_booking`, idempotency key = dedupe key. Push (`QueueDoubleBookingPush`,
   `push.msg.double_booking.*` keys) only if it is a pure copy of the
   cancelled_with_guests trio; otherwise leave push out and note it in the report.
4. **Python parity.** `_check_double_bookings` in `icalsync.py` (same SQL with `?`
   placeholders via `db.query`, `alerts.raise_alert` / `alerts.resolve`,
   `mail_notify.double_booking`), `"double_booking"` in `mail.py` KINDS + HOST_KINDS.
5. **i18n.** Add the en/cs/vi keys listed in §3. Suggested en title:
   `"%(property)s: two bookings overlap on %(dates)s."`; reason: name the other stay's dates
   and source and say only one guest can stay — check both portals and cancel or move one
   booking. Mail subject e.g. `"Double booking: %(property)s, %(dates)s"`.
6. **Golden mail cases.** Extend `App/scripts/mail_golden.py` with `double_booking_cases.json`
   (≥2 cases: two feeds, one feed twice), Go test reads it like
   `TestCancelledWithGuestsMatchesPython`.
7. **Tests.** New `App/tests/test_ical_double_booking.py` (fixture pattern from
   `tests/test_booking_ical.py`: create account + apartment + two feeds, insert
   reservations directly or via `sync_feed(ics_text=…)`): overlapping pair → exactly one
   open alert with dedupe key + one `email_outbox` row kind `double_booking`; second sync
   unchanged → still one alert, still one outbox row (idempotency); cancel one stay →
   alert resolved; adjacent ranges (r1.date_to == r2.date_from) → no alert; status
   `ignored` → no alert. Go: equivalent cases in `doublebooking_test.go`.
8. Run the test-map rows in §6, plus `python3 scripts/context_lint.py` from the repo root.

## 5. Do not touch

- UbyPort submission/claim logic (`reporting.py`, `claim.py`, `go/internal/statemachine`) —
  hard rule 1.
- Templates and CSS: the alert banner on every page already renders `alert` rows
  (`alerts.py` → base template); no new page, so no new screenshots and no UX-gate
  screenshots are required, but the alerts test row must be green with 0 skipped.
- `docs/`, `go/` files other than those in §3, and any migration: none is needed
  (`alert.dedupe_key` unique partial index `idx_alert_dedupe` already dedupes;
  `email_outbox.idempotency_key` dedupes the mail).
- No new env var, no new dependency (AGENTS.md rule 4).

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_ical_double_booking.py tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_feed_*.py tests/test_dashboard_calendar*.py tests/test_calendar_*.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_ses_mail.py tests/test_mail_*.py tests/test_mail_golden.py tests/test_notification_copy.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_alert*.py tests/test_needs_you*.py tests/test_host_alert_stack_browser.py tests/test_design_alerts_phone.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_*_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30
```
From `go/`:
```
go test ./internal/ical/ ./internal/mail/ ./internal/ubyport/ 2>&1 | tail -30
```
From the repo root:
```
python3 scripts/context_lint.py 2>&1 | tail -30
```

## 7. Acceptance

- [ ] Two active overlapping reservations of one apartment produce exactly one open
      `double_booking` alert (dedupe key `double_booking:{aid}:{min}:{max}`) and one
      `email_outbox` row kind `double_booking`; re-running the sync changes neither count.
- [ ] When the overlap ends (cancel, move, or `ignored`), the alert's `resolved_at` is set.
- [ ] Adjacent stays (`date_to` == other's `date_from`) and non-`active` rows never alert.
- [ ] Alert card renders in en/cs/vi from `notification.double_booking.*` and links to the
      stay page; `test_*_i18n.py` passes (key parity).
- [ ] Go and Python mail builders produce identical bytes for the golden cases
      (`TestDoubleBookingMatchesPython`, `test_mail_golden.py`).
- [ ] All §6 commands green; no file outside §3 changed.

## 8. Stop and ask

Stop and write the report if: an excerpt in §2 is not found verbatim; a §6 test fails twice;
you need a schema change or a new dependency; a file outside §3 must change; the Go test
pool is unavailable in the sandbox (then say so — CI runs `go test`); or you reach 25 tool
calls / ~50k tokens.

## 9. Report

Write `docs/tasks/1166-report.md` (≤600 tokens), set `Status: review`: files changed
(`git diff --stat`), each §6 command with its last 5 lines, §7 ticked, deviations,
questions, owner steps left.

## Risk list (for the reviewer)

`go/internal/ical/doublebooking.go` (new pair query + raise/resolve), `App/app/icalsync.py`
(hook placement vs the in-flight deferrals), `go/internal/mail/double_booking.go` +
`App/app/mail_notify.py` (byte parity), `App/app/mail.py` (kind lists).

## Owner steps

1. Merge the green PR with `scripts/merge-pr-on-green.sh <pr>`; deploy production via
   GitHub Actions → Deploy production.
2. On staging, point two demo feeds of one apartment at overlapping dates and confirm one
   alert banner + one e-mail arrive; cancel one event and confirm the alert clears.
