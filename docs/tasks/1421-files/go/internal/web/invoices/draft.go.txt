package invoices

// The invoice draft: App/app/invoices.py build_draft with its helpers
// (seller_snapshot, _stay_item, _extras_from_form, validate_for_issue). Pure
// functions over the posted form; nothing here reads the database. Only the
// stay path is ported: every route passes a stay, so _items_from_form (the
// free-form lines of an invoice without a stay) is not reachable.

import (
	"math/big"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// Limits of invoices.py.
const (
	maxItems         = 4
	staleDays        = 400 // STAY_PAST_DAYS
	futureDays       = 365 // STAY_FUTURE_DAYS
	stayMaxInvoices  = 3
	extraMaxQuantity = 99
	otherMaxChars    = 60
)

// extraKinds is EXTRA_KINDS.
var extraKinds = []string{"cleaning", "stay_fee", "breakfast", "parking", "pet", "extra_bed", "late_checkout", "other"}

var extraLabels = map[string]map[string]string{
	"cs": {
		"cleaning": "Úklid", "stay_fee": "Poplatek z pobytu", "breakfast": "Snídaně",
		"parking": "Parkování", "pet": "Domácí zvíře", "extra_bed": "Přistýlka",
		"late_checkout": "Pozdní odjezd",
	},
	"en": {
		"cleaning": "Cleaning", "stay_fee": "Local stay fee", "breakfast": "Breakfast",
		"parking": "Parking", "pet": "Pet", "extra_bed": "Extra bed",
		"late_checkout": "Late check-out",
	},
}

var stayLinePrefix = map[string]string{"cs": "Ubytování", "en": "Accommodation"}

var paidViaLabels = map[string]string{
	"airbnb": "Airbnb", "booking": "Booking.com", "direct_transfer": "Převodem",
	"cash": "Hotově", "other": "Jinak",
}

// customPaidViaLabel is custom_paid_via_label.
func customPaidViaLabel(paidVia string) string {
	if paidVia == "" {
		return ""
	}
	if label, ok := paidViaLabels[paidVia]; ok {
		return label
	}
	return paidVia
}

// entity is a legal_entity row (the columns the invoice pages read).
type entity struct {
	ID             int64
	Name           string
	Seat           string
	ICO            string
	DIC            string
	ContactEmail   string
	ContactPhone   string
	BankAccount    string
	IBAN           string
	BIC            string
	VATStatus      string // never empty: "non_payer" when unset
	RegistryEntry  string
	InvoicePrefix  string
	NextNumber     *int64
	NextNumberYear *int64
	DueDays        int64
}

func (e entity) payer() bool { return e.VATStatus == "payer" }

// stay is _stay_for: the host's own reservation, shaped for the draft.
type stay struct {
	ReservationID int64
	ApartmentID   int64
	DateFrom      string
	DateTo        string
	Status        string
	Source        string
	GuestEmail    string
	PropertyName  string
	EntityID      *int64 // the property's operator, when it has one
}

type item struct {
	Kind         string
	ExtraKind    string
	Description  string
	Quantity     int64
	Unit         string
	VATRate      *int64
	Base         *int64
	VAT          *int64
	Gross        int64
	PriceInvalid bool
}

type sellerSnap struct {
	Name, Seat, ICO, DIC, Registry, BankAccount, IBAN, BIC, Email, Phone string
}

type buyerSnap struct {
	Name, Street, City, Zip, Country, ICO, DIC, Email string
}

// draft is the dict build_draft returns. An empty string stands for None in
// the date and text fields Python writes as `... or None`.
type draft struct {
	Kind          string
	Lang          string
	VATStatus     string
	IssueDate     string
	DUZP          string
	DueDate       string
	PaidOn        string
	PaidVia       string
	Seller        sellerSnap
	Buyer         buyerSnap
	Note          string
	Items         []item
	TotalBase     *int64
	TotalVAT      *int64
	TotalHaler    int64
	ReservationID *int64
	ApartmentID   *int64
	StayFrom      string
	StayTo        string
	StayLabel     string
	LegalEntityID int64
	OwnerUserID   *int64
	// Corrections (cancel) only.
	CorrectsInvoiceID *int64
	CorrectionReason  string
	CorrectionDate    string
}

type issue struct{ Field, Message string }

func isoDate(s string) string {
	if len(s) > 10 {
		return s[:10]
	}
	return s
}

// stayNights is stay_nights: nights between check-in and check-out, 0 when a
// date is unreadable (date.fromisoformat on the first ten characters).
func stayNights(from, to string) int {
	a, err1 := time.Parse("2006-01-02", isoDate(from))
	b, err2 := time.Parse("2006-01-02", isoDate(to))
	if err1 != nil || err2 != nil {
		return 0
	}
	return int(b.Sub(a).Hours() / 24)
}

// stayProblem is stay_problem: "" when an invoice may be issued for the stay,
// else an i18n key.
func stayProblem(s *stay, today time.Time) string {
	if s == nil {
		return "invoice.err.no_stay"
	}
	if s.Source == "demo" {
		return "invoice.err.demo_stay"
	}
	if s.Status == "cancelled" {
		return "invoice.err.stay_cancelled"
	}
	if stayNights(s.DateFrom, s.DateTo) < 1 {
		return "invoice.err.stay_dates"
	}
	if isoDate(s.DateTo) < today.AddDate(0, 0, -staleDays).Format("2006-01-02") {
		return "invoice.err.stay_too_old"
	}
	if isoDate(s.DateFrom) > today.AddDate(0, 0, futureDays).Format("2006-01-02") {
		return "invoice.err.stay_too_far"
	}
	return ""
}

func nightsText(nights int, lang string) string {
	var word string
	if lang == "cs" {
		switch {
		case nights == 1:
			word = "noc"
		case nights >= 2 && nights <= 4:
			word = "noci"
		default:
			word = "nocí"
		}
	} else if nights == 1 {
		word = "night"
	} else {
		word = "nights"
	}
	return itoa(int64(nights)) + " " + word
}

// fmtDate is validation.fmt_date: DD.MM.YYYY, or the input unchanged.
func fmtDate(value string) string {
	if t, ok := validation.ParseISODate(value); ok {
		return t.Format("02.01.2006")
	}
	return value
}

// fmtDateRange is validation.fmt_date_range (en dash).
func fmtDateRange(from, to string) string {
	a, b := fmtDate(from), fmtDate(to)
	if a != "" && b != "" {
		return a + " – " + b
	}
	if a != "" {
		return a
	}
	return b
}

// stayLabel is stay_label: 'Chata, 12.10.2026 – 15.10.2026 (3 noci)'.
func stayLabel(property, from, to, lang string) string {
	return property + ", " + fmtDateRange(from, to) + " (" + nightsText(stayNights(from, to), lang) + ")"
}

func present(form url.Values, key string) bool {
	_, ok := form[key]
	return ok
}

// ---- amounts ----

func priceInvalid(raw string, price *big.Rat) bool {
	if raw == "" {
		return true
	}
	if _, ok := parseDecimal(raw); !ok {
		return true
	}
	return price.Sign() <= 0
}

func cut(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

func at(values []string, i int, def string) string {
	if i < len(values) {
		return values[i]
	}
	return def
}

func ptr(v int64) *int64 { return &v }

// stayItem is _stay_item: line 1, only the price (and, for payers, the rate)
// comes from the form.
func stayItem(form url.Values, payer bool, label, lang string) item {
	raw := formStr(form, "stay_price")
	price := toDecimal(raw)
	it := item{Kind: "accommodation", ExtraKind: "stay", Quantity: 1}
	if payer {
		rate := formStr(form, "stay_vat_rate")
		if rate == "" {
			rate = "12"
		}
		r := toRate(rate)
		base, vat, gross := vatParts(1, price, r)
		it.VATRate, it.Base, it.VAT, it.Gross = ptr(r), ptr(base), ptr(vat), gross
	} else {
		it.Gross = grossNoVAT(1, price)
	}
	it.Description = cut(stayLinePrefix[lang]+" – "+label, 150)
	if lang == "cs" {
		it.Unit = "pobyt"
	} else {
		it.Unit = "stay"
	}
	it.PriceInvalid = priceInvalid(raw, price)
	return it
}

func maxLen(lists ...[]string) int {
	n := 0
	for _, l := range lists {
		if len(l) > n {
			n = len(l)
		}
	}
	return n
}

func isExtraKind(kind string) bool {
	for _, k := range extraKinds {
		if k == kind {
			return true
		}
	}
	return false
}

// extrasFromForm is _extras_from_form: lines 2-4. The wording comes from
// extraLabels; only "other" takes typed text.
func extrasFromForm(form url.Values, payer bool, lang string) []item {
	kinds, descs := form["item_kind"], form["item_description"]
	qtys, units := form["item_quantity"], form["item_unit"]
	prices, rates := form["item_unit_price"], form["item_vat_rate"]
	var items []item
	for i := 0; i < maxLen(kinds, descs, qtys, units, prices, rates); i++ {
		kind := strings.TrimSpace(at(kinds, i, ""))
		text := strings.TrimSpace(at(descs, i, ""))
		rawPrice := strings.TrimSpace(at(prices, i, ""))
		if kind == "" && text == "" && rawPrice == "" {
			continue // an untouched blank row
		}
		if kind == "" {
			kind = "other"
		}
		// "stay" is the accommodation line only; a forged extra must not use it.
		if kind == "stay" {
			kind = "invalid"
		}
		quantity := toInt(at(qtys, i, "1"))
		price := toDecimal(rawPrice)
		var description string
		if kind == "other" {
			description = cut(text, otherMaxChars)
		} else {
			description = extraLabels[lang][kind]
		}
		it := item{ExtraKind: kind, Description: description, Quantity: quantity}
		if payer {
			// The local stay fee is a municipal fee outside VAT (owner, 2026-10-08).
			rate := int64(0)
			if kind != "stay_fee" {
				rate = toRate(at(rates, i, ""))
			}
			base, vat, gross := vatParts(quantity, price, rate)
			it.VATRate, it.Base, it.VAT, it.Gross = ptr(rate), ptr(base), ptr(vat), gross
		} else {
			it.Gross = grossNoVAT(quantity, price)
		}
		if kind == "stay_fee" {
			it.Kind = "stay_fee"
		} else {
			it.Kind = "other"
		}
		it.Unit = cut(strings.TrimSpace(at(units, i, "")), 20)
		it.PriceInvalid = priceInvalid(rawPrice, price)
		items = append(items, it)
	}
	return items
}

// ---- seller ----

var (
	accountRE = regexp.MustCompile(`^(?:([0-9]{1,6})-)?([0-9]{2,10})/([0-9]{4})$`)
	ibanRE    = regexp.MustCompile(`^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$`)
)

var weights = [10]int{6, 3, 7, 9, 10, 5, 8, 4, 2, 1}

func mod11OK(digits string) bool {
	padded := strings.Repeat("0", max(0, 10-len(digits))) + digits
	sum := 0
	for i, c := range padded {
		sum += int(c-'0') * weights[i]
	}
	return sum%11 == 0
}

func ibanOK(iban string) bool {
	moved := iban[4:] + iban[:4]
	mod := 0
	for _, c := range moved {
		if c >= 'A' && c <= 'Z' {
			mod = (mod*100 + int(c-'A') + 10) % 97
		} else {
			mod = (mod*10 + int(c-'0')) % 97
		}
	}
	return mod == 1
}

// normaliseAccount is payments.normalise_account: (display, iban), ok false
// where Python raises ValueError.
func normaliseAccount(raw string) (string, string, bool) {
	text := strings.ToUpper(strings.Join(strings.Fields(raw), ""))
	if ibanRE.MatchString(text) {
		if !ibanOK(text) {
			return "", "", false
		}
		return text, text, true
	}
	m := accountRE.FindStringSubmatch(text)
	if m == nil {
		return "", "", false
	}
	prefix, number, bank := m[1], m[2], m[3]
	if (prefix != "" && !mod11OK(prefix)) || !mod11OK(number) {
		return "", "", false
	}
	bban := bank + strings.Repeat("0", 6-len(prefix)) + prefix + strings.Repeat("0", 10-len(number)) + number
	mod := 0
	for _, c := range bban + "123500" {
		mod = (mod*10 + int(c-'0')) % 97
	}
	display := number + "/" + bank
	if prefix != "" {
		display = prefix + "-" + number + "/" + bank
	}
	return display, "CZ" + pad2(int64(98-mod)) + bban, true
}

// sellerSnapshot is seller_snapshot: a field the form carries is used
// verbatim (a deliberate blank included); the rest falls back to the
// operator's stored details. The invoice form posts none of the seller_*
// fields; a forged post can.
func sellerSnapshot(e entity, form url.Values) sellerSnap {
	pick := func(key, stored string) string {
		if present(form, "seller_"+key) {
			return formStr(form, "seller_"+key)
		}
		return stored
	}
	s := sellerSnap{
		Name: pick("name", e.Name), Seat: pick("seat", e.Seat), ICO: pick("ico", e.ICO),
		DIC: pick("dic", e.DIC), Registry: pick("registry", e.RegistryEntry),
		BankAccount: pick("bank_account", e.BankAccount), IBAN: pick("iban", e.IBAN),
		BIC: pick("bic", e.BIC), Email: pick("email", e.ContactEmail), Phone: pick("phone", e.ContactPhone),
	}
	if present(form, "seller_bank_account") {
		if formBank := formStr(form, "seller_bank_account"); formBank != "" {
			if display, iban, ok := normaliseAccount(formBank); ok {
				s.BankAccount, s.IBAN = display, iban
			} else {
				// A bank number the helper rejects is never printed; the
				// operator's stored account stays on the document.
				s.BankAccount, s.IBAN = e.BankAccount, e.IBAN
			}
		} else {
			s.BankAccount, s.IBAN = "", ""
		}
	}
	return s
}

// buildDraft is build_draft for a stay (every route passes one).
func buildDraft(e entity, form url.Values, today time.Time, st *stay) draft {
	docLang := "en"
	if formStr(form, "lang") == "cs" {
		docLang = "cs"
	}
	payer := e.payer()
	label := stayLabel(st.PropertyName, st.DateFrom, st.DateTo, docLang)
	items := append([]item{stayItem(form, payer, label, docLang)}, extrasFromForm(form, payer, docLang)...)
	d := draft{Kind: "invoice", Lang: docLang, VATStatus: e.VATStatus, Items: items}
	if payer {
		var base, vat int64
		for _, it := range items {
			if it.Base != nil {
				base += *it.Base
			}
			if it.VAT != nil {
				vat += *it.VAT
			}
		}
		d.TotalBase, d.TotalVAT = ptr(base), ptr(vat)
	}
	for _, it := range items {
		d.TotalHaler += it.Gross
	}
	// The payment row is a radio pair ("already paid" = "1", "payment
	// requested" = "0"); older clients post a checkbox that appears only when
	// ticked, so both spellings land on the same decision.
	paid := formStr(form, "already_paid")
	alreadyPaid := paid == "1" || paid == "on"
	dueDate := formStr(form, "due_date")
	if dueDate == "" && !alreadyPaid {
		dueDate = today.AddDate(0, 0, int(e.DueDays)).Format("2006-01-02")
	}
	paidVia := ""
	if alreadyPaid {
		paidVia = formStr(form, "paid_via")
		if paidVia == "custom" {
			paidVia = cut(formStr(form, "paid_via_custom"), 60)
		}
	}
	d.IssueDate = today.Format("2006-01-02")
	d.DUZP = formStr(form, "duzp")
	d.DueDate = dueDate
	if alreadyPaid {
		d.PaidOn = d.IssueDate
	}
	d.PaidVia = paidVia
	d.Seller = sellerSnapshot(e, form)
	country := formStr(form, "buyer_country")
	if country == "" {
		country = "CZE"
	}
	d.Buyer = buyerSnap{
		Name: formStr(form, "buyer_name"), Street: formStr(form, "buyer_street"),
		City: formStr(form, "buyer_city"), Zip: formStr(form, "buyer_zip"), Country: country,
		ICO: formStr(form, "buyer_ico"), DIC: formStr(form, "buyer_dic"), Email: formStr(form, "buyer_email"),
	}
	d.Note = cut(formStr(form, "note"), 300)
	stayTo := isoDate(st.DateTo)
	d.ReservationID, d.ApartmentID = ptr(st.ReservationID), ptr(st.ApartmentID)
	d.StayFrom, d.StayTo, d.StayLabel = isoDate(st.DateFrom), stayTo, label
	if d.DUZP == "" {
		// Tax point: the check-out day, never in the future.
		d.DUZP = min(stayTo, d.IssueDate)
	}
	d.LegalEntityID = e.ID
	return d
}

// stayIssues is _stay_issues.
func stayIssues(d draft) []issue {
	items := d.Items
	if len(items) == 0 || items[0].ExtraKind != "stay" {
		return []issue{{"items", "invoice.err.extra_kind"}}
	}
	var out []issue
	stayGross := items[0].Gross
	extras := items[1:]
	bad, others, badQty := false, 0, false
	for _, it := range extras {
		if !isExtraKind(it.ExtraKind) || it.Description == "" {
			bad = true
		}
		if it.ExtraKind == "other" {
			others++
		}
		if it.Quantity < 1 || it.Quantity > extraMaxQuantity {
			badQty = true
		}
	}
	if bad {
		out = append(out, issue{"items", "invoice.err.extra_kind"})
	}
	if others > 1 {
		out = append(out, issue{"items", "invoice.err.one_other"})
	}
	if badQty {
		out = append(out, issue{"items", "invoice.err.extra_quantity"})
	}
	// Skip noisy caps when the stay price is already invalid (the amount
	// error covers it).
	if items[0].PriceInvalid || stayGross <= 0 {
		return out
	}
	var extrasGross, otherGross int64
	for _, it := range extras {
		extrasGross += it.Gross
		if it.ExtraKind == "other" {
			otherGross += it.Gross
		}
	}
	// EXTRAS_MAX_SHARE 1.00, OTHER_MAX_SHARE 0.30, exactly.
	if extrasGross > stayGross {
		out = append(out, issue{"items", "invoice.err.extras_cap"})
	}
	if otherGross*100 > stayGross*30 {
		out = append(out, issue{"items", "invoice.err.other_cap"})
	}
	return out
}

// validateForIssue is validate_for_issue: the legal minimum, as issue keys.
func validateForIssue(d draft) []issue {
	var out []issue
	if d.Seller.Name == "" {
		out = append(out, issue{"seller_name", "invoice.err.seller_name"})
	}
	if d.Seller.Seat == "" {
		out = append(out, issue{"seller_seat", "invoice.err.seller_seat"})
	}
	if d.Seller.Registry == "" {
		out = append(out, issue{"seller_registry", "invoice.err.registry"})
	}
	if d.VATStatus == "payer" && d.Seller.DIC == "" {
		out = append(out, issue{"seller_dic", "invoice.err.seller_dic"})
	}
	if d.Buyer.Name == "" {
		out = append(out, issue{"buyer_name", "invoice.buyer.required"})
	}
	if len(d.Items) == 0 {
		out = append(out, issue{"items", "invoice.err.no_items"})
	} else if len(d.Items) > maxItems {
		out = append(out, issue{"items", "invoice.err.too_many_items"})
	}
	anyInvalid := false
	for _, it := range d.Items {
		if it.PriceInvalid {
			anyInvalid = true
		}
	}
	if d.TotalHaler <= 0 || anyInvalid {
		out = append(out, issue{"price_czk", "invoice.err.amount"})
	}
	if d.Kind == "invoice" && d.ReservationID != nil {
		out = append(out, stayIssues(d)...)
	}
	return out
}
