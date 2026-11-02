package payments

// Go port of App/app/routes/payments.py payment_request_qr_png (222-236) with
// payment_request.get and qr_payload (App/app/payment_request.py), and the
// SPAYD helpers from App/app/payments.py: normalise_account, ascii_upper,
// spayd and qr_png_bytes. The Python HTML page /payments/qr/{request_id} stays
// on Python; Caddy decides which paths reach Go.

import (
	"context"
	"errors"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/skip2/go-qrcode"
	"golang.org/x/text/unicode/norm"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

var (
	// _ACCOUNT_RE and _IBAN_RE from App/app/payments.py.
	qrAccountRE = regexp.MustCompile(`^(?:([0-9]{1,6})-)?([0-9]{2,10})/([0-9]{4})$`)
	qrIBANRE    = regexp.MustCompile(`^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$`)
)

// qrWeights is _WEIGHTS from App/app/payments.py.
var qrWeights = [10]int{6, 3, 7, 9, 10, 5, 8, 4, 2, 1}

const qrChars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $+-./:"

const (
	qrRequestSQL = `SELECT owner_user_id, rail, amount_czk, variable_symbol FROM payment_request WHERE id = $1`
	qrEntitySQL  = `SELECT iban, bank_account FROM legal_entity WHERE owner_user_id = $1`
)

// errQRAccount marks input that payment_request.qr_payload turns into a
// ValueError (the route answers 404 for it).
var errQRAccount = errors.New("qr account")

func qrMod11OK(digits string) bool {
	padded := strings.Repeat("0", max(0, 10-len(digits))) + digits
	sum := 0
	for i, c := range padded {
		sum += int(c-'0') * qrWeights[i]
	}
	return sum%11 == 0
}

func qrIBANOK(iban string) bool {
	moved := iban[4:] + iban[:4]
	var b strings.Builder
	for _, c := range moved {
		if c >= 'A' && c <= 'Z' {
			b.WriteString(strconv.Itoa(int(c-'A') + 10))
		} else {
			b.WriteRune(c)
		}
	}
	mod := 0
	for _, c := range b.String() {
		mod = (mod*10 + int(c-'0')) % 97
	}
	return mod == 1
}

// qrNormaliseAccount is payments.normalise_account: (display account, IBAN).
func qrNormaliseAccount(raw string) (string, string, error) {
	text := strings.Map(func(r rune) rune {
		if unicode.IsSpace(r) {
			return -1
		}
		return r
	}, raw)
	text = strings.ToUpper(text)
	if qrIBANRE.MatchString(text) {
		if !qrIBANOK(text) {
			return "", "", errQRAccount
		}
		return text, text, nil
	}
	m := qrAccountRE.FindStringSubmatch(text)
	if m == nil {
		return "", "", errQRAccount
	}
	prefix, number, bank := m[1], m[2], m[3]
	if (prefix != "" && !qrMod11OK(prefix)) || !qrMod11OK(number) {
		return "", "", errQRAccount
	}
	padPrefix := strings.Repeat("0", max(0, 6-len(prefix))) + prefix
	padNumber := strings.Repeat("0", max(0, 10-len(number))) + number
	bban := bank + padPrefix + padNumber
	// check = 98 - int(bban + "123500") % 97, computed without big integers.
	mod := 0
	for _, c := range bban + "123500" {
		mod = (mod*10 + int(c-'0')) % 97
	}
	check := 98 - mod
	display := number + "/" + bank
	if prefix != "" {
		display = prefix + "-" + number + "/" + bank
	}
	iban := "CZ" + twoDigits(check) + bban
	return display, iban, nil
}

func twoDigits(n int) string {
	if n < 10 {
		return "0" + strconv.Itoa(n)
	}
	return strconv.Itoa(n)
}

// qrASCIIUpper is payments.ascii_upper: NFKD, drop combining marks, upper,
// keep only the QR character set (other characters become spaces), collapse
// spaces, cut to limit characters.
func qrASCIIUpper(text string, limit int) string {
	var up strings.Builder
	for _, r := range norm.NFKD.String(text) {
		// unicodedata.combining(ch) is the canonical combining class.
		if norm.NFC.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		// Python str.upper() maps ß to SS; strings.ToUpper keeps it.
		if r == 'ß' {
			up.WriteString("SS")
			continue
		}
		up.WriteRune(unicode.ToUpper(r))
	}
	var b strings.Builder
	lastSpace := false
	for _, r := range up.String() {
		if !strings.ContainsRune(qrChars, r) {
			r = ' '
		}
		if r == ' ' {
			if lastSpace {
				continue
			}
			lastSpace = true
		} else {
			lastSpace = false
		}
		b.WriteRune(r)
	}
	plain := strings.TrimSpace(b.String())
	if len(plain) > limit {
		plain = plain[:limit]
	}
	return strings.TrimRight(plain, " ")
}

// qrSPAYD is payments.spayd without the BIC part. The variable symbol is
// formatted as Python formats a None value (text "None") when it is absent.
func qrSPAYD(iban string, amountCZK int64, vs string, message string) string {
	parts := []string{
		"SPD", "1.0",
		"ACC:" + iban,
		"AM:" + strconv.FormatInt(amountCZK, 10) + ".00",
		"CC:CZK",
		"X-VS:" + vs,
		"MSG:" + qrASCIIUpper(message, 60),
	}
	return strings.Join(parts, "*")
}

// qrPayload is payment_request.qr_payload for a qr-rail request: the SPAYD
// string, or errQRAccount when the host has no usable bank account.
func qrPayload(ctx context.Context, pool *pgxpool.Pool, owner int64, amount int64, vs *string) (string, error) {
	var iban, bank *string
	err := pool.QueryRow(ctx, qrEntitySQL, owner).Scan(&iban, &bank)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", errQRAccount
	}
	if err != nil {
		return "", err
	}
	ibanVal := ""
	if iban != nil {
		ibanVal = *iban
	}
	bankVal := ""
	if bank != nil {
		bankVal = *bank
	}
	if ibanVal == "" && bankVal == "" {
		return "", errQRAccount
	}
	account := ibanVal
	if account == "" {
		_, normalised, err := qrNormaliseAccount(bankVal)
		if err != nil {
			return "", err
		}
		account = normalised
	}
	vsText := "None"
	if vs != nil {
		vsText = *vs
	}
	return qrSPAYD(account, amount, vsText, "UbyHost payment request"), nil
}

// qrPNGID accepts only "<digits>.png" and returns the request id.
func qrPNGID(file string) (int64, bool) {
	digits, ok := strings.CutSuffix(file, ".png")
	if !ok || digits == "" {
		return 0, false
	}
	for _, c := range digits {
		if c < '0' || c > '9' {
			return 0, false
		}
	}
	id, err := strconv.ParseInt(digits, 10, 64)
	if err != nil {
		return 0, false
	}
	return id, true
}

// qrPNGBytes is payment_request.qr_payload's PNG: medium error correction, 6 px
// modules, 4-module border (qr_png_bytes).
func qrPNGBytes(payload string) ([]byte, error) {
	code, err := qrcode.New(payload, qrcode.Medium)
	if err != nil {
		return nil, err
	}
	return code.PNG(-6)
}

// QRPNGHandler serves GET /payments/qr/{file} for <digits>.png. Every
// refusal is a 404 with an empty body, as in Python.
func QRPNGHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := qrPNGID(r.PathValue("file"))
		if !ok {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		h, err := hostweb.Login(w, r, pool, getenv, now())
		if err != nil {
			requestFail(w, err)
			return
		}
		if h == nil {
			return
		}
		ctx := r.Context()
		owner := h.Workspace.ID

		var (
			rowOwner int64
			rail     string
			amount   int64
			vs       *string
		)
		err = pool.QueryRow(ctx, qrRequestSQL, id).Scan(&rowOwner, &rail, &amount, &vs)
		if errors.Is(err, pgx.ErrNoRows) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		if err != nil {
			requestFail(w, err)
			return
		}
		if rowOwner != owner || rail != "qr" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		payload, err := qrPayload(ctx, pool, rowOwner, amount, vs)
		if errors.Is(err, errQRAccount) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		if err != nil {
			requestFail(w, err)
			return
		}
		png, err := qrPNGBytes(payload)
		if err != nil {
			requestFail(w, err)
			return
		}
		w.Header().Set("Content-Type", "image/png")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(png)
	}
}
