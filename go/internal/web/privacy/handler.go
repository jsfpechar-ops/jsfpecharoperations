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
