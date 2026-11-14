package invoices

// POST /invoices/preview and POST /invoices: routes/invoices.py
// invoice_preview (790-811) and invoice_issue (814-880), with their helpers
// _draft (304-309) and _preview_view (312-367).

import (
	"errors"
	"net/http"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pdf"
)

func init() { addRoutes(issueRoutes) }

func issueRoutes(d deps) []Route {
	return []Route{
		{"POST /invoices/preview", "/invoices/preview", d.previewHandler},
		{"POST /invoices", "/invoices", d.issueHandler},
	}
}

// previewInvoice is _preview_view: the draft as the view invoice_pdf.render
// takes. The number and variable symbol are dashes, the country name is empty.
func previewInvoice(d draft) pdf.Invoice {
	return pdf.Invoice{
		Number: "—", VS: "—", Kind: d.Kind, VATStatus: d.VATStatus, IssueDate: d.IssueDate, DUZP: d.DUZP,
		DueDate: d.DueDate, PaidOn: d.PaidOn, PaidViaLabel: customPaidViaLabel(d.PaidVia), Note: d.Note,
		SellerName: d.Seller.Name, SellerSeat: d.Seller.Seat, SellerICO: d.Seller.ICO, SellerDIC: d.Seller.DIC,
		SellerRegistry: d.Seller.Registry, SellerBankAccount: d.Seller.BankAccount, SellerIBAN: d.Seller.IBAN,
		SellerBIC: d.Seller.BIC, SellerEmail: d.Seller.Email, SellerPhone: d.Seller.Phone,
		BuyerName: d.Buyer.Name, BuyerStreet: d.Buyer.Street, BuyerCity: d.Buyer.City, BuyerZip: d.Buyer.Zip,
		BuyerICO: d.Buyer.ICO, BuyerDIC: d.Buyer.DIC, StayLabel: d.StayLabel, TotalHaler: d.TotalHaler,
	}
}

func previewItems(d draft) []pdf.Item {
	out := make([]pdf.Item, len(d.Items))
	for i, it := range d.Items {
		p := pdf.Item{Description: it.Description, Quantity: int(it.Quantity), Unit: it.Unit, GrossHaler: it.Gross}
		if it.VATRate != nil {
			r := int(*it.VATRate)
			p.VATRate = &r
		}
		if it.Base != nil {
			p.BaseHaler = *it.Base
		}
		if it.VAT != nil {
			p.VATHaler = *it.VAT
		}
		out[i] = p
	}
	return out
}

// posted is what the two POST handlers read before they diverge: the host's
// operators, the stay and the chosen operator. ok false means the handler
// already redirected.
type posted struct {
	list   []entity
	stay   *stay
	entity *entity
}

func (c *call) loadPosted(previewOnly bool) (posted, bool, error) {
	ctx := c.r.Context()
	var p posted
	var err error
	if p.list, err = entities(ctx, c.pool, c.owner); err != nil {
		return p, false, err
	}
	if p.stay, err = stayFor(ctx, c.pool, c.owner, c.formStr("reservation_id")); err != nil {
		return p, false, err
	}
	today := pragueDay(c.at)
	if previewOnly {
		if p.stay == nil || stayProblem(p.stay, today) != "" {
			c.back("/invoices/new", noFlash, c.flash("invoice.err.no_stay", nil))
			return p, false, nil
		}
	} else {
		if p.stay == nil {
			c.back("/invoices/new", noFlash, c.flash("invoice.err.no_stay", nil))
			return p, false, nil
		}
		if problem := stayProblem(p.stay, today); problem != "" {
			c.back("/invoices/new", noFlash, c.flash(problem, nil))
			return p, false, nil
		}
	}
	p.entity = entityForStay(p.list, p.stay, c.formStr("legal_entity_id"), queryLast(c.r.URL.Query(), "entity"))
	if p.entity == nil {
		c.back("/invoices/new", noFlash, c.flash("invoice.err.no_entity", nil))
		return p, false, nil
	}
	return p, true, nil
}

// previewHandler is invoice_preview: the draft as an inline PDF with a
// PREVIEW watermark; nothing is saved.
func (d deps) previewHandler(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r)
	if c == nil {
		return
	}
	p, ok, err := c.loadPosted(true)
	if err != nil {
		c.fail(err)
		return
	}
	if !ok {
		return
	}
	dr := buildDraft(*p.entity, r.PostForm, pragueDay(c.at), p.stay)
	blob, err := pdf.Render(previewInvoice(dr), previewItems(dr), dr.Lang, true, false)
	if err != nil {
		c.fail(err)
		return
	}
	writePDF(w, blob, map[string]string{"Content-Disposition": `inline; filename="nahled-faktura.pdf"`})
}

func hasFillKey(c *call) bool {
	for key := range c.r.PostForm {
		if strings.HasPrefix(key, "fill_") {
			return true
		}
	}
	return false
}

// issueHandler is invoice_issue: POST /invoices.
func (d deps) issueHandler(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r)
	if c == nil {
		return
	}
	if err := c.issue(); err != nil {
		c.fail(err)
	}
}

func (c *call) issue() error {
	ctx := c.r.Context()
	p, ok, err := c.loadPosted(false)
	if err != nil || !ok {
		return err
	}
	if c.formTruthy("fill_buyer_from_register") {
		values, rows := formState(c)
		if values["buyer_kind"] == "company" {
			guest, err := leadGuest(ctx, c.pool, c.getenv, p.stay, c.at)
			if err != nil {
				return err
			}
			dropGuestSuggestion(values, guest)
		}
		meta, err := c.buyerAresFill(values)
		if err != nil {
			return err
		}
		data, err := c.formContext(p.list, p.entity, nil, values, rows, p.stay)
		if err != nil {
			return err
		}
		data.AresError, data.AresNote = meta.Error, meta.Note
		return c.renderForm(data, 0)
	}
	if c.formTruthy("fill_from_guest") {
		guest, err := leadGuest(ctx, c.pool, c.getenv, p.stay, c.at)
		if err != nil {
			return err
		}
		values, rows := formState(c)
		if guest != nil {
			mergeGuestFill(values, guest)
		}
		data, err := c.formContext(p.list, p.entity, nil, values, rows, p.stay)
		if err != nil {
			return err
		}
		if guest == nil {
			data.Errors = []string{c.t("invoice.fill_guest.none", nil)}
		}
		return c.renderForm(data, 0)
	}
	if hasFillKey(c) {
		values, rows := formState(c)
		data, err := c.formContext(p.list, p.entity, nil, values, rows, p.stay)
		if err != nil {
			return err
		}
		return c.renderForm(data, 0)
	}
	dr := buildDraft(*p.entity, c.r.PostForm, pragueDay(c.at), p.stay)
	issues := validateForIssue(dr)
	if len(issues) == 0 {
		long, err := pdf.TooLong(previewInvoice(dr), previewItems(dr), dr.Lang)
		if err != nil {
			return err
		}
		if long {
			issues = []issue{{"note", "invoice.err.too_long"}}
		}
	}
	if len(issues) > 0 {
		errs := make([]string, len(issues))
		for i, is := range issues {
			errs[i] = c.t(is.Message, nil)
		}
		values, rows := formState(c)
		data, err := c.formContext(p.list, p.entity, errs, values, rows, p.stay)
		if err != nil {
			return err
		}
		return c.renderForm(data, http.StatusUnprocessableEntity)
	}
	id, number, err := c.issueInvoice(dr)
	var limit *stayLimit
	if errors.As(err, &limit) {
		if limit.InvoiceID != 0 {
			c.back("/invoices/"+itoa(limit.InvoiceID), noFlash, c.flash(limit.Key, nil))
		} else {
			c.back("/reservations/"+itoa(p.stay.ReservationID), noFlash, c.flash(limit.Key, nil))
		}
		return nil
	}
	if err != nil {
		return err
	}
	c.back("/invoices/"+itoa(id), c.flash("invoice.issued_flash", map[string]any{"number": number}), noFlash)
	return nil
}
