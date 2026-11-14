package stayfees

// Brief 1587: POST /stay-fees/{apartment_id}/guest-pay-preview, the live sample
// QR of the guest-pay block (guest_pay_preview, App/app/routes/stay_fees.py
// 134-163). Nothing is saved. Parity notes:
//   stay_fee_guest_pay_on 262-264        -> guestPayOn
//   _entity_payment_account 419-429      -> guestpayEntityAccount
//   _resolved_operator_account 486-506   -> guestpayResolve
//   guest_pay_operator_context 509-569   -> guestpayContext
//   payments.qr_data_uri / qr_png_bytes  -> guestpayQRDataURI

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"math/big"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/skip2/go-qrcode"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// guestPaySampleVS is GUEST_OPERATOR_SAMPLE_VS.
const guestPaySampleVS = "1234567890"

// guestPayOn is stay_fee_guest_pay_on: UBYHOST_STAY_FEE_GUEST_PAY is "on".
func guestPayOn(getenv func(string) string) bool {
	return strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STAY_FEE_GUEST_PAY"))) == "on"
}

// guestpayEntity is the legal_entity row the preview reads.
type guestpayEntity struct {
	BankAccount string
	IBAN        string
}

// guestpayEntityAccount is _entity_payment_account: the IBAN, else the Czech account.
func guestpayEntityAccount(e *guestpayEntity) string {
	if e == nil {
		return ""
	}
	if e.IBAN != "" {
		return e.IBAN
	}
	return e.BankAccount
}

// guestpayResolve is _resolved_operator_account: (display, account for SPAYD).
func guestpayResolve(e *guestpayEntity, draft string) (string, string) {
	raw := strings.TrimSpace(draft)
	if raw != "" {
		iban, ok := stayfee.NormaliseAccount(raw)
		if !ok {
			return "", ""
		}
		return stayfee.FormatIBAN(iban), iban
	}
	stored := guestpayEntityAccount(e)
	if stored == "" {
		return "", ""
	}
	if e != nil && e.IBAN != "" {
		return stayfee.FormatIBAN(stored), stored
	}
	if iban, ok := stayfee.NormaliseAccount(stored); ok {
		return stayfee.FormatIBAN(iban), iban
	}
	return stored, stored
}

// guestpayPNG is payments.qr_png_bytes: medium error correction, 6 px modules,
// 4-module border.
func guestpayPNG(payload string) ([]byte, error) {
	code, err := qrcode.New(payload, qrcode.Medium)
	if err != nil {
		return nil, err
	}
	return code.PNG(-6)
}

// guestpayQRDataURI is payments.qr_data_uri.
func guestpayQRDataURI(payload string) (string, error) {
	png, err := guestpayPNG(payload)
	if err != nil {
		return "", err
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(png), nil
}

// guestpaySampleAmount is min(max(int(rate or 50), 1), 50) where rate is the
// typed sample rate when there is one, else the property's own.
func guestpaySampleAmount(rate *big.Int, aptRate int64) int {
	r := big.NewInt(aptRate)
	if rate != nil {
		r = rate
	}
	switch {
	case r.Sign() == 0:
		return 50
	case r.Cmp(big.NewInt(1)) < 0:
		return 1
	case r.Cmp(big.NewInt(50)) > 0:
		return 50
	}
	return int(r.Int64())
}

// guestpayContext is guest_pay_operator_context with the switch on: whether an
// account is known, its display form and the sample QR. rate is the typed
// sample rate (nil when none) and aptRate the property's own.
func guestpayContext(e *guestpayEntity, draft string, rate *big.Int, aptRate int64) (bool, string, string, error) {
	display, account := guestpayResolve(e, draft)
	if account == "" {
		return false, display, "", nil
	}
	uri, err := guestpayQRDataURI(stayfee.SPAYD(account, guestpaySampleAmount(rate, aptRate), guestPaySampleVS, "Stay fee sample"))
	return true, display, uri, err
}

// guestpayParseRate is int(form_str(rate) or 0) or None: a value that is not an
// integer, or is 0, is nil. Python's int() also takes a sign and single
// underscores between digits; other Unicode digits are not read here.
func guestpayParseRate(text string) *big.Int {
	if text == "" {
		return nil
	}
	body := text
	if body[0] == '+' || body[0] == '-' {
		body = body[1:]
	}
	if body == "" || body[0] == '_' || body[len(body)-1] == '_' || strings.Contains(body, "__") {
		return nil
	}
	for i := 0; i < len(body); i++ {
		if (body[i] < '0' || body[i] > '9') && body[i] != '_' {
			return nil
		}
	}
	n, ok := new(big.Int).SetString(text[:len(text)-len(body)]+strings.ReplaceAll(body, "_", ""), 10)
	if !ok || n.Sign() == 0 {
		return nil
	}
	return n
}

func guestpayJSON(w http.ResponseWriter, status int, v any) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(bytes.TrimRight(buf.Bytes(), "\n"))
}

type guestpayAnswer struct {
	OK      bool   `json:"ok"`
	Invalid bool   `json:"invalid"`
	Account string `json:"account"`
	QR      string `json:"qr"`
}

// guestpayLoad reads the property of this owner with its operator account.
// found is false when the property is not this host's.
func (c *call) guestpayLoad(ctx context.Context, id int64) (found bool, e *guestpayEntity, rate int64, err error) {
	var entityID *int64
	err = c.pool.QueryRow(ctx,
		`SELECT legal_entity_id, COALESCE(stay_fee_rate_czk, 0) FROM apartment WHERE id = $1 AND owner_user_id = $2`,
		id, c.owner).Scan(&entityID, &rate)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil, 0, nil
	}
	if err != nil {
		return false, nil, 0, err
	}
	if entityID == nil {
		return true, nil, rate, nil
	}
	var ent guestpayEntity
	err = c.pool.QueryRow(ctx,
		`SELECT COALESCE(bank_account, ''), COALESCE(iban, '') FROM legal_entity WHERE id = $1`,
		*entityID).Scan(&ent.BankAccount, &ent.IBAN)
	if errors.Is(err, pgx.ErrNoRows) {
		return true, nil, rate, nil
	}
	if err != nil {
		return false, nil, 0, err
	}
	return true, &ent, rate, nil
}

// GuestPayPreviewHandler serves POST /stay-fees/{apartment_id}/guest-pay-preview.
func GuestPayPreviewHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := deps{pool, getenv, now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enter(w, r)
		if c == nil {
			return
		}
		id, ok := pathID(w, r, "apartment_id")
		if !ok {
			return
		}
		found := false
		var entity *guestpayEntity
		var aptRate int64
		if !id.none && guestPayOn(getenv) {
			var err error
			if found, entity, aptRate, err = c.guestpayLoad(r.Context(), id.id); err != nil {
				c.fail(err)
				return
			}
		}
		if !found {
			guestpayJSON(w, http.StatusNotFound, map[string]bool{"ok": false})
			return
		}
		typed := c.formStr("account")
		has, display, qr, err := guestpayContext(entity, typed, guestpayParseRate(c.formStr("rate")), aptRate)
		if err != nil {
			c.fail(err)
			return
		}
		guestpayJSON(w, http.StatusOK, guestpayAnswer{OK: has, Invalid: typed != "" && !has, Account: display, QR: qr})
	}
}
