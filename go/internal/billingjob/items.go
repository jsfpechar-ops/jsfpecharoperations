package billingjob

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pdf"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// account is the billing_account columns the invoicer reads. Text columns that
// Python reads with `or ""` are COALESCEd in the query.
type account struct {
	Plan, Interval                    *string
	AddonTTLock, AddonWhitelabel      bool
	ApartmentsBilled                  int64
	CarryCZK                          int64
	DiscountPercent                   int64
	DiscountReason                    string
	BuyerName, BuyerStreet, BuyerCity string
	BuyerZip, BuyerICO, BuyerDIC      string
	BuyerEmail                        string
}

// account is billing.account for one owner; nil when there is no row.
func (v *Invoicer) account(ctx context.Context, owner int64) (*account, error) {
	var a account
	var ttlock, whitelabel int64
	err := v.Pool.QueryRow(ctx,
		`SELECT plan, billing_interval, addon_ttlock, addon_whitelabel, apartments_billed,
		        carry_czk, discount_percent, COALESCE(discount_reason, ''),
		        COALESCE(buyer_name, ''), COALESCE(buyer_street, ''), COALESCE(buyer_city, ''),
		        COALESCE(buyer_zip, ''), COALESCE(buyer_ico, ''), COALESCE(buyer_dic, ''),
		        COALESCE(buyer_email, '')
		 FROM billing_account WHERE owner_user_id = $1`, owner,
	).Scan(&a.Plan, &a.Interval, &ttlock, &whitelabel, &a.ApartmentsBilled,
		&a.CarryCZK, &a.DiscountPercent, &a.DiscountReason,
		&a.BuyerName, &a.BuyerStreet, &a.BuyerCity, &a.BuyerZip, &a.BuyerICO, &a.BuyerDIC,
		&a.BuyerEmail)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	a.AddonTTLock = ttlock != 0
	a.AddonWhitelabel = whitelabel != 0
	return &a, nil
}

// apartmentsCS is apartments_cs.
func apartmentsCS(n int64) string {
	switch {
	case n == 1:
		return "1 apartmán"
	case n >= 2 && n <= 4:
		return fmt.Sprintf("%d apartmány", n)
	}
	return fmt.Sprintf("%d apartmánů", n)
}

var planNames = map[string]string{"standard": "Standard", "max": "Max"}

// periodItems is period_items: the (description, whole Kč) lines for one period
// of the ordered plan.
func periodItems(a account) ([]item, error) {
	n := a.ApartmentsBilled
	q, err := billing.Quote(int(n), *a.Plan, *a.Interval, a.AddonTTLock, a.AddonWhitelabel, int(a.DiscountPercent))
	if err != nil {
		return nil, err
	}
	items := []item{{"Předplatné UbyHost " + planNames[*a.Plan] + ", " + apartmentsCS(n), int64(q.Base + q.Max)}}
	if q.TTLock != 0 {
		items = append(items, item{"Doplněk TTLock, " + apartmentsCS(n), int64(q.TTLock)})
	}
	if q.Whitelabel != 0 {
		items = append(items, item{"Doplněk vlastní značka", int64(q.Whitelabel)})
	}
	if q.Discount != 0 {
		label := fmt.Sprintf("Sleva %d %%", a.DiscountPercent)
		if a.DiscountReason != "" {
			label += " (" + a.DiscountReason + ")"
		}
		items = append(items, item{label, -int64(q.Discount)})
	}
	if a.CarryCZK != 0 {
		items = append(items, item{"Doplatek za změny v minulém období", a.CarryCZK})
	}
	return items, nil
}

// fmtDate is validation.fmt_date: DD.MM.YYYY, or the input unchanged.
func fmtDate(value string) string {
	if t, ok := validation.ParseISODate(value); ok {
		return t.Format("02.01.2006")
	}
	return value
}

// fmtDateRange is validation.fmt_date_range, with an en dash.
func fmtDateRange(from, to string) string {
	start, end := fmtDate(from), fmtDate(to)
	if start != "" && end != "" {
		return start + " – " + end
	}
	if start != "" {
		return start
	}
	return end
}

// seller is _seller().
type seller struct {
	Name, Seat, ICO, DIC, Email, IBAN, BankAccount, VATStatus string
}

// invoiceDoc is the `inv` dict of issue().
type invoiceDoc struct {
	seller
	buyer                                      account
	Kind, Number, VS, IssueDate, DueDate, Note string
	CorrectsNumber, CorrectionReason           string
	TotalHaler                                 int64
}

func (i invoiceDoc) pdfInvoice() pdf.Invoice {
	return pdf.Invoice{
		Number: i.Number, Kind: i.Kind, VATStatus: i.VATStatus,
		SellerName: i.Name, SellerSeat: i.Seat, SellerICO: i.ICO, SellerDIC: i.DIC,
		SellerEmail: i.Email, SellerIBAN: i.IBAN, SellerBankAccount: i.BankAccount,
		BuyerName: i.buyer.BuyerName, BuyerStreet: i.buyer.BuyerStreet, BuyerZip: i.buyer.BuyerZip,
		BuyerCity: i.buyer.BuyerCity, BuyerICO: i.buyer.BuyerICO, BuyerDIC: i.buyer.BuyerDIC,
		IssueDate: i.IssueDate, DueDate: i.DueDate, VS: i.VS, Note: i.Note,
		CorrectsNumber: i.CorrectsNumber, CorrectionReason: i.CorrectionReason,
		TotalHaler: i.TotalHaler,
	}
}

// snapshotJSON is json.dumps({"invoice": inv, "items": rows}, ensure_ascii=False,
// sort_keys=True): sorted keys, ", " and ": " separators, non-ASCII written raw.
func snapshotJSON(i invoiceDoc, items []item) string {
	fields := map[string]string{
		"seller_name": pyStr(i.Name), "seller_seat": pyStr(i.Seat), "seller_ico": pyStr(i.ICO),
		"seller_dic": pyStr(i.DIC), "seller_email": pyStr(i.Email), "seller_iban": pyStr(i.IBAN),
		"seller_bank_account": pyStr(i.BankAccount), "vat_status": pyStr(i.VATStatus),
		"buyer_name": pyStr(i.buyer.BuyerName), "buyer_street": pyStr(i.buyer.BuyerStreet),
		"buyer_city": pyStr(i.buyer.BuyerCity), "buyer_zip": pyStr(i.buyer.BuyerZip),
		"buyer_ico": pyStr(i.buyer.BuyerICO), "buyer_dic": pyStr(i.buyer.BuyerDIC),
		"kind": pyStr(i.Kind), "number": pyStr(i.Number), "vs": pyStr(i.VS),
		"issue_date": pyStr(i.IssueDate), "due_date": pyStr(i.DueDate),
		"total_haler": strconv.FormatInt(i.TotalHaler, 10), "note": pyStr(i.Note),
		"corrects_number": pyStr(i.CorrectsNumber), "correction_reason": pyStr(i.CorrectionReason),
	}
	var b strings.Builder
	b.WriteString(`{"invoice": `)
	writeObject(&b, fields)
	b.WriteString(`, "items": [`)
	for n, it := range items {
		if n > 0 {
			b.WriteString(", ")
		}
		writeObject(&b, map[string]string{
			"description": pyStr(it.Description), "quantity": "1",
			"gross_haler": strconv.FormatInt(it.CZK*100, 10),
		})
	}
	b.WriteString("]}")
	return b.String()
}

func writeObject(b *strings.Builder, fields map[string]string) {
	keys := make([]string, 0, len(fields))
	for k := range fields {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	b.WriteByte('{')
	for n, k := range keys {
		if n > 0 {
			b.WriteString(", ")
		}
		b.WriteString(pyStr(k) + ": " + fields[k])
	}
	b.WriteByte('}')
}

// pyStr is json.dumps(s, ensure_ascii=False): quotes, backslash and control
// characters escaped, everything else raw.
func pyStr(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if r < 0x20 {
				fmt.Fprintf(&b, `\u%04x`, r)
			} else if r == utf8.RuneError {
				b.WriteString("�")
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}
