package billingjob

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// Days after the due date: first reminder, second reminder, monthly repeat,
// read-only (billing_jobs.py).
const (
	remindAfter  = 7
	secondAfter  = 14
	monthlyAfter = 44
	pauseAfter   = 14
)

// Counts is billing_jobs.run's result, with Python's keys in Map.
type Counts struct {
	Rolled, Invoiced, Apartments, Errors                  int
	TrialStarted, TrialReminded, TrialActive, TrialPaused int
	DunningOverdue, DunningReminded, DunningPaused        int
}

// Map is the dict Python returns.
func (c Counts) Map() map[string]int {
	return map[string]int{
		"rolled": c.Rolled, "invoiced": c.Invoiced, "apartments": c.Apartments, "errors": c.Errors,
		"trial_started": c.TrialStarted, "trial_reminded": c.TrialReminded,
		"trial_active": c.TrialActive, "trial_paused": c.TrialPaused,
		"dunning_overdue": c.DunningOverdue, "dunning_reminded": c.DunningReminded,
		"dunning_paused": c.DunningPaused,
	}
}

// Total is the number the job queue records: every count except errors.
func (c Counts) Total() int {
	return c.Rolled + c.Invoiced + c.Apartments + c.TrialStarted + c.TrialReminded +
		c.TrialActive + c.TrialPaused + c.DunningOverdue + c.DunningReminded + c.DunningPaused
}

// Runner is the daily billing run. Owner, when not zero, limits the account
// loop and the dunning to one host (Python's owner_user_id argument).
type Runner struct {
	Pool     *pgxpool.Pool
	Invoicer *Invoicer // nil: an Invoicer on Pool
	Owner    int64
}

func (r *Runner) invoicer() *Invoicer {
	if r.Invoicer != nil {
		return r.Invoicer
	}
	return &Invoicer{Pool: r.Pool}
}

// BillingEnabled is billing.enabled(): UBYHOST_BILLING_ENABLED is 1, true or yes.
func BillingEnabled() bool {
	switch strings.ToLower(os.Getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// Today is the calendar date of t (the caller passes the server-local time, as
// Python's date.today()), at midnight UTC.
func Today(t time.Time) time.Time {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// Run is billing_jobs.run: trials, new periods, invoices, apartment counts,
// dunning. One account's failure never stops the others (audit billing_run_failed,
// Errors counts it). A failure in the trial step or the dunning step stops the
// run with an error, as the exception does in Python; the counts so far return.
func (r *Runner) Run(ctx context.Context, today time.Time) (Counts, error) {
	var c Counts
	if !BillingEnabled() {
		return c, nil
	}
	day := Today(today)
	trial, err := r.runTrial(ctx, day)
	c.TrialStarted, c.TrialReminded, c.TrialActive, c.TrialPaused = trial.started, trial.reminded, trial.active, trial.paused
	if err != nil {
		return c, fmt.Errorf("billing trial: %w", err)
	}
	accounts, err := r.billedAccounts(ctx)
	if err != nil {
		return c, err
	}
	for _, acc := range accounts {
		if err := r.runAccount(ctx, acc, day, &c); err != nil {
			slog.Error("billing run failed for one account", "owner_user_id", acc.Owner, "error", err)
			if aerr := audit(ctx, r.Pool, "system", "billing_run_failed", "", &acc.Owner); aerr != nil {
				return c, aerr
			}
			c.Errors++
		}
	}
	d, err := r.dunning(ctx, day)
	c.DunningOverdue, c.DunningReminded, c.DunningPaused = d.overdue, d.reminded, d.paused
	if err != nil {
		return c, fmt.Errorf("billing dunning: %w", err)
	}
	return c, nil
}

// runAccount is the body of Python's account loop.
func (r *Runner) runAccount(ctx context.Context, acc jobAccount, day time.Time, c *Counts) error {
	rolled, err := r.roll(ctx, acc, day)
	if err != nil {
		return err
	}
	if rolled != "" {
		c.Rolled++
		fresh, err := loadAccount(ctx, r.Pool, acc.Owner)
		if err != nil {
			return err
		}
		if fresh == nil {
			return errors.New("billing account vanished")
		}
		acc = *fresh
		if !billedStatus(acc.Status) {
			return nil
		}
	}
	invoiced, err := r.invoicePeriod(ctx, acc, day)
	if err != nil {
		return err
	}
	if invoiced {
		c.Invoiced++
	}
	fresh, err := loadAccount(ctx, r.Pool, acc.Owner)
	if err != nil {
		return err
	}
	if fresh == nil {
		return errors.New("billing account vanished")
	}
	when, err := r.followApartments(ctx, *fresh, day)
	if err != nil {
		return err
	}
	if when != "" {
		c.Apartments++
	}
	return nil
}

func billedStatus(s string) bool {
	return s == "active" || s == "overdue" || s == "canceling"
}

// roll starts the next period once the current one has ended: "rolled",
// "paused" or "" (nothing to do).
func (r *Runner) roll(ctx context.Context, acc jobAccount, today time.Time) (string, error) {
	if acc.PeriodEnd == "" {
		return "", nil
	}
	end, err := parseDate(acc.PeriodEnd)
	if err != nil {
		return "", err
	}
	if !today.After(end) {
		return "", nil
	}
	if acc.Status == "canceling" {
		if _, err := setStatus(ctx, r.Pool, acc.Owner, "paused", "system"); err != nil {
			return "", err
		}
		return "paused", nil
	}
	start := end.AddDate(0, 0, 1)
	pending, err := parsePending(acc.PendingJSON)
	if err != nil {
		return "", err
	}
	plan, err := pending.text("plan", acc.Plan)
	if err != nil {
		return "", err
	}
	interval, err := pending.text("billing_interval", acc.Interval)
	if err != nil {
		return "", err
	}
	ttlock, err := pending.flag("addon_ttlock", acc.AddonTTLock)
	if err != nil {
		return "", err
	}
	whitelabel, err := pending.flag("addon_whitelabel", acc.AddonWhitelabel)
	if err != nil {
		return "", err
	}
	count, err := apartments(ctx, r.Pool, acc.Owner)
	if err != nil {
		return "", err
	}
	intervalText := ""
	if interval != nil {
		intervalText = *interval
	}
	if _, err := r.Pool.Exec(ctx,
		`UPDATE billing_account SET plan = $1, billing_interval = $2, addon_ttlock = $3, addon_whitelabel = $4,
		   apartments_billed = $5, period_start = $6, period_end = $7, pending_change_json = NULL, updated_at = $8
		 WHERE owner_user_id = $9`,
		plan, interval, ttlock, whitelabel, count, start.Format(isoDate),
		periodEnd(start, intervalText).Format(isoDate), ubyport.UTCNow(), acc.Owner); err != nil {
		return "", err
	}
	if err := audit(ctx, r.Pool, "system", "billing_period",
		start.Format(isoDate)+" "+pyOptional(plan)+" "+pyOptional(interval), &acc.Owner); err != nil {
		return "", err
	}
	return "rolled", nil
}

// invoicePeriod issues and mails the current period's invoice once; true when it
// was new.
func (r *Runner) invoicePeriod(ctx context.Context, acc jobAccount, today time.Time) (bool, error) {
	if acc.PeriodStart == "" {
		return false, nil
	}
	start, err := parseDate(acc.PeriodStart)
	if err != nil {
		return false, err
	}
	if start.After(today) {
		return false, nil
	}
	if acc.PeriodEnd == "" { // Python: None[:10] raises
		return false, errors.New("billing account has a period start but no period end")
	}
	if _, err := parseDate(acc.PeriodEnd); err != nil {
		return false, err
	}
	from, to := day10(acc.PeriodStart), day10(acc.PeriodEnd)
	var existing int64
	err = r.Pool.QueryRow(ctx,
		`SELECT id FROM platform_invoice WHERE owner_user_id = $1 AND period_from = $2 AND period_to = $3
		 AND kind = 'invoice' AND voided = 0`, acc.Owner, from, to).Scan(&existing)
	if err == nil {
		return false, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return false, err
	}
	inv := r.invoicer()
	id, err := inv.IssueForPeriod(ctx, acc.Owner, from, to, today)
	if err != nil {
		return false, err
	}
	r.send(ctx, inv, id)
	return true, nil
}

// send queues an invoice mail. Python's mail.enqueue logs a failure and goes on, so
// the account is still counted as invoiced.
func (r *Runner) send(ctx context.Context, inv *Invoicer, invoiceID int64) {
	if err := inv.Send(ctx, invoiceID); err != nil {
		slog.Error("billing invoice mail not queued", "invoice_id", invoiceID, "error", err)
	}
}
