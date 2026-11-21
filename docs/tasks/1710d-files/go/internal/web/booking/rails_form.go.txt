package booking

// booking_rails.parse_form for POST .../booking-site/pay (brief 1710d).

import (
	"context"
	"fmt"
	"sort"
	"strings"
)

const guestNoteMax = 300

// RailsFormValues is the apartment columns booking_rails.parse_form writes.
type RailsFormValues struct {
	Rails       string
	RevolutLink *string
	CashNote    *string
	DefaultRail *string
}

// ParseRailsForm turns the pay panel POST into apartment updates.
// Error codes match Python ValueError: pay_none, pay_revolut, pay_iban.
func ParseRailsForm(ctx context.Context, db DB, apartmentID int64, rails []string, revolut, cash, curDefault string) (RailsFormValues, error) {
	posted := map[string]bool{}
	for _, v := range rails {
		if contains(Rails, v) {
			posted[v] = true
		}
	}
	if len(posted) == 0 {
		return RailsFormValues{}, fmt.Errorf("pay_none")
	}
	a, err := loadRailApartment(ctx, db, apartmentID)
	if a == nil || err != nil {
		return RailsFormValues{}, fmt.Errorf("pay_none")
	}
	if err != nil {
		return RailsFormValues{}, err
	}
	out := RailsFormValues{}
	keys := make([]string, 0, len(posted))
	for k := range posted {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	out.Rails = strings.Join(keys, ",")
	if posted["revolut"] {
		link := strings.TrimSpace(revolut)
		if !RevolutLinkOK(link) {
			return RailsFormValues{}, fmt.Errorf("pay_revolut")
		}
		out.RevolutLink = &link
	}
	if posted["iban"] {
		acct, err := AccountOnFile(ctx, db, a.legalEntityID)
		if err != nil {
			return RailsFormValues{}, err
		}
		if acct == "" {
			return RailsFormValues{}, fmt.Errorf("pay_iban")
		}
	}
	if posted["cash"] {
		note := strings.TrimSpace(cash)
		if len([]rune(note)) > guestNoteMax {
			runes := []rune(note)
			note = string(runes[:guestNoteMax])
		}
		if note != "" {
			out.CashNote = &note
		}
	}
	first := strings.TrimSpace(curDefault)
	if first == "qr" {
		first = "iban"
	}
	if !posted[first] {
		for _, r := range Rails {
			if posted[r] {
				out.DefaultRail = &r
				break
			}
		}
	}
	return out, nil
}
