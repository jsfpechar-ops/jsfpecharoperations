package billingjob

import (
	"context"
	"fmt"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

type dunningCounts struct{ overdue, reminded, paused int }

// overdueInvoice is one row of _unpaid_overdue: an unpaid invoice past its due
// date, with its account's status as it was when the list was read.
type overdueInvoice struct {
	id, owner, totalHaler int64
	number, due, status   string
}

// unpaidOverdue is _unpaid_overdue(today).
func (r *Runner) unpaidOverdue(ctx context.Context, today time.Time) ([]overdueInvoice, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT i.id, i.owner_user_id, i.number, i.total_haler, i.due_date, b.status
		 FROM platform_invoice i JOIN billing_account b ON b.owner_user_id = i.owner_user_id
		 WHERE i.kind IN ('invoice', 'supplementary') AND i.voided = 0 AND i.paid_on IS NULL
		   AND i.due_date < $1 AND ($2::bigint = 0 OR i.owner_user_id = $2)
		 ORDER BY i.id`, today.Format(isoDate), r.Owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []overdueInvoice
	for rows.Next() {
		var i overdueInvoice
		if err := rows.Scan(&i.id, &i.owner, &i.number, &i.totalHaler, &i.due, &i.status); err != nil {
			return nil, err
		}
		out = append(out, i)
	}
	return out, rows.Err()
}

// dunning is billing_jobs.dunning: reminders 7 and 14 days after the due date,
// then monthly; read-only after 14.
func (r *Runner) dunning(ctx context.Context, today time.Time) (dunningCounts, error) {
	var c dunningCounts
	list, err := r.unpaidOverdue(ctx, today)
	if err != nil {
		return c, err
	}
	for _, inv := range list {
		due, err := parseDate(inv.due)
		if err != nil {
			return c, err
		}
		late := int(today.Sub(due).Hours() / 24)
		if inv.status == "active" {
			changed, err := setStatus(ctx, r.Pool, inv.owner, "overdue", "system")
			if err != nil {
				return c, err
			}
			if changed {
				c.overdue++
			}
		}
		stage := ""
		switch {
		case late >= pauseAfter:
			changed, err := setStatus(ctx, r.Pool, inv.owner, "paused", "system")
			if err != nil {
				return c, err
			}
			if changed {
				c.paused++
			}
			stage = "paused"
		case late >= secondAfter:
			stage = "second"
		case late >= remindAfter:
			stage = "reminder"
		}
		if (stage == "second" || stage == "paused") && late >= monthlyAfter {
			// Monthly repeat: one mail per ~30 days even after the pause,
			// bucketed so it never duplicates within a month.
			stage = fmt.Sprintf("monthly%d", (late-secondAfter)/30)
		}
		if stage == "" {
			continue
		}
		sent, err := r.billingOverdueMail(ctx, inv, stage, today)
		if err != nil {
			return c, err
		}
		if sent {
			c.reminded++
		}
	}
	return c, nil
}

// billingOverdueMail is mail_notify.billing_overdue: one mail per invoice and
// stage, key billing-overdue-<invoice>-<stage>.
func (r *Runner) billingOverdueMail(ctx context.Context, inv overdueInvoice, stage string, today time.Time) (bool, error) {
	content := mail.BuildBillingOverdue(AppBaseURL(), PublicBaseURL(), OperatorEmail(), stage, inv.number,
		floorDiv(inv.totalHaler, 100), fmtDate(day10(inv.due)), fmtDate(today.Format(isoDate)))
	return r.queueServiceMail(ctx, "billing_overdue", fmt.Sprintf("billing-overdue-%d-%s", inv.id, stage), inv.owner, content)
}
