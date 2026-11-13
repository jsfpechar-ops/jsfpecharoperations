// Package privacy is the host data-subject request register (BE-8): the two
// POST routes of App/app/routes/privacy_requests.py and the store functions
// of App/app/dsr.py they use. The GET page comes in a later brief.
package privacy

import (
	"context"
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// Channels is dsr.CHANNELS.
var Channels = []string{"email", "post", "in_person", "support", "other"}

// RequestTypes is dsr.REQUEST_TYPES.
var RequestTypes = []string{"access", "rectification", "erasure", "restriction", "portability", "objection", "other"}

// SubjectKinds is dsr.SUBJECT_KINDS.
var SubjectKinds = []string{"guest", "host_user", "other"}

// Statuses is dsr.STATUSES.
var Statuses = []string{"open", "extended", "fulfilled", "refused", "withdrawn"}

// Closed is _CLOSED in routes/privacy_requests.py: a status that sets closed_at.
var Closed = []string{"fulfilled", "refused", "withdrawn"}

// In reports whether v is one of set.
func In(set []string, v string) bool {
	for _, s := range set {
		if s == v {
			return true
		}
	}
	return false
}

// DB is the part of *pgxpool.Pool the store uses.
type DB interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// Request is one data_subject_request row, ready for a template: a NULL
// text column is "" and a NULL id is 0, as the Jinja template reads `row.x or ""`.
// Ids start at 1, so 0 never names a real row.
type Request struct {
	ID                int64
	OwnerUserID       int64
	ReceivedAt        string
	DueAt             string
	Channel           string
	RequestType       string
	SubjectKind       string
	GuestID           int64
	ReservationID     int64
	IdentityCheckedAt string
	Status            string
	ExtendedUntil     string
	ClosedAt          string
	OutcomeNote       string
	HandledBy         int64
	CreatedAt         string
	UpdatedAt         string
}

// Open reports whether the request still runs (open or extended), the first
// sort key of ListForOwner.
func (r Request) Open() bool {
	return r.Status == "open" || r.Status == "extended"
}

const requestColumns = `id, owner_user_id, received_at, due_at, channel, request_type, subject_kind,
	guest_id, reservation_id, identity_checked_at, status, extended_until, closed_at,
	outcome_note, handled_by, created_at, updated_at`

// listSQL is dsr.list_for_owner on Postgres (db.null_safe_eq).
const listSQL = `SELECT ` + requestColumns + ` FROM data_subject_request
	WHERE owner_user_id IS NOT DISTINCT FROM $1
	ORDER BY (status IN ('open','extended')) DESC, due_at, id`

// getSQL is dsr.get.
const getSQL = `SELECT ` + requestColumns + ` FROM data_subject_request WHERE id = $1`

// createSQL is dsr.create through db.insert, in the same column order.
const createSQL = `INSERT INTO data_subject_request (owner_user_id, received_at, due_at, channel,
	request_type, subject_kind, guest_id, reservation_id, status, handled_by, created_at, updated_at)
	VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'open', $9, $10, $10) RETURNING id`

// auditSQL is db.audit through db.insert.
const auditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
	VALUES ($1, $2, $3, $4, $5, $6, $7)`

// resolveSQL is alerts.resolve.
const resolveSQL = `UPDATE alert SET resolved_at = $1 WHERE dedupe_key = $2 AND resolved_at IS NULL`

func scanRequest(row pgx.Row) (Request, error) {
	var r Request
	var owner, guest, reservation, handledBy *int64
	var identity, extended, closed, note *string
	err := row.Scan(&r.ID, &owner, &r.ReceivedAt, &r.DueAt, &r.Channel, &r.RequestType,
		&r.SubjectKind, &guest, &reservation, &identity, &r.Status,
		&extended, &closed, &note, &handledBy, &r.CreatedAt, &r.UpdatedAt)
	if err != nil {
		return Request{}, err
	}
	for _, p := range []struct {
		dst *int64
		src *int64
	}{{&r.OwnerUserID, owner}, {&r.GuestID, guest}, {&r.ReservationID, reservation}, {&r.HandledBy, handledBy}} {
		if p.src != nil {
			*p.dst = *p.src
		}
	}
	for _, p := range []struct {
		dst *string
		src *string
	}{{&r.IdentityCheckedAt, identity}, {&r.ExtendedUntil, extended}, {&r.ClosedAt, closed}, {&r.OutcomeNote, note}} {
		if p.src != nil {
			*p.dst = *p.src
		}
	}
	return r, nil
}

// ListForOwner is dsr.list_for_owner: open and extended first, then by due
// date and id. A nil owner matches the rows with no owner.
func ListForOwner(ctx context.Context, db DB, owner *int64) ([]Request, error) {
	rows, err := db.Query(ctx, listSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Request
	for rows.Next() {
		r, err := scanRequest(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// Get is dsr.get; found is false when there is no such row.
func Get(ctx context.Context, db DB, id int64) (Request, bool, error) {
	r, err := scanRequest(db.QueryRow(ctx, getSQL, id))
	if errors.Is(err, pgx.ErrNoRows) {
		return Request{}, false, nil
	}
	if err != nil {
		return Request{}, false, err
	}
	return r, true, nil
}

// NewRequest holds the keyword arguments of dsr.create.
type NewRequest struct {
	OwnerUserID   *int64
	ReceivedAt    string
	Channel       string
	RequestType   string
	SubjectKind   string
	GuestID       *int64
	ReservationID *int64
	HandledBy     *int64
}

// Create is dsr.create: due_at is one calendar month after received_at, and
// created_at and updated_at are stamp. A received_at that
// datetime.fromisoformat refuses is an error before anything is written.
func Create(ctx context.Context, db DB, n NewRequest, stamp string) (int64, error) {
	due, err := OneMonthLater(n.ReceivedAt)
	if err != nil {
		return 0, err
	}
	var id int64
	err = db.QueryRow(ctx, createSQL, n.OwnerUserID, n.ReceivedAt, due, n.Channel, n.RequestType,
		n.SubjectKind, n.GuestID, n.ReservationID, n.HandledBy, stamp).Scan(&id)
	return id, err
}

// Change is the values dict the update route builds; a nil field is left out.
type Change struct {
	Status            *string
	ClosedAt          *string
	OutcomeNote       *string
	IdentityCheckedAt *string
}

// Empty reports whether the route has nothing to write.
func (c Change) Empty() bool {
	return c.Status == nil && c.ClosedAt == nil && c.OutcomeNote == nil && c.IdentityCheckedAt == nil
}

// Update is dsr.update: the given columns plus updated_at = stamp.
func Update(ctx context.Context, db DB, id int64, c Change, stamp string) error {
	var sets []string
	var args []any
	add := func(col string, v *string) {
		if v != nil {
			args = append(args, *v)
			sets = append(sets, fmt.Sprintf("%s = $%d", col, len(args)))
		}
	}
	add("status", c.Status)
	add("closed_at", c.ClosedAt)
	add("outcome_note", c.OutcomeNote)
	add("identity_checked_at", c.IdentityCheckedAt)
	add("updated_at", &stamp)
	args = append(args, id)
	sql := "UPDATE data_subject_request SET " + strings.Join(sets, ", ") +
		fmt.Sprintf(" WHERE id = $%d", len(args))
	_, err := db.Exec(ctx, sql, args...)
	return err
}

// Actor is who db.audit records: the signed-in account, the workspace it acts
// in, and whether that is someone else's workspace.
type Actor struct {
	AccountID     int64
	Username      string
	WorkspaceID   int64
	Impersonating bool
}

// Audit is db.audit inside a signed-in host request: the actor is the
// account's username, the owner is the workspace, and impersonator_user_id
// is the account id only while impersonating.
func Audit(ctx context.Context, db DB, a Actor, action, detail, stamp string) error {
	var impersonator *int64
	if a.Impersonating {
		id := a.AccountID
		impersonator = &id
	}
	_, err := db.Exec(ctx, auditSQL, stamp, a.Username, action, detail, a.WorkspaceID, a.AccountID, impersonator)
	return err
}

// ResolveAlert is alerts.resolve: close the open alert with this dedupe key.
func ResolveAlert(ctx context.Context, db DB, dedupeKey, stamp string) error {
	_, err := db.Exec(ctx, resolveSQL, stamp, dedupeKey)
	return err
}

// Stamp is db.utcnow: UTC to the second with a +00:00 offset.
func Stamp(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// isoRE is the part of datetime.fromisoformat this port accepts: an extended
// date, then optionally "T" or " ", HH[:MM[:SS[(.|,)fraction]]] and an offset
// Z or +-HH[:MM[:SS[.fraction]]]. Python also accepts basic (20260131), week
// (2026-W05-1) and other separators; those return an error here.
var isoRE = regexp.MustCompile(`^([0-9]{4})-([0-9]{2})-([0-9]{2})(?:[T ]([0-9]{2})(?::([0-9]{2})(?::([0-9]{2})(?:[.,]([0-9]+))?)?)?(Z|[+-][0-9]{2}(?::[0-9]{2}(?::[0-9]{2}(?:\.([0-9]+))?)?)?)?)?$`)

// ErrISO is returned for a received_at that OneMonthLater cannot read.
var ErrISO = errors.New("invalid isoformat string")

// micros reads a fraction the way fromisoformat does: the first six digits.
func micros(frac string) int {
	if len(frac) > 6 {
		frac = frac[:6]
	}
	for len(frac) < 6 {
		frac += "0"
	}
	n, _ := strconv.Atoi(frac)
	return n
}

func daysIn(year, month int) int {
	return time.Date(year, time.Month(month)+1, 0, 0, 0, 0, 0, time.UTC).Day()
}

// OneMonthLater is dsr.one_month_later: fromisoformat, the same day one month
// on (clamped to the month's last day), then isoformat.
func OneMonthLater(iso string) (string, error) {
	m := isoRE.FindStringSubmatch(iso)
	if m == nil {
		return "", ErrISO
	}
	num := func(s string) int {
		n, _ := strconv.Atoi(s)
		return n
	}
	year, month, day := num(m[1]), num(m[2]), num(m[3])
	if year < 1 || month < 1 || month > 12 || day < 1 || day > daysIn(year, month) {
		return "", ErrISO
	}
	hour, minute, second, micro := num(m[4]), num(m[5]), num(m[6]), 0
	if m[7] != "" {
		micro = micros(m[7])
	}
	if hour > 23 || minute > 59 || second > 59 {
		return "", ErrISO
	}
	tz := ""
	if zone := m[8]; zone != "" {
		offset := 0 // microseconds
		sign := 1
		if zone != "Z" {
			if zone[0] == '-' {
				sign = -1
			}
			parts := strings.SplitN(zone[1:], ":", 3)
			oh := num(parts[0])
			om, osec, ou := 0, 0, 0
			if len(parts) > 1 {
				om = num(parts[1])
			}
			if len(parts) > 2 {
				secPart, frac, _ := strings.Cut(parts[2], ".")
				osec = num(secPart)
				if frac != "" {
					ou = micros(frac)
				}
			}
			if om > 59 || osec > 59 {
				return "", ErrISO
			}
			offset = ((oh*60+om)*60+osec)*1000000 + ou
			if offset >= 24*3600*1000000 {
				return "", ErrISO
			}
		}
		tz = isoOffset(sign * offset)
	}
	month++
	if month > 12 {
		month = 1
		year++
	}
	if year > 9999 {
		return "", ErrISO
	}
	if d := daysIn(year, month); day > d {
		day = d
	}
	out := fmt.Sprintf("%04d-%02d-%02dT%02d:%02d:%02d", year, month, day, hour, minute, second)
	if micro != 0 {
		out += fmt.Sprintf(".%06d", micro)
	}
	return out + tz, nil
}

// isoOffset is the offset part of isoformat: +HH:MM, then :SS and .ffffff
// only when they are not zero. A zero offset is +00:00.
func isoOffset(us int) string {
	sign := "+"
	if us < 0 {
		sign = "-"
		us = -us
	}
	h := us / 3600000000
	m := us / 60000000 % 60
	s := us / 1000000 % 60
	u := us % 1000000
	out := fmt.Sprintf("%s%02d:%02d", sign, h, m)
	if s != 0 || u != 0 {
		out += fmt.Sprintf(":%02d", s)
		if u != 0 {
			out += fmt.Sprintf(".%06d", u)
		}
	}
	return out
}
