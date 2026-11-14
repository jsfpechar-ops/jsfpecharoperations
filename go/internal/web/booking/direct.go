package booking

// The direct payment request of the booking site: booking_checkout.start_direct
// (booking_checkout.py 133-164), booking_direct.notify_request and
// notify_request_guest (booking_direct.py 115-172) and booking_rails.guest_view
// (booking_rails.py 123-154). The guest pays the host by bank transfer,
// Revolut or cash; the dates are held for 24 hours; nothing is charged here.
//
// Mails go through the same outbox as every other Go mail (ubyport.EnqueueMail)
// with Python's idempotency keys, so a booking started on either side never
// mails twice. Mail off queues nothing. A failed mail is logged by kind and key
// only, never the address.

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// RequestHours is booking_checkout.REQUEST_HOURS.
const RequestHours = 24

// GuestRail is one way a guest can pay the host (booking_rails.guest_view).
type GuestRail struct {
	Key    string // iban, revolut or cash
	IBAN   string // grouped by four
	QR     string // data URI of the SPAYD code
	VS     string
	Amount int
	Link   string
	Note   string
}

// GuestRails is booking_rails.guest_view: the enabled rails, the host's
// default first. The variable symbol is the booking id and the QR payload is
// built here, never stored. qr turns a SPAYD string into a data URI (the
// payments package supplies it; tests pass a stub).
func GuestRails(ctx context.Context, db DB, apartmentID, bookingID int64, totalCZK int, qr func(string) (string, error)) ([]GuestRail, error) {
	var entity *int64
	var def, link, note *string
	err := db.QueryRow(ctx, `SELECT legal_entity_id, stay_fee_guest_default_rail, stay_fee_guest_revolut_link, stay_fee_guest_cash_note
		FROM apartment WHERE id = $1`, apartmentID).Scan(&entity, &def, &link, &note)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	vs := strconv.FormatInt(bookingID, 10)
	first := ""
	if def != nil {
		first = *def
	}
	if first == "qr" {
		first = "iban"
	}
	order := []string{}
	if contains(Rails, first) {
		order = append(order, first)
	}
	for _, r := range Rails {
		if r != first {
			order = append(order, r)
		}
	}
	live, err := EnabledRails(ctx, db, apartmentID)
	if err != nil {
		return nil, err
	}
	var out []GuestRail
	for _, rail := range order {
		if !contains(live, rail) {
			continue
		}
		switch rail {
		case "iban":
			account, err := guestIBAN(ctx, db, entity)
			if err != nil {
				return nil, err
			}
			uri, err := qr(stayfee.SPAYD(account, totalCZK, vs, "Stay "+vs))
			if err != nil {
				return nil, err
			}
			out = append(out, GuestRail{Key: "iban", IBAN: stayfee.FormatIBAN(account), QR: uri, VS: vs, Amount: totalCZK})
		case "revolut":
			l := ""
			if link != nil {
				l = *link
			}
			out = append(out, GuestRail{Key: "revolut", Link: l})
		default:
			n := ""
			if note != nil {
				n = *note
			}
			out = append(out, GuestRail{Key: "cash", Note: n})
		}
	}
	return out, nil
}

// guestIBAN is the legal entity's iban, else the IBAN of its bank account
// (payments.normalise_account(...)[1]). An account number that does not
// validate is an error, as Python's ValueError is.
func guestIBAN(ctx context.Context, db DB, entity *int64) (string, error) {
	if entity == nil {
		return "", nil
	}
	var iban, account *string
	err := db.QueryRow(ctx, `SELECT iban, bank_account FROM legal_entity WHERE id = $1`, *entity).Scan(&iban, &account)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if iban != nil && *iban != "" {
		return *iban, nil
	}
	raw := ""
	if account != nil {
		raw = *account
	}
	out, ok := stayfee.NormaliseAccount(raw)
	if !ok {
		return "", errors.New("legal entity bank account does not validate")
	}
	return out, nil
}

// Direct stores direct requests.
type Direct struct {
	Pool   *pgxpool.Pool
	Getenv func(string) string
	Now    func() time.Time
	QR     func(string) (string, error)
}

// Start is booking_checkout.start_direct as a DirectFunc: the booking id, or
// the error kind "taken" or "unavailable".
func (d Direct) Start(ctx context.Context, in DirectInput) (int64, string, error) {
	var owner int64
	var name string
	var entity *int64
	err := d.Pool.QueryRow(ctx, `SELECT owner_user_id, internal_name, legal_entity_id FROM apartment WHERE id = $1`,
		in.ApartmentID).Scan(&owner, &name, &entity)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, "unavailable", nil
	}
	if err != nil {
		return 0, "", err
	}
	demo, err := isDemo(ctx, d.Pool, d.Getenv, name, entity)
	if err != nil || demo {
		return 0, "unavailable", err
	}
	ready, err := RailsReady(ctx, d.Pool, in.ApartmentID)
	if err != nil || !ready {
		return 0, "unavailable", err
	}
	now := d.Now()
	holdID, ok, err := HoldDates(ctx, d.Pool, in.ApartmentID, in.Q.DateFrom, in.Q.DateTo, RequestHours*60, now)
	if err != nil {
		return 0, "", err
	}
	if !ok {
		return 0, "taken", nil
	}
	expires := now.UTC().Add(RequestHours*time.Hour).Format("2006-01-02T15:04:05") + "Z"
	id, err := CreatePending(ctx, d.Pool, Pending{ApartmentID: in.ApartmentID, OwnerID: owner, HoldID: holdID, Q: in.Q,
		Name: in.Name, Email: in.Email, Lang: in.Lang, Status: "requested", PayMethod: "direct", RequestExpiresAt: expires}, now)
	if err != nil {
		return 0, "", err
	}
	if _, err := d.Pool.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, 'host', 'site_booking_requested', $2, $3)`,
		StampAt(now), fmt.Sprintf("id=%d", id), owner); err != nil {
		return 0, "", err
	}
	// Best effort, as in Python: a failed mail never fails the request.
	if err := d.notifyHost(ctx, in, id, owner, name, entity); err != nil {
		log.Printf("site booking %d: request mail failed", id)
	}
	if err := d.notifyGuest(ctx, in, id, owner, name, entity); err != nil {
		log.Printf("site booking %d: guest request mail failed", id)
	}
	return id, "", nil
}

func mailOn(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND"))) {
	case "console", "ses":
		return true
	}
	return false
}

func (d Direct) hostEmail(ctx context.Context, entity *int64) (string, error) {
	if entity == nil || *entity == 0 {
		return "", nil
	}
	var contact *string
	err := d.Pool.QueryRow(ctx, `SELECT contact_email FROM legal_entity WHERE id = $1`, *entity).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) || contact == nil {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return ubyport.NormaliseEmail(*contact), nil
}

// facts is booking_webhook._facts.
func facts(in DirectInput, aptName, lang string) map[string]any {
	dates := func(iso string) string {
		if lang == "cs" {
			return czDate(iso)
		}
		return iso
	}
	return map[string]any{
		"property": aptName, "dates": dates(in.Q.DateFrom) + " – " + dates(in.Q.DateTo),
		"guests": in.Q.Guests, "total": in.Q.TotalCZK,
		"name": strings.Join(strings.Fields(in.Name), " "), "email": strings.TrimSpace(in.Email),
		"policy": guestStrings.T(lang, "pp.book.policy."+in.Q.CancellationPolicy, nil),
	}
}

func (d Direct) enqueue(ctx context.Context, kind, key, to, subject, payload string, in DirectInput, owner int64) error {
	if !mailOn(d.Getenv) {
		log.Printf("mail disabled; skip enqueue kind=%s key=%s", kind, key)
		return nil
	}
	to = ubyport.NormaliseEmail(to)
	if to == "" {
		return nil
	}
	apartment := in.ApartmentID
	_, err := ubyport.EnqueueMail(ctx, d.Pool, ubyport.OutboxMail{Kind: kind, Key: key, ApartmentID: &apartment,
		OwnerUserID: &owner, To: to, Subject: subject, Payload: payload})
	return err
}

// notifyHost is booking_direct.notify_request: one short Czech mail to the host.
func (d Direct) notifyHost(ctx context.Context, in DirectInput, id, owner int64, aptName string, entity *int64) error {
	host, err := d.hostEmail(ctx, entity)
	if err != nil || host == "" {
		return err
	}
	f := facts(in, aptName, "cs")
	f["link"] = hostweb.PublicBase(d.Getenv) + "/apartments/" + strconv.FormatInt(in.ApartmentID, 10) + "/booking-site"
	payload := `{"text": ` + ubyport.PyString(guestStrings.T("cs", "site_booking.mail.request_text", f)) + `, "lang": "cs"}`
	return d.enqueue(ctx, "site_booking_request_host", fmt.Sprintf("site_booking:%d:request_host", id), host,
		guestStrings.T("cs", "site_booking.mail.request_subject", f), payload, in, owner)
}

// notifyGuest is booking_direct.notify_request_guest: the guest's copy of the
// payment details, with the link to the private booking page.
func (d Direct) notifyGuest(ctx context.Context, in DirectInput, id, owner int64, aptName string, entity *int64) error {
	lang := in.Lang
	if lang != "cs" && lang != "en" {
		lang = "cs"
	}
	rails, err := GuestRails(ctx, d.Pool, in.ApartmentID, id, in.Q.TotalCZK, d.QR)
	if err != nil {
		return err
	}
	f := facts(in, aptName, lang)
	var lines []string
	for _, r := range rails {
		switch r.Key {
		case "iban":
			lines = append(lines, guestStrings.T(lang, "site_booking.mail.request_guest_iban",
				map[string]any{"iban": r.IBAN, "vs": r.VS, "amount": r.Amount}))
		case "revolut":
			lines = append(lines, guestStrings.T(lang, "site_booking.mail.request_guest_revolut", map[string]any{"link": r.Link}))
		default:
			if r.Note != "" {
				lines = append(lines, r.Note)
			} else {
				lines = append(lines, guestStrings.T(lang, "pp.book.req_cash_default", nil))
			}
		}
	}
	f["ways"] = strings.Join(lines, "\n\n")
	secret, err := secure.LoadSecret(d.Getenv)
	if err != nil {
		return err
	}
	link, err := ManageURL(ctx, d.Pool, hostweb.PublicBase(d.Getenv), secret, in.ApartmentID, id)
	if err != nil {
		return err
	}
	f["link"] = link
	host, err := d.hostEmail(ctx, entity)
	if err != nil {
		return err
	}
	text := guestStrings.T(lang, "site_booking.mail.request_guest_text", f) + "\n\n" +
		guestStrings.T(lang, "site_booking.mail.request_guest_link", map[string]any{"link": link})
	payload := `{"text": ` + ubyport.PyString(text) + `, "lang": "` + lang + `", "reply_to": ` + ubyport.PyString(host) + `}`
	return d.enqueue(ctx, "site_booking_request_guest", fmt.Sprintf("site_booking:%d:request_guest", id), strings.TrimSpace(in.Email),
		guestStrings.T(lang, "site_booking.mail.request_guest_subject", f), payload, in, owner)
}
