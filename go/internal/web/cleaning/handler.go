package cleaning

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

var (
	errDates    = errors.New("dates")
	errNotFound = errors.New("not found")
)

// setPrivate is routes/cleaning.PRIVATE.
func setPrivate(w http.ResponseWriter) {
	h := w.Header()
	h.Set("Cache-Control", "no-store")
	h.Set("Referrer-Policy", "no-referrer")
	h.Set("X-Robots-Tag", "noindex, nofollow")
}

// writeJSON writes compact JSON without HTML escaping, as Python's JSONResponse does.
func writeJSON(w http.ResponseWriter, status int, v any) {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(bytes.TrimSuffix(b.Bytes(), []byte("\n")))
}

// writeDetail is FastAPI's HTTPException body.
func writeDetail(w http.ResponseWriter, status int, detail string) {
	writeJSON(w, status, map[string]string{"detail": detail})
}

func serverError(w http.ResponseWriter) {
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// ownerID is access.owner_id: the workspace owner, nil when there is none.
func ownerID(h *session.Host) *int64 {
	if h == nil || h.Workspace.ID == 0 {
		return nil
	}
	id := h.Workspace.ID
	return &id
}

// pyInt is Python int(text) for plain decimal text.
func pyInt(s string) (int64, bool) {
	n, err := strconv.ParseInt(strings.TrimSpace(s), 10, 64)
	return n, err == nil
}

type propOut struct {
	ID   int64  `json:"id"`
	Name string `json:"name"`
}

// payload is the JSON of /cleaning/schedule. Key order is Python's dict order.
type payload struct {
	Properties []propOut       `json:"properties"`
	Events     []any           `json:"events"`
	Cleanings  []*cleaningItem `json:"cleanings"`
	From       string          `json:"from"`
	To         string          `json:"to"`
	ListHTML   string          `json:"listHtml"`
}

// buildPayload is routes/cleaning._payload.
func buildPayload(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, r *http.Request,
	first, last time.Time, ids []int64, readOnly bool, owner *int64, lang string, at time.Time) (*payload, error) {
	allowed, err := properties(ctx, pool, owner, ids)
	if err != nil {
		return nil, err
	}
	q := r.URL.Query()
	raw := q.Get("property")
	if raw == "" {
		raw = q.Get("cal_property")
	}
	var selected int64
	if raw != "" {
		n, ok := pyInt(raw)
		if !ok {
			return nil, errDates
		}
		selected = n
		if !containsID(propIDs(allowed), selected) {
			return nil, errNotFound
		}
	}
	use := ids
	if selected != 0 {
		use = []int64{selected}
	}
	sch, err := buildSchedule(ctx, pool, getenv, owner, first, last, use, at)
	if err != nil {
		return nil, err
	}
	firstS, lastS := iso(first), iso(last)
	if readOnly {
		for _, e := range sch.Events {
			if b, ok := e.(*booking); ok {
				b.Start = maxStr(b.Start, firstS)
				b.End = minStr(b.End, lastS)
				b.DisplayStart = maxStr(b.DisplayStart, firstS+"T00:00")
				b.DisplayEnd = minStr(b.DisplayEnd, lastS+"T00:00")
			}
		}
	}
	out := &payload{Events: sch.Events, Cleanings: sch.Cleanings, From: sch.From, To: sch.To, Properties: []propOut{}}
	for _, h := range allowed {
		out.Properties = append(out.Properties, propOut{ID: h.ID, Name: h.Name})
	}
	todayISO := iso(today(at))
	p := page{Lang: lang, Today: todayISO}
	name := "list.html"
	if readOnly {
		p.Groups = groupsOf(sch.Cleanings)
	} else {
		p.Sections = sectionsOf(sch.Cleanings, todayISO)
		p.Phone = phoneOf(lang, p.Sections)
		name = "table.html"
	}
	out.ListHTML, err = render(name, p)
	return out, err
}

func propIDs(list []home) []int64 {
	ids := make([]int64, 0, len(list))
	for _, h := range list {
		ids = append(ids, h.ID)
	}
	return ids
}

func maxStr(a, b string) string {
	if a > b {
		return a
	}
	return b
}

func minStr(a, b string) string {
	if a < b {
		return a
	}
	return b
}

// ScheduleHandler serves GET /cleaning/schedule for the signed-in owner.
func ScheduleHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			serverError(w)
			return
		}
		if h == nil {
			return
		}
		q := r.URL.Query()
		first, last, err := parseRange(q.Get("from"), q.Get("to"))
		if err != nil {
			setPrivate(w)
			writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": "dates"})
			return
		}
		p, err := buildPayload(r.Context(), pool, getenv, r, first, last, nil, false, ownerID(h), hostweb.Lang(r), at)
		switch {
		case errors.Is(err, errDates):
			setPrivate(w)
			writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": "dates"})
		case errors.Is(err, errNotFound):
			writeDetail(w, http.StatusNotFound, "Not Found")
		case err != nil:
			serverError(w)
		default:
			setPrivate(w)
			writeJSON(w, http.StatusOK, p)
		}
	}
}

// sharedPayload is routes/cleaning._shared_payload. found is false for a share
// that does not exist, is revoked, expired or malformed.
func sharedPayload(r *http.Request, pool *pgxpool.Pool, getenv func(string) string, lang string, at time.Time) (p *payload, found bool, err error) {
	owner, ids, ok, err := sharedLink(r.Context(), pool, r.PathValue("token"), at)
	if err != nil || !ok {
		return nil, false, err
	}
	first := today(at)
	last := first.AddDate(0, 0, 30)
	q := r.URL.Query()
	_, hasFrom := q["from"]
	_, hasTo := q["to"]
	if hasFrom || hasTo {
		rf, rl, err := parseRange(q.Get("from"), q.Get("to"))
		if err != nil {
			return nil, true, errDates
		}
		if rf.After(first) {
			first = rf
		}
		if rl.Before(last) {
			last = rl
		}
	}
	p, err = buildPayload(r.Context(), pool, getenv, r, first, last, ids, true, owner, lang, at)
	return p, true, err
}

// SharedScheduleHandler serves GET /cleaning/shared/{token}/schedule.
func SharedScheduleHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		p, found, err := sharedPayload(r, pool, getenv, hostweb.Lang(r), now())
		switch {
		case !found && err == nil:
			writeDetail(w, http.StatusNotFound, "Not Found")
		case errors.Is(err, errDates):
			setPrivate(w)
			writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": "dates"})
		case errors.Is(err, errNotFound):
			writeDetail(w, http.StatusNotFound, "Not Found")
		case err != nil:
			serverError(w)
		default:
			setPrivate(w)
			writeJSON(w, http.StatusOK, p)
		}
	}
}

// SharedPageHandler serves GET /cleaning/shared/{token}, the standalone cleaner page.
func SharedPageHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		lang := hostweb.Lang(r)
		p, found, err := sharedPayload(r, pool, getenv, lang, at)
		switch {
		case !found && err == nil:
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		case errors.Is(err, errDates):
			writeDetail(w, http.StatusUnprocessableEntity, "Unprocessable Entity")
			return
		case errors.Is(err, errNotFound):
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		case err != nil:
			serverError(w)
			return
		}
		pg := page{
			Lang: lang, Today: iso(today(at)), Tier: strings.ToLower(getenv("UBYHOST_DEPLOYMENT")),
			Source: "/cleaning/shared/" + r.PathValue("token") + "/schedule", From: p.From, To: p.To,
			Groups: groupsOf(p.Cleanings), Props: p.Properties,
			LabelsScript: labelsScript(lang), CalScripts: calScripts(lang, p.Properties),
		}
		body, err := render("shared.html", pg)
		if err != nil {
			serverError(w)
			return
		}
		setPrivate(w)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte(body))
	}
}

// formMaxBody is hostweb's csrfMaxBody. hostweb.CSRF sets that limit only when
// the token comes in the form, so a header token left the body unlimited.
const formMaxBody = 64 << 10

// parseLimitedForm parses the form with the hostweb.CSRF body limit. It returns
// false after writing 413 when the body is too large.
func parseLimitedForm(w http.ResponseWriter, r *http.Request) bool {
	r.Body = http.MaxBytesReader(w, r.Body, formMaxBody)
	var tooBig *http.MaxBytesError
	if err := r.ParseForm(); errors.As(err, &tooBig) {
		writeDetail(w, http.StatusRequestEntityTooLarge, "Request Entity Too Large")
		return false
	}
	return true
}

// DeleteHandler serves POST /cleaning/events/{id}/delete: dismiss one cleaning.
func DeleteHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		if err != nil {
			writeDetail(w, http.StatusUnprocessableEntity, "Unprocessable Entity")
			return
		}
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			serverError(w)
			return
		}
		if h == nil {
			return
		}
		owned, err := eventOwned(r.Context(), pool, ownerID(h), id)
		if err != nil {
			serverError(w)
			return
		}
		if !owned {
			writeDetail(w, http.StatusNotFound, "Not Found")
			return
		}
		revision := int64(0)
		if !parseLimitedForm(w, r) {
			return
		}
		if _, present := r.PostForm["revision"]; present {
			n, ok := pyInt(r.PostForm.Get("revision"))
			if !ok {
				writeDetail(w, http.StatusConflict, "Cleaning changed")
				return
			}
			revision = n
		}
		done, err := dismiss(r.Context(), pool, id, revision, at)
		if err != nil {
			serverError(w)
			return
		}
		if !done {
			writeDetail(w, http.StatusConflict, "Cleaning changed")
			return
		}
		setPrivate(w)
		w.Header().Set("Location", "/cleaning?notice=removed")
		w.WriteHeader(http.StatusSeeOther)
	}
}

// RevokeHandler serves POST /cleaning/shares/{id}/revoke.
func RevokeHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		if err != nil {
			writeDetail(w, http.StatusUnprocessableEntity, "Unprocessable Entity")
			return
		}
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			serverError(w)
			return
		}
		if h == nil {
			return
		}
		if err := revokeShare(r.Context(), pool, ownerID(h), id, at); err != nil {
			serverError(w)
			return
		}
		setPrivate(w)
		w.Header().Set("Location", "/cleaning/shares")
		w.WriteHeader(http.StatusSeeOther)
	}
}
