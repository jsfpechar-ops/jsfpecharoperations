package booking

import (
	"context"
	"errors"
	"net/url"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"
)

// Rails is booking_rails.RAILS, in display order.
var Rails = []string{"iban", "revolut", "cash"}

// guestLinkHosts is stay_fees.GUEST_LINK_HOSTS.
var guestLinkHosts = []string{"revolut.me", "revolut.com"}

var (
	errBadStoredDate = errors.New("booking: stored date is not an ISO date")
	errBadMonth      = errors.New("booking: bad year or month")
)

// RevolutLinkOK is stay_fees.revolut_link_ok: https only, host revolut.me or
// revolut.com (or a subdomain), no userinfo, default port.
func RevolutLinkOK(raw string) bool {
	s := strings.TrimSpace(raw)
	// urlsplit drops tab, CR and LF anywhere.
	s = strings.NewReplacer("\t", "", "\r", "", "\n", "").Replace(s)
	u, err := url.Parse(s)
	if err != nil {
		return false
	}
	if u.User != nil {
		pw, _ := u.User.Password()
		if u.User.Username() != "" || pw != "" {
			return false
		}
	}
	if port := u.Port(); port != "" {
		n, err := strconv.Atoi(port)
		if err != nil || n < 0 || n > 65535 || n != 443 {
			return false
		}
	}
	if strings.ToLower(u.Scheme) != "https" {
		return false
	}
	host := strings.ToLower(u.Hostname())
	for _, base := range guestLinkHosts {
		if host == base || strings.HasSuffix(host, "."+base) {
			return true
		}
	}
	return false
}

type railApartment struct {
	legalEntityID *int64
	rails         string
	revolutLink   *string
}

func loadRailApartment(ctx context.Context, db DB, apartmentID int64) (*railApartment, error) {
	var a railApartment
	err := db.QueryRow(ctx, `SELECT legal_entity_id, stay_fee_guest_rails, stay_fee_guest_revolut_link
		FROM apartment WHERE id = $1`, apartmentID).Scan(&a.legalEntityID, &a.rails, &a.revolutLink)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// AccountOnFile is booking_rails.account_on_file: the legal entity's IBAN,
// else its account number, stripped; "" when none.
func AccountOnFile(ctx context.Context, db DB, legalEntityID *int64) (string, error) {
	if legalEntityID == nil || *legalEntityID == 0 {
		return "", nil
	}
	var iban, account *string
	err := db.QueryRow(ctx, `SELECT iban, bank_account FROM legal_entity WHERE id = $1`, *legalEntityID).Scan(&iban, &account)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	out := ""
	if iban != nil && *iban != "" {
		out = *iban
	} else if account != nil {
		out = *account
	}
	return strings.TrimSpace(out), nil
}

// EnabledRails is booking_rails.enabled: ticked rails that can really be
// shown to a guest, in Rails order. The legacy "qr" rail counts as "iban".
func EnabledRails(ctx context.Context, db DB, apartmentID int64) ([]string, error) {
	a, err := loadRailApartment(ctx, db, apartmentID)
	if err != nil || a == nil {
		return []string{}, err
	}
	ticked := map[string]bool{}
	for _, part := range strings.Split(a.rails, ",") {
		if part != "" {
			ticked[part] = true
		}
	}
	if ticked["qr"] {
		ticked["iban"] = true
	}
	out := []string{}
	for _, rail := range Rails {
		if !ticked[rail] {
			continue
		}
		if rail == "iban" {
			acct, err := AccountOnFile(ctx, db, a.legalEntityID)
			if err != nil {
				return nil, err
			}
			if acct == "" {
				continue
			}
		}
		if rail == "revolut" {
			link := ""
			if a.revolutLink != nil {
				link = *a.revolutLink
			}
			if !RevolutLinkOK(link) {
				continue
			}
		}
		out = append(out, rail)
	}
	return out, nil
}

// RailsReady is booking_rails.ready: at least one direct rail works.
func RailsReady(ctx context.Context, db DB, apartmentID int64) (bool, error) {
	rails, err := EnabledRails(ctx, db, apartmentID)
	return len(rails) > 0, err
}

// StripeMode is config.STRIPE_MODE: UBYHOST_STRIPE_MODE stripped and lower
// case, "off" when unset.
func StripeMode(getenv func(string) string) string {
	v := getenv("UBYHOST_STRIPE_MODE")
	if v == "" {
		return "off"
	}
	return strings.ToLower(strings.TrimSpace(v))
}

// StripeComplete is stripe_connect.account_for_owner(owner) with
// onboarding_state == "complete", in the current Stripe mode.
func StripeComplete(ctx context.Context, db DB, mode string, ownerUserID int64) (bool, error) {
	var state string
	err := db.QueryRow(ctx, `SELECT onboarding_state FROM stripe_account
		WHERE owner_user_id = $1 AND mode = $2 LIMIT 1`, ownerUserID, mode).Scan(&state)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return state == "complete", nil
}

// PayModes is booking_rails.pay_modes: "stripe" and/or "direct".
func PayModes(ctx context.Context, db DB, mode string, apartmentID, ownerUserID int64) ([]string, error) {
	modes := []string{}
	ok, err := StripeComplete(ctx, db, mode, ownerUserID)
	if err != nil {
		return nil, err
	}
	if ok {
		modes = append(modes, "stripe")
	}
	ready, err := RailsReady(ctx, db, apartmentID)
	if err != nil {
		return nil, err
	}
	if ready {
		modes = append(modes, "direct")
	}
	return modes, nil
}
