package invoices

// GET /invoices/{id}: routes/invoices.py invoice_detail, lines 902-927, with
// the template invoice_detail.html. The same handler answers
// GET /invoices/{id}.pdf (see downloads.go), because ServeMux wildcards are
// whole path segments.

import (
	"html/template"
	"net/http"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func init() { addRoutes(detailRoutes) }

func detailRoutes(d deps) []Route {
	return []Route{{"GET /invoices/{id}", "/invoices/{id}", d.invoiceGet}}
}

type detailItem struct {
	Description, Unit   string
	Quantity            int64
	UnitBase, UnitGross string
	Rate                int64
	VAT, Gross          string
}

type detailData struct {
	Invoice      invoiceRow
	Heading      string
	StateNote    string
	StatePill    template.HTML
	CanMarkPaid  bool
	CanSend      bool
	CanCancel    bool
	StayID       int64
	SettingsHref string
	Total        string
	IssueDate    string
	PaidRecorded string
	Payer        bool
	Items        []detailItem
	BaseTotal    string
	VATTotal     string
}

// invoiceGet routes GET /invoices/{id}: "<n>.pdf" is the download, "preview"
// is a path only POST serves (Starlette answers 405), a number is the detail
// page, anything else is a 404.
func (d deps) invoiceGet(w http.ResponseWriter, r *http.Request) {
	raw := r.PathValue("id")
	if strings.HasSuffix(raw, ".pdf") {
		d.pdfDownload(w, r, strings.TrimSuffix(raw, ".pdf"))
		return
	}
	if raw == "preview" {
		methodNotAllowed(w, "POST")
		return
	}
	if !isDigits(raw) {
		notFound(w)
		return
	}
	c, id := d.enterID(w, r, raw)
	if c == nil {
		return
	}
	if err := c.detail(id); err != nil {
		c.fail(err)
	}
}

func (c *call) detail(id int64) error {
	ctx := c.r.Context()
	inv, err := loadInvoice(ctx, c.pool, c.owner, id)
	if err != nil {
		return err
	}
	if inv == nil {
		c.back("/invoices", noFlash, c.flash("flash.error.no_such_invoice", nil))
		return nil
	}
	items, err := loadItems(ctx, c.pool, id)
	if err != nil {
		return err
	}
	var base, vat int64
	if err := c.pool.QueryRow(ctx,
		`SELECT COALESCE(SUM(base_haler), 0), COALESCE(SUM(vat_haler), 0) FROM invoice_item WHERE invoice_id = $1`,
		id).Scan(&base, &vat); err != nil {
		return err
	}
	d := detailData{
		Invoice: *inv, Heading: c.t("invoice.detail.title", map[string]any{"number": inv.Number}),
		Total: moneyCZK(inv.TotalHaler, 1), IssueDate: fmtDate(inv.IssueDate), Payer: inv.VATStatus == "payer",
		BaseTotal: moneyCZK(base, 1), VATTotal: moneyCZK(vat, 1),
		SettingsHref: "/entities?edit=" + itoa(inv.LegalEntityID) + "&next=" + pyQuote("/invoices/"+itoa(inv.ID)) + "#entity-invoice",
	}
	switch {
	case inv.Kind == "storno" || inv.Kind == "corrective":
		d.StatePill = template.HTML(`<span class="ui-badge ui-badge-neutral" data-tone="grey">` +
			template.HTMLEscapeString(c.t("invoice.kind."+inv.Kind, nil)) + `</span>`)
		d.StateNote = c.t("invoice.detail.note_"+inv.Kind, nil)
	case inv.paid():
		d.StatePill = template.HTML(`<span class="ui-badge ui-badge-done" data-tone="green">` +
			template.HTMLEscapeString(c.t("invoice.state.paid", nil)) + `</span>`)
		d.StateNote = c.t("invoice.detail.note_paid", nil)
	default:
		d.StatePill = template.HTML(`<span class="ui-badge ui-badge-neutral" data-tone="teal">` +
			template.HTMLEscapeString(c.t("invoice.state.unpaid", nil)) + `</span>`)
		d.StateNote = c.t("invoice.detail.note_unpaid", nil)
	}
	d.CanMarkPaid = inv.Kind == "invoice" && !inv.paid()
	d.CanSend = inv.BuyerEmail != "" && inv.Kind == "invoice"
	d.CanCancel = inv.Kind == "invoice" && inv.CorrectsInvoiceID == nil
	if inv.ReservationID != nil {
		d.StayID = *inv.ReservationID
	}
	if inv.Kind == "invoice" && inv.paid() {
		when := inv.PaidOn
		if when == "" {
			when = isoDate(inv.MarkedPaidAt)
		}
		d.PaidRecorded = fmtDate(when)
	}
	for _, it := range items {
		di := detailItem{Description: it.Description, Quantity: it.Quantity, Unit: it.Unit,
			Gross: moneyCZK(it.Gross, 1), UnitGross: moneyCZK(it.Gross, it.Quantity)}
		if it.Base != nil {
			di.UnitBase = moneyCZK(*it.Base, it.Quantity)
		} else {
			di.UnitBase = moneyCZK(0, it.Quantity)
		}
		if it.VAT != nil {
			di.VAT = moneyCZK(*it.VAT, 1)
		} else {
			di.VAT = moneyCZK(0, 1)
		}
		if it.VATRate != nil {
			di.Rate = *it.VATRate
		}
		d.Items = append(d.Items, di)
	}
	page := layout.Page{Title: d.Heading, Nav: "invoices", BodyKind: "detail", V2: true, BackURL: "/invoices"}
	return layout.Render(c.w, c.r, layout.Env{Pool: c.pool, Getenv: c.getenv, Now: c.at}, c.h, page, pages, "invoice_detail", d)
}

// pyQuote is Python's urllib.parse.quote(s) (safe "/"), which is what the
// Jinja urlencode filter applies to a string.
func pyQuote(s string) string {
	const hex = "0123456789ABCDEF"
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c >= 'a' && c <= 'z', c >= 'A' && c <= 'Z', c >= '0' && c <= '9', strings.IndexByte("_.-~/", c) >= 0:
			b.WriteByte(c)
		default:
			b.WriteByte('%')
			b.WriteByte(hex[c>>4])
			b.WriteByte(hex[c&15])
		}
	}
	return b.String()
}
