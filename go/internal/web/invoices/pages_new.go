package invoices

// GET /invoices/new: routes/invoices.py invoice_new (444-489), with the
// templates invoice_stay_picker.html and invoice_form.html.

import (
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func init() { addRoutes(newRoutes) }

func newRoutes(d deps) []Route {
	return []Route{{"GET /invoices/new", "/invoices/new", d.newHandler}}
}

type pickerData struct {
	Stays      []stayOption
	QuickStays []stayOption
	DetailsURL string
}

func (d deps) newHandler(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r)
	if c == nil {
		return
	}
	if err := c.newPage(); err != nil {
		c.fail(err)
	}
}

func (c *call) newPage() error {
	ctx := c.r.Context()
	today := pragueDay(c.at)
	q := c.r.URL.Query()
	raw := queryLast(q, "reservation_id")
	if raw == "" {
		stays, err := stayOptions(ctx, c.pool, c.owner, today)
		if err != nil {
			return err
		}
		quick, err := quickStays(ctx, c.pool, stays, today)
		if err != nil {
			return err
		}
		list, err := entities(ctx, c.pool, c.owner)
		if err != nil {
			return err
		}
		page := layout.Page{Title: c.t("invoice.new", nil), Nav: "invoices", BodyKind: "form", V2: true, BackURL: "/invoices"}
		return layout.Render(c.w, c.r, layout.Env{Pool: c.pool, Getenv: c.getenv, Now: c.at}, c.h, page, pages, "invoice_picker",
			pickerData{Stays: stays, QuickStays: quick, DetailsURL: invoiceDetailsURL(list)})
	}
	st, err := stayFor(ctx, c.pool, c.owner, raw)
	if err != nil {
		return err
	}
	if st == nil {
		c.back("/invoices/new", noFlash, c.flash("invoice.err.no_stay", nil))
		return nil
	}
	if problem := stayProblem(st, today); problem != "" {
		c.back("/invoices/new", noFlash, c.flash(problem, nil))
		return nil
	}
	active, err := activeInvoiceForStay(ctx, c.pool, st.ReservationID)
	if err != nil {
		return err
	}
	if active != nil {
		c.back("/invoices/"+itoa(active.ID), noFlash, c.flash("invoice.err.stay_has_invoice", nil))
		return nil
	}
	list, err := entities(ctx, c.pool, c.owner)
	if err != nil {
		return err
	}
	e := entityForStay(list, st, "", queryLast(q, "entity"))
	if e != nil && queryLast(q, "entity") != itoa(e.ID) {
		// Pin the operator in the URL once, so the details page returns here.
		redirectSeeOther(c.w, "/invoices/new?reservation_id="+itoa(st.ReservationID)+"&entity="+itoa(e.ID))
		return nil
	}
	if e != nil && st.EntityID != nil && *st.EntityID == e.ID {
		list = []entity{*e} // the property names its operator: no other choice
	}
	data, err := c.formContext(list, e, nil, nil, nil, st)
	if err != nil {
		return err
	}
	if e == nil {
		data.Errors = []string{c.t("invoice.err.no_entity", nil)}
	}
	return c.renderForm(data, 0)
}

// redirectSeeOther is RedirectResponse(url, status_code=303) for a url that
// needs no quoting.
func redirectSeeOther(w http.ResponseWriter, location string) {
	w.Header().Set("Location", location)
	w.WriteHeader(http.StatusSeeOther)
}

// renderForm renders invoice_form.html with status (0 is 200).
func (c *call) renderForm(data formData, status int) error {
	page := layout.Page{Title: c.t("invoice.new", nil), Nav: "invoices", BodyKind: "form", V2: true, BackURL: "/invoices", Status: status}
	return layout.Render(c.w, c.r, layout.Env{Pool: c.pool, Getenv: c.getenv, Now: c.at}, c.h, page, pages, "invoice_form", data)
}
