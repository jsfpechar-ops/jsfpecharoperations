package billingjob

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strings"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// Send is billing_invoices.send: queue the invoice mail (kind billing_invoice,
// key billing-invoice-<id>) with the stored PDF attached at send time. Nothing is
// queued when the invoice is missing or its workspace is gone, when mail is off,
// or when no usable recipient exists.
func (v *Invoicer) Send(ctx context.Context, invoiceID int64) error {
	var (
		owner                                 *int64
		number, vs, due, periodFrom, periodTo string
		totalHaler                            int64
	)
	err := v.Pool.QueryRow(ctx,
		`SELECT owner_user_id, number, vs, total_haler, due_date, period_from, period_to
		 FROM platform_invoice WHERE id = $1`, invoiceID,
	).Scan(&owner, &number, &vs, &totalHaler, &due, &periodFrom, &periodTo)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && owner == nil) {
		return nil
	}
	if err != nil {
		return err
	}
	if !MailEnabled() {
		return nil
	}
	to, err := v.Recipient(ctx, *owner)
	if err != nil {
		return err
	}
	to = ubyport.NormaliseEmail(to)
	if to == "" {
		return nil
	}
	content := mail.BuildBillingInvoice(AppBaseURL(), PublicBaseURL(), OperatorEmail(),
		number, vs, floorDiv(totalHaler, 100), fmtDate(due), fmtDateRange(periodFrom, periodTo))
	payload := fmt.Sprintf(
		`{"text": %s, "html": %s, "lang": "cs", "reply_to": %s, "platform_invoice_id": %d, "attachment_name": %s}`,
		ubyport.PyString(content.Text), ubyport.PyString(content.HTML),
		ubyport.PyString(OperatorEmail()), invoiceID, ubyport.PyString(number+".pdf"))
	_, err = ubyport.EnqueueMail(ctx, v.Pool, ubyport.OutboxMail{
		Kind: "billing_invoice", Key: fmt.Sprintf("billing-invoice-%d", invoiceID),
		OwnerUserID: owner, To: to, Subject: content.Subject, Payload: payload,
	})
	return err
}

// Recipient is billing_invoices.recipient: the billing e-mail from the order,
// else the account's login address (both stripped; "" when neither exists).
func (v *Invoicer) Recipient(ctx context.Context, owner int64) (string, error) {
	acc, err := v.account(ctx, owner)
	if err != nil {
		return "", err
	}
	if acc != nil && strings.TrimSpace(acc.BuyerEmail) != "" {
		return strings.TrimSpace(acc.BuyerEmail), nil
	}
	var email *string
	err = v.Pool.QueryRow(ctx, `SELECT email FROM user_account WHERE id = $1`, owner).Scan(&email)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && email == nil) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(*email), nil
}

// MailEnabled is mail.mail_enabled: UBYHOST_MAIL_BACKEND is console or ses.
func MailEnabled() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("UBYHOST_MAIL_BACKEND"))) {
	case "console", "ses":
		return true
	}
	return false
}

// PublicBaseURL is config.PUBLIC_BASE_URL.
func PublicBaseURL() string {
	v, ok := os.LookupEnv("UBYHOST_PUBLIC_BASE_URL")
	if !ok {
		v = "http://127.0.0.1:8080"
	}
	return strings.TrimRight(v, "/")
}

// AppBaseURL is config.app_base_url(): UBYHOST_APP_BASE_URL, else the public URL.
func AppBaseURL() string {
	if v := strings.TrimRight(strings.TrimSpace(os.Getenv("UBYHOST_APP_BASE_URL")), "/"); v != "" {
		return v
	}
	return PublicBaseURL()
}
