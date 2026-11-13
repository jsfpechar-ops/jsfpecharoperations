package billing

import (
	"context"
	"time"
)

// Invoicer is what the engine needs from the invoice side (billing_invoices.py
// in Python: issue, storno, PDF, mail). The billing job thread implements it;
// the engine never issues a document itself. today is used for its Y-M-D only.
// Periods are YYYY-MM-DD strings. Ids are platform_invoice ids.
type Invoicer interface {
	// IssueForPeriod is issue_for_period: the period's invoice, issued once.
	IssueForPeriod(ctx context.Context, owner int64, periodFrom, periodTo string, today time.Time) (int64, error)
	// IssueSupplementary is issue_supplementary (amountCZK in whole Kc).
	IssueSupplementary(ctx context.Context, owner int64, amountCZK int64, description, periodFrom, periodTo string, today time.Time) (int64, error)
	// Storno is storno: cancel an unpaid invoice, returning the storno id.
	Storno(ctx context.Context, invoiceID int64, reason string, today time.Time) (int64, error)
	// Send is send: mail the invoice with its PDF.
	Send(ctx context.Context, invoiceID int64) error
}
