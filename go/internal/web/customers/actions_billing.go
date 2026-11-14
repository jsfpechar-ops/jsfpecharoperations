package customers

// Brief 1591: the three actions that change a customer's plan or price and can
// issue, cancel or mail an invoice. Python: routes/admin_customers.py
// customer_discount (111-132), customer_plan (135-162) and customer_assign_plan
// (165-181). The billing engine (go/internal/billing) does the work in the same
// order as Python; the invoice side is go/internal/billingjob.Invoicer, which
// queues the invoice mail.

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
)

// DiscountHandler serves POST /admin/customers/{user_id}/sleva (customer_discount):
// set or clear the operator's discount. An unpaid invoice of the customer is
// cancelled (storno) and issued again with the discount (decision D1).
func DiscountHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return actionHandler(pool, getenv, now, func(w http.ResponseWriter, r *http.Request, c *actionCtx) error {
		raw := formValue(r, "percent")
		if raw == "" {
			raw = "0"
		}
		n, ok := pyInt(raw)
		if !ok {
			c.refuse(w, r, "billing.admin.discount.bad_percent")
			return nil
		}
		reason := pyStrip(formValue(r, "reason"))
		if runes := []rune(reason); len(runes) > 200 {
			reason = string(runes[:200])
		}
		inv := newRequestInvoicer(c)
		result, err := billing.ApplyDiscount(c.ctx, c.pool, inv, c.userID, clampInt(n), reason, c.actor(), c.today())
		if err != nil {
			if code, isValue := valueError(err); isValue {
				c.refuse(w, r, "billing.admin.discount."+code)
				return nil
			}
			return err
		}
		if len(result.ReissuedInvoiceIDs) > 0 {
			c.done(w, r, "billing.admin.discount.done_reissued", nil)
			return nil
		}
		c.done(w, r, "billing.admin.discount.done", nil)
		return nil
	})
}

// PlanChangeHandler serves POST /admin/customers/{user_id}/plan (customer_plan):
// one change of the customer's plan, with the engine the host's own plan page
// uses. A rise on an annual plan may issue and mail a supplementary invoice.
func PlanChangeHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return actionHandler(pool, getenv, now, func(w http.ResponseWriter, r *http.Request, c *actionCtx) error {
		field := pyStrip(formValue(r, "field"))
		if _, known := billing.ChangeColumns[field]; !known {
			c.refuse(w, r, "billing.admin.plan.bad_field")
			return nil
		}
		raw := pyStrip(formValue(r, "value"))
		var value any
		switch field {
		case "apartments", "addon_ttlock", "addon_whitelabel":
			n, ok := pyInt(raw)
			if !ok {
				c.refuse(w, r, "billing.admin.plan.bad_value")
				return nil
			}
			value = clampInt(n)
			if field != "apartments" {
				// int(bool(value))
				if value.(int) != 0 {
					value = 1
				} else {
					value = 0
				}
			}
		default:
			value = raw
		}
		inv := newRequestInvoicer(c)
		if _, err := billing.Change(c.ctx, c.pool, inv, c.userID, field, value, true, c.today(), billing.HostActor); err != nil {
			if _, isValue := valueError(err); isValue {
				c.refuse(w, r, "billing.admin.plan.refused")
				return nil
			}
			return err
		}
		if err := c.snapshot(); err != nil {
			return err
		}
		c.done(w, r, "billing.admin.plan.done", nil)
		return nil
	})
}

// AssignPlanHandler serves POST /admin/customers/{user_id}/priradit
// (customer_assign_plan): give a host who has no plan a first one. It starts
// today and the first invoice is issued and mailed at once.
func AssignPlanHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return actionHandler(pool, getenv, now, func(w http.ResponseWriter, r *http.Request, c *actionCtx) error {
		values, errs := billing.ReadForm(formMap(r))
		if len(errs) > 0 {
			c.refuse(w, r, "billing.admin.assign.error")
			return nil
		}
		inv := newRequestInvoicer(c)
		if _, err := billing.PlaceForOperator(c.ctx, c.pool, inv, c.userID, values, c.today(), c.actor()); err != nil {
			if _, isValue := valueError(err); isValue {
				c.refuse(w, r, "billing.admin.assign.refused")
				return nil
			}
			return err
		}
		if err := c.snapshot(); err != nil {
			return err
		}
		c.done(w, r, "billing.admin.assign.done", nil)
		return nil
	})
}
