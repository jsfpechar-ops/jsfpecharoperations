// Package billingweb holds the subscription billing web area: the read side
// behind /admin/fakturace (briefs 1341 and later) and the handlers of
// routes/billing.py (/predplatne) and routes/admin_billing.py (/admin/fakturace)
// from brief 1555 on. Production keeps every path on Python: Caddy sends none
// to Go until UBYHOST_GO_PATHS names it.
package billingweb

import (
	"context"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"errors"
	"io"
	"log"
	"mime"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session/admingate"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the flash and page texts of these routes. App/scripts/go_host_i18n.py
// writes i18n.json from App/app/host_i18n.py and i18n_keys.txt.
var catalog = hostweb.Load(catalogJSON)

// Route is one method and path with its handler. The pattern is a Go 1.22 mux pattern.
type Route struct {
	Pattern string
	Handler http.HandlerFunc
}

// call is one signed-in request.
type call struct {
	deps
	w    http.ResponseWriter
	r    *http.Request
	h    *session.Host
	at   time.Time
	lang string
}

// gate says which Python dependencies a route has besides the CSRF check.
type gate struct {
	admin bool // _require_admin (routes/admin_accounts.py 716-723)
	// open is auth._READ_ONLY_OPEN_PREFIXES: a paused account may still post here
	// (/predplatne). hostweb.Login redirects every POST of a paused workspace, so
	// an open route masks the method for that one call.
	open bool
}

// enter runs the Python dependencies in their order: protect_host_post (CSRF,
// POST only) on the router, then require_login or _require_admin in the
// function. It returns nil when it has written the response.
func (d deps) enter(w http.ResponseWriter, r *http.Request, g gate) *call {
	if !d.csrf(w, r) {
		return nil
	}
	return d.login(w, r, g)
}

const (
	multipartMaxBody = 11 << 20 // hostweb's csrfMaxMultipart
	multipartMemory  = 1 << 20  // parts over this spill to temp files
)

// csrf is the router dependency protect_host_post: a POST needs a valid token.
// It returns false after writing the response. A route with an integer path
// parameter calls csrf, then checks the integer (FastAPI's 422 comes after the
// router dependencies and before the function body), then login.
func (d deps) csrf(w http.ResponseWriter, r *http.Request) bool {
	if r.Method != http.MethodPost {
		return true
	}
	// request.form() reads multipart bodies too. Parse one here, once, before CSRF:
	// with the token in the header CSRF reads no body, and the handler then finds
	// the files on r.MultipartForm. The cap is hostweb's: 10 MiB of file and the fields.
	if mt, _, err := mime.ParseMediaType(r.Header.Get("Content-Type")); err == nil && mt == "multipart/form-data" {
		r.Body = http.MaxBytesReader(w, r.Body, multipartMaxBody)
		if err := r.ParseMultipartForm(multipartMemory); err != nil {
			log.Printf("billingweb: multipart form: %v", err)
		}
	}
	if !hostweb.CSRF(w, r, d.getenv, d.now()) {
		return false
	}
	if err := r.ParseForm(); err != nil {
		log.Printf("billingweb: form: %v", err)
	}
	return true
}

// login is require_login or _require_admin; nil when it has written the response.
func (d deps) login(w http.ResponseWriter, r *http.Request, g gate) *call {
	at := d.now()
	var h *session.Host
	var err error
	if g.admin {
		h, err = admingate.Require(w, r, d.pool, d.getenv, at)
	} else {
		lr := r
		if g.open && r.Method == http.MethodPost {
			lr = r.Clone(r.Context())
			lr.Method = http.MethodGet
		}
		h, err = hostweb.Login(w, lr, d.pool, d.getenv, at)
	}
	if err != nil {
		fail(w, err)
		return nil
	}
	if h == nil {
		return nil
	}
	return &call{deps: d, w: w, r: r, h: h, at: at, lang: hostweb.Lang(r)}
}

// fail is Starlette's 500.
func fail(w http.ResponseWriter, err error) {
	log.Printf("billingweb: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// notFound is FastAPI's 404 for a path no route matches.
func notFound(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotFound)
	_, _ = io.WriteString(w, `{"detail":"Not Found"}`)
}

// ctx is the request context with the acting user, as db.set_current_actor:
// audit rows carry the signed-in id, and impersonator_user_id only while an
// admin is inside another workspace.
func (c *call) ctx() context.Context {
	var imp *int64
	if c.h.Impersonating {
		id := c.h.Account.ID
		imp = &id
	}
	return billing.WithAuditActor(c.r.Context(), c.h.Account.ID, c.h.Account.Username, imp)
}

// today is date.today(): the calendar date of the server clock, at midnight UTC.
func (c *call) today() time.Time { return billingjob.Today(c.at) }

// flash is admin_helpers.flash: the text in the host's language, with its key.
func (c *call) flash(key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(c.lang, key, params), Key: key}
}

// back is admin_helpers.back with a message or an error.
func (c *call) back(path string, msg, err hostweb.Flash) {
	hostweb.Back(c.w, c.r, path, msg, err)
}

// billingOn is billing.enabled(): UBYHOST_BILLING_ENABLED is 1, true or yes.
func billingOn(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// invoiceIDFromFile reads the {invoice_id}.pdf path segment. A segment without
// ".pdf" matches no Python route (404); one that is not an integer is FastAPI's
// 422. It returns false after writing the response.
func invoiceIDFromFile(w http.ResponseWriter, file string) (int64, bool) {
	stem, ok := strings.CutSuffix(file, ".pdf")
	if !ok || stem == "" {
		notFound(w)
		return 0, false
	}
	id, err := strconv.ParseInt(stem, 10, 64)
	if err != nil {
		http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
		return 0, false
	}
	return id, true
}

// invoiceFile is the part of a platform_invoice row the PDF routes read.
type invoiceFile struct {
	Number string
	Owner  *int64
	Blob   []byte
	Sum    *string
}

// getInvoiceFile is billing_invoices.get for these columns; nil when missing.
func getInvoiceFile(ctx context.Context, q interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}, id int64) (*invoiceFile, error) {
	var f invoiceFile
	err := q.QueryRow(ctx,
		`SELECT number, owner_user_id, pdf_blob, pdf_sha256 FROM platform_invoice WHERE id = $1`, id,
	).Scan(&f.Number, &f.Owner, &f.Blob, &f.Sum)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &f, nil
}

// pdfBytes is billing_invoices.pdf_bytes: always the stored bytes, checked
// against their hash; never re-rendered. Python raises ValueError (a 500).
func (f *invoiceFile) pdfBytes() ([]byte, error) {
	if len(f.Blob) == 0 {
		return nil, errors.New("platform_invoice_pdf_missing")
	}
	sum := sha256.Sum256(f.Blob)
	if f.Sum == nil || hex.EncodeToString(sum[:]) != *f.Sum {
		return nil, errors.New("platform_invoice_pdf_changed")
	}
	return f.Blob, nil
}

// writePDF is Response(bytes, media_type="application/pdf", Content-Disposition inline).
func writePDF(w http.ResponseWriter, f *invoiceFile) {
	blob, err := f.pdfBytes()
	if err != nil {
		fail(w, err)
		return
	}
	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", `inline; filename="`+f.Number+`.pdf"`)
	w.Header().Set("Content-Length", strconv.Itoa(len(blob)))
	_, _ = w.Write(blob)
}

// hostInvoicePDF serves GET /predplatne/faktury/{invoice_id}.pdf (routes/billing.py
// plan_invoice_pdf, lines 178-189): the host's own invoice, else back to the plan page.
func (d deps) hostInvoicePDF(w http.ResponseWriter, r *http.Request) {
	id, ok := invoiceIDFromFile(w, r.PathValue("file"))
	if !ok {
		return
	}
	c := d.enter(w, r, gate{open: true})
	if c == nil {
		return
	}
	f, err := getInvoiceFile(r.Context(), d.pool, id)
	if err != nil {
		fail(w, err)
		return
	}
	// owner is never None after require_login: the workspace is always set.
	if f == nil || f.Owner == nil || *f.Owner != c.h.Workspace.ID {
		c.back("/predplatne", hostweb.Flash{}, hostweb.Flash{})
		return
	}
	writePDF(w, f)
}

// hostCancel serves POST /predplatne/zrusit (plan_cancel, lines 149-159).
func (d deps) hostCancel(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{open: true})
	if c == nil {
		return
	}
	moved := false
	if billingOn(d.getenv) {
		var err error
		if moved, err = billing.Cancel(c.ctx(), d.pool, c.h.Workspace.ID, billing.HostActor); err != nil {
			fail(w, err)
			return
		}
	}
	if !moved {
		c.back("/predplatne", hostweb.Flash{}, c.flash("billing.order.error.state", nil))
		return
	}
	c.back("/predplatne", c.flash("billing.cancel.done", nil), hostweb.Flash{})
}

// hostResume serves POST /predplatne/obnovit (plan_resume, lines 162-172).
func (d deps) hostResume(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{open: true})
	if c == nil {
		return
	}
	moved := false
	if billingOn(d.getenv) {
		var err error
		if moved, err = billing.Resume(c.ctx(), d.pool, c.h.Workspace.ID, billing.HostActor); err != nil {
			fail(w, err)
			return
		}
	}
	if !moved {
		c.back("/predplatne", hostweb.Flash{}, c.flash("billing.order.error.state", nil))
		return
	}
	c.back("/predplatne", c.flash("billing.resume.done", nil), hostweb.Flash{})
}

// adminInvoicePDF serves GET /admin/fakturace/{invoice_id}.pdf
// (billing_admin_pdf, lines 108-117): any invoice, for an admin only.
func (d deps) adminInvoicePDF(w http.ResponseWriter, r *http.Request) {
	id, ok := invoiceIDFromFile(w, r.PathValue("file"))
	if !ok {
		return
	}
	c := d.enter(w, r, gate{admin: true})
	if c == nil {
		return
	}
	f, err := getInvoiceFile(r.Context(), d.pool, id)
	if err != nil {
		fail(w, err)
		return
	}
	if f == nil {
		c.back(adminPage, hostweb.Flash{}, hostweb.Flash{})
		return
	}
	writePDF(w, f)
}

// adminPage is routes/admin_billing.PAGE.
const adminPage = "/admin/fakturace"
