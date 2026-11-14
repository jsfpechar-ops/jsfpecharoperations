package customers

// Brief 1590: the three account actions that need no invoice. Python:
// routes/admin_customers.py customer_status (241-262), customer_extend_trial
// (184-202) and customer_resend_verification (228-238).

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
)

// statuses is admin_customers.STATUSES.
var statuses = []string{"trial_pending", "trialing", "active", "overdue", "canceling", "paused"}

func isStatus(s string) bool {
	for _, v := range statuses {
		if v == s {
			return true
		}
	}
	return false
}

// StatusHandler serves POST /admin/customers/{user_id}/stav (customer_status):
// a status change through the billing state machine, no bypass. "canceling" and
// the return from "canceling" go through Cancel and Resume, which also set
// cancel_at_period_end; they write their audit rows with the signed-in
// username (Python's actor "host" is replaced by db.audit), every other move
// with "operator:<username>". A refused move writes nothing. The month
// snapshot is rewritten after every change.
func StatusHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return actionHandler(pool, getenv, now, func(w http.ResponseWriter, r *http.Request, c *actionCtx) error {
		next := pyStrip(formValue(r, "status"))
		if !isStatus(next) {
			c.refuse(w, r, "billing.admin.status.bad")
			return nil
		}
		var ok bool
		var err error
		switch next {
		case "canceling":
			ok, err = billing.Cancel(c.ctx, c.pool, c.userID, billing.HostActor)
		case "active":
			var acc *billing.BillingAccount
			if acc, err = billing.Account(c.ctx, c.pool, c.userID); err != nil {
				return err
			}
			if acc != nil && acc.Status == "canceling" {
				ok, err = billing.Resume(c.ctx, c.pool, c.userID, billing.HostActor)
			} else {
				ok, err = billing.SetStatus(c.ctx, c.pool, c.userID, "active", c.actor())
			}
		default:
			ok, err = billing.SetStatus(c.ctx, c.pool, c.userID, next, c.actor())
		}
		if err != nil {
			return err
		}
		if !ok {
			c.refuse(w, r, "billing.admin.status.refused")
			return nil
		}
		if err := c.snapshot(); err != nil {
			return err
		}
		c.done(w, r, "billing.admin.status.done", nil)
		return nil
	})
}

// ExtendTrialHandler serves POST /admin/customers/{user_id}/prodlouzit
// (customer_extend_trial): move a running trial's end by N days (1 to 365).
func ExtendTrialHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return actionHandler(pool, getenv, now, func(w http.ResponseWriter, r *http.Request, c *actionCtx) error {
		n, ok := pyInt(formValue(r, "days"))
		if !ok {
			c.refuse(w, r, "billing.admin.extend.bad_days")
			return nil
		}
		days := clampInt(n)
		end, err := billing.ExtendTrial(c.ctx, c.pool, c.userID, days, c.actor(), c.today())
		if err != nil {
			if code, isValue := valueError(err); isValue && code == billing.ErrBadDays.Error() {
				c.refuse(w, r, "billing.admin.extend.bad_days")
				return nil
			}
			return err
		}
		if end == "" {
			c.refuse(w, r, "billing.admin.extend.not_trialing")
			return nil
		}
		c.done(w, r, "billing.admin.extend.done", map[string]any{"days": days})
		return nil
	})
}

// ResendVerificationHandler serves POST /admin/customers/{user_id}/overit-znovu
// (customer_resend_verification): a pending sign-up gets a new verification link
// (the new nonce retires the old one); one signup_verify mail is queued and the
// resend is audited. Any other account is refused.
func ResendVerificationHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return actionHandler(pool, getenv, now, func(w http.ResponseWriter, r *http.Request, c *actionCtx) error {
		ok, err := signup.ResendOperator(c.ctx, c.pool, c.userID, c.actor(), c.getenv, c.at)
		if err != nil {
			return err
		}
		if !ok {
			c.refuse(w, r, "customers.ops.verify_refused")
			return nil
		}
		c.done(w, r, "customers.ops.verify_sent", nil)
		return nil
	})
}
