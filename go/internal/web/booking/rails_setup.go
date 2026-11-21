package booking

// booking_rails.setup_view for the host booking-site setup page.

import (
	"context"
	"sort"
	"strings"
)

// PaySetupView is booking_rails.setup_view.
type PaySetupView struct {
	Ticked      []string
	RevolutLink string
	CashNote    string
	IBANOK      bool
}

// SetupView loads the "How guests pay" form context.
func SetupView(ctx context.Context, db DB, apartmentID int64) (PaySetupView, error) {
	var rails, revolut, cash *string
	var legalID *int64
	err := db.QueryRow(ctx, `SELECT legal_entity_id, stay_fee_guest_rails, stay_fee_guest_revolut_link, stay_fee_guest_cash_note
		FROM apartment WHERE id = $1`, apartmentID).Scan(&legalID, &rails, &revolut, &cash)
	if err != nil {
		return PaySetupView{}, err
	}
	ticked := tickedRails(rails)
	acct, err := AccountOnFile(ctx, db, legalID)
	if err != nil {
		return PaySetupView{}, err
	}
	out := PaySetupView{Ticked: ticked, IBANOK: acct != ""}
	if revolut != nil {
		out.RevolutLink = *revolut
	}
	if cash != nil {
		out.CashNote = *cash
	}
	return out, nil
}

func tickedRails(raw *string) []string {
	if raw == nil {
		return nil
	}
	set := map[string]bool{}
	for _, part := range strings.Split(*raw, ",") {
		if part != "" {
			set[part] = true
		}
	}
	out := make([]string, 0, len(Rails))
	for _, rail := range Rails {
		if set[rail] || (rail == "iban" && set["qr"]) {
			out = append(out, rail)
		}
	}
	sort.Strings(out)
	return out
}
