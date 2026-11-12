# 1166: double-booking alarm from the iCal calendars — Go implementation

Status: todo
Depends on: none | Base commit: 07d7328c (main) | Branch: task/1166-double-booking-alarm, created from vibe/double-booking-brief-2f907d — this brief is delivered on that UNMERGED branch (PR #952 is kept open for the executor, not for merging)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Owner decisions (2026-11-12, orchestrator chat):
1. **Implement in Go only.** Production runs the `ical` job in the Go service
   (`UBYHOST_GO_JOB_KINDS` contains `ical`, docs/ENVIRONMENT.md:53; the handler is
   `go/cmd/ubyhost-web/main.go:266-276` → `ical.SyncAll` every 60 min). The Python
   fallback `App/app/icalsync.py` (used only when `ical` is rolled back out of
   `UBYHOST_GO_JOB_KINDS`, or in local `UBYHOST_ROLE=all` dev) is **not** changed:
   on that path there is no double-booking alarm. Say this in the report.
2. **Fit the implicit state machines without changing them.** No new state, no new
   transition, no `TRANSITIONS` table edit, no `test_sm_*` edit: the mail row is
   inserted only through the already-pinned writer `ubyport.EnqueueMail`
   (`INSERT INTO email_outbox ... 'queued'` = the legal `<none>` → `queued` move in
   `mail.OUTBOX_TRANSITIONS` / `statemachine.Tables["email_outbox.state"]`), and
   alerts are written only through `ubyport.RaiseAlert` / `ubyport.ResolveAlert`
   (alert open/resolved via `resolved_at` is the existing implicit lifecycle;
   `idx_alert_dedupe`, db.py:340, handles the race). The overlap itself is
   **derived, never stored**: recomputed from `reservation` rows on every sync.
   This feature only ever *reads* `reservation` (`status = 'active'`,
   `archived_at IS NULL`).

## 1. Objective

When two active stays of one apartment overlap in dates after an iCal sync (e.g.
Airbnb + Booking.com both booked the same nights), the host gets one in-app alert
per overlapping pair (the existing banner on every page) plus one e-mail per pair
while the pair stays open. The booking site already prevents its own clashes
(`site_booking.mail.host_clash_*`, booking_webhook.py:223) and manual stay creation
warns (`calendar.overlap`, routes/admin.py:3889); feed-vs-feed overlaps are the gap.

## 2. Context (verbatim excerpts — if one is not found, STOP, §8)

Overlap predicate to reuse — `App/app/routes/dashboard_calendar.py:54-61`:
```python
def overlapping_count(apartment_id: int, start: str, end: str) -> int:
    return int(db.query_one(
        "SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ? "
        "AND status = 'active' AND archived_at IS NULL "
        "AND date_from < ? AND date_to > ?",
        (apartment_id, end, start),
    )["n"])
```
`date_to` is exclusive: check-out day == next check-in is NOT an overlap.

Go sync entry — `go/internal/ical/syncall.go:61` calls `SyncFeed` per feed;
`SyncFeed` is `go/internal/ical/syncfeed.go:258`. Its early returns: `not_modified`
(~:282), `unchanged` (~:300), feed error (`failFeedSync`), and the `suspect`
branch that ends with `return stats, nil` after the
`log.Printf("ical_incomplete_feed_retained ...")` line (~:540). The normal path ends
with the final `updateRow(ctx, pool, "ical_feed", feed.ID, feedUpdate)` then
`return stats, nil` (~:612-618).

Pinned writers to reuse (do NOT add new write sites) — `go/internal/ubyport/notify.go:326-349`:
```go
func EnqueueMail(ctx context.Context, pool *pgxpool.Pool, m OutboxMail) (int64, error) {
...		`INSERT INTO email_outbox (idempotency_key, kind, reservation_id, apartment_id, owner_user_id,
		   to_email, cc_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'queued', 0, $10, $10, $10)
		 RETURNING id`,
```
`OutboxMail` fields (notify.go:308-321): Kind, Key, ReservationID, ApartmentID,
OwnerUserID (*int64), To, CC, Subject, Text, HTML, Payload. `payloadJSON()`
(notify.go:413-418) builds the payload from Text/HTML when Payload is empty.
Helpers in the same file: `normaliseEmail` (:67), `cutRunes` (:88), `mailSubjectMax` (:46).

Alert writers — `go/internal/ubyport/effects.go:85`:
```go
func RaiseAlert(ctx context.Context, pool *pgxpool.Pool, level, kind, message, detail, dedupeKey string,
	apartmentID, reservationID, ownerUserID *int64, params AlertParams) error
```
and `effects.go:148` `func ResolveAlert(ctx context.Context, pool *pgxpool.Pool, dedupeKey string) error`.
`AlertParams` is `map[string]any` (effects.go:22); params are stored as JSON
(sort_keys, like Python `json.dumps`), e.g. `ubyport.AlertParams{"date": res.DateFrom, "variant": variant}`
in reconcile.go:393-397.

Mail queue pattern to mirror — `go/internal/ubyport/cancelled_notify.go:30-101`
(`QueueCancelledWithGuestsMail`): check `UBYHOST_MAIL_BACKEND` ∈ {console, ses} →
apartment `legal_entity_id, owner_user_id, internal_name` → `legal_entity.contact_email`
→ `normaliseEmail` → base URLs from `UBYHOST_APP_BASE_URL` else `UBYHOST_PUBLIC_BASE_URL`
(trimmed of trailing `/`) → `mail.BuildCancelledWithGuests(...)` → `EnqueueMail`.
It returns `(0, nil)` when mail is off or there is no address; wrap errors in a
sentinel like `errNotifyCancelled` (errors carry no address/text/key).

Mail builder pattern — `go/internal/mail/cancelled_with_guests.go` (whole file, 56
lines): EN constants at top, `mail.Content{Subject, Text, HTML}`
(submission_problem.go:34-38), and same-package helpers `shell(publicBaseURL, pageTitle, preheader, blocks, footerLines)`
(submission_problem.go:308), `blockHeading` (:220), `blockParagraph` (:225),
`blockButton` (:259), `blockFact` (deadline_at_risk.go:73), `fmtDate` (submission_problem.go:167,
ISO → `DD.MM.YYYY`), `strCancelledFooterSupport` (cancelled_with_guests.go), `esc`.
Host mail is English only (`mail_notify.HOST_MAIL_LANGUAGE = "en"`), so the builder
hardcodes EN copy — same as `BuildCancelledWithGuests`.

Date format — `App/app/validation.py:1203-1218`: `fmt_date` is always `DD.MM.YYYY`,
`fmt_date_range` joins two with an en dash U+2013. So alert params carry
pre-formatted strings and the card copy needs no date logic. In Go use
`fmtDay(iso) = t.Format("02.01.2006")` (see `pyDay` in cancelled_notify.go:131-138).

Alert card rendering — `App/app/alerts.py`: a kind NOT in `_COMPUTED_ALERT_KINDS` is
rendered by `_present_stored` from keys `notification.<kind>.title` and
`notification.<kind>.detail` with the stored `params` (plain `%`-interpolation,
host_i18n.lookup:11033). `action_for` falls back to `notification.open_stay` →
`/reservations/{reservation_id}` when the alert has a `reservation_id` — no
`alerts.py` change needed. `notification.mail_kind.<kind>` is the label a
`mail_failed` card prints (alerts.mail_kind_label; falls back to the raw kind).

i18n files — en and cs blocks in `App/app/host_i18n.py` (insert right after the
`"mail.cancelled_with_guests.action": ...` line, en ≈ :700, cs ≈ :2862); vi keys in
`App/app/host_vi_i18n.py` (same dict that holds
`"notification.cancelled_with_guests.detail"`, grep it). `test_host_i18n.py`
enforces en/cs/vi key parity.

Mail kind lists — `App/app/mail.py`: add `"double_booking"` to `KINDS` (:45, after
`"cancelled_with_guests",` ≈ :63) and to `HOST_KINDS` (:123, after
`"cancelled_with_guests",` ≈ :135). `test_claim_mail.py:1792` asserts
`KINDS == GUEST_KINDS | HOST_KINDS`. The Python sender never builds this kind (Go
inserts the row directly); only the lists change. No Python `mail_notify` builder,
no golden file — this is the Go-only decision above.

Go test scaffolding — `go/internal/ical/reconcile_test.go`: `testPool(t)` (:31, fresh
database from `UBYHOST_TEST_DATABASE_URL`, applies `App/migrations_pg/*.sql`, skips
without the env var — CI sets it), `must` (:75), `seedApartment` (:84),
`seedReservation(t, pool, apartmentID, uid, dateFrom, dateTo)` (:94),
`seedFeed` (:353), `openAlerts(t, pool, key)` (:142). Reuse them; do not redefine.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ical/doublebooking.go` | new | `checkDoubleBookings` + pair query + copy (full code in §4 step 1) |
| `go/internal/ical/syncfeed.go` | edit | two one-line call sites (§4 step 2) |
| `go/internal/mail/double_booking.go` | new | `BuildDoubleBooking` (full code in §4 step 3) |
| `go/internal/mail/double_booking_test.go` | new | builder unit test, no DB (§4 step 6) |
| `go/internal/ubyport/double_booking_notify.go` | new | `QueueDoubleBookingMail` (§4 step 4) |
| `go/internal/ical/doublebooking_test.go` | new | DB tests with `testPool` (§4 step 6) |
| `App/app/mail.py` | edit | `"double_booking"` in `KINDS` and `HOST_KINDS` |
| `App/app/host_i18n.py` | edit | en + cs keys (§4 step 5) |
| `App/app/host_vi_i18n.py` | edit | vi keys (§4 step 5) |
| `App/tests/test_alert_language.py` | edit | one `double_booking` card render test (§4 step 6) |

No other file may change. No migration, no new dependency, no new env var.

## 4. Steps

Branch first: `git fetch origin vibe/double-booking-brief-2f907d && git checkout -b task/1166-double-booking-alarm vibe/double-booking-brief-2f907d` (the brief file itself is on that branch; do not wait for a merge).

### Step 1 — `go/internal/ical/doublebooking.go` (create with exactly this content)

```go
package ical

// Double-booking alarm (brief 1166). After a feed reconciles, every pair of
// active stays of the apartment whose date ranges overlap raises one warning
// alert and queues one host e-mail while the pair stays open. The overlap is
// derived from the reservation rows on every sync, never stored, so the alert
// resolves itself when a stay is cancelled, moved or marked ignored.

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// overlapPairsSQL is the overlapping_count predicate of
// App/app/routes/dashboard_calendar.py:54 as a self-join. date_to is exclusive:
// r1.date_to == r2.date_from is not an overlap.
const overlapPairsSQL = `SELECT r1.id, r1.date_from, r1.date_to, r1.source,
       r2.id, r2.date_from, r2.date_to, r2.source
  FROM reservation r1
  JOIN reservation r2
    ON r2.apartment_id = r1.apartment_id AND r2.id > r1.id
   AND r2.date_from < r1.date_to AND r2.date_to > r1.date_from
 WHERE r1.apartment_id = $1 AND r1.status = 'active' AND r1.archived_at IS NULL
   AND r2.status = 'active' AND r2.archived_at IS NULL
 ORDER BY r1.id, r2.id`

type stayPair struct {
	firstID, secondID             int64
	firstFrom, firstTo            string
	secondFrom, secondTo          string
	firstSource, secondSource     string
}

// fmtDay is validation.fmt_date: ISO to DD.MM.YYYY, unparseable passes through.
func fmtDay(value string) string {
	t, err := time.Parse(dateLayout, value)
	if err != nil {
		return value
	}
	return t.Format("02.01.2006")
}

// fmtRange is validation.fmt_date_range: two dates joined by an en dash (U+2013).
func fmtRange(from, to string) string {
	return fmtDay(from) + " – " + fmtDay(to)
}

// checkDoubleBookings raises or resolves the double_booking alerts of one
// apartment from the stays currently stored. It only reads reservation rows;
// the only writes go through the pinned writers ubyport.RaiseAlert,
// ubyport.ResolveAlert and ubyport.EnqueueMail. The caller logs an error and
// continues: the reconciliation already succeeded and the next sync retries.
func checkDoubleBookings(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, apartmentID int64) error {
	var internalName *string
	err := pool.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1`, apartmentID).Scan(&internalName)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	property := "UbyHost"
	if internalName != nil && *internalName != "" {
		property = *internalName
	}

	rows, err := pool.Query(ctx, overlapPairsSQL, apartmentID)
	if err != nil {
		return err
	}
	var pairs []stayPair
	for rows.Next() {
		var p stayPair
		if err := rows.Scan(&p.firstID, &p.firstFrom, &p.firstTo, &p.firstSource,
			&p.secondID, &p.secondFrom, &p.secondTo, &p.secondSource); err != nil {
			rows.Close()
			return err
		}
		pairs = append(pairs, p)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}

	openRows, err := pool.Query(ctx,
		`SELECT dedupe_key FROM alert WHERE kind = 'double_booking' AND apartment_id = $1 AND resolved_at IS NULL`,
		apartmentID)
	if err != nil {
		return err
	}
	open := map[string]bool{}
	for openRows.Next() {
		var key string
		if err := openRows.Scan(&key); err != nil {
			openRows.Close()
			return err
		}
		open[key] = true
	}
	openRows.Close()
	if err := openRows.Err(); err != nil {
		return err
	}

	current := map[string]bool{}
	for _, p := range pairs {
		key := fmt.Sprintf("double_booking:%d:%d:%d", apartmentID, p.firstID, p.secondID)
		current[key] = true
		if open[key] {
			continue // already alarmed; one e-mail per pair while it stays open
		}
		dates := fmtRange(p.firstFrom, p.firstTo)
		otherDates := fmtRange(p.secondFrom, p.secondTo)
		otherSource := p.secondSource
		if otherSource == "" {
			otherSource = "ical"
		}
		aid, rid := apartmentID, p.secondID
		title := fmt.Sprintf("%s: two bookings overlap on %s.", property, dates)
		detail := fmt.Sprintf("A second booking (%s, source %s) covers the same nights. Only one of them can happen: cancel or move one booking on the portal.", otherDates, otherSource)
		if err := ubyport.RaiseAlert(ctx, pool, "warning", "double_booking", title, detail, key, &aid, &rid, nil,
			ubyport.AlertParams{
				"property": property, "dates": dates,
				"other_dates": otherDates, "other_source": otherSource,
			}); err != nil {
			return err
		}
		if _, err := ubyport.QueueDoubleBookingMail(ctx, pool, getenv, ubyport.DoubleBooking{
			ApartmentID: apartmentID, Property: property, Key: key,
			FirstID: p.firstID, FirstFrom: p.firstFrom, FirstTo: p.firstTo, FirstSource: p.firstSource,
			SecondID: p.secondID, SecondFrom: p.secondFrom, SecondTo: p.secondTo, SecondSource: p.secondSource,
		}); err != nil {
			log.Printf("ical double_booking mail not queued apartment_id=%d key=%s: %v", apartmentID, key, err)
		}
		log.Printf("ical_double_booking apartment_id=%d pair=%d:%d dates=%s other=%s source=%s",
			apartmentID, p.firstID, p.secondID, dates, otherDates, otherSource)
	}
	for key := range open {
		if !current[key] {
			if err := ubyport.ResolveAlert(ctx, pool, key); err != nil {
				return err
			}
			log.Printf("ical_double_booking_resolved apartment_id=%d key=%s", apartmentID, key)
		}
	}
	return nil
}
```

Note: write the en dash in `fmtRange` as the escape `" \u2013 "` in the Go source
(`return fmtDay(from) + " \u2013 " + fmtDay(to)`), never a literal em dash
(test_no_em_dashes). `dateLayout` is `"2006-01-02"` (reconcile.go:55).

### Step 2 — hook into `go/internal/ical/syncfeed.go` (two call sites, nothing else)

Site A, in the `suspect` early-return branch, immediately before its
`return stats, nil` (after the `log.Printf("ical_incomplete_feed_retained ...")` block):
```go
		if err := checkDoubleBookings(ctx, pool, getenv, feed.ApartmentID); err != nil {
			log.Printf("ical_double_booking_check_failed apartment_id=%d: %v", feed.ApartmentID, err)
		}
		return stats, nil
```
Site B, at the very end of `SyncFeed`, after the final
`if err := updateRow(ctx, pool, "ical_feed", feed.ID, feedUpdate); err != nil { ... }`
block, before `return stats, nil`:
```go
	if err := checkDoubleBookings(ctx, pool, getenv, feed.ApartmentID); err != nil {
		log.Printf("ical_double_booking_check_failed apartment_id=%d: %v", feed.ApartmentID, err)
	}
	return stats, nil
```
Do NOT add the call to the `not_modified` / `unchanged` / error early returns.

### Step 3 — `go/internal/mail/double_booking.go` (create with exactly this content)

```go
package mail

// Host e-mail for a double booking (brief 1166). English only, like every host
// mail (mail_notify.HOST_MAIL_LANGUAGE). The shell and blocks are the ones in
// submission_problem.go / cancelled_with_guests.go.

import (
	"strconv"
	"strings"
)

const (
	strDBSubject = "Double booking: %(property)s, %(dates)s"
	strDBTitle   = "%(property)s: two bookings overlap on %(dates)s."
	strDBIntro   = "Two bookings now cover the same nights:"
	strDBAfter   = "Only one of them can happen. Check both portals and cancel or move one of the bookings."
	strDBAction  = "Open stay"
)

// StaySpan is one booking in the mail: its dates and where it came from.
type StaySpan struct {
	From, To, Source string
}

// BuildDoubleBooking composes subject, text and HTML. propertyName is the
// apartment internal name ("UbyHost" when empty, the caller does that);
// openID is the newer reservation id the button opens.
func BuildDoubleBooking(appBaseURL, publicBaseURL, propertyName string, first, second StaySpan, openID int64) Content {
	rangeOf := func(s StaySpan) string { return fmtDate(s.From) + " \u2013 " + fmtDate(s.To) }
	sourceOf := func(s StaySpan) string {
		if s.Source == "" {
			return "ical"
		}
		return s.Source
	}
	dates := rangeOf(first)
	title := strings.NewReplacer("%(property)s", propertyName, "%(dates)s", dates).Replace(strDBTitle)
	subject := strings.NewReplacer("%(property)s", propertyName, "%(dates)s", dates).Replace(strDBSubject)
	line := func(s StaySpan) string { return rangeOf(s) + " (" + sourceOf(s) + ")" }
	stayURL := appBaseURL + "/reservations/" + strconv.FormatInt(openID, 10)
	text := strings.Join([]string{
		title, "", strDBIntro,
		"- " + line(first),
		"- " + line(second),
		"", strDBAfter, "", strDBAction + ": " + stayURL,
	}, "\n")
	html := shell(publicBaseURL, propertyName, title, []string{
		blockHeading(title),
		blockParagraph(strDBIntro, false),
		blockParagraph("- "+line(first), false),
		blockParagraph("- "+line(second), false),
		blockParagraph(strDBAfter, false),
		blockButton(stayURL, strDBAction),
	}, []string{"UbyHost", strCancelledFooterSupport})
	return Content{Subject: subject, Text: text, HTML: html}
}
```

### Step 4 — `go/internal/ubyport/double_booking_notify.go` (create; mirror cancelled_notify.go)

```go
package ubyport

// Queues the host e-mail Python would raise for a double booking (brief 1166).
// Go-only feature: there is no Python builder, so there is no golden parity
// test. Errors carry no address, text or key.

import (
	"context"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

var errNotifyDoubleBooking = errors.New("notify: double-booking mail not queued")

// DoubleBooking carries one overlapping pair plus the alert dedupe key.
type DoubleBooking struct {
	ApartmentID                          int64
	Property, Key                        string
	FirstID, SecondID                    int64
	FirstFrom, FirstTo, FirstSource      string
	SecondFrom, SecondTo, SecondSource   string
}

// QueueDoubleBookingMail returns the email_outbox id, or 0 when nothing is
// queued (mail off, no apartment, no contact address). The idempotency key is
// the alert dedupe key, so one mail per pair ever; a resolved and re-raised
// pair reopens the alert but sends no second mail.
func QueueDoubleBookingMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, b DoubleBooking) (int64, error) {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	if backend != "console" && backend != "ses" {
		return 0, nil
	}
	var entity, owner *int64
	var internalName *string
	err := pool.QueryRow(ctx,
		`SELECT legal_entity_id, owner_user_id, internal_name FROM apartment WHERE id = $1`, b.ApartmentID,
	).Scan(&entity, &owner, &internalName)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errNotifyDoubleBooking
	}
	if entity == nil || *entity == 0 {
		return 0, nil
	}
	var contact *string
	err = pool.QueryRow(ctx, `SELECT contact_email FROM legal_entity WHERE id = $1`, *entity).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errNotifyDoubleBooking
	}
	to := normaliseEmail("")
	if contact != nil {
		to = normaliseEmail(*contact)
	}
	if to == "" {
		return 0, nil
	}
	property := b.Property
	if property == "" {
		if internalName != nil && *internalName != "" {
			property = *internalName
		} else {
			property = "UbyHost"
		}
	}
	publicBase := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL")), "/")
	appBase := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/")
	if appBase == "" {
		appBase = publicBase
	}
	content := mail.BuildDoubleBooking(appBase, publicBase, property,
		mail.StaySpan{From: b.FirstFrom, To: b.FirstTo, Source: b.FirstSource},
		mail.StaySpan{From: b.SecondFrom, To: b.SecondTo, Source: b.SecondSource},
		b.SecondID)
	secondID := b.SecondID
	apartmentID := b.ApartmentID
	return EnqueueMail(ctx, pool, OutboxMail{
		Kind:          "double_booking",
		Key:           b.Key,
		ReservationID: &secondID,
		ApartmentID:   &apartmentID,
		OwnerUserID:   owner,
		To:            to,
		Subject:       content.Subject,
		Text:          content.Text,
		HTML:          content.HTML,
	})
}
```

### Step 5 — i18n keys

`App/app/mail.py`: add `"double_booking",` directly after `"cancelled_with_guests",`
in `KINDS` (≈:63) and in `HOST_KINDS` (≈:135).

`App/app/host_i18n.py`, en block, right after `"mail.cancelled_with_guests.action": "Open stay",` (≈:700):
```python
        "notification.double_booking.title": "%(property)s: two bookings overlap on %(dates)s.",
        "notification.double_booking.detail": "A second booking (%(other_dates)s, source %(other_source)s) covers the same nights. Only one of them can happen: cancel or move one booking on the portal.",
        "notification.mail_kind.double_booking": "double booking",
```
cs block, after `"mail.cancelled_with_guests.action": "Otevřít pobyt",` (≈:2862):
```python
        "notification.double_booking.title": "%(property)s: dvě rezervace se překrývají %(dates)s.",
        "notification.double_booking.detail": "Další rezervace (%(other_dates)s, zdroj %(other_source)s) kryje stejné noci. Proběhnout může jen jedna: jednu z rezervací na portálu zrušte nebo přesuňte.",
        "notification.mail_kind.double_booking": "dvojí rezervace",
```
`App/app/host_vi_i18n.py`, in the same dict as `"notification.cancelled_with_guests.detail"`:
```python
    "notification.double_booking.title": "%(property)s: hai đặt phòng trùng nhau vào %(dates)s.",
    "notification.double_booking.detail": "Một đặt phòng thứ hai (%(other_dates)s, nguồn %(other_source)s) trùng các đêm này. Chỉ một có thể diễn ra: hãy hủy hoặc dời một đặt phòng trên cổng.",
    "notification.mail_kind.double_booking": "đặt phòng trùng lặp",
```
Placeholders must match the Go params exactly: `property`, `dates`, `other_dates`, `other_source`.

### Step 6 — tests

`go/internal/mail/double_booking_test.go` (no DB): build with
`BuildDoubleBooking("https://app.example.test", "https://app.example.test", "Test flat",
  StaySpan{"2027-05-05", "2027-05-08", "airbnb"}, StaySpan{"2027-05-07", "2027-05-10", "booking"}, 42)`
and assert Subject contains "Test flat" and "05.05.2027", Text contains both ranges
and "airbnb"/"booking", HTML contains `/reservations/42`.

`go/internal/ical/doublebooking_test.go` (DB; reuse `testPool`, `must`,
`seedApartment`, `seedReservation`, `openAlerts` from reconcile_test.go — same
package, just call them):
```go
func testGetenv(key string) string {
	switch key {
	case "UBYHOST_MAIL_BACKEND":
		return "console"
	case "UBYHOST_PUBLIC_BASE_URL", "UBYHOST_APP_BASE_URL":
		return "https://app.example.test"
	}
	return ""
}
```
Tests (use `context.Background()`):
1. `TestDoubleBookingRaisesAlertAndMailOnce`: seed apartment; two overlapping
   reservations (`seedReservation(t, pool, aid, "abnb-1", "2027-05-05", "2027-05-08")`
   and `("b-1", "2027-05-07", "2027-05-10")`); `UPDATE reservation SET source='booking' WHERE uid='b-1'`;
   run `checkDoubleBookings(ctx, pool, testGetenv, aid)`; assert
   `openAlerts(t, pool, fmt.Sprintf("double_booking:%d:%d:%d", aid, r1, r2)) == 1`;
   assert one `email_outbox` row with `kind='double_booking'` and
   `idempotency_key` = that key, `state='queued'`; run `checkDoubleBookings` again;
   assert still 1 alert and still 1 outbox row. Then
   `UPDATE reservation SET status='cancelled' WHERE id = <r2>`; run again; assert the
   alert row now has `resolved_at IS NOT NULL`.
   (Seeding the mail path also needs a legal entity: insert into `legal_entity`
   the columns the migrations mark NOT NULL without default plus `contact_email`,
   and set `apartment.legal_entity_id`; grep `App/migrations_pg/` for the exact
   columns. Without it the mail is skipped by design and the outbox assertion
   fails — so seed it.)
2. `TestDoubleBookingIgnoresAdjacentAndIgnored`: r1 `2027-06-01..2027-06-03`,
   r2 `2027-06-03..2027-06-05` (touching, not overlapping) → no alert; r3 active
   `2027-06-10..2027-06-12` overlapping r4 with `status='ignored'` → no alert.
3. `TestDoubleBookingFiresFromSyncFeed`: `seedFeed`, then `SyncFeed(ctx, pool, testGetenv, feed, FetchOptions{}, &icsText)`
   where icsText is a minimal VCALENDAR with two overlapping VEVENTs (copy the
   shape from `go/internal/ical/testdata` or `parse_test.go`); assert one open
   `double_booking` alert for the apartment.

`App/tests/test_alert_language.py`: add one test mirroring
`test_a_calendar_failure_card_names_the_feed_and_the_error` (:96): raise via
`alerts.raise_alert("warning", "double_booking", "...", "...", dedupe_key="double_booking:1:2:3",
apartment_id=<seeded>, reservation_id=<seeded>, params={"property": "Test flat",
"dates": "05.05.2027 – 08.05.2027", "other_dates": "07.05.2027 – 10.05.2027",
"other_source": "booking"})`, then `alerts.present(row, "en")` and `("cs")` and
assert the en title contains "05.05.2027 – 08.05.2027" and the cs title starts
with "Test flat: dvě rezervace". Look at how that test seeds rows (it uses db.init_db
and direct inserts — copy its fixture).

### Step 7 — run (each ending `| tail -30`)

```
cd go && gofmt -l . && go build ./... && go vet ./internal/ical/ ./internal/mail/ ./internal/ubyport/ 2>&1 | tail -30
cd go && go test ./internal/ical/ ./internal/mail/ ./internal/ubyport/ 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_sm_queues.py tests/test_sm_go_parity.py tests/test_host_i18n.py tests/test_alert_language.py tests/test_notification_copy.py tests/test_claim_mail.py -q --tb=short -x 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_feed_*.py tests/test_dashboard_calendar*.py tests/test_calendar_*.py -q --tb=short -x 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```
The first pytest row must pass **unchanged** — that is the proof the feature adds
no writer outside the pinned state machines. Go tests skip without
`UBYHOST_TEST_DATABASE_URL` locally; CI provides it.

## 5. Do not touch

- `App/app/icalsync.py`, `App/app/scheduler.py`, `App/app/alerts.py`,
  `go/internal/statemachine/tables.go`, all `App/tests/test_sm_*.py` — the feature
  reuses pinned writers; any edit there fails the point of this brief.
- Templates/CSS: the alert banner already renders `alert` rows; no new page, so no
  UX-gate screenshots. `test_alert_language.py` covers the card copy.
- No push notification (owner asked for e-mail + in-app only), no migration, no new
  dependency, no new env var, no new personal-data column (hard rules 1-4).
- No comment in any new Go file may contain the literal text `INSERT INTO email_outbox`
  or `UPDATE email_outbox` — `test_sm_queues.py` scans Go sources as text.

## 6. Commands — as in §4 step 7.

## 7. Acceptance

- [ ] `gofmt -l go/` empty; `go build ./...` clean.
- [ ] Overlapping pair → exactly one open `double_booking` alert (dedupe
      `double_booking:{aid}:{min}:{max}`, `reservation_id` = max id) and one
      `email_outbox` row kind `double_booking`, state `queued`; re-running the check
      changes neither count.
- [ ] When the overlap ends (cancel/move/`ignored`), the alert's `resolved_at` is set.
- [ ] Adjacent stays and non-`active` rows never alert.
- [ ] `test_sm_queues.py` and `test_sm_go_parity.py` pass with zero edits — no new
      writer of any pinned column, no table change.
- [ ] en/cs/vi key parity tests pass; the card renders in all three languages
      (`test_alert_language.py` new case).
- [ ] All §4 step 7 commands green; no file outside §3 changed.

## 8. Stop and ask

Stop and write the report if: an excerpt in §2 is not found verbatim; a §4 command
fails twice; `UBYHOST_TEST_DATABASE_URL` is unavailable and you cannot verify the
Go DB tests (say so, CI runs them); a file outside §3 must change; you need a
migration or dependency; or you reach 25 tool calls / ~50k tokens.

## 9. Report

Write `docs/tasks/1166-report.md` (≤600 tokens), set `Status: review`: files changed
(`git diff --stat`), each command with its last 5 lines, §7 ticked, deviations,
and explicitly: "Python fallback path (icalsync.py) intentionally has no
double-booking alarm — owner decision, Go only."

## Risk list (for the reviewer)

`go/internal/ical/doublebooking.go` (pair SQL, raise/resolve logic),
`go/internal/ical/syncfeed.go` (the two call sites vs the early returns),
`go/internal/ubyport/double_booking_notify.go` (EnqueueMail reuse — the only
`email_outbox` write), `App/app/mail.py` (kind lists), the three i18n files.

## Owner steps

1. Merge the green PR with `scripts/merge-pr-on-green.sh <pr>`; deploy production
   via GitHub Actions → Deploy production.
2. On staging, add two demo calendars of one apartment with overlapping nights
   (or insert two overlapping reservations directly) and confirm one alert banner
   + one console-logged e-mail appear; cancel one and confirm the alert clears on
   the next ical job run (≤60 min).
