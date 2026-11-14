package billingweb

// The operator's POST routes under /admin/fakturace (routes/admin_billing.py,
// lines 72-105), brief 1558: the statement upload and "mark paid".

import (
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// statementMaxBytes is STATEMENT_MAX_BYTES: 5 MiB.
const statementMaxBytes = 5 * 1024 * 1024

// payer is the request's actor for the audit rows and the payment steps.
func (c *call) payer() payer {
	var imp *int64
	if c.h.Impersonating {
		id := c.h.Account.ID
		imp = &id
	}
	return payer{pool: c.pool, username: c.h.Account.Username, userID: c.h.Account.ID, impersonator: imp,
		workspace: c.h.Workspace.ID, today: c.today()}
}

// invoiceIDParam reads the {invoice_id} path integer; FastAPI's 422 when it is not one.
func invoiceIDParam(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("invoice_id"), 10, 64)
	if err != nil {
		http.Error(w, "Unprocessable Entity", http.StatusUnprocessableEntity)
		return 0, false
	}
	return id, true
}

// adminStatement serves POST /admin/fakturace/vypis (billing_admin_statement, lines 72-87).
func (d deps) adminStatement(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{admin: true})
	if c == nil {
		return
	}
	// request.form().get("statement"): the last file part with a file name.
	var data []byte
	found := false
	if r.MultipartForm != nil {
		if files := r.MultipartForm.File["statement"]; len(files) > 0 {
			f := files[len(files)-1]
			if f.Filename != "" {
				file, err := f.Open()
				if err != nil {
					fail(w, err)
					return
				}
				defer file.Close()
				if data, err = io.ReadAll(io.LimitReader(file, statementMaxBytes+1)); err != nil {
					fail(w, err)
					return
				}
				found = true
			}
		}
	}
	if !found {
		c.back(adminPage, hostweb.Flash{}, c.flash("billing.admin.statement.missing", nil))
		return
	}
	unreadable := func() { c.back(adminPage, hostweb.Flash{}, c.flash("billing.admin.statement.unreadable", nil)) }
	if len(data) > statementMaxBytes {
		unreadable()
		return
	}
	counts, err := c.payer().importStatement(c.r.Context(), data)
	if err != nil {
		if IsStatementError(err) {
			unreadable()
			return
		}
		fail(w, err)
		return
	}
	c.back(adminPage, c.flash("billing.admin.statement.done", counts.Params()), hostweb.Flash{})
}

// adminMarkPaid serves POST /admin/fakturace/{invoice_id}/zaplaceno (billing_admin_mark_paid, lines 90-101).
func (d deps) adminMarkPaid(w http.ResponseWriter, r *http.Request) {
	if !d.csrf(w, r) {
		return
	}
	id, ok := invoiceIDParam(w, r)
	if !ok {
		return
	}
	c := d.login(w, r, gate{admin: true})
	if c == nil {
		return
	}
	paidOn := strings.TrimSpace(lastForm(r, "paid_on"))
	if !pyISODate(paidOn) {
		c.back(adminPage, hostweb.Flash{}, c.flash("billing.admin.paid.bad_date", nil))
		return
	}
	done, err := c.payer().markPaidManually(r.Context(), id, paidOn)
	if err != nil {
		fail(w, err)
		return
	}
	if !done {
		c.back(adminPage, hostweb.Flash{}, c.flash("billing.admin.paid.not_open", nil))
		return
	}
	c.back(adminPage, c.flash("billing.admin.paid.done", nil), hostweb.Flash{})
}

// pyISODate is whether datetime.date.fromisoformat (Python 3.12) accepts s:
// YYYY-MM-DD and YYYYMMDD, and the week forms YYYY-Www[-D] and YYYYWww[D],
// ASCII digits only, a real calendar date.
func pyISODate(s string) bool {
	ascii := func(t string) bool {
		for _, r := range t {
			if r < '0' || r > '9' {
				return false
			}
		}
		return t != ""
	}
	switch len(s) {
	case 10:
		if s[4] == '-' && s[7] == '-' && ascii(s[:4]+s[5:7]+s[8:]) {
			return validDay(s[:4], s[5:7], s[8:])
		}
		if s[4] == '-' && s[5] == 'W' && s[8] == '-' && ascii(s[:4]+s[6:8]+s[9:]) {
			return validWeek(s[:4], s[6:8], s[9:])
		}
	case 8:
		if ascii(s) {
			return validDay(s[:4], s[4:6], s[6:])
		}
		if s[4] == 'W' && ascii(s[:4]+s[5:]) {
			return validWeek(s[:4], s[5:7], s[7:])
		}
		if s[4] == '-' && s[5] == 'W' && ascii(s[:4]+s[6:]) {
			return validWeek(s[:4], s[6:], "1")
		}
	case 7:
		if s[4] == 'W' && ascii(s[:4]+s[5:]) {
			return validWeek(s[:4], s[5:], "1")
		}
	}
	return false
}

func validDay(y, m, d string) bool {
	yy, _ := strconv.Atoi(y)
	mm, _ := strconv.Atoi(m)
	dd, _ := strconv.Atoi(d)
	if yy < 1 || mm < 1 || mm > 12 || dd < 1 {
		return false
	}
	t := time.Date(yy, time.Month(mm), dd, 0, 0, 0, 0, time.UTC)
	return t.Year() == yy && int(t.Month()) == mm && t.Day() == dd
}

func validWeek(y, w, d string) bool {
	yy, _ := strconv.Atoi(y)
	ww, _ := strconv.Atoi(w)
	dd, _ := strconv.Atoi(d)
	if yy < 1 || ww < 1 || dd < 1 || dd > 7 {
		return false
	}
	_, weeks := time.Date(yy, 12, 28, 0, 0, 0, 0, time.UTC).ISOWeek()
	return ww <= weeks
}
