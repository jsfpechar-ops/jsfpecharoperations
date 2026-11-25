package guest

// Brief 2063: the stay-fee box on the claimed-stay hub (guest/_fee_pay.html).
// Python builds it in stay_overview only when the stay is fully declared
// (remaining <= 0) and UBYHOST_STAY_FEE_GUEST_PAY is on.

import (
	"context"
	"html/template"
	"log"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// feeRail is one guest pay way shown in the box. Only the fields of its Key are set.
type feeRail struct {
	Key        string
	IBANGroups []string
	QR         template.URL
	HasQR      bool
	Link       string
	Note       string
}

// feePerson is one guest who owes: N is the 1-based position, Days the liable nights.
type feePerson struct {
	N, Days, Amount int
}

// feePanel is the view model of _fee_pay.html.
type feePanel struct {
	Total, Rate int
	Persons     []feePerson
	Rails       []feeRail
	VS, Payee   string
	Group       bool // several guests, all with the same nights: the group calc line
	Guests      int
	Days        int
}

// buildFeePanel maps the stayfee completion fee to the box. Nil in, nil out.
// qr renders the SPAYD payload; a failure leaves the rail without a QR code.
func buildFeePanel(fee *stayfee.CompletionFee, qr func(string) (string, error), cashDefault string) *feePanel {
	if fee == nil {
		return nil
	}
	p := &feePanel{Total: fee.Total, Rate: fee.Rate, VS: fee.VS}
	for i, l := range fee.Lines {
		p.Persons = append(p.Persons, feePerson{N: i + 1, Days: l[0], Amount: l[1]})
	}
	p.Guests = len(p.Persons)
	if p.Guests > 0 {
		p.Days = p.Persons[0].Days
	}
	p.Group = p.Guests > 1 && sameNights(p.Persons)
	for _, w := range fee.Ways {
		switch w.Key {
		case "iban":
			if p.Payee == "" {
				p.Payee = w.Payee
			}
			r := feeRail{Key: "iban", IBANGroups: ibanGroups(w.Account)}
			if w.SPAYD != "" && qr != nil {
				if img, err := qr(w.SPAYD); err == nil && img != "" {
					r.QR = template.URL(img)
					r.HasQR = true
				}
			}
			p.Rails = append(p.Rails, r)
		case "revolut":
			p.Rails = append(p.Rails, feeRail{Key: "revolut", Link: w.Link})
		case "cash":
			note := w.Note
			if note == "" {
				note = cashDefault
			}
			p.Rails = append(p.Rails, feeRail{Key: "cash", Note: note})
		}
	}
	return p
}

// sameNights reports whether every guest in the list has the same nights.
func sameNights(ps []feePerson) bool {
	for _, p := range ps[1:] {
		if p.Days != ps[0].Days {
			return false
		}
	}
	return true
}

// ibanGroups splits an IBAN into display groups, as _fee_pay.html does: on the
// existing spaces when there are any, else in blocks of four.
func ibanGroups(iban string) []string {
	if strings.Contains(iban, " ") {
		return strings.Fields(iban)
	}
	var out []string
	for i := 0; i < len(iban); i += 4 {
		end := i + 4
		if end > len(iban) {
			end = len(iban)
		}
		out = append(out, iban[i:end])
	}
	return out
}

// loadFeePanel reads the box for one reservation. Any failure drops the box and
// is logged without amounts, accounts or names (Python drops it the same way).
func (d stayClaimDeps) loadFeePanel(ctx context.Context, reservationID, apartmentID int64, cashDefault string) *feePanel {
	guestPay := strings.ToLower(strings.TrimSpace(d.getenv("UBYHOST_STAY_FEE_GUEST_PAY"))) == "on"
	if !guestPay {
		return nil
	}
	keys, err := secure.LoadDataKeys(d.getenv)
	if err != nil {
		log.Printf("stay_fee_panel_failed reservation=%d err=%v", reservationID, err)
		return nil
	}
	ap, err := stayfee.LoadApartment(ctx, d.pool, apartmentID)
	if err != nil {
		log.Printf("stay_fee_panel_failed reservation=%d err=%v", reservationID, err)
		return nil
	}
	y, m, day := d.now().In(praguePick).Date()
	today := time.Date(y, m, day, 0, 0, 0, 0, time.UTC)
	fee, err := stayfee.LoadCompletionFee(ctx, d.pool, stayfee.FernetDecrypter(keys), ap, reservationID, guestPay, today)
	if err != nil {
		log.Printf("stay_fee_panel_failed reservation=%d err=%v", reservationID, err)
		return nil
	}
	return buildFeePanel(fee, payments.QRDataURI, cashDefault)
}
