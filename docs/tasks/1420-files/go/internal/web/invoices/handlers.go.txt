// Package invoices ports the host invoice pages of App/app/routes/invoices.py
// to Go: the list, the stay picker and form, preview, issue, the PDF
// downloads, mark paid, cancel and the public download link. Each handler
// follows its Python function; the invoice maths and numbering follow
// App/app/invoices.py. Production keeps every path on Python: Caddy sends no
// path to Go until UBYHOST_GO_PATHS names it.
package invoices

import (
	_ "embed"
	"errors"
	"io"
	"log"
	"mime"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds every host string of the invoice pages and flash messages,
// generated from App/app/host_i18n.py by App/scripts/go_host_i18n.py from
// i18n_keys.txt.
var catalog = hostweb.Load(catalogJSON)

var prague = func() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("invoices: " + err.Error())
	}
	return loc
}()

// pragueDay is claim.prague_today: the Prague date as a UTC midnight.
func pragueDay(at time.Time) time.Time {
	y, m, d := at.In(prague).Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// stamp is db.utcnow: seconds, UTC, "+00:00".
func stamp(at time.Time) string {
	return at.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// Route is one pattern for http.ServeMux with its metrics label.
type Route struct {
	Pattern string
	Label   string
	Handler http.HandlerFunc
}

// deps are what every handler needs.
type deps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

// routeFns are the route groups the files of this package add from init(), so
// no brief edits another brief's file.
var routeFns []func(deps) []Route

func addRoutes(fn func(deps) []Route) { routeFns = append(routeFns, fn) }

// Routes lists the ported routes. It never touches the pool, so it can be
// called with a nil one.
func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	d := deps{pool: pool, getenv: getenv, now: now}
	var out []Route
	for _, fn := range routeFns {
		out = append(out, fn(d)...)
	}
	return out
}

// call is one signed-in request.
type call struct {
	deps
	w     http.ResponseWriter
	r     *http.Request
	h     *session.Host
	at    time.Time
	lang  string
	owner int64
}

const multipartMaxBody = 1 << 20

func isMultipart(r *http.Request) bool {
	mediaType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	return err == nil && mediaType == "multipart/form-data"
}

// readForm parses the POST body once, before CSRF reads it, the way
// request.form() does (url-encoded and multipart).
func (d deps) readForm(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		return
	}
	if isMultipart(r) {
		r.Body = http.MaxBytesReader(w, r.Body, multipartMaxBody)
		if err := r.ParseMultipartForm(multipartMaxBody); err != nil {
			log.Printf("invoices: multipart form: %v", err)
		}
	}
}

// enter runs the Python dependencies in their order: protect_host_post (CSRF
// on a POST), then auth.require_login. It returns nil when it has written the
// response.
func (d deps) enter(w http.ResponseWriter, r *http.Request) *call {
	at := d.now()
	if r.Method == http.MethodPost {
		d.readForm(w, r)
		if !hostweb.CSRF(w, r, d.getenv, at) {
			return nil
		}
		if err := r.ParseForm(); err != nil {
			log.Printf("invoices: form: %v", err)
		}
	}
	return d.login(w, r, at)
}

func (d deps) login(w http.ResponseWriter, r *http.Request, at time.Time) *call {
	h, err := hostweb.Login(w, r, d.pool, d.getenv, at)
	if err != nil {
		fail(w, err)
		return nil
	}
	if h == nil {
		return nil
	}
	return &call{deps: d, w: w, r: r, h: h, at: at, lang: hostweb.Lang(r), owner: h.Workspace.ID}
}

var intPath = regexp.MustCompile(`^[+-]?[0-9]+$`)

// enterID is enter for a route with an `invoice_id: int` path parameter:
// FastAPI validates the parameter after the router dependency (CSRF) and
// before the handler (login), so a bad id is a 422 for a signed-out visitor
// too. A well-formed id too big for int64 matches no invoice (id 0).
func (d deps) enterID(w http.ResponseWriter, r *http.Request, raw string) (*call, int64) {
	at := d.now()
	if r.Method == http.MethodPost {
		d.readForm(w, r)
		if !hostweb.CSRF(w, r, d.getenv, at) {
			return nil, 0
		}
		if err := r.ParseForm(); err != nil {
			log.Printf("invoices: form: %v", err)
		}
	}
	if !intPath.MatchString(raw) {
		unprocessableInt(w, "invoice_id", raw)
		return nil, 0
	}
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		id = 0
	}
	c := d.login(w, r, at)
	if c == nil {
		return nil, 0
	}
	return c, id
}

// unprocessableInt is FastAPI's 422 for a path parameter that is not an int.
func unprocessableInt(w http.ResponseWriter, name, input string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnprocessableEntity)
	_, _ = io.WriteString(w, `{"detail":[{"type":"int_parsing","loc":["path",`+jsonString(name)+`],"msg":"Input should be a valid integer, unable to parse string as an integer","input":`+jsonString(input)+`}]}`)
}

func jsonString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '"' || r == '\\':
			b.WriteByte('\\')
			b.WriteRune(r)
		case r < 0x20:
			b.WriteString(`\u00`)
			b.WriteString(strconv.FormatInt(int64(r)+0x100, 16)[1:])
		default:
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
	return b.String()
}

// notFound is Starlette's 404 for a path no route matches.
func notFound(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotFound)
	_, _ = io.WriteString(w, `{"detail":"Not Found"}`)
}

// methodNotAllowed is Starlette's 405 for a method the route does not list.
func methodNotAllowed(w http.ResponseWriter, allow string) {
	w.Header().Set("Allow", allow)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusMethodNotAllowed)
	_, _ = io.WriteString(w, `{"detail":"Method Not Allowed"}`)
}

// plain is Starlette's Response("text", status_code=n): the body, no
// content type of its own.
func plain(w http.ResponseWriter, status int, body string) {
	w.Header()["Content-Type"] = nil
	w.WriteHeader(status)
	_, _ = w.Write([]byte(body))
}

func fail(w http.ResponseWriter, err error) {
	log.Printf("invoices route failed: %v", err)
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusInternalServerError)
	_, _ = io.WriteString(w, "Internal Server Error")
}

func (c *call) fail(err error) { fail(c.w, err) }

// flash is admin_helpers.flash: the text in the host's language, with its key.
func (c *call) flash(key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(c.lang, key, params), Key: key}
}

// t is host_i18n.translate for the request language.
func (c *call) t(key string, params map[string]any) string {
	return catalog.T(c.lang, key, params)
}

// back is admin_helpers.back with a message or an error.
func (c *call) back(path string, msg, err hostweb.Flash) {
	hostweb.Back(c.w, c.r, path, msg, err)
}

// formStr is admin_helpers.form_str: the last posted value, stripped.
func (c *call) formStr(key string) string { return formStr(c.r.PostForm, key) }

// formTruthy is `form.get(key)` as a Python condition: the last posted value
// is not empty (a value of spaces is still true).
func (c *call) formTruthy(key string) bool {
	values := c.r.PostForm[key]
	return len(values) > 0 && values[len(values)-1] != ""
}

func formStr(form url.Values, key string) string {
	values := form[key]
	if len(values) == 0 {
		return ""
	}
	return strings.TrimSpace(values[len(values)-1])
}

// audit is db.audit for the signed-in account: the actor is the username, the
// owner the workspace, and the impersonator the account while it is inside
// another workspace.
func (c *call) audit(action, detail string) error {
	var impersonator *int64
	if c.h.Impersonating {
		id := c.h.Account.ID
		impersonator = &id
	}
	_, err := c.pool.Exec(c.r.Context(),
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		stamp(c.at), c.h.Account.Username, action, detail, c.owner, c.h.Account.ID, impersonator)
	return err
}

var errNotFound = errors.New("not found")

// noFlash is the absent message of hostweb.Back.
var noFlash hostweb.Flash
