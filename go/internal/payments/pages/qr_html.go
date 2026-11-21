package pages

import (
	"bytes"
	_ "embed"
	"errors"
	"html/template"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest"
)

//go:embed templates/payments_qr_standalone.tmpl
var qrStandaloneTmpl string

const hostQRRowSQL = `SELECT owner_user_id, rail, status, amount_czk, variable_symbol FROM payment_request WHERE id = $1`

var qrPageTpl = template.Must(template.New("qr").Parse(qrStandaloneTmpl))

// payNoAccount is i18n pay_no_account for guest languages (App/app/i18n.py and guest_uk_i18n.py).
var payNoAccount = map[string]string{
	"en": "The host has not set up bank payment yet. Please ask the host for another way to pay.",
	"cs": "Hostitel zatím nemá nastavenou platbu převodem. Zeptejte se ho na jiný způsob platby.",
	"de": "Der Gastgeber hat die Banküberweisung noch nicht eingerichtet. Bitte fragen Sie ihn nach einer anderen Zahlungsweise.",
	"es": "El anfitrión aún no ha configurado el pago por transferencia. Pídale otra forma de pago.",
	"fr": "L'hôte n'a pas encore configuré le paiement par virement. Demandez-lui un autre moyen de paiement.",
	"uk": "Господар ще не налаштував оплату переказом. Запитайте в нього інший спосіб оплати.",
}

type qrPageView struct {
	Lang          string
	Title         string
	Heading       string
	Paid          bool
	PaidLabel     string
	NoAccountText string
	AmountLabel   string
	Amount        int64
	CZK           string
	VSLabel       string
	VS            string
	PNGURL        string
	Alt           string
	Disclosure    string
}

func payNoAccountText(lang string) string {
	code := guest.GuestLanguage(lang)
	if t, ok := payNoAccount[code]; ok {
		return t
	}
	return payNoAccount["en"]
}

func hostQRStrings(lang string) (title, amount, vs, alt, disclosure, paid, czk string) {
	return cat.T(lang, "payments.qr.title", nil),
		cat.T(lang, "payments.qr.amount", nil),
		cat.T(lang, "payments.qr.vs", nil),
		cat.T(lang, "payments.qr.alt", nil),
		cat.T(lang, "payments.qr.disclosure", nil),
		cat.T(lang, "payments.status.paid", nil),
		cat.T(lang, "payments.czk", nil)
}

func writeQRPage(w http.ResponseWriter, v qrPageView) error {
	var buf bytes.Buffer
	if err := qrPageTpl.Execute(&buf, v); err != nil {
		return err
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, err := w.Write(buf.Bytes())
	return err
}

// HostQRPageHandler serves GET /payments/qr/{id} (host preview, login required).
func HostQRPageHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		raw := strings.TrimSpace(r.PathValue("file"))
		if raw == "" || strings.HasSuffix(raw, ".png") {
			notFound(w)
			return
		}
		id, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || id < 0 {
			notFound(w)
			return
		}
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			fail(w, err)
			return
		}
		if h == nil {
			return
		}
		lang := hostweb.Lang(r)
		ctx := r.Context()
		var owner int64
		var rail, status string
		var amount int64
		var vs *string
		err = pool.QueryRow(ctx, hostQRRowSQL, id).Scan(&owner, &rail, &status, &amount, &vs)
		if errors.Is(err, pgx.ErrNoRows) {
			backErr(w, r, "/payments", "payments.err.invalid", "")
			return
		}
		if err != nil {
			fail(w, err)
			return
		}
		if owner != h.Workspace.ID || rail != "qr" {
			backErr(w, r, "/payments", "payments.err.invalid", "")
			return
		}
		if _, err := payments.QRPayload(ctx, pool, owner, amount, vs); errors.Is(err, payments.ErrQRAccount) {
			backErr(w, r, "/payments", "payments.err.no_iban", "bank")
			return
		} else if err != nil {
			fail(w, err)
			return
		}
		title, amountLbl, vsLbl, alt, disc, paidLbl, czk := hostQRStrings(lang)
		vsText := ""
		if vs != nil {
			vsText = *vs
		}
		v := qrPageView{
			Lang: lang, Title: title, Heading: title,
			Paid: status == "paid", PaidLabel: paidLbl,
			AmountLabel: amountLbl, Amount: amount, CZK: czk,
			VSLabel: vsLbl, VS: vsText,
			PNGURL: "/payments/qr/" + strconv.FormatInt(id, 10) + ".png",
			Alt:    alt, Disclosure: disc,
		}
		if err := writeQRPage(w, v); err != nil {
			fail(w, err)
		}
	}
}

// GuestQRPageHandler serves GET /pay/{id}/{token} (guest bank-transfer page).
func GuestQRPageHandler(pool *pgxpool.Pool, getenv func(string) string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token := strings.TrimSpace(r.PathValue("file"))
		if token == "" || strings.HasSuffix(token, ".png") {
			notFound(w)
			return
		}
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		if err != nil || id < 0 {
			notFound(w)
			return
		}
		ctx := r.Context()
		owner, amount, vs, status, ok, err := payments.GuestQRRequest(ctx, pool, getenv, id, token)
		if err != nil {
			fail(w, err)
			return
		}
		if !ok {
			notFound(w)
			return
		}
		lang := guest.Language(r)
		title, amountLbl, vsLbl, alt, disc, paidLbl, czk := hostQRStrings(lang)
		v := qrPageView{
			Lang: lang, Title: title, Heading: title,
			Paid: status == "paid", PaidLabel: paidLbl,
			PNGURL: "/pay/" + strconv.FormatInt(id, 10) + "/" + token + ".png",
		}
		if _, err := payments.QRPayload(ctx, pool, owner, amount, vs); errors.Is(err, payments.ErrQRAccount) {
			v.NoAccountText = payNoAccountText(lang)
		} else if err != nil {
			fail(w, err)
			return
		} else {
			vsText := ""
			if vs != nil {
				vsText = *vs
			}
			v.AmountLabel = amountLbl
			v.Amount = amount
			v.CZK = czk
			v.VSLabel = vsLbl
			v.VS = vsText
			v.Alt = alt
			v.Disclosure = disc
		}
		w.Header().Set("X-Robots-Tag", "noindex")
		if err := writeQRPage(w, v); err != nil {
			fail(w, err)
		}
	}
}

// HostQRDispatch serves GET /payments/qr/{file}: *.png to png, else the host page.
func HostQRDispatch(png, page http.Handler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.PathValue("file"), ".png") {
			png.ServeHTTP(w, r)
			return
		}
		page.ServeHTTP(w, r)
	}
}

// GuestPayDispatch serves GET /pay/{id}/{file}: *.png to png, else the guest page.
func GuestPayDispatch(png, page http.Handler) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.PathValue("file"), ".png") {
			png.ServeHTTP(w, r)
			return
		}
		page.ServeHTTP(w, r)
	}
}
