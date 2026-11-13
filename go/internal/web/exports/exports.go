// Package exports ports the host download routes of App/app/routes/exports.py
// (briefs 1320 and 1321): the stays and house-book CSVs, the stored
// Doručenka and error PDFs, the SOAP envelopes, the receipt zips and one
// guest's Art 15/20 bundle. The Python files are the reference; each function
// names its source. The routes stay on Python until the owner lists their
// paths in UBYHOST_GO_PATHS.
package exports

import (
	"context"
	_ "embed"
	"encoding/base64"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the flash texts these routes raise (i18n_keys.txt), written
// by App/scripts/exports_golden.py from App/app/host_i18n.py.
var catalog = hostweb.Load(catalogJSON)

// maxReceiptDownloads is reporting.MAX_RECEIPT_DOWNLOADS.
const maxReceiptDownloads = 100

// auditSQL is db.audit's insert.
const auditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
	VALUES ($1, $2, $3, $4, $5, $6, $7)`

// deps is what every handler needs. Nothing here touches the pool until a
// request arrives.
type deps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

// begin is the start of every route: the method check FastAPI's @router.get
// makes (HEAD is 405 there), the Cache-Control the Python middleware sets on
// every non-static response, and auth.require_login. ok is false when the
// response is written.
func (d deps) begin(w http.ResponseWriter, r *http.Request, method string) (*session.Host, time.Time, bool) {
	at := d.now()
	w.Header().Set("Cache-Control", "no-store, private")
	if r.Method != method {
		w.Header().Set("Allow", method)
		writeText(w, http.StatusMethodNotAllowed, "application/json", `{"detail":"Method Not Allowed"}`)
		return nil, at, false
	}
	h, err := hostweb.Login(w, r, d.pool, d.getenv, at)
	if err != nil {
		serverError(w, err)
		return nil, at, false
	}
	if h == nil {
		return nil, at, false
	}
	return h, at, true
}

// serverError is the plain 500 Starlette answers when a route raises.
func serverError(w http.ResponseWriter, err error) {
	log.Printf("exports route failed: %v", err)
	writeText(w, http.StatusInternalServerError, "text/plain; charset=utf-8", "Internal Server Error")
}

// writeText writes a whole body with its content type.
func writeText(w http.ResponseWriter, status int, contentType, body string) {
	w.Header().Set("Content-Type", contentType)
	w.WriteHeader(status)
	_, _ = io.WriteString(w, body)
}

// plain is Response(text, status_code=..., media_type="text/plain"):
// Starlette adds the charset to a text/* type.
func plain(w http.ResponseWriter, status int, text string) {
	writeText(w, status, "text/plain; charset=utf-8", text)
}

// attachment writes a 200 download, as Response(..., headers={"Content-Disposition": ...})
// and FileResponse(filename=...) do for an ASCII file name.
func attachment(w http.ResponseWriter, contentType, filename string, body []byte) {
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Content-Disposition", `attachment; filename="`+filename+`"`)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(body)
}

// flash is admin_helpers.flash: the text in the host's language with its key.
func flash(r *http.Request, key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(hostweb.Lang(r), key, params), Key: key}
}

// backErr is admin_helpers.back(path, err=flash(request, key, ...)).
func backErr(w http.ResponseWriter, r *http.Request, path, key string, params map[string]any) {
	hostweb.Back(w, r, path, hostweb.Flash{}, flash(r, key, params))
}

// ownerID is access.owner_id: the workspace id, nil when there is none.
func ownerID(h *session.Host) any {
	if h == nil || h.Workspace.ID == 0 {
		return nil
	}
	return h.Workspace.ID
}

// identityVisible is access.identity_visible: an admin always, a host in
// their own workspace always, an impersonation only for a revealed guest.
func identityVisible(h *session.Host, guestID *int64) bool {
	if h.Account.Role == "admin" {
		return true
	}
	if !h.Impersonating {
		return true
	}
	if guestID == nil {
		return false
	}
	for _, id := range revealedGuestIDs(h) {
		if id == *guestID {
			return true
		}
	}
	return false
}

// revealedGuestIDs is auth.revealed_guest_ids: the integers in "rv".
func revealedGuestIDs(h *session.Host) []int64 {
	if !h.Impersonating {
		return nil
	}
	values, ok := h.Payload["rv"].([]any)
	if !ok {
		return nil
	}
	var out []int64
	for _, v := range values {
		if n, ok := v.(int64); ok {
			out = append(out, n)
		}
	}
	return out
}

// audit is db.audit with the actor require_login set (db.set_current_actor)
// and the workspace owner (db.set_current_owner).
func audit(ctx context.Context, pool *pgxpool.Pool, h *session.Host, at time.Time, action, detail string) error {
	var impersonator any
	if h.Impersonating {
		impersonator = h.Account.ID
	}
	_, err := pool.Exec(ctx, auditSQL, utcStamp(at), h.Account.Username, action, detail,
		ownerID(h), h.Account.ID, impersonator)
	return err
}

// utcStamp is db.utcnow: seconds, UTC, "+00:00".
func utcStamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// dayStamp is datetime.now().strftime("%Y%m%d") in server-local time.
func dayStamp(t time.Time) string {
	return t.Local().Format("20060102")
}

// queryValue is request.query_params.get(key): Starlette keeps the last value.
func queryValue(r *http.Request, key string) string {
	values := r.URL.Query()[key]
	if len(values) == 0 {
		return ""
	}
	return values[len(values)-1]
}

// queryDate is admin_helpers.query_date: an ISO date, else "".
func queryDate(r *http.Request, key string) string {
	t, ok := validation.ParseISODate(strings.TrimSpace(queryValue(r, key)))
	if !ok {
		return ""
	}
	return t.Format("2006-01-02")
}

// queryInt is admin_helpers.query_int: an integer, else 0 (None; the callers
// only test it for truth).
func queryInt(r *http.Request, key string) int64 {
	n, err := strconv.ParseInt(strings.TrimSpace(queryValue(r, key)), 10, 64)
	if err != nil {
		return 0
	}
	return n
}

// pathID reads an integer path parameter. ok is false after a 404: FastAPI
// answers a non-integer id with a validation error, which main.py turns into
// the HTML not-found page for a browser and a 422 for a script; the Go
// service has no host layout yet, so it answers as its "/" catch-all does.
func pathID(w http.ResponseWriter, r *http.Request, name string) (int64, bool) {
	raw := r.PathValue(name)
	n, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || raw == "" || raw[0] == '+' {
		http.NotFound(w, r)
		return 0, false
	}
	return n, true
}

// b64decode is base64.b64decode(s) with validate=False: characters outside
// the alphabet are dropped, a non-ASCII string or bad padding is an error.
func b64decode(s string) ([]byte, bool) {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 0x80 {
			return nil, false
		}
		if c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c >= '0' && c <= '9' || c == '+' || c == '/' || c == '=' {
			b.WriteByte(c)
		}
	}
	out, err := base64.StdEncoding.DecodeString(b.String())
	if err != nil {
		return nil, false
	}
	return out, true
}

// pdfResponse is exports._pdf_response.
func pdfResponse(w http.ResponseWriter, value *string, filename string) {
	if value == nil || *value == "" {
		plain(w, http.StatusNotFound, "No document was returned for this submission.")
		return
	}
	raw, ok := b64decode(*value)
	if !ok {
		plain(w, http.StatusInternalServerError, "Stored document is not valid base64.")
		return
	}
	attachment(w, "application/pdf", filename, raw)
}
