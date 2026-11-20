package stayfee

import (
	"context"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// CompletionWay is one guest pay way of stay_fee.guest_pay_ways. Only the keys
// of its kind are set; the JSON tags are the golden file's keys.
type CompletionWay struct {
	Key     string `json:"key"`
	Payee   string `json:"payee"`
	Account string `json:"account"`
	SPAYD   string `json:"spayd"`
	Link    string `json:"link"`
	Note    string `json:"note"`
}

// CompletionFee is the dict claim._completion_fee returns: the stay fee the
// receipt and the completion mail state. Nil means the guest pays no fee here.
type CompletionFee struct {
	Total int             `json:"total"`
	Lines [][2]int        `json:"lines"` // (liable nights, amount CZK) of the guests who owe
	Rate  int             `json:"rate"`
	Rails []string        `json:"rails"`
	Ways  []CompletionWay `json:"ways"`
	VS    string          `json:"vs"`
}

// CompletionInput is what the fee reads, already loaded. The golden test feeds
// it straight from testdata/completion_fee_golden.json.
type CompletionInput struct {
	Apartment     *Apartment
	Entity        *Entity // nil when there is no legal entity row
	Rates         []RateRow
	Guests        []GuestRow // live guests of the reservation, in Python's order
	Nationalities []string   // guest nationalities of the reservation (qr_offered)
	ReservationID int64
	GuestPay      bool      // config.STAY_FEE_GUEST_PAY
	Today         time.Time // schedule_for's today
}

// CompletionFeeOf is claim._completion_fee over loaded inputs. Any read failure
// in Python drops the fee block; here the only error is a bad rate row, which
// the caller reports.
func CompletionFeeOf(in CompletionInput) (*CompletionFee, error) {
	ap := in.Apartment
	if ap == nil || !ap.Collect || !in.GuestPay {
		return nil, nil
	}
	// charge_for_reservation: inactive apartments and the switch-off give no charge.
	if !IsActive(ap) {
		return nil, nil
	}
	schedule, err := ScheduleFor(ap.StayFeeRateCZK, in.Rates, in.Today)
	if err != nil {
		return nil, err
	}
	first := Day(1, time.January, 1)
	last := Day(9999, time.December, 31)
	var charge [][2]int
	total := 0
	for _, g := range in.Guests {
		line, ok := GuestPeriod(g, first, last, ap, schedule)
		if !ok {
			continue
		}
		applyScopeBoundary(&line, ap)
		charge = append(charge, [2]int{line.LiableNights, line.AmountCZK})
		total += line.AmountCZK
	}
	if len(charge) == 0 || total <= 0 {
		return nil, nil
	}

	// The stay's last night comes from the first guest row, as in Python.
	lastNight, ok := validation.ParseISODate(in.Guests[0].ResTo)
	if !ok {
		lastNight = in.Today
	}
	rate := RateOn(schedule, lastNight)

	lines := make([][2]int, 0, len(charge))
	for _, l := range charge {
		if l[0] > 0 {
			lines = append(lines, l)
		}
	}

	vs := strconv.FormatInt(in.ReservationID, 10)
	qrOK := false
	for _, n := range in.Nationalities {
		if code := strings.ToUpper(n); code == "CZE" || code == "SVK" {
			qrOK = true
		}
	}
	account, payee := payoutAccount(ap, in.Entity)
	rails := usableRails(ap, account)
	ways := make([]CompletionWay, 0, len(rails))
	for _, key := range rails {
		switch key {
		case "iban":
			spayd := ""
			if qrOK {
				spayd = SPAYD(account, total, vs, "Stay fee "+vs)
			}
			ways = append(ways, CompletionWay{Key: "iban", Payee: payee, Account: FormatIBAN(account), SPAYD: spayd})
		case "revolut":
			ways = append(ways, CompletionWay{Key: "revolut", Link: ap.RevolutLink})
		default:
			ways = append(ways, CompletionWay{Key: "cash", Note: ap.CashNote})
		}
	}
	return &CompletionFee{Total: total, Lines: lines, Rate: rate, Rails: rails, Ways: ways, VS: vs}, nil
}

// payoutAccount is stay_fee.payout_account: the IBAN and payee guests pay to,
// ("", "") when no account is on file. A stored bank account counts only when
// it normalises (a malformed one is no pay way, as in Python).
func payoutAccount(ap *Apartment, entity *Entity) (string, string) {
	if ap.LegalEntityID == 0 || entity == nil {
		return "", ""
	}
	payee := strings.TrimSpace(entity.Name)
	account := ""
	if entity.IBAN != "" {
		account = entity.IBAN
	} else if entity.BankAccount != "" {
		if iban, ok := NormaliseAccount(entity.BankAccount); ok {
			account = iban
		}
	}
	return account, payee
}

// usableRails is stay_fee.usable_rail_keys: the enabled pay ways that have what
// they need, the default first.
func usableRails(ap *Apartment, account string) []string {
	enabled := map[string]bool{}
	for _, part := range strings.Split(ap.GuestRails, ",") {
		if part != "" {
			enabled[part] = true
		}
	}
	if enabled["qr"] {
		enabled["iban"] = true
	}
	first := ap.GuestDefaultRail
	if first == "qr" {
		first = "iban"
	}
	order := []string{}
	if first == "iban" || first == "revolut" || first == "cash" {
		order = append(order, first)
	}
	for _, key := range railOrder {
		if key != first {
			order = append(order, key)
		}
	}
	usable := []string{}
	for _, key := range order {
		if !enabled[key] {
			continue
		}
		if key == "iban" && account == "" {
			continue
		}
		if key == "revolut" && ap.RevolutLink == "" {
			continue
		}
		usable = append(usable, key)
	}
	return usable
}

// LoadCompletionFee reads the rows CompletionFeeOf needs for one reservation
// (the same guest, rate and entity reads as stay_fee) and returns its fee block.
// Apartment is the caller's row (LoadApartment); guestPay is the env switch.
func LoadCompletionFee(ctx context.Context, q Querier, dec Decrypter, ap *Apartment,
	reservationID int64, guestPay bool, today time.Time) (*CompletionFee, error) {
	if ap == nil || !ap.Collect || !guestPay {
		return nil, nil
	}
	guests, err := loadGuests(ctx, q, dec, guestSelect(false)+
		`WHERE r.apartment_id = $1 AND r.id = $2 AND r.status = 'active' AND g.archived_at IS NULL
		AND COALESCE(r.source, '') != 'demo'
		ORDER BY COALESCE(g.stay_from, r.date_from), g.id`, ap.ID, reservationID)
	if err != nil {
		return nil, err
	}
	if len(guests) == 0 {
		return nil, nil
	}
	rates, err := loadRateRows(ctx, q, ap.ID)
	if err != nil {
		return nil, err
	}
	entity, err := loadCompletionEntity(ctx, q, ap.LegalEntityID)
	if err != nil {
		return nil, err
	}
	nats, err := loadNationalities(ctx, q, reservationID)
	if err != nil {
		return nil, err
	}
	return CompletionFeeOf(CompletionInput{
		Apartment: ap, Entity: entity, Rates: rates, Guests: guests,
		Nationalities: nats, ReservationID: reservationID, GuestPay: guestPay, Today: today,
	})
}

func loadCompletionEntity(ctx context.Context, q Querier, id int64) (*Entity, error) {
	if id == 0 {
		return nil, nil
	}
	rows, err := q.Query(ctx, `SELECT COALESCE(iban, ''), COALESCE(bank_account, ''), COALESCE(name, '')
		FROM legal_entity WHERE id = $1`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	if !rows.Next() {
		return nil, rows.Err()
	}
	var e Entity
	if err := rows.Scan(&e.IBAN, &e.BankAccount, &e.Name); err != nil {
		return nil, err
	}
	return &e, rows.Err()
}

func loadNationalities(ctx context.Context, q Querier, reservationID int64) ([]string, error) {
	rows, err := q.Query(ctx, `SELECT COALESCE(nationality, '') FROM guest
		WHERE reservation_id = $1 AND archived_at IS NULL`, reservationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var n string
		if err := rows.Scan(&n); err != nil {
			return nil, err
		}
		out = append(out, n)
	}
	return out, rows.Err()
}
