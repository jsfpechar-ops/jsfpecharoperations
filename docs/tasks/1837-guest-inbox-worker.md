# 1837: Guest inbox worker core: claim, decode, re-check, one-transaction guest write, `received_at` as the legal time

Status: todo
Depends on: 1834, 1835, 1836 | Base commit: current tip of the working branch (written at 4d3bc7bc) | Branch: task/1837-guest-inbox-worker
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (filing deadlines and legal submission time; exact diffs only; orchestrator reads the full diff before ready)
Plan: [guest-form-isolation](../plans/guest-form-isolation.md) section 3 rules 2, 3, 4 and 6; section 7 (alerts); section 8 rollout step 2.

> **One PR mode.** Commit each step as `1837 step k`. Never push, merge or deploy. Hand the owner the steps in "Owner steps".

## Open questions (orchestrator answers before execute)

Step 0 stops until each line below carries `Answer:`.

1. **Which record says a link is revoked.** This brief holds a submission as `link_revoked` when `guest_form_snapshot` has no row for its `token_hash` with `expires_at > received_at`. That makes the snapshot (written by the app in the same transaction as every link change, brief 1836) the authority. Recommended answer: yes, the snapshot is the authority.
2. **What counts as "already registered on this stay"** (plan rule 4, kept once, `done` + `already_registered`). This brief: a live guest (`archived_at IS NULL`) on the same reservation with the same normalised document number, or with the same surname, first name and birth date (case-insensitive names). Today's Python path has no duplicate check at all. Recommended answer: approve.
3. **"Today" of the shared checks.** Python uses the server date at save time (`date.today()` for two-digit birth years and age checks). The worker uses the Prague calendar date of `received_at`, so a late worker cannot change a guest's age or birth year. Recommended answer: Prague date of `received_at`.
4. **Over-count changes what is filed.** Python today refuses a form when the stay is full (nothing saved). Plan rule 4 (2026-11-09 filing decision) says register and file it, `done` + `over_count`. Rule 1 applies: confirm the 2026-11-09 decision covers inbox submissions. Recommended answer: yes, per plan rule 4.
5. **`filled_ip`.** The contract carries no IP address (privacy first). Inbox guests get `filled_ip` NULL. Recommended answer: NULL.
6. **Where the guest row keeps `received_at`** (so a later brief can delete inbox rows; asked for by brief 1839). The `guest` table has no `received_at` column. This brief writes `filled_at` (and `notice_ack_at`, `created_at`, `updated_at`) as `UTCStamp(received_at)` for every inbox guest, child or adult, so `filled_at` already is the received time, with no schema change. A separate `received_at` column would be a new `App/migrations_pg/` file and its own brief. Recommended answer: `filled_at` is the record; no schema change.
7. **A row the host attached to another stay (brief 1838).** The worker always takes the stay from the `guest_inbox.reservation_id` column, never from the payload. When that column differs from the payload's `reservation_id`, the host attached it by hand: the worker then skips the link checks (snapshot present, stay in the link's list, same property) and keeps only "stay exists and is active", the shared checks, already registered and the count. Without the snapshot the default purpose is empty, as for a link with none. If the host attaches it back to the same stay it was sent for (for example a stay restored), the link checks still apply and it may be held again. Recommended answer: approve; if 1838 wants a re-attach to the same stay to bypass the link checks too, 1838 adds an explicit marker column and 1837c reads it.

Answers:

1. Answer: yes, recommended (orchestrator, 2026-11-17). yes, recommended (orchestrator, 2026-11-17).
2. Answer: yes, recommended (orchestrator, 2026-11-17). yes, recommended (orchestrator, 2026-11-17).
3. Answer: Prague date of `received_at` (orchestrator, 2026-11-17). Prague date of `received_at` (orchestrator, 2026-11-17).
4. Answer: OWNER (open: confirm the 2026-11-09 decision covers inbox submissions). OWNER (open: confirm the 2026-11-09 decision covers inbox submissions).
5. Answer: OWNER (open: NULL recommended). OWNER (open: NULL recommended).
6. Answer: yes, recommended (orchestrator, 2026-11-17). yes, recommended (orchestrator, 2026-11-17).
7. Answer: yes, recommended (orchestrator, 2026-11-17). yes, recommended (orchestrator, 2026-11-17).

## 1. Objective

Add `go/internal/guestinbox`: the code that claims one `guest_inbox` row with `FOR UPDATE SKIP LOCKED`, decodes it, runs the shared checks again, decides `done` / `done` with host note / `held`, and in one transaction writes the guest row and marks the inbox row, with `signed_at`, `notice_ack_at`, `filled_at`, `created_at` and `updated_at` all taken from `received_at`. Nothing registers or runs the worker yet, and the old form path is unchanged, so nothing about what is filed, or when, changes in production.

## 2. Context

Hard rules: 1 filing correctness first (this brief changes nothing that is filed: the package is not wired; brief 1837c wires it only after the parity golden passes); 2 privacy (host notes and alerts carry codes and field names, never guest values); 4 no new dependency (pgx, already in `go/go.mod`); 5 SQL is Postgres; 8 never push to `main`; 11 Go first (no Python file changes).

Plan rules pasted (section 3):

- Rule 2: "`received_at` is the legal time of submission. Signed-at times, the consent record and UbyPort deadlines are computed from it, never from the processing time."
- Rule 3: "The app worker claims inbox rows with `FOR UPDATE SKIP LOCKED` and, in one transaction, writes the guest rows and marks the inbox row `done`. The unique idempotency key makes a repeated submission a no-op."
- Rule 4: three outcomes: `done`; `done` with a note (already registered on this stay, kept once; more guests than expected, registered and filed); `held` (link revoked, stay cancelled or moved). "A stored submission that fails a shared check on processing is a bug, not a guest error: it is `held`, raises the disagreement alert."
- Rule 6: the app runs the shared checks again on processing; a disagreement is an alert.

**The UbyPort deadline.** `go/internal/deadlines/deadlines.go`: `ReportingDeadline(checkIn)` is "23:59:59 on the third working day of the window that opens on checkIn". It depends on the stay's first day only. So for an inbox guest the deadline is `ReportingDeadline(stay_from)`, the same as the Python path for the same stay, whatever `received_at` or the processing time. The test pins this.

**Today's write path** (`App/app/routes/guest.py`, `guest_form_save`, line 2362, new guest only: the contract has no `guest_id`, so inbox submissions are always new guests):

| Python step (guest.py) | What it writes | Where in Go |
|---|---|---|
| `values = validation.normalise_guest(raw, clamp=False)`, `_locked_stay_dates` (booking `date_from`/`date_to`) | guest columns | **1837** `BuildRow` |
| `payload`: `signed_at` (None for a child), `notice_version` (`config.GUEST_NOTICE_VERSION`, env `UBYHOST_GUEST_NOTICE_VERSION`, default `1.0`), `notice_lang`, `notice_ack_at`, `filled_at`, `filled_ip`, `entered_by="guest"`, `updated_at`, `submit_state` (`pending` / `not_required`), `last_errors=None` | guest columns, all from `now = db.utcnow()` | **1837**, all from `received_at` |
| `db.insert_in(cur, "guest", ...)` with `is_lead`, `created_at`, encrypted columns via `ENCRYPTED_GUEST_COLUMNS` (`doc_number`, `visa_number`, `signature_png`, `birth_date`, `res_street`, `res_city` -> `*_enc`, plain column NULL) | guest row | **1837** `insertGuest` |
| `db.lock_key(cur, "reservation", id)` then capacity re-check | advisory lock | **1837** (same lock key) |
| `headcount.apply_declared_in(cur, reservation_id, party_size)` when no expected count | `reservation.declared_guests` | **1837b** (1837 leaves such rows `new`: `ErrNotPorted`) |
| `_sign_for_fields(...)` for a child (`signed_for_*`) and `_link_signed_children(...)` for an adult | guest `signed_for_*` columns | **1837b** (1837 writes them NULL; the contract has no `sign_for_ids`, which 1837b adds as contract field or drops, orchestrator decides there) |
| `headcount.record(...)` | headcount audit | **1837b** |
| `db.audit("guest_form_saved", ...)` | audit row | **1837b** |
| `reporting.submit_stay_if_complete(apartment_id, reservation_id)` (UbyPort immediate send; Go has `ubyport.RefreshRegistrationCompletedAt` and `ubyport.SubmitForApartment`) | registration_completed_at, submission | **1837b** |
| `door_codes.on_registration_complete(reservation_id)` | door codes | **1837b** |
| `claim.maybe_notify_completion(...)` (completion mail) | mail queue | **1837b** |
| `guest_draft.delete(...)` | draft row | not needed (the guest program owns its drafts) |
| passport photo `passport_photos.save_photo` | photo file | **1842** (spool and uploads) |
| registering the worker as a background task, Python parity golden of the whole guest row, alert wiring | | **1837c** |

**Retention constraint (brief 1839).** Every inbox row the worker settles, `done` (with or without a host note) and `held`, gets `processed_at` and its status in the same transaction as the guest row (`finishSQL`, before `Commit`). 1839 nulls `payload_enc` only for `done` rows whose `processed_at` is older than 7 days, so a `done` row without `processed_at` would keep guest data for ever. `processed_at` is the processing time (it is not a legal time). The guest row keeps the received time in `filled_at` (open question 6).

**Contract with brief 1838 (host page).** The stay is the `guest_inbox.reservation_id` column, set by the guest program or by the host's "attach"; the worker never takes it from the payload (open question 7). Host notes of `done` rows are exactly `already_registered` and `over_count`. 1838 dismisses a row by setting `status = 'done'`, `host_note = 'dismissed'` and `processed_at`; the worker claims `status = 'new'` only, so it never picks such a row up.

1837b and 1837c are separate briefs (orchestrator writes them; each `Depends on` the one before). The old form path writing through the inbox (plan rollout step 2) is a later brief, not 1837b or 1837c.

**Anchors** (verify each with `grep -nF`; if one is missing, STOP):

`go/internal/deadlines/deadlines.go`:
```
func ReportingDeadline(checkIn time.Time) time.Time {
```
```
func LocalNow(now time.Time) time.Time {
```
`go/internal/headcount/headcount.go`:
```
func Expected(override, declared, reduced *int64) *int64 {
```
`go/internal/secure/datakeys.go`:
```
func (m *MultiFernet) EncryptString(plain string) (string, error) {
```
`go/internal/secure/fernet.go`:
```
func (m *MultiFernet) Decrypt(token string, ttl time.Duration, now time.Time) ([]byte, error) {
```
`go/internal/validation/validation.go`:
```
func GuestIsReportable(nationality string) bool {
```
Brief 1835, merged (`go/internal/guestcontract/check.go`, `payload.go`, `go/internal/validation`):
```
func CheckNewGuest(g GuestForm, cfg FormConfig, st Stay, today time.Time) []validation.Issue {
```
```
func DecodePayload(keys *secure.MultiFernet, data []byte) (Submission, error) {
```
```
func NormaliseGuest(raw map[string]string, today time.Time) GuestRow {
```
```
func CertainlyUnderAge(birth string, when *time.Time, years int) bool {
```
Brief 1834, merged: `App/migrations_pg/` holds a file containing `CREATE TABLE guest_inbox`.
`App/app/reporting.py`: `PENDING = "pending"` and `NOT_REQUIRED = "not_required"`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/guestinbox/row.go` | create | `UTCStamp`, `LegalToday`, `BuildRow`, `Deadline`, `Decide` (pure) |
| `go/internal/guestinbox/worker.go` | create | `Worker`, `ProcessOne`, `ProcessBatch`, SQL |
| `go/internal/guestinbox/row_test.go` | create | signed-at, child, deadline, outcomes (no database) |
| `go/internal/guestinbox/worker_test.go` | create | claim SQL, idempotency key (database; skips without `UBYHOST_TEST_DATABASE_URL`) |

No other file may change. No file under `App/app/` changes.

## 4. Steps

**Step 0.** Check that every open question has `Answer:` followed by text. If one is empty, STOP and write the report as `blocked`.
Command: `grep -c '^[1-7]\. Answer: .\+' docs/tasks/1837-guest-inbox-worker.md 2>&1 | tail -30`. Expected: `7`.

**Step 1.** Verify the anchors of section 2.
Command:
```
cd go && grep -nF 'func ReportingDeadline(checkIn time.Time) time.Time {' internal/deadlines/deadlines.go; grep -nF 'func CheckNewGuest(' internal/guestcontract/check.go; grep -nF 'func DecodePayload(' internal/guestcontract/payload.go; grep -rnF 'func CertainlyUnderAge(' internal/validation/; grep -nF 'func Expected(override, declared, reduced *int64) *int64 {' internal/headcount/headcount.go; grep -lF 'CREATE TABLE guest_inbox' ../App/migrations_pg/*.sql 2>&1 | tail -30
```
Expected: one line per grep, the last one a file name. Any empty result: STOP (1834 or 1835 not merged).

**Step 2.** Create `go/internal/guestinbox/row.go` with exactly this content:

```go
// Package guestinbox is the app side of the guest form contract
// (docs/plans/guest-form-isolation.md section 3, rules 2-4 and 6): it turns one
// guest_inbox row into a guest row. received_at is the legal time of the
// submission: every time written to the guest row comes from it, never from
// the clock of the worker. Brief 1837.
package guestinbox

import (
	"sort"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// Submit states, as reporting.PENDING and reporting.NOT_REQUIRED.
const (
	SubmitPending     = "pending"
	SubmitNotRequired = "not_required"
)

// guest_inbox statuses and host notes. Notes are codes and field names, never
// guest values.
const (
	StatusDone = "done"
	StatusHeld = "held"

	NoteDuplicate      = "already_registered"
	NoteOverCount      = "over_count"
	NoteLinkRevoked    = "link_revoked"
	NoteStayCancelled  = "stay_cancelled"
	NoteStayMoved      = "stay_moved"
	NoteUnsupported    = "unsupported_version"
	NoteUndecodable    = "undecodable"
	NoteDisagreePrefix = "check_disagreement:"
)

// UTCStamp is db.utcnow() for the instant t: whole seconds, UTC, "+00:00".
func UTCStamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05-07:00")
}

// LegalToday is the Prague calendar date of receivedAt (UTC midnight): the
// "today" of the shared checks and of two-digit birth years.
func LegalToday(receivedAt time.Time) time.Time {
	l := deadlines.LocalNow(receivedAt)
	return time.Date(l.Year(), l.Month(), l.Day(), 0, 0, 0, 0, time.UTC)
}

// Row is one new guest row as guest_form_save builds it. Stamp is
// notice_ack_at, filled_at, created_at and updated_at.
type Row struct {
	Values        validation.GuestRow
	Child         bool
	SignedAt      *string
	Stamp         string
	Lang          string
	NoticeVersion string
	SubmitState   string
}

// BuildRow is the payload of guest_form_save for a new guest. It takes no
// clock: every time in it is receivedAt.
func BuildRow(sub guestcontract.Submission, defaultPurpose, dateFrom, dateTo string, receivedAt time.Time, noticeVersion string) Row {
	raw := validation.GuestFormRaw(sub.Guest.Fields(), defaultPurpose)
	v := validation.NormaliseGuest(raw, LegalToday(receivedAt))
	v.StayFrom, v.StayTo = dateFrom, dateTo
	child := validation.CertainlyUnderAge(v.BirthDate, isoDate(dateFrom), guestcontract.UnderSignAge)
	v.SignaturePNG = validation.Strip(sub.Guest.Signature)
	if child {
		// 1089: a child's signature is neither asked for nor kept.
		v.SignaturePNG = ""
	}
	stamp := UTCStamp(receivedAt)
	r := Row{Values: v, Child: child, Stamp: stamp, Lang: sub.Lang, NoticeVersion: noticeVersion, SubmitState: SubmitNotRequired}
	if !child {
		s := stamp
		r.SignedAt = &s
	}
	if validation.GuestIsReportable(v.Nationality) {
		r.SubmitState = SubmitPending
	}
	return r
}

// Deadline is the UbyPort reporting deadline of the row: three working days
// from the stay's first day. It depends on the stay only, so neither the
// submission time nor the processing time can move it.
func Deadline(r Row) (time.Time, bool) {
	from := isoDate(r.Values.StayFrom)
	if from == nil {
		return time.Time{}, false
	}
	return deadlines.ReportingDeadline(*from), true
}

func isoDate(s string) *time.Time {
	t, ok := validation.ParseISODate(s)
	if !ok {
		return nil
	}
	return &t
}

// Live is a guest already on the stay (archived_at IS NULL), decrypted.
type Live struct {
	ID        int64
	Surname   string
	FirstName string
	BirthDate string
	DocNumber string
}

// Facts is what the worker read in its transaction.
type Facts struct {
	SnapshotFound        bool
	SnapshotApartment    int64
	Config               guestcontract.FormConfig
	ReservationFound     bool
	ReservationApartment int64
	Active               bool
	Expected             *int64
	Live                 []Live
	// Attached is true when the host attached the row to another stay
	// (guest_inbox.reservation_id differs from the payload, brief 1838).
	Attached bool
}

// Decision is the outcome for one inbox row.
type Decision struct {
	Status      string
	Note        string
	Insert      bool
	NeedsCount  bool
	DuplicateOf int64
	Disagree    bool
}

// Decide applies plan section 3 rule 4, in this order: link, stay, shared
// checks, already registered, expected count.
func Decide(reservationID int64, r Row, f Facts, issues []validation.Issue) Decision {
	switch {
	case !f.Attached && !f.SnapshotFound:
		return Decision{Status: StatusHeld, Note: NoteLinkRevoked}
	case !f.ReservationFound || !f.Active:
		return Decision{Status: StatusHeld, Note: NoteStayCancelled}
	case !f.Attached && (f.ReservationApartment != f.SnapshotApartment || !linkCovers(f.Config, reservationID)):
		return Decision{Status: StatusHeld, Note: NoteStayMoved}
	}
	if fields := errorFields(issues); len(fields) > 0 {
		return Decision{Status: StatusHeld, Note: NoteDisagreePrefix + strings.Join(fields, ","), Disagree: true}
	}
	if id := duplicateOf(r.Values, f.Live); id != 0 {
		return Decision{Status: StatusDone, Note: NoteDuplicate, DuplicateOf: id}
	}
	if f.Expected == nil {
		return Decision{Status: StatusDone, Insert: true, NeedsCount: true}
	}
	if int64(len(f.Live)) >= *f.Expected {
		return Decision{Status: StatusDone, Note: NoteOverCount, Insert: true}
	}
	return Decision{Status: StatusDone, Insert: true}
}

func linkCovers(cfg guestcontract.FormConfig, reservationID int64) bool {
	for _, s := range cfg.Stays {
		if s.ReservationID == reservationID {
			return true
		}
	}
	return false
}

func errorFields(issues []validation.Issue) []string {
	seen := map[string]bool{}
	var out []string
	for _, i := range issues {
		if i.Severity == "warning" || seen[i.Field] {
			continue
		}
		seen[i.Field] = true
		out = append(out, i.Field)
	}
	sort.Strings(out)
	return out
}

func duplicateOf(v validation.GuestRow, live []Live) int64 {
	for _, g := range live {
		if v.DocNumber != "" && strings.EqualFold(v.DocNumber, g.DocNumber) {
			return g.ID
		}
		if v.Surname != "" && v.FirstName != "" && v.BirthDate != "" &&
			strings.EqualFold(v.Surname, g.Surname) &&
			strings.EqualFold(v.FirstName, g.FirstName) &&
			v.BirthDate == g.BirthDate {
			return g.ID
		}
	}
	return 0
}
```

Command: `cd go && gofmt -l internal/guestinbox && go build ./internal/guestinbox/ 2>&1 | tail -30`. Expected: no output.

**Step 3.** Create `go/internal/guestinbox/worker.go` with exactly this content:

```go
package guestinbox

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// Alerter raises an owner alert. Text is codes and ids only.
type Alerter interface {
	Raise(ctx context.Context, dedupeKey, text string) error
}

// DeclareFunc is headcount.apply_declared_in on the open transaction
// (brief 1837b).
type DeclareFunc func(ctx context.Context, tx pgx.Tx, reservationID int64, partySize int) error

// ErrNotPorted leaves a row `new` while the declared count is not in Go.
var ErrNotPorted = errors.New("guestinbox: declared guest count not ported yet (brief 1837b)")

// Worker processes guest_inbox rows. Now is used for processed_at only.
type Worker struct {
	Pool          *pgxpool.Pool
	Keys          *secure.MultiFernet
	NoticeVersion string
	Alerts        Alerter
	Declare       DeclareFunc
	Now           func() time.Time
}

// Result is one processed row, for the after-commit effects of brief 1837b.
type Result struct {
	InboxID       int64
	ReservationID int64
	ApartmentID   int64
	GuestID       int64
	Status        string
	Note          string
}

const claimSQL = `SELECT id, token_hash, reservation_id, contract_version, received_at, payload_enc
FROM guest_inbox WHERE status = 'new'
ORDER BY received_at, id LIMIT 1 FOR UPDATE SKIP LOCKED`

const finishSQL = `UPDATE guest_inbox SET status = $1, host_note = NULLIF($2, ''),
attempts = attempts + 1, processed_at = $3 WHERE id = $4`

const bumpSQL = `UPDATE guest_inbox SET attempts = attempts + 1 WHERE id = $1 AND status = 'new'`

const insertGuestSQL = `INSERT INTO guest (reservation_id, is_lead, surname, first_name,
nationality, res_country, purpose, note, stay_from, stay_to,
birth_date_enc, doc_number_enc, visa_number_enc, res_street_enc, res_city_enc, signature_png_enc,
signed_at, notice_version, notice_lang, notice_ack_at, filled_at, entered_by,
created_at, updated_at, submit_state)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
$17, $18, $19, $20, $21, 'guest', $22, $23, $24) RETURNING id`

// ProcessOne claims and settles one `new` row. ok is false when none is left.
func (w *Worker) ProcessOne(ctx context.Context) (res Result, ok bool, err error) {
	tx, err := w.Pool.Begin(ctx)
	if err != nil {
		return res, false, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck // no-op after commit

	var tokenHash string
	var version int
	var receivedAt time.Time
	var payload []byte
	err = tx.QueryRow(ctx, claimSQL).Scan(&res.InboxID, &tokenHash, &res.ReservationID, &version, &receivedAt, &payload)
	if errors.Is(err, pgx.ErrNoRows) {
		return res, false, nil
	}
	if err != nil {
		return res, false, err
	}
	// Same key as db.lock_key(cur, "reservation", id) in guest_form_save.
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "reservation", int32(res.ReservationID)); err != nil {
		return res, true, err
	}
	if !guestcontract.Supported(version) {
		return w.finish(ctx, tx, res, Decision{Status: StatusHeld, Note: NoteUnsupported})
	}
	sub, err := guestcontract.DecodePayload(w.Keys, payload)
	if err != nil {
		return w.finish(ctx, tx, res, Decision{Status: StatusHeld, Note: NoteUndecodable})
	}
	// The stay is the guest_inbox.reservation_id column (the guest program's
	// choice, or the host's "attach" in brief 1838), never the payload.
	f, dateFrom, dateTo, err := w.loadFacts(ctx, tx, tokenHash, res.ReservationID, receivedAt)
	if err != nil {
		return res, true, err
	}
	f.Attached = sub.ReservationID != res.ReservationID
	res.ApartmentID = f.ReservationApartment
	row := BuildRow(sub, f.Config.DefaultPurpose, dateFrom, dateTo, receivedAt, w.NoticeVersion)
	st := guestcontract.Stay{ReservationID: res.ReservationID, DateFrom: dateFrom, DateTo: dateTo}
	if f.Expected != nil {
		n := int(*f.Expected)
		st.ExpectedGuests = &n
	}
	issues := guestcontract.CheckNewGuest(sub.Guest, f.Config, st, LegalToday(receivedAt))
	d := Decide(res.ReservationID, row, f, issues)
	if d.NeedsCount {
		if w.Declare == nil {
			return res, true, ErrNotPorted
		}
		n, _ := strconv.Atoi(validation.Strip(sub.Guest.PartySize))
		if err := w.Declare(ctx, tx, res.ReservationID, n); err != nil {
			return res, true, err
		}
		if len(f.Live) >= n {
			d.Note = NoteOverCount
		}
	}
	if d.Insert {
		id, err := w.insertGuest(ctx, tx, res.ReservationID, row)
		if err != nil {
			return res, true, err
		}
		res.GuestID = id
	}
	return w.finish(ctx, tx, res, d)
}

// ProcessBatch settles up to max rows. On an error the row stays `new` with
// attempts raised, and the batch stops.
func (w *Worker) ProcessBatch(ctx context.Context, max int) (int, error) {
	done := 0
	for done < max {
		res, ok, err := w.ProcessOne(ctx)
		if err != nil {
			if res.InboxID != 0 {
				_, _ = w.Pool.Exec(ctx, bumpSQL, res.InboxID)
			}
			return done, err
		}
		if !ok {
			return done, nil
		}
		done++
	}
	return done, nil
}

func (w *Worker) finish(ctx context.Context, tx pgx.Tx, res Result, d Decision) (Result, bool, error) {
	res.Status, res.Note = d.Status, d.Note
	now := time.Now
	if w.Now != nil {
		now = w.Now
	}
	if _, err := tx.Exec(ctx, finishSQL, d.Status, d.Note, now().UTC(), res.InboxID); err != nil {
		return res, true, err
	}
	if err := tx.Commit(ctx); err != nil {
		return res, true, err
	}
	if d.Status == StatusHeld && w.Alerts != nil {
		key := fmt.Sprintf("guest_inbox_held:%d", res.InboxID)
		if d.Disagree {
			key = fmt.Sprintf("guest_inbox_disagreement:%d", res.InboxID)
		}
		_ = w.Alerts.Raise(ctx, key, fmt.Sprintf("guest inbox %d held: %s", res.InboxID, d.Note))
	}
	return res, true, nil
}

func (w *Worker) loadFacts(ctx context.Context, tx pgx.Tx, tokenHash string, reservationID int64, receivedAt time.Time) (Facts, string, string, error) {
	var f Facts
	var cfgJSON []byte
	err := tx.QueryRow(ctx,
		`SELECT apartment_id, form_config FROM guest_form_snapshot WHERE token_hash = $1 AND expires_at > $2`,
		tokenHash, receivedAt).Scan(&f.SnapshotApartment, &cfgJSON)
	switch {
	case errors.Is(err, pgx.ErrNoRows):
	case err != nil:
		return f, "", "", err
	default:
		if err := jsonUnmarshal(cfgJSON, &f.Config); err != nil {
			return f, "", "", err
		}
		f.SnapshotFound = true
	}
	var status, dateFrom, dateTo string
	var archived bool
	var override, declared, reduced *int64
	err = tx.QueryRow(ctx,
		`SELECT apartment_id, COALESCE(status,''), archived_at IS NOT NULL, COALESCE(date_from,''), COALESCE(date_to,''),
		expected_guests_override, declared_guests, lead_reduced_guests FROM reservation WHERE id = $1`,
		reservationID).Scan(&f.ReservationApartment, &status, &archived, &dateFrom, &dateTo, &override, &declared, &reduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return f, "", "", nil
	}
	if err != nil {
		return f, "", "", err
	}
	f.ReservationFound = true
	f.Active = status == "active" && !archived
	f.Expected = headcount.Expected(override, declared, reduced)
	rows, err := tx.Query(ctx,
		`SELECT id, COALESCE(surname,''), COALESCE(first_name,''), COALESCE(birth_date_enc,''), COALESCE(birth_date,''),
		COALESCE(doc_number_enc,''), COALESCE(doc_number,'') FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id`,
		reservationID)
	if err != nil {
		return f, "", "", err
	}
	defer rows.Close()
	for rows.Next() {
		var g Live
		var birthEnc, birthPlain, docEnc, docPlain string
		if err := rows.Scan(&g.ID, &g.Surname, &g.FirstName, &birthEnc, &birthPlain, &docEnc, &docPlain); err != nil {
			return f, "", "", err
		}
		g.BirthDate = w.decrypt(birthEnc, birthPlain)
		g.DocNumber = w.decrypt(docEnc, docPlain)
		f.Live = append(f.Live, g)
	}
	return f, dateFrom, dateTo, rows.Err()
}

// decrypt is db.decrypt_field: the _enc column, else the plaintext fallback.
func (w *Worker) decrypt(enc, plain string) string {
	if enc == "" {
		return plain
	}
	b, err := w.Keys.Decrypt(enc, 0, time.Now())
	if err != nil {
		return plain
	}
	return string(b)
}

// encrypt is db.encrypt_field: an empty value stays NULL.
func (w *Worker) encrypt(plain string) (*string, error) {
	if plain == "" {
		return nil, nil
	}
	t, err := w.Keys.EncryptString(plain)
	if err != nil {
		return nil, err
	}
	return &t, nil
}

func (w *Worker) insertGuest(ctx context.Context, tx pgx.Tx, reservationID int64, r Row) (int64, error) {
	var existing int
	if err := tx.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE reservation_id = $1`, reservationID).Scan(&existing); err != nil {
		return 0, err
	}
	isLead := 0
	if existing == 0 {
		isLead = 1
	}
	v := r.Values
	enc := make([]*string, 0, 6)
	for _, plain := range []string{v.BirthDate, v.DocNumber, v.VisaNumber, v.ResStreet, v.ResCity, v.SignaturePNG} {
		e, err := w.encrypt(plain)
		if err != nil {
			return 0, err
		}
		enc = append(enc, e)
	}
	var id int64
	err := tx.QueryRow(ctx, insertGuestSQL,
		reservationID, isLead, v.Surname, v.FirstName,
		v.Nationality, v.ResCountry, v.Purpose, v.Note, v.StayFrom, v.StayTo,
		enc[0], enc[1], enc[2], enc[3], enc[4], enc[5],
		r.SignedAt, r.NoticeVersion, r.Lang, r.Stamp, r.Stamp,
		r.Stamp, r.Stamp, r.SubmitState).Scan(&id)
	return id, err
}
```

Then append to the same file (it is part of the file, kept last):

```go
func jsonUnmarshal(data []byte, v any) error {
	if err := json.Unmarshal(data, v); err != nil {
		return fmt.Errorf("guestinbox: form_config: %w", err)
	}
	return nil
}
```

and add `"encoding/json"` as the first line of the import block (before `"context"`).

Command: `cd go && gofmt -l internal/guestinbox && go vet ./internal/guestinbox/ 2>&1 | tail -30`. Expected: no output. A compile error naming a 1835 function or field: STOP (1835 changed shape).

**Step 4.** Create `go/internal/guestinbox/row_test.go` with exactly this content:

```go
package guestinbox

import (
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

var prague = func() *time.Location {
	l, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic(err)
	}
	return l
}()

func adult() guestcontract.Submission {
	return guestcontract.Submission{
		ContractVersion: guestcontract.V1,
		IdempotencyKey:  "0123456789abcdef0123456789abcdef",
		ReservationID:   7,
		Lang:            "de",
		Guest: guestcontract.GuestForm{
			Surname: "Novak", FirstName: "Jan", BirthDate: "1980-05-01",
			Nationality: "deu", DocNumber: "C01X00T47", ResStreet: "Hauptstr. 1",
			ResCity: "Berlin", ResCountry: "deu", Signature: "data:image/png;base64,AAAA",
			LegalAck: true,
		},
	}
}

func TestUTCStampIsDbUtcnowFormat(t *testing.T) {
	got := UTCStamp(time.Date(2026, 11, 16, 14, 32, 7, 900, prague))
	if got != "2026-11-16T13:32:07+00:00" {
		t.Fatalf("got %q", got)
	}
}

func TestSignedAtIsReceivedAt(t *testing.T) {
	received := time.Date(2026, 11, 16, 14, 32, 0, 0, prague)
	r := BuildRow(adult(), "10", "2026-11-13", "2026-11-20", received, "1.0")
	want := "2026-11-16T13:32:00+00:00"
	if r.SignedAt == nil || *r.SignedAt != want || r.Stamp != want {
		t.Fatalf("signed_at %v stamp %q, want %q", r.SignedAt, r.Stamp, want)
	}
	if r.SubmitState != SubmitPending || r.Values.Nationality != "DEU" || r.Lang != "de" || r.NoticeVersion != "1.0" {
		t.Fatalf("row %+v", r)
	}
	if r.Values.StayFrom != "2026-11-13" || r.Values.StayTo != "2026-11-20" || r.Values.SignaturePNG == "" {
		t.Fatalf("stay or signature %+v", r.Values)
	}
}

func TestChildHasNoSignatureAndNoSignedAt(t *testing.T) {
	s := adult()
	s.Guest.BirthDate = "2020-01-01"
	r := BuildRow(s, "10", "2026-11-13", "2026-11-20", time.Date(2026, 11, 16, 9, 0, 0, 0, time.UTC), "1.0")
	if !r.Child || r.SignedAt != nil || r.Values.SignaturePNG != "" {
		t.Fatalf("child row %+v", r)
	}
}

func TestLegalTodayIsPragueDateOfReceivedAt(t *testing.T) {
	got := LegalToday(time.Date(2026, 12, 31, 23, 30, 0, 0, time.UTC))
	if !got.Equal(time.Date(2027, 1, 1, 0, 0, 0, 0, time.UTC)) {
		t.Fatalf("got %v", got)
	}
}

// The deadline is three working days from the stay's first day (Friday
// 13 Nov 2026 -> Tuesday 17 Nov 23:59:59), the same answer the Python path
// gives for the same stay, whenever the form was received or processed.
func TestDeadlineDependsOnStayOnly(t *testing.T) {
	want := time.Date(2026, 11, 17, 23, 59, 59, 0, time.UTC)
	for _, received := range []time.Time{
		time.Date(2026, 11, 13, 22, 0, 0, 0, prague),
		time.Date(2026, 11, 16, 14, 32, 0, 0, prague),
		time.Date(2026, 11, 17, 23, 0, 0, 0, prague),
	} {
		got, ok := Deadline(BuildRow(adult(), "10", "2026-11-13", "2026-11-20", received, "1.0"))
		if !ok || !got.Equal(want) {
			t.Fatalf("received %v: deadline %v, want %v", received, got, want)
		}
	}
}

func facts(expected *int64, live ...Live) Facts {
	return Facts{
		SnapshotFound: true, SnapshotApartment: 3,
		Config:           guestcontract.FormConfig{ApartmentID: 3, Stays: []guestcontract.Stay{{ReservationID: 7}}},
		ReservationFound: true, ReservationApartment: 3, Active: true,
		Expected: expected, Live: live,
	}
}

func TestDecideOutcomes(t *testing.T) {
	two := int64(2)
	row := BuildRow(adult(), "10", "2026-11-13", "2026-11-20", time.Date(2026, 11, 16, 9, 0, 0, 0, time.UTC), "1.0")
	other := Live{ID: 40, Surname: "MUSTER", FirstName: "Eva", BirthDate: "1990-01-01", DocNumber: "X1234567"}
	same := Live{ID: 41, DocNumber: row.Values.DocNumber}
	revoked := facts(&two)
	revoked.SnapshotFound = false
	cancelled := facts(&two)
	cancelled.Active = false
	moved := facts(&two)
	moved.ReservationApartment = 9
	attached := facts(&two)
	attached.Attached, attached.SnapshotFound, attached.ReservationApartment = true, false, 9
	attachedCancelled := attached
	attachedCancelled.Active = false
	if NoteDuplicate != "already_registered" || NoteOverCount != "over_count" {
		t.Fatal("host notes are the contract of brief 1838")
	}
	disagree := []validation.Issue{
		{Field: "doc_number", Message: "x", Severity: "error"},
		{Field: "note", Message: "y", Severity: "warning"},
	}
	cases := []struct {
		name   string
		f      Facts
		issues []validation.Issue
		want   Decision
	}{
		{"revoked link", revoked, nil, Decision{Status: StatusHeld, Note: NoteLinkRevoked}},
		{"cancelled stay", cancelled, nil, Decision{Status: StatusHeld, Note: NoteStayCancelled}},
		{"moved stay", moved, nil, Decision{Status: StatusHeld, Note: NoteStayMoved}},
		{"disagreement", facts(&two), disagree, Decision{Status: StatusHeld, Note: "check_disagreement:doc_number", Disagree: true}},
		{"duplicate", facts(&two, same), nil, Decision{Status: StatusDone, Note: NoteDuplicate, DuplicateOf: 41}},
		{"over count", facts(&two, other, Live{ID: 42}), nil, Decision{Status: StatusDone, Note: NoteOverCount, Insert: true}},
		{"no count yet", facts(nil), nil, Decision{Status: StatusDone, Insert: true, NeedsCount: true}},
		{"host attached, link gone", attached, nil, Decision{Status: StatusDone, Insert: true}},
		{"host attached, stay cancelled", attachedCancelled, nil, Decision{Status: StatusHeld, Note: NoteStayCancelled}},
		{"plain", facts(&two, other), nil, Decision{Status: StatusDone, Insert: true}},
	}
	for _, c := range cases {
		if got := Decide(7, row, c.f, c.issues); got != c.want {
			t.Errorf("%s: got %+v, want %+v", c.name, got, c.want)
		}
	}
}
```

Command: `cd go && go test ./internal/guestinbox/ -run 'TestUTCStamp|TestSignedAt|TestChild|TestLegalToday|TestDeadline|TestDecide' -count=1 2>&1 | tail -30`. Expected: `ok`. If `TestChildHasNoSignatureAndNoSignedAt` fails because the normalised birth date is not read as under 15, STOP (do not change the test data).

**Step 5.** Create `go/internal/guestinbox/worker_test.go` with exactly this content:

```go
package guestinbox

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// The worker only ever claims `new` rows and skips rows another worker holds,
// so a row settled once is never processed again (plan section 3 rule 3).
func TestClaimSQLTakesOnlyNewRowsAndSkipsLocked(t *testing.T) {
	for _, part := range []string{"status = 'new'", "FOR UPDATE SKIP LOCKED", "LIMIT 1"} {
		if !strings.Contains(claimSQL, part) {
			t.Fatalf("claimSQL lacks %q", part)
		}
	}
	// Brief 1839: every settled row gets processed_at in the same statement
	// as its status, or its payload is never deleted.
	for _, part := range []string{"status = $1", "processed_at = $3"} {
		if !strings.Contains(finishSQL, part) {
			t.Fatalf("finishSQL lacks %q", part)
		}
	}
	// A row brief 1838 dismissed is status done, host_note dismissed: never claimed.
	if strings.Contains(claimSQL, "dismissed") || strings.Contains(claimSQL, "'done'") {
		t.Fatal("claimSQL must select status new only")
	}
	if !strings.Contains(bumpSQL, "status = 'new'") {
		t.Fatal("bumpSQL must not touch a settled row")
	}
}

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	url := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL not set")
	}
	pool, err := pgxpool.New(context.Background(), url)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	return pool
}

// The guest program's insert, as brief 1840 will write it: a repeated post
// with the same idempotency key is one inbox row, so one guest.
const insertInboxSQL = `INSERT INTO guest_inbox
(idempotency_key, token_hash, reservation_id, contract_version, received_at, payload_enc)
VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (idempotency_key) DO NOTHING`

func TestSameIdempotencyKeyTwiceIsOneRow(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	key := "fedcba9876543210fedcba9876543210"
	t.Cleanup(func() { _, _ = pool.Exec(ctx, `DELETE FROM guest_inbox WHERE idempotency_key = $1`, key) })
	received := time.Date(2026, 11, 16, 13, 32, 0, 0, time.UTC)
	for i := 0; i < 2; i++ {
		if _, err := pool.Exec(ctx, insertInboxSQL, key, strings.Repeat("a", 64), int64(999999), 1, received, []byte("x")); err != nil {
			t.Fatal(err)
		}
	}
	var n int
	var status string
	var got time.Time
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) OVER (), status, received_at FROM guest_inbox WHERE idempotency_key = $1`, key).Scan(&n, &status, &got); err != nil {
		t.Fatal(err)
	}
	if n != 1 || status != "new" || !got.Equal(received) {
		t.Fatalf("rows %d status %q received_at %v", n, status, got)
	}
}
```

Command: `cd go && go test ./internal/guestinbox/ -count=1 -v -run 'TestClaimSQL|TestSameIdempotency' 2>&1 | tail -30`. Expected: `TestClaimSQL...` PASS; `TestSameIdempotencyKeyTwiceIsOneRow` PASS, or SKIP when `UBYHOST_TEST_DATABASE_URL` is unset (say which in the report).

**Step 6.** Run the package tests, the shared package, and vet.
Command: `cd go && go vet ./internal/guestinbox/ ./internal/guestcontract/ && go test ./internal/guestinbox/... ./internal/guestcontract/... ./internal/deadlines/... -count=1 2>&1 | tail -30`. Expected: three `ok` lines.

**Step 7.** Lint.
Command: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no finding naming a file of this brief.

## 5. Do not touch

- `App/app/routes/guest.py` and every other Python file: the old form path is unchanged here (plan rollout step 2 is a later brief).
- `go/cmd/ubyhost-web/`: no `register_*.go`; the worker is wired by 1837c.
- `go/internal/guestcontract/`, `go/internal/validation/`, `go/internal/deadlines/`, `go/internal/ubyport/`, `App/migrations_pg/`.
- Hard rules 1, 2, 3, 4, 5, 8, 11 of AGENTS.md.

## 6. Commands

| Command | Expected |
|---|---|
| `cd go && gofmt -l internal/guestinbox 2>&1 \| tail -30` | no output |
| `cd go && go vet ./internal/guestinbox/ 2>&1 \| tail -30` | no output |
| `cd go && go test ./internal/guestinbox/... ./internal/guestcontract/... ./internal/deadlines/... -count=1 2>&1 \| tail -30` | three `ok` |
| `python3 scripts/context_lint.py 2>&1 \| tail -30` | no finding for this brief |

## 7. Acceptance

- [ ] `git diff --stat` lists exactly the four files of section 3.
- [ ] `TestSignedAtIsReceivedAt`, `TestChildHasNoSignatureAndNoSignedAt`, `TestDeadlineDependsOnStayOnly`, `TestDecideOutcomes`, `TestClaimSQLTakesOnlyNewRowsAndSkipsLocked` pass.
- [ ] `TestSameIdempotencyKeyTwiceIsOneRow` passes or skips (report says which).
- [ ] `grep -n 'time.Now' go/internal/guestinbox/row.go` prints nothing (no clock in the row).
- [ ] `grep -c 'processed_at = \$3' go/internal/guestinbox/worker.go` prints `1` and `finish` runs it before `tx.Commit` (brief 1839).
- [ ] `grep -rn 'guestinbox' go/cmd/` prints nothing (not wired).

## 8. Stop and ask

Stop, and write the report, if:

- an open question has no answer (step 0);
- an anchor is not found, or 1834 or 1835 is not merged;
- a compile error names a function or field of `guestcontract` or `validation`;
- `TestChildHasNoSignatureAndNoSignedAt` or `TestDeadlineDependsOnStayOnly` fails (never edit expected values);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1837-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/guestinbox/row.go`: every time comes from `receivedAt`; `Decide` order; duplicate rule (open question 2).
- `go/internal/guestinbox/worker.go`: `insertGuestSQL` columns against the `guest` table (omitted columns take their defaults, as Python's insert does; `last_errors`, `filled_ip`, `signed_for_*` end NULL); lock key `reservation` as `db.lock_key`; over-count uses the live guest count, while Python uses `reservation_progress()["filled"]`: 1837c's Python parity golden must confirm they agree, or 1837c fixes it before wiring.
- `finish`: `processed_at` and status written for every outcome in the guest row's transaction (brief 1839 retention).
- Nothing is wired: confirm no `go/cmd/` change.

## Owner steps

None. The worker does not run until brief 1837c is merged and its owner steps are followed.
