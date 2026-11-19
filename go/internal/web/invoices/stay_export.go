package invoices

import (
	"context"

	"github.com/jackc/pgx/v5"
)

// StayInvoice is the stay's live invoice: its id and number.
type StayInvoice struct {
	ID     int64
	Number string
}

// ActiveInvoiceForStay is invoices.active_invoice_for_stay: the stay's invoice
// that has no storno/ODD yet, or nil. It only calls activeInvoiceForStay.
func ActiveInvoiceForStay(ctx context.Context, q interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}, reservationID int64) (*StayInvoice, error) {
	a, err := activeInvoiceForStay(ctx, q, reservationID)
	if err != nil || a == nil {
		return nil, err
	}
	return &StayInvoice{ID: a.ID, Number: a.Number}, nil
}
