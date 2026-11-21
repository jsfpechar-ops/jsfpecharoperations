package invoices

// invoice_send, routes/invoices.py 961-1001: queue invoice_issued mail to the buyer.

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

func init() { addRoutes(sendRoutes) }

func sendRoutes(d deps) []Route {
	return []Route{{"POST /invoices/{id}/send", "/invoices/{id}/send", d.sendInvoice}}
}

func (d deps) sendInvoice(w http.ResponseWriter, r *http.Request) {
	c, id := d.enterID(w, r, r.PathValue("id"))
	if c == nil {
		return
	}
	ctx := r.Context()
	inv, err := loadInvoice(ctx, d.pool, c.owner, id)
	if err != nil {
		c.fail(err)
		return
	}
	if inv == nil {
		c.back("/invoices", noFlash, c.flash("flash.error.no_such_invoice", nil))
		return
	}
	if inv.BuyerEmail == "" {
		c.back("/invoices/"+itoa(id), noFlash, c.flash("invoice.err.no_email", nil))
		return
	}
	ent, err := entityForInvoice(ctx, d.pool, c.owner, inv.LegalEntityID)
	if err != nil {
		c.fail(err)
		return
	}
	issuer := "UbyHost"
	if ent != nil && ent.Name != "" {
		issuer = ent.Name
	}
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		c.fail(err)
		return
	}
	token, err := downloadTokenFor(secret, id, inv.PDFSHA256, c.at)
	if err != nil {
		c.fail(err)
		return
	}
	public := strings.TrimRight(d.getenv("UBYHOST_PUBLIC_BASE_URL"), "/")
	downloadURL := public + "/invoice/d/" + mail.ClaimSecretMarker
	host, err := invoiceHostDetails(ctx, d.pool, inv.LegalEntityID)
	if err != nil {
		c.fail(err)
		return
	}
	stayProp, err := stayPropertyName(ctx, d.pool, inv.ReservationID)
	if err != nil {
		c.fail(err)
		return
	}
	content := mail.BuildInvoiceIssued(public, inv.Lang, issuer, inv.Number,
		moneyCZK(inv.TotalHaler, 1), downloadURL, host, stayProp)
	payload, err := invoiceGuestPayload(ctx, d.pool, inv.LegalEntityID, content, inv.Lang)
	if err != nil {
		c.fail(err)
		return
	}
	keys, err := secure.LoadDataKeys(d.getenv)
	if err != nil {
		c.fail(err)
		return
	}
	enc, err := keys.EncryptString(token)
	if err != nil {
		c.fail(err)
		return
	}
	payload = strings.TrimSuffix(payload, "}") + fmt.Sprintf(`, "%s": %s}`, mail.ClaimSecretPayloadKey, ubyport.PyString(enc))
	var sentBefore int
	if err := d.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM email_outbox WHERE idempotency_key LIKE $1`,
		fmt.Sprintf("invoice_issued:%d:%%", id)).Scan(&sentBefore); err != nil {
		c.fail(err)
		return
	}
	key := fmt.Sprintf("invoice_issued:%d:%d", id, sentBefore)
	if _, err := ubyport.EnqueueMail(ctx, d.pool, ubyport.OutboxMail{
		Kind: "invoice_issued", Key: key, To: inv.BuyerEmail,
		Subject: content.Subject, Payload: payload, OwnerUserID: &c.owner,
	}); err != nil {
		c.fail(err)
		return
	}
	if _, err := d.pool.Exec(ctx, `UPDATE invoice SET emailed_at = $1 WHERE id = $2`, stamp(c.at), id); err != nil {
		c.fail(err)
		return
	}
	if err := c.audit("invoice_sent", "id="+itoa(id)); err != nil {
		c.fail(err)
		return
	}
	c.back("/invoices/"+itoa(id), c.flash("invoice.sent_flash", nil), noFlash)
}

func entityForInvoice(ctx context.Context, pool *pgxpool.Pool, owner, id int64) (*entity, error) {
	e, err := scanEntity(pool.QueryRow(ctx,
		`SELECT `+entityColumns+` FROM legal_entity WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2::bigint`,
		id, ownerArg(owner)))
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &e, nil
}

func invoiceHostDetails(ctx context.Context, pool *pgxpool.Pool, legalEntityID int64) (mail.HostDetails, error) {
	var name, seat, email, phone string
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(name,''), COALESCE(seat,''), COALESCE(contact_email,''), COALESCE(contact_phone,'')
		 FROM legal_entity WHERE id = $1`, legalEntityID).Scan(&name, &seat, &email, &phone)
	if errors.Is(err, pgx.ErrNoRows) {
		return mail.HostDetails{}, nil
	}
	if err != nil {
		return mail.HostDetails{}, err
	}
	return mail.HostDetails{Name: name, Seat: seat, Email: email, Phone: phone}, nil
}

func stayPropertyName(ctx context.Context, pool *pgxpool.Pool, reservationID *int64) (string, error) {
	if reservationID == nil {
		return "", nil
	}
	var internal, uby string
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(a.internal_name,''), COALESCE(a.uby_name,'')
		 FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = $1`,
		*reservationID).Scan(&internal, &uby)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if s := strings.TrimSpace(internal); s != "" {
		return s, nil
	}
	return strings.TrimSpace(uby), nil
}

// invoiceGuestPayload is mail_notify.guest_payload({"legal_entity_id": id}, ...).
func invoiceGuestPayload(ctx context.Context, pool *pgxpool.Pool, legalEntityID int64, content mail.Content, lang string) (string, error) {
	var reply string
	err := pool.QueryRow(ctx, `SELECT COALESCE(contact_email,'') FROM legal_entity WHERE id = $1`, legalEntityID).Scan(&reply)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	var b strings.Builder
	b.WriteString(`{"text": `)
	b.WriteString(ubyport.PyString(content.Text))
	b.WriteString(`, "lang": `)
	b.WriteString(ubyport.PyString(lang))
	if content.HTML != "" {
		b.WriteString(`, "html": `)
		b.WriteString(ubyport.PyString(content.HTML))
	}
	if reply != "" {
		b.WriteString(`, "reply_to": `)
		b.WriteString(ubyport.PyString(reply))
	}
	b.WriteString("}")
	return b.String(), nil
}
