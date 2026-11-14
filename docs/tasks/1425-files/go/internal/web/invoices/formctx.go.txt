package invoices

// The context of the invoice form: routes/invoices.py _form_context (266-301)
// and _form_state (244-263), shared by GET /invoices/new and the POST
// re-renders.

import (
	"strings"
)

type entityOption struct {
	ID       int64
	Name     string
	Payer    bool
	Selected bool
}

type extraKindOption struct{ Value, Label string }

// itemRow is one raw extra line the browser posted (form_item_rows).
type itemRow struct {
	Kind, Description, Quantity, Unit, UnitPrice, VATRate string
}

type formData struct {
	Errors         []string
	Entity         *entity
	Entities       []entityOption
	Payer          bool
	StayID         int64
	StayLabel      string
	EditHref       string
	Values         map[string]string
	ItemRows       []itemRow
	Countries      []countryOption
	ExtraKinds     []extraKindOption
	ShowFillGuest  bool
	GuestPrefilled bool
	BuyerKind      string
	StayPriceHint  string
	NextNumber     string
	AresError      string
	AresNote       string
	Today          string
	StayRates      []string
	ItemRates      []string
}

// formState is _form_state: a failed POST reshaped so the re-render loses
// nothing the host typed. It is never empty, so the render is not "fresh".
func formState(c *call) (map[string]string, []itemRow) {
	state := map[string]string{}
	for _, key := range []string{
		"stay_price", "stay_vat_rate", "reservation_id",
		"buyer_name", "buyer_street", "buyer_city", "buyer_zip", "buyer_country",
		"buyer_ico", "buyer_dic", "buyer_email", "paid_via", "paid_via_custom",
		"due_date", "duzp", "note", "buyer_kind", "legal_entity_id",
	} {
		state[key] = c.formStr(key)
	}
	// Radio value "0" (Payment requested) is truthy in Python; only "1"/"on"
	// mean paid. A 422 or fill-* re-render must keep the host's choice.
	if v := c.formStr("already_paid"); v == "1" || v == "on" {
		state["already_paid"] = "1"
	} else {
		state["already_paid"] = "0"
	}
	state["lang"] = c.formStr("lang")
	return state, formItemRows(c.r.PostForm)
}

// formItemRows is form_item_rows: trailing blank rows (a cloned template row)
// are dropped but a part-typed row survives.
func formItemRows(form map[string][]string) []itemRow {
	kinds, descs := form["item_kind"], form["item_description"]
	qtys, units := form["item_quantity"], form["item_unit"]
	prices, rates := form["item_unit_price"], form["item_vat_rate"]
	var rows []itemRow
	for i := 0; i < maxLen(kinds, descs, qtys, units, prices, rates); i++ {
		row := itemRow{
			Kind: at(kinds, i, ""), Description: at(descs, i, ""), Quantity: at(qtys, i, "1"),
			Unit: at(units, i, ""), UnitPrice: at(prices, i, ""), VATRate: at(rates, i, "21"),
		}
		if strings.TrimSpace(row.Kind) == "" && strings.TrimSpace(row.Description) == "" && strings.TrimSpace(row.UnitPrice) == "" {
			continue
		}
		rows = append(rows, row)
	}
	return rows
}

// formContext is _form_context. values nil means a fresh page; formState
// always gives a non-nil map.
func (c *call) formContext(list []entity, e *entity, errs []string, values map[string]string, rows []itemRow, st *stay) (formData, error) {
	ctx := c.r.Context()
	fresh := values == nil
	vals := map[string]string{}
	for k, v := range values {
		vals[k] = v
	}
	if fresh && st.GuestEmail != "" {
		vals["buyer_email"] = st.GuestEmail
	}
	docLang := "en"
	if c.lang == "cs" {
		docLang = "cs"
	}
	guest, err := leadGuest(ctx, c.pool, c.getenv, st, c.at)
	if err != nil {
		return formData{}, err
	}
	prefilled := false
	if fresh && guest != nil {
		// 0836: suggest the lead guest as buyer on first open; the host checks before issuing.
		mergeGuestFill(vals, guest)
		prefilled = vals["buyer_name"] != ""
	}
	kind := vals["buyer_kind"]
	if kind != "guest" && kind != "company" {
		kind = "guest"
		if strings.TrimSpace(vals["buyer_ico"]) != "" {
			kind = "company"
		}
	}
	hint, err := lastStayPriceHint(ctx, c.pool, c.owner, st.ApartmentID)
	if err != nil {
		return formData{}, err
	}
	if e != nil {
		_, a := vals["already_paid"]
		_, b := vals["paid_via"]
		_, d := vals["paid_via_custom"]
		if !a && !b && !d {
			remembered, err := rememberedPaidVia(ctx, c.pool, c.owner, e.ID)
			if err != nil {
				return formData{}, err
			}
			for k, v := range remembered {
				vals[k] = v
			}
		}
	}
	countryList, err := countryOptions(ctx, c.pool, c.lang)
	if err != nil {
		return formData{}, err
	}
	data := formData{
		Errors: errs, Entity: e, StayID: st.ReservationID, Values: vals, ItemRows: rows, Countries: countryList,
		StayLabel:     stayLabel(st.PropertyName, st.DateFrom, st.DateTo, docLang),
		ShowFillGuest: guest != nil, GuestPrefilled: prefilled, BuyerKind: kind, StayPriceHint: hint,
		Today: pragueDay(c.at).Format("2006-01-02"), StayRates: []string{"12", "21", "0"}, ItemRates: []string{"21", "12", "0"},
	}
	for _, k := range extraKinds {
		data.ExtraKinds = append(data.ExtraKinds, extraKindOption{Value: k, Label: c.t("invoice.extra."+k, nil)})
	}
	if e != nil {
		data.Payer = e.payer()
		number, err := previewNumber(ctx, c.pool, *e, c.at.UTC().Year())
		if err != nil {
			return formData{}, err
		}
		data.NextNumber = number
		data.EditHref = "/entities?edit=" + itoa(e.ID) + "&next=" +
			pyQuote("/invoices/new?reservation_id="+itoa(st.ReservationID)+"&entity="+itoa(e.ID)) + "#entity-invoice"
		for _, o := range list {
			data.Entities = append(data.Entities, entityOption{ID: o.ID, Name: o.Name, Payer: o.payer(), Selected: o.ID == e.ID})
		}
	}
	return data, nil
}
