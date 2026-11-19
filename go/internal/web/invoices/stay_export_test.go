package invoices

import (
	"context"
	"testing"

	"github.com/jackc/pgx/v5"
)

type stayExportRow struct {
	id     int64
	number string
	err    error
}

func (r stayExportRow) Scan(dest ...any) error {
	if r.err != nil {
		return r.err
	}
	*dest[0].(*int64) = r.id
	*dest[1].(*string) = r.number
	return nil
}

type stayExportQ struct{ row stayExportRow }

func (q stayExportQ) QueryRow(context.Context, string, ...any) pgx.Row { return q.row }

func TestActiveInvoiceForStayWrapsUnexported(t *testing.T) {
	ctx := context.Background()
	found := stayExportQ{stayExportRow{id: 5, number: "2026-0005"}}
	got, err := ActiveInvoiceForStay(ctx, found, 9)
	want, werr := activeInvoiceForStay(ctx, found, 9)
	if err != nil || werr != nil || got == nil || want == nil || got.ID != want.ID || got.Number != want.Number {
		t.Fatalf("found: wrapper %+v %v, unexported %+v %v", got, err, want, werr)
	}
	none := stayExportQ{stayExportRow{err: pgx.ErrNoRows}}
	got, err = ActiveInvoiceForStay(ctx, none, 9)
	want, werr = activeInvoiceForStay(ctx, none, 9)
	if got != nil || err != nil || want != nil || werr != nil {
		t.Fatalf("none: wrapper %+v %v, unexported %+v %v", got, err, want, werr)
	}
}
