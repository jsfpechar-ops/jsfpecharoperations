package customers

// The invoice side of the plan actions. billingjob.Invoicer writes its
// platform_invoice_issued audit row with actor_user_id and impersonator_user_id
// NULL, as the billing job does (no signed-in user). Python's db.audit fills both
// from the signed-in account, so an invoice issued inside an operator's request
// carries the operator's id. requestInvoicer adds that to the rows its call just
// wrote, and only to them: rows with an id above the audit high-water mark taken
// before the call, written by the invoicer itself (actor "system", no user yet).
// Once billingjob reads the actor from the context, the update finds nothing to do.

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
)

type requestInvoicer struct {
	*billingjob.Invoicer
	pool         *pgxpool.Pool
	actorID      int64
	impersonator *int64
}

func newRequestInvoicer(c *actionCtx) *requestInvoicer {
	var impersonator *int64
	if c.admin.Impersonating {
		id := c.admin.Account.ID
		impersonator = &id
	}
	return &requestInvoicer{Invoicer: &billingjob.Invoicer{Pool: c.pool}, pool: c.pool,
		actorID: c.admin.Account.ID, impersonator: impersonator}
}

// stamped runs call and then marks the issue rows it wrote with the operator.
func (v *requestInvoicer) stamped(ctx context.Context, owner int64, call func() (int64, error)) (int64, error) {
	var mark int64
	if err := v.pool.QueryRow(ctx, "SELECT COALESCE(MAX(id), 0) FROM audit").Scan(&mark); err != nil {
		return 0, err
	}
	id, err := call()
	if _, uerr := v.pool.Exec(ctx, `UPDATE audit SET actor_user_id = $1, impersonator_user_id = $2
		WHERE id > $3 AND action = 'platform_invoice_issued' AND actor = 'system'
		AND actor_user_id IS NULL AND owner_user_id = $4`, v.actorID, v.impersonator, mark, owner); uerr != nil && err == nil {
		err = uerr
	}
	return id, err
}

// IssueForPeriod is billing.Invoicer.IssueForPeriod, stamped.
func (v *requestInvoicer) IssueForPeriod(ctx context.Context, owner int64, periodFrom, periodTo string, today time.Time) (int64, error) {
	return v.stamped(ctx, owner, func() (int64, error) {
		return v.Invoicer.IssueForPeriod(ctx, owner, periodFrom, periodTo, today)
	})
}

// IssueSupplementary is billing.Invoicer.IssueSupplementary, stamped.
func (v *requestInvoicer) IssueSupplementary(ctx context.Context, owner int64, amountCZK int64, description, periodFrom, periodTo string, today time.Time) (int64, error) {
	return v.stamped(ctx, owner, func() (int64, error) {
		return v.Invoicer.IssueSupplementary(ctx, owner, amountCZK, description, periodFrom, periodTo, today)
	})
}

// Storno is billing.Invoicer.Storno, stamped. The storno document is an
// issue of its own, written to the cancelled invoice's owner.
func (v *requestInvoicer) Storno(ctx context.Context, invoiceID int64, reason string, today time.Time) (int64, error) {
	var owner int64
	if err := v.pool.QueryRow(ctx, "SELECT COALESCE(owner_user_id, 0) FROM platform_invoice WHERE id = $1", invoiceID).Scan(&owner); err != nil {
		return v.Invoicer.Storno(ctx, invoiceID, reason, today)
	}
	return v.stamped(ctx, owner, func() (int64, error) {
		return v.Invoicer.Storno(ctx, invoiceID, reason, today)
	})
}
