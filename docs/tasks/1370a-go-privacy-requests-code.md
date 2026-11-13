# 1370a: code for brief 1370

The nine files of [brief 1370](1370-go-privacy-requests.md), one block each. Step 1 of the brief extracts the blocks byte for byte; do not read, edit or retype them. Named 1370a (like 0789a) so the brief lint does not treat it as a brief or cap its size.

## go/internal/web/privacy/store.go

````go path=go/internal/web/privacy/store.go
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
````

## go/internal/web/privacy/handler.go

````go path=go/internal/web/privacy/handler.go
package privacy

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the keys in i18n_keys.txt, generated from host_i18n.py.
// App/tests/test_go_privacy_requests.py fails when it is stale.
var catalog = hostweb.Load(catalogJSON)

// listPath is where both routes send the host back to.
const listPath = "/privacy-requests"

// dateOnly is the re.fullmatch the create route uses before it adds midnight UTC.
var dateOnly = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`)

// pathInt is what pydantic's lax int accepts from a path string once
// surrounding whitespace is gone: a sign, digit groups joined by single
// underscores, and an optional .0... tail.
var pathInt = regexp.MustCompile(`^[+-]?[0-9]+(?:_[0-9]+)*(?:\.0+)?$`)

func flash(lang, key string) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(lang, key, nil), Key: key}
}

func fail(w http.ResponseWriter, err error) {
	log.Printf("privacy request route failed: %v", err)
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusInternalServerError)
	_, _ = io.WriteString(w, "Internal Server Error")
}

// pySpace is str.isspace for one rune: Go's unicode.IsSpace plus the
// separators U+001C to U+001F, which Python also strips.
func pySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// parseForm is request.form(): a urlencoded or multipart body; any other
// content type is an empty form.
func parseForm(r *http.Request) error {
	if strings.HasPrefix(strings.ToLower(r.Header.Get("Content-Type")), "multipart/form-data") {
		return r.ParseMultipartForm(1 << 20)
	}
	return r.ParseForm()
}

// formStr is admin_helpers.form_str: the last value posted under key,
// stripped, or "" when there is none or it is a file.
func formStr(r *http.Request, key string) string {
	vals := r.PostForm[key]
	if len(vals) == 0 {
		return ""
	}
	return strings.TrimFunc(vals[len(vals)-1], pySpace)
}

// formHas is `key in form`.
func formHas(r *http.Request, key string) bool {
	if _, ok := r.PostForm[key]; ok {
		return true
	}
	if r.MultipartForm != nil {
		if _, ok := r.MultipartForm.File[key]; ok {
			return true
		}
	}
	return false
}

func isASCIIDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

// actorOf is the db.set_current_actor and db.set_current_owner pair that
// require_login leaves for db.audit.
func actorOf(h *session.Host) Actor {
	return Actor{
		AccountID:     h.Account.ID,
		Username:      h.Account.Username,
		WorkspaceID:   h.Workspace.ID,
		Impersonating: h.Impersonating,
	}
}

// login runs the router's CSRF dependency first and require_login second, as
// FastAPI does. A nil host means the response is written.
func login(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time, beforeLogin func() bool) *session.Host {
	if !hostweb.CSRF(w, r, getenv, at) {
		return nil
	}
	if beforeLogin != nil && !beforeLogin() {
		return nil
	}
	h, err := hostweb.Login(w, r, pool, getenv, at)
	if err != nil {
		fail(w, err)
		return nil
	}
	return h
}

// CreateHandler is POST /privacy-requests (privacy_request_create).
func CreateHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h := login(w, r, pool, getenv, at, nil)
		if h == nil {
			return
		}
		if err := parseForm(r); err != nil {
			fail(w, err)
			return
		}
		lang := hostweb.Lang(r)
		channel := formStr(r, "channel")
		requestType := formStr(r, "request_type")
		subjectKind := formStr(r, "subject_kind")
		if !In(Channels, channel) || !In(RequestTypes, requestType) || !In(SubjectKinds, subjectKind) {
			hostweb.Back(w, r, listPath, hostweb.Flash{}, flash(lang, "flash.error.bad_dsr"))
			return
		}
		var guestID *int64
		// Python's isdigit also takes non-ASCII digits; only ASCII counts here.
		if guestRaw := formStr(r, "guest_id"); isASCIIDigits(guestRaw) {
			id, err := strconv.ParseInt(guestRaw, 10, 64)
			if err != nil {
				// Python passes the big int on and Postgres refuses it: a 500.
				fail(w, err)
				return
			}
			guestID = &id
		}
		owner := h.Workspace.ID
		stamp := Stamp(at)
		received := formStr(r, "received_at")
		if dateOnly.MatchString(received) {
			received += "T00:00:00+00:00"
		}
		if received == "" {
			received = stamp
		}
		id, err := Create(r.Context(), pool, NewRequest{
			OwnerUserID: &owner,
			ReceivedAt:  received,
			Channel:     channel,
			RequestType: requestType,
			SubjectKind: subjectKind,
			GuestID:     guestID,
			HandledBy:   &owner,
		}, stamp)
		if err != nil {
			// A received_at fromisoformat refuses, or a guest_id with no guest
			// row: Python raises and answers 500 too, having written nothing.
			fail(w, err)
			return
		}
		if err := Audit(r.Context(), pool, actorOf(h), "dsr_created",
			fmt.Sprintf("request=%d type=%s", id, requestType), stamp); err != nil {
			fail(w, err)
			return
		}
		hostweb.Back(w, r, listPath, flash(lang, "flash.dsr.created"), hostweb.Flash{})
	}
}

// unprocessable is FastAPI's 422 for a {request_id} that is not an int.
func unprocessable(w http.ResponseWriter, raw string) {
	// A struct, not a map: the fields keep pydantic's order.
	type detail struct {
		Type  string   `json:"type"`
		Loc   []string `json:"loc"`
		Msg   string   `json:"msg"`
		Input string   `json:"input"`
	}
	body := struct {
		Detail []detail `json:"detail"`
	}{[]detail{{
		Type:  "int_parsing",
		Loc:   []string{"path", "request_id"},
		Msg:   "Input should be a valid integer, unable to parse string as an integer",
		Input: raw,
	}}}
	var buf strings.Builder
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(body)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnprocessableEntity)
	_, _ = io.WriteString(w, strings.TrimSuffix(buf.String(), "\n"))
}

// UpdateHandler is POST /privacy-requests/{id} (privacy_request_update).
func UpdateHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		raw := r.PathValue("id")
		var id int64
		h := login(w, r, pool, getenv, at, func() bool {
			clean := strings.TrimFunc(raw, pySpace)
			if !pathInt.MatchString(clean) {
				unprocessable(w, raw)
				return false
			}
			clean, _, _ = strings.Cut(clean, ".")
			n, err := strconv.ParseInt(strings.ReplaceAll(clean, "_", ""), 10, 64)
			if err != nil {
				// pydantic takes the big int and Postgres refuses it: a 500.
				fail(w, err)
				return false
			}
			id = n
			return true
		})
		if h == nil {
			return
		}
		ctx := r.Context()
		lang := hostweb.Lang(r)
		row, found, err := Get(ctx, pool, id)
		if err != nil {
			fail(w, err)
			return
		}
		owner := h.Workspace.ID
		if !found || row.OwnerUserID != owner {
			hostweb.Back(w, r, listPath, hostweb.Flash{}, flash(lang, "flash.error.no_such_dsr"))
			return
		}
		if err := parseForm(r); err != nil {
			fail(w, err)
			return
		}
		stamp := Stamp(at)
		var c Change
		if status := formStr(r, "status"); In(Statuses, status) {
			c.Status = &status
			if In(Closed, status) {
				c.ClosedAt = &stamp
			}
		}
		if formHas(r, "outcome_note") {
			note := formStr(r, "outcome_note")
			c.OutcomeNote = &note
		}
		if formHas(r, "identity_checked") {
			c.IdentityCheckedAt = &stamp
		}
		if !c.Empty() {
			if err := Update(ctx, pool, id, c, stamp); err != nil {
				fail(w, err)
				return
			}
			if c.Status != nil && In(Closed, *c.Status) {
				if err := ResolveAlert(ctx, pool, fmt.Sprintf("dsr_due:%d", id), stamp); err != nil {
					fail(w, err)
					return
				}
			}
		}
		if err := Audit(ctx, pool, actorOf(h), "dsr_updated", fmt.Sprintf("request=%d", id), stamp); err != nil {
			fail(w, err)
			return
		}
		hostweb.Back(w, r, listPath, flash(lang, "flash.dsr.updated"), hostweb.Flash{})
	}
}
````

## go/internal/web/privacy/i18n_keys.txt

````text path=go/internal/web/privacy/i18n_keys.txt
# Host strings read by go/internal/web/privacy (privacy_requests.py POST routes)
flash.dsr.created
flash.dsr.updated
flash.error.bad_dsr
flash.error.no_such_dsr
````

## go/internal/web/privacy/i18n.json

````json path=go/internal/web/privacy/i18n.json
{
 "cs": {
  "flash.dsr.created": "Žádost zaznamenána.",
  "flash.dsr.updated": "Žádost aktualizována.",
  "flash.error.bad_dsr": "Zvolte platný kanál, typ žádosti a subjekt.",
  "flash.error.no_such_dsr": "Tato žádost neexistuje."
 },
 "en": {
  "flash.dsr.created": "Request recorded.",
  "flash.dsr.updated": "Request updated.",
  "flash.error.bad_dsr": "Choose a valid channel, request type and subject.",
  "flash.error.no_such_dsr": "No such request."
 },
 "vi": {
  "flash.dsr.created": "Đã ghi nhận yêu cầu.",
  "flash.dsr.updated": "Đã cập nhật yêu cầu.",
  "flash.error.bad_dsr": "Chọn kênh, loại yêu cầu và chủ thể hợp lệ.",
  "flash.error.no_such_dsr": "Không có yêu cầu này."
 }
}
````

## go/cmd/ubyhost-web/register_web_privacy.go

````go path=go/cmd/ubyhost-web/register_web_privacy.go
package main

// Brief 1370: the two POST routes of the data-subject request register
// (routes/privacy_requests.py). The GET page comes in a later brief. Caddy
// sends a path here only when it is in UBYHOST_GO_PATHS, so these stay off
// until the owner adds them.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/privacy"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("POST /privacy-requests", m.wrap("/privacy-requests", privacy.CreateHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /privacy-requests/{id}", m.wrap("/privacy-requests/{id}", privacy.UpdateHandler(pool, os.Getenv, time.Now)))
	})
}
````

## go/internal/web/privacy/store_test.go

````go path=go/internal/web/privacy/store_test.go
package privacy

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// golden is testdata/privacy_requests_golden.json, written by
// App/scripts/privacy_requests_golden.py from the real Python routes.
type golden struct {
	Now  string `json:"now"`
	Seed []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Steps []struct {
		Name      string                      `json:"name"`
		Account   int64                       `json:"account"`
		Workspace int64                       `json:"workspace"`
		Lang      string                      `json:"lang"`
		Path      string                      `json:"path"`
		Body      string                      `json:"body"`
		Status    int                         `json:"status"`
		Location  string                      `json:"location"`
		Response  string                      `json:"response"`
		State     map[string][]map[string]any `json:"state"`
	} `json:"steps"`
	OneMonthLater [][2]string        `json:"one_month_later"`
	ListForOwner  map[string][]int64 `json:"list_for_owner"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/privacy_requests_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestOneMonthLaterMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.OneMonthLater) < 20 {
		t.Fatalf("only %d one_month_later cases", len(g.OneMonthLater))
	}
	for _, c := range g.OneMonthLater {
		got, err := OneMonthLater(c[0])
		if err != nil {
			got = "error"
		}
		if got != c[1] {
			t.Errorf("OneMonthLater(%q) = %q, Python %q", c[0], got, c[1])
		}
	}
}

func TestStamp(t *testing.T) {
	at := time.Date(2026, 11, 13, 10, 30, 0, 999, time.FixedZone("CET", 3600))
	if got := Stamp(at); got != "2026-11-13T09:30:00+00:00" {
		t.Errorf("Stamp = %q", got)
	}
}

func TestListForOwnerDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	stmts := []string{
		`INSERT INTO user_account (id, username, password_hash, created_at) VALUES
			(1, 'a@example.test', 'x', 'now'), (2, 'b@example.test', 'x', 'now')`,
		`INSERT INTO data_subject_request (id, owner_user_id, received_at, due_at, channel,
			request_type, subject_kind, status, outcome_note, guest_id, created_at, updated_at) VALUES
			(1, 1, 'r', '2026-03-01', 'email', 'access', 'guest', 'fulfilled', 'done', NULL, 'c', 'u'),
			(2, 1, 'r', '2026-05-01', 'email', 'access', 'guest', 'open', NULL, NULL, 'c', 'u'),
			(3, 1, 'r', '2026-04-01', 'post', 'erasure', 'guest', 'extended', NULL, NULL, 'c', 'u'),
			(4, 2, 'r', '2026-01-01', 'email', 'access', 'guest', 'open', NULL, NULL, 'c', 'u'),
			(5, NULL, 'r', '2026-01-01', 'email', 'access', 'other', 'open', NULL, NULL, 'c', 'u'),
			(6, 1, 'r', '2026-04-01', 'email', 'access', 'guest', 'open', NULL, NULL, 'c', 'u')`,
	}
	for _, q := range stmts {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	ids := func(owner *int64) []int64 {
		rows, err := ListForOwner(ctx, pool, owner)
		if err != nil {
			t.Fatal(err)
		}
		var out []int64
		for _, r := range rows {
			out = append(out, r.ID)
		}
		return out
	}
	one, two := int64(1), int64(2)
	if got := fmt.Sprint(ids(&one)); got != "[3 6 2 1]" {
		t.Errorf("owner 1: %s", got)
	}
	if got := fmt.Sprint(ids(&two)); got != "[4]" {
		t.Errorf("owner 2: %s", got)
	}
	if got := fmt.Sprint(ids(nil)); got != "[5]" {
		t.Errorf("no owner: %s", got)
	}
	rows, err := ListForOwner(ctx, pool, &one)
	if err != nil {
		t.Fatal(err)
	}
	last := rows[len(rows)-1]
	if last.ID != 1 || last.OutcomeNote != "done" || last.GuestID != 0 || last.ClosedAt != "" || last.Open() {
		t.Errorf("row 1 read as %+v", last)
	}
	if !rows[0].Open() || rows[0].Status != "extended" || rows[0].OwnerUserID != 1 {
		t.Errorf("row 3 read as %+v", rows[0])
	}
	if _, found, err := Get(ctx, pool, 999); err != nil || found {
		t.Errorf("Get(999): found %v, err %v", found, err)
	}
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops the database at the end.
// It skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_privacy_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}
````

## go/internal/web/privacy/handler_test.go

````go path=go/internal/web/privacy/handler_test.go
package privacy

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	testSecret     = "privacy-test-secret-key-0123456789abcdef"
	testCSRFCookie = "privacy-test-csrf-cookie"
)

func testEnv(k string) string {
	return map[string]string{
		"UBYHOST_SECRET_KEY":      testSecret,
		"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
		"UBYHOST_TERMS_VERSION":   "t1",
		"UBYHOST_PRIVACY_VERSION": "p1",
		"UBYHOST_DPA_VERSION":     "d1",
	}[k]
}

// csrfToken mints a token bound to the CSRF cookie value, as csrf_token does.
func csrfToken(t *testing.T, cookie string, at time.Time) string {
	t.Helper()
	sum := sha256.Sum256([]byte(cookie))
	tok, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").
		Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, at)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func TestFormStr(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/privacy-requests",
		strings.NewReader("channel=fax&channel=+email%1F+&outcome_note=&empty"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if err := parseForm(req); err != nil {
		t.Fatal(err)
	}
	if got := formStr(req, "channel"); got != "email" {
		t.Errorf("channel = %q, want the last value stripped", got)
	}
	if got := formStr(req, "missing"); got != "" || formHas(req, "missing") {
		t.Errorf("missing key: %q", got)
	}
	if !formHas(req, "outcome_note") || !formHas(req, "empty") {
		t.Error("a posted empty key must count as present")
	}
}

func TestPathInt(t *testing.T) {
	for raw, ok := range map[string]bool{
		"5": true, "+5": true, "-5": true, "05": true, "5.00": true, "1_0.0": true,
		"5.": false, "5.5": false, "_5": false, "5_": false, "1__0": false, "0x10": false, "": false,
	} {
		if got := pathInt.MatchString(raw); got != ok {
			t.Errorf("pathInt(%q) = %v, want %v", raw, got, ok)
		}
	}
}

func TestBadCSRFNeverTouchesThePool(t *testing.T) {
	at := time.Date(2026, 11, 13, 9, 30, 0, 0, time.UTC)
	now := func() time.Time { return at }
	mux := http.NewServeMux()
	mux.Handle("POST /privacy-requests", CreateHandler(nil, testEnv, now))
	mux.Handle("POST /privacy-requests/{id}", UpdateHandler(nil, testEnv, now))
	for _, path := range []string{"/privacy-requests", "/privacy-requests/5", "/privacy-requests/abc"} {
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader("status=fulfilled"))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("x-csrf-token", "not-a-token")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: testCSRFCookie})
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req) // a nil pool would panic if it were used
		if rec.Code != http.StatusForbidden && rec.Code != http.StatusSeeOther {
			t.Errorf("%s: code %d", path, rec.Code)
		}
		if loc := rec.Header().Get("Location"); strings.HasPrefix(loc, "/privacy-requests") {
			t.Errorf("%s: bad CSRF reached the route, Location %q", path, loc)
		}
	}
}

// seedValue turns a JSON number into the int64 the seed columns hold.
func seedValue(v any) any {
	if f, ok := v.(float64); ok && f == math.Trunc(f) {
		return int64(f)
	}
	return v
}

func TestPrivacyRequestsGolden(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table,
			strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(v)
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	// The seed wrote ids by hand; SQLite's next id is MAX(id) + 1, so move the
	// Postgres identity there too.
	if _, err := pool.Exec(ctx, `SELECT setval(pg_get_serial_sequence('data_subject_request', 'id'),
		(SELECT MAX(id) FROM data_subject_request))`); err != nil {
		t.Fatal(err)
	}
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	now := func() time.Time { return at }
	mux := http.NewServeMux()
	mux.Handle("POST /privacy-requests", CreateHandler(pool, testEnv, now))
	mux.Handle("POST /privacy-requests/{id}", UpdateHandler(pool, testEnv, now))

	read := func(sql string) []map[string]any {
		rows, err := pool.Query(ctx, sql)
		if err != nil {
			t.Fatal(err)
		}
		defer rows.Close()
		out := []map[string]any{}
		for rows.Next() {
			var raw []byte
			if err := rows.Scan(&raw); err != nil {
				t.Fatal(err)
			}
			var m map[string]any
			if err := json.Unmarshal(raw, &m); err != nil {
				t.Fatal(err)
			}
			out = append(out, m)
		}
		if err := rows.Err(); err != nil {
			t.Fatal(err)
		}
		return out
	}
	queries := map[string]string{
		"data_subject_request": `SELECT to_jsonb(t)::text FROM data_subject_request t ORDER BY id`,
		"audit":                `SELECT (to_jsonb(t) - 'id')::text FROM audit t ORDER BY id`,
		"alert": `SELECT jsonb_build_object('id', id, 'dedupe_key', dedupe_key,
			'resolved_at', resolved_at)::text FROM alert ORDER BY id`,
	}
	for _, step := range g.Steps {
		req := httptest.NewRequest(http.MethodPost, step.Path, strings.NewReader(step.Body))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("x-csrf-token", csrfToken(t, testCSRFCookie, at))
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: testCSRFCookie})
		payload := map[string]any{"uid": step.Account, "sv": int64(1), "iat": at.Unix()}
		if step.Account != step.Workspace {
			payload["as"] = step.Workspace
			payload["ast"] = at.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, at)})
		if step.Lang != "" {
			req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: step.Lang})
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		if rec.Code != step.Status {
			t.Errorf("%s: status %d, Python %d (body %q)", step.Name, rec.Code, step.Status, rec.Body.String())
		}
		if got := rec.Header().Get("Location"); got != step.Location {
			t.Errorf("%s: Location %q, Python %q", step.Name, got, step.Location)
		}
		if step.Status != http.StatusSeeOther && rec.Body.String() != step.Response {
			t.Errorf("%s: body %q, Python %q", step.Name, rec.Body.String(), step.Response)
		}
		for table, sql := range queries {
			got, want := read(sql), step.State[table]
			if !reflect.DeepEqual(got, want) {
				gj, _ := json.Marshal(got)
				wj, _ := json.Marshal(want)
				t.Errorf("%s: %s\n got  %s\n want %s", step.Name, table, gj, wj)
			}
		}
		if t.Failed() {
			t.Fatalf("stopped after step %s", step.Name)
		}
	}
	for key, want := range g.ListForOwner {
		var owner *int64
		if key != "None" {
			var id int64
			fmt.Sscan(key, &id)
			owner = &id
		}
		rows, err := ListForOwner(ctx, pool, owner)
		if err != nil {
			t.Fatal(err)
		}
		got := []int64{}
		for _, r := range rows {
			got = append(got, r.ID)
		}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("ListForOwner(%s) = %v, Python %v", key, got, want)
		}
	}
}
````

## App/scripts/privacy_requests_golden.py

````python path=App/scripts/privacy_requests_golden.py
"""Write go/internal/web/privacy/testdata/privacy_requests_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/privacy_requests_golden.py

It seeds a throwaway SQLite database with SEED, mounts the real
routes/privacy_requests.py router on a bare FastAPI app and posts each entry of
STEPS through it. The clock is fixed at NOW, so every timestamp a step writes
is NOW. Sign-in and CSRF are not what this file pins: the CSRF dependency is
switched off and require_login is replaced by one that sets the step's actor
the way the real one does. After each step it records the status, Location
and body of the answer and every data_subject_request, audit and alert row.
It also records dsr.one_month_later for each ONE_MONTH input ("error" when it
raises) and the ids dsr.list_for_owner returns for owners 1, 2 and None at the
end. go/internal/web/privacy/handler_test.go seeds PostgreSQL from the same
file, signs in for real, posts the same bodies and compares.
App/tests/test_go_privacy_requests.py fails when this file is stale.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "privacy" / "testdata" / "privacy_requests_golden.json"

NOW = "2026-11-13T09:30:00+00:00"
STAMP = "2026-09-01T00:00:00+00:00"
FORM = "application/x-www-form-urlencoded"

SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "active", "session_version", "created_at"],
        "rows": [
            [1, "owner@example.test", "x", "host", 1, 1, STAMP],
            [2, "other@example.test", "x", "host", 1, 1, STAMP],
            [3, "admin@example.test", "x", "admin", 1, 1, STAMP],
        ],
    },
    {
        "table": "legal_acceptance",
        "columns": ["id", "user_account_id", "document", "version", "accepted_at", "method"],
        "rows": [
            [101, 1, "terms", "t1", STAMP, "clickwrap"],
            [102, 1, "privacy", "p1", STAMP, "clickwrap"],
            [103, 1, "dpa", "d1", STAMP, "clickwrap"],
            [104, 3, "terms", "t1", STAMP, "clickwrap"],
            [105, 3, "privacy", "p1", STAMP, "clickwrap"],
            [106, 3, "dpa", "d1", STAMP, "clickwrap"],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "internal_name", "created_at"],
        "rows": [[1, 1, "Byt A", STAMP]],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "source", "uid", "date_from", "date_to",
                    "status", "created_at", "updated_at"],
        "rows": [[1, 1, "manual", "r1", "2026-10-01", "2026-10-03", "active", STAMP, STAMP]],
    },
    {
        "table": "guest",
        "columns": ["id", "reservation_id", "created_at", "updated_at"],
        "rows": [[7, 1, STAMP, STAMP]],
    },
    {
        "table": "data_subject_request",
        "columns": ["id", "owner_user_id", "received_at", "due_at", "channel",
                    "request_type", "subject_kind", "status", "created_at", "updated_at"],
        "rows": [
            [49, None, STAMP, "2026-10-01T00:00:00+00:00", "other", "other", "other", "fulfilled", STAMP, STAMP],
            [50, 2, STAMP, "2026-10-01T00:00:00+00:00", "email", "access", "guest", "open", STAMP, STAMP],
            [51, 1, STAMP, "2026-10-01T00:00:00+00:00", "post", "erasure", "guest", "open", STAMP, STAMP],
        ],
    },
    {
        "table": "alert",
        "columns": ["id", "level", "kind", "owner_user_id", "dedupe_key", "message",
                    "created_at", "user_dismissed"],
        "rows": [
            [9001, "info", "dsr_due", 1, "dsr_due:51", "seeded", STAMP, 0],
            [9002, "info", "dsr_due", 2, "dsr_due:50", "seeded", STAMP, 0],
        ],
    },
]

OWNER = {"account": 1, "workspace": 1}
ADMIN_AS_OWNER = {"account": 3, "workspace": 1}

# Each step: name, actor, language cookie ("" for none), path, raw form body.
# Created requests get ids 52, 53, ... in order.
STEPS = [
    ["create_date_only", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&received_at=2026-01-31&guest_id="],
    ["create_bad_channel", OWNER, "",
     "/privacy-requests", "channel=fax&request_type=access&subject_kind=guest"],
    ["create_bad_subject_cs", OWNER, "cs",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=robot"],
    ["create_received_empty_is_now", OWNER, "",
     "/privacy-requests", "channel=post&request_type=erasure&subject_kind=host_user&received_at="],
    ["create_guest_digits_offset_passthrough", OWNER, "",
     "/privacy-requests", "channel=in_person&request_type=objection&subject_kind=guest&guest_id=+7+&received_at=2026-03-31T23%3A15%3A00%2B02%3A00"],
    ["create_guest_not_digits_space_separator", OWNER, "",
     "/privacy-requests", "channel=support&request_type=portability&subject_kind=other&guest_id=12a&received_at=2026-12-31+08%3A00"],
    ["create_received_invalid_500", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&received_at=31.01.2026"],
    ["create_last_value_wins_cs_fraction", OWNER, "cs",
     "/privacy-requests", "channel=fax&channel=other&request_type=rectification&subject_kind=guest&received_at=2026-05-31T10%3A00%3A00.5Z"],
    ["create_impersonating", ADMIN_AS_OWNER, "",
     "/privacy-requests", "channel=email&request_type=restriction&subject_kind=guest&received_at=2024-01-31"],
    ["update_closed_resolves_alert", OWNER, "",
     "/privacy-requests/51", "status=fulfilled"],
    ["update_note_identity_unknown_status", OWNER, "",
     "/privacy-requests/52", "status=pending&outcome_note=+Sent+the+export+&identity_checked=on"],
    ["update_extended_keeps_alert", OWNER, "",
     "/privacy-requests/52", "status=extended&outcome_note="],
    ["update_nothing_still_audits", OWNER, "",
     "/privacy-requests/52", "status=bogus"],
    ["update_other_owner", OWNER, "",
     "/privacy-requests/50", "status=fulfilled"],
    ["update_missing_cs", OWNER, "cs",
     "/privacy-requests/999", "status=fulfilled"],
    ["update_path_int_forms", OWNER, "",
     "/privacy-requests/+5_2.00", "status=refused"],
    ["update_path_not_int_422", OWNER, "",
     "/privacy-requests/abc", "status=refused"],
    ["update_impersonating_withdrawn", ADMIN_AS_OWNER, "",
     "/privacy-requests/53", "status=withdrawn&outcome_note=Asked+to+stop"],
    # Last on purpose: on Postgres the refused INSERT still uses up an id,
    # on SQLite it does not, so no step may create a request after this one.
    ["create_guest_missing_row_500", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&guest_id=999&received_at=2026-01-01"],
]

ONE_MONTH = [
    "2026-01-31", "2024-01-31", "2026-12-31", "2026-02-28", "2026-03-31T23:15:00+02:00",
    "2026-01-31T00:00:00+00:00", "2026-01-31T10:00", "2026-01-31T10", "2026-01-31 10:00:00Z",
    "2026-12-31T23:59:59.5+02:00", "2026-01-31T10:00:00,5", "2026-01-31T10:00:00.1234567",
    "2026-01-31T10:00:00.000000", "2026-01-31T10:00:00-00:00", "2026-01-31T10:00:00-05:30",
    "2026-01-31T10:00:00+05:30:15", "2026-01-31T10:00:00.123+05:30:15.25", "2026-01-31T10:00+01",
    "9999-11-30", "9999-12-01", "0000-01-01", "2026-13-01", "2026-02-30", "2026-01-31T24:00",
    "2026-01-31T23:59:60", "2026-01-31T10:00:00+24:00", "31.01.2026", "garbage", "",
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _rows(db, sql: str) -> list:
    return [dict(row) for row in db.query(sql)]


def _state(db) -> dict:
    return {
        "data_subject_request": _rows(db, "SELECT * FROM data_subject_request ORDER BY id"),
        "audit": _rows(db, "SELECT at, actor, action, detail, owner_user_id, actor_user_id, "
                           "impersonator_user_id FROM audit ORDER BY id"),
        "alert": _rows(db, "SELECT id, dedupe_key, resolved_at FROM alert ORDER BY id"),
    }


def _one_month(dsr) -> list:
    out = []
    for value in ONE_MONTH:
        try:
            due = dsr.one_month_later(value)
        except ValueError:
            due = "error"
        out.append([value, due])
    return out


def render() -> str:
    """Seed a fresh database, post every step, and return the golden JSON text."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app import access, auth, db, dsr, security
    from app.routes import privacy_requests

    db.init_db()
    _seed(db)
    current = {}

    def fake_login(request):
        account, workspace = current["account"], current["workspace"]
        username = db.query_one("SELECT username FROM user_account WHERE id = ?", (account,))[0]
        db.set_current_actor(account, username, impersonating=account != workspace)
        db.set_current_owner(workspace)
        return None

    saved = (db.utcnow, auth.require_login, access.owner_id)
    db.utcnow = lambda: NOW
    auth.require_login = fake_login
    access.owner_id = lambda request: current["workspace"]
    try:
        app = FastAPI()
        app.include_router(privacy_requests.router)
        app.dependency_overrides[security.protect_host_post] = lambda: None
        client = TestClient(app, raise_server_exceptions=False)
        steps = []
        for name, actor, lang, path, body in STEPS:
            current.update(actor)
            headers = {"Content-Type": FORM}
            if lang:
                headers["Cookie"] = f"ubyhost_lang={lang}"
            response = client.request(
                "POST", path, content=body.encode("utf-8"), headers=headers, follow_redirects=False
            )
            steps.append({
                "name": name,
                "account": actor["account"],
                "workspace": actor["workspace"],
                "lang": lang,
                "path": path,
                "body": body,
                "status": response.status_code,
                "location": response.headers.get("location", ""),
                "response": "" if response.status_code == 303 else response.text,
                "state": _state(db),
            })
    finally:
        db.utcnow, auth.require_login, access.owner_id = saved
    listed = {
        str(owner): [row["id"] for row in dsr.list_for_owner(owner)] for owner in (1, 2, None)
    }
    golden = {
        "list_for_owner": listed,
        "now": NOW,
        "seed": SEED,
        "steps": steps,
        "one_month_later": _one_month(dsr),
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "privacy_requests_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
````

## App/tests/test_go_privacy_requests.py

````python path=App/tests/test_go_privacy_requests.py
"""go/internal/web/privacy reads two generated files; both must match the Python."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
PRIVACY_DIR = APP_DIR.parent / "go" / "internal" / "web" / "privacy"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, APP_DIR / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_privacy_requests_golden_matches_python_routes(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "privacy-requests-golden.sqlite3")
    generator = _load("privacy_requests_golden")
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"name"') >= 19


def test_privacy_catalog_matches_host_i18n():
    # go_host_i18n.py only globs go/internal/*/, so this package is checked here.
    generator = _load("go_host_i18n")
    keys = PRIVACY_DIR / "i18n_keys.txt"
    current = (PRIVACY_DIR / "i18n.json").read_text(encoding="utf-8")
    assert generator.render(generator.read_keys(keys)) == current
````
