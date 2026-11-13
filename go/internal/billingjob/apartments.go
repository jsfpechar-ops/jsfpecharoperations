package billingjob

import (
	"context"
	"errors"
	"math"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// changeResult is billing.apply_change's result, the keys the job uses.
type changeResult struct {
	When          string // now, next_period or none
	Supplementary int64
	Carry         int64
}

// followApartments is billing_jobs.follow_apartments: more active apartments than
// billed are billed from today, fewer from the next period. It returns the "when"
// of the change ("" when nothing was to do; "none" still counts, as in Python).
func (r *Runner) followApartments(ctx context.Context, acc jobAccount, today time.Time) (string, error) {
	count, err := apartments(ctx, r.Pool, acc.Owner)
	if err != nil {
		return "", err
	}
	if (acc.Status != "active" && acc.Status != "overdue") || count == acc.ApartmentsBilled {
		return "", nil
	}
	pend, err := parsePending(acc.PendingJSON)
	if err != nil {
		return "", err
	}
	if count < acc.ApartmentsBilled && pend.equalsInt("apartments", count) {
		return "", nil
	}
	result, err := r.change(ctx, acc.Owner, count, today)
	if err != nil {
		return "", err
	}
	return result.When, nil
}

// change is billing_order.change(owner, "apartments", count, confirm=True): save
// the change; a rise on an annual plan may issue and mail a supplementary invoice.
func (r *Runner) change(ctx context.Context, owner, count int64, today time.Time) (changeResult, error) {
	result, err := r.applyApartments(ctx, owner, count, today)
	if err != nil {
		return result, err
	}
	if result.Supplementary == 0 {
		return result, nil
	}
	acc, err := loadAccount(ctx, r.Pool, owner)
	if err != nil {
		return result, err
	}
	if acc == nil {
		return result, errors.New("billing account vanished")
	}
	to := today.Format(isoDate)
	if acc.PeriodEnd != "" {
		to = day10(acc.PeriodEnd)
	}
	inv := r.invoicer()
	id, err := inv.IssueSupplementary(ctx, owner, result.Supplementary,
		"Doplatek za změnu předplatného od "+fmtDate(today.Format(isoDate)), today.Format(isoDate), to, today)
	if err != nil {
		return result, err
	}
	r.send(ctx, inv, id)
	return result, nil
}

// applyApartments is billing.apply_change(owner, {"apartments": count},
// confirm=True) with actor "host": the same quote, rounding (half to even), carry,
// pending change and audit row (billing_change, "apartments <when>").
func (r *Runner) applyApartments(ctx context.Context, owner, count int64, today time.Time) (changeResult, error) {
	var result changeResult
	acc, err := loadAccount(ctx, r.Pool, owner)
	if err != nil {
		return result, err
	}
	if acc == nil || acc.Plan == nil {
		return result, errors.New("no ordered plan to change")
	}
	interval := ""
	if acc.Interval != nil {
		interval = *acc.Interval
	}
	total := func(apartments int64) (int64, error) {
		q, err := billing.Quote(int(apartments), *acc.Plan, interval, acc.AddonTTLock, acc.AddonWhitelabel, int(acc.DiscountPercent))
		return int64(q.Total), err
	}
	before, err := total(acc.ApartmentsBilled)
	if err != nil {
		return result, err
	}
	after, err := total(count)
	if err != nil {
		return result, err
	}
	switch {
	case after == before:
		result.When = "none"
	case after > before:
		result.When = "now"
	default:
		result.When = "next_period"
	}
	var difference int64
	if result.When == "now" && interval == "year" && acc.PeriodEnd != "" {
		end, err := parseDate(acc.PeriodEnd)
		if err != nil {
			return result, err
		}
		months := wholeMonths(today, end)
		difference = int64(math.RoundToEven(float64((after-before)*months) / 12))
	}
	if difference >= SupplementaryMinCZK {
		result.Supplementary = difference
	}
	result.Carry = difference - result.Supplementary
	if result.When == "none" {
		return result, nil
	}
	if result.When == "now" {
		if _, err := r.Pool.Exec(ctx,
			`UPDATE billing_account SET apartments_billed = $1, carry_czk = carry_czk + $2, updated_at = $3
			 WHERE owner_user_id = $4`, count, result.Carry, ubyport.UTCNow(), owner); err != nil {
			return result, err
		}
	} else {
		pend, err := parsePending(acc.PendingJSON)
		if err != nil {
			return result, err
		}
		pend.values["apartments"] = jsonNumber(count)
		if _, err := r.Pool.Exec(ctx,
			`UPDATE billing_account SET pending_change_json = $1, updated_at = $2 WHERE owner_user_id = $3`,
			pend.dump(), ubyport.UTCNow(), owner); err != nil {
			return result, err
		}
	}
	err = audit(ctx, r.Pool, "host", "billing_change", "apartments "+result.When, &owner)
	return result, err
}

// wholeMonths is billing._whole_months.
func wholeMonths(start, end time.Time) int64 {
	months := int64(end.Year()-start.Year())*12 + int64(end.Month()) - int64(start.Month())
	if end.Day() < start.Day() {
		months--
	}
	if months < 0 {
		return 0
	}
	return months
}
