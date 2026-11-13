package invoices

// The two small POST actions of routes/invoices.py: invoice_mark_paid
// (930-940) and invoice_cancel (1004-1027).

import (
	"errors"
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

func init() { addRoutes(actionRoutes) }

func actionRoutes(d deps) []Route {
	return []Route{
		{"POST /invoices/{id}/paid", "/invoices/{id}/paid", d.markPaid},
		{"POST /invoices/{id}/cancel", "/invoices/{id}/cancel", d.cancel},
	}
}

// markPaid is invoice_mark_paid: POST /invoices/{id}/paid.
func (d deps) markPaid(w http.ResponseWriter, r *http.Request) {
	c, id := d.enterID(w, r, r.PathValue("id"))
	if c == nil {
		return
	}
	inv, err := loadInvoice(r.Context(), d.pool, c.owner, id)
	if err != nil {
		c.fail(err)
		return
	}
	if inv == nil {
		c.back("/invoices", noFlash, c.flash("flash.error.no_such_invoice", nil))
		return
	}
	if _, err := d.pool.Exec(r.Context(), `UPDATE invoice SET marked_paid_at = $1 WHERE id = $2`, stamp(c.at), id); err != nil {
		c.fail(err)
		return
	}
	if err := c.audit("invoice_marked_paid", "id="+itoa(id)); err != nil {
		c.fail(err)
		return
	}
	c.back("/invoices/"+itoa(id), c.flash("invoice.marked_paid_flash", nil), noFlash)
}

// cancel is invoice_cancel: POST /invoices/{id}/cancel.
func (d deps) cancel(w http.ResponseWriter, r *http.Request) {
	c, id := d.enterID(w, r, r.PathValue("id"))
	if c == nil {
		return
	}
	inv, err := loadInvoice(r.Context(), d.pool, c.owner, id)
	if err != nil {
		c.fail(err)
		return
	}
	if inv == nil {
		c.back("/invoices", noFlash, c.flash("flash.error.no_such_invoice", nil))
		return
	}
	newID, err := c.cancelInvoice(id, c.formStr("reason"), c.formStr("correction_date"))
	var refused errCancel
	if errors.As(err, &refused) {
		key := "invoice.err.not_cancellable"
		if refused == "reason_required" {
			key = "invoice.err.reason_required"
		}
		c.back("/invoices/"+itoa(id), noFlash, hostweb.Flash{Text: c.t(key, nil)})
		return
	}
	if err != nil {
		c.fail(err)
		return
	}
	c.back("/invoices/"+itoa(newID), c.flash("invoice.cancelled_flash", nil), noFlash)
}
