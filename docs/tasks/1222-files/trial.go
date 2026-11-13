package billingjob

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const trialDays = 30

type trialCounts struct{ started, reminded, active, paused int }

// runTrial is billing_trial.run: start due trials, send the reminders, end
// finished trials. day is the date billing_jobs.run passes down.
func (r *Runner) runTrial(ctx context.Context, day time.Time) (trialCounts, error) {
	var c trialCounts
	if !BillingEnabled() {
		return c, nil
	}
	pendingOwners, err := r.ownerIDs(ctx, `SELECT owner_user_id FROM billing_account WHERE status = 'trial_pending' ORDER BY owner_user_id`)
	if err != nil {
		return c, err
	}
	for _, owner := range pendingOwners {
		started, err := r.startTrial(ctx, owner, day)
		if err != nil {
			return c, err
		}
		if started {
			c.started++
		}
	}
	rows, err := r.Pool.Query(ctx,
		`SELECT owner_user_id, COALESCE(trial_ends_at, ''), COALESCE(plan, '') FROM billing_account
		 WHERE status = 'trialing' ORDER BY owner_user_id`)
	if err != nil {
		return c, err
	}
	type trialing struct {
		owner      int64
		ends, plan string
	}
	var list []trialing
	for rows.Next() {
		var t trialing
		if err := rows.Scan(&t.owner, &t.ends, &t.plan); err != nil {
			rows.Close()
			return c, err
		}
		list = append(list, t)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return c, err
	}
	for _, t := range list {
		ends, err := parseDate(t.ends)
		if err != nil {
			return c, err
		}
		left := int(ends.Sub(day).Hours() / 24)
		switch {
		case left < 0:
			state, err := r.finishTrial(ctx, t.owner)
			if err != nil {
				return c, err
			}
			if state == "active" {
				c.active++
			} else {
				c.paused++
			}
		case (left == 7 || left == 3 || left == 0) && t.plan == "":
			ok, err := r.billingTrialMail(ctx, t.owner, left, t.ends[:10])
			if err != nil {
				return c, err
			}
			if ok {
				c.reminded++
			}
		}
	}
	return c, nil
}

func (r *Runner) ownerIDs(ctx context.Context, query string) ([]int64, error) {
	rows, err := r.Pool.Query(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		out = append(out, id)
	}
	return out, rows.Err()
}

// startTrial is billing_trial.start: recover a pending trial from its verified
// date. One conditional write, so a competing job cannot reset a started trial.
func (r *Runner) startTrial(ctx context.Context, owner int64, day time.Time) (bool, error) {
	var stamp *string
	err := r.Pool.QueryRow(ctx,
		`SELECT email_verified_at FROM user_account WHERE id = $1 AND active = 1`, owner).Scan(&stamp)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if stamp == nil || *stamp == "" {
		return false, nil
	}
	first, last, err := activationDates(*stamp)
	if err != nil {
		return false, err
	}
	if first.After(day) {
		return false, nil
	}
	tag, err := r.Pool.Exec(ctx,
		`UPDATE billing_account SET status = 'trialing', trial_started_at = $1, trial_ends_at = $2, updated_at = $3
		 WHERE owner_user_id = $4 AND status = 'trial_pending' AND trial_started_at IS NULL AND trial_ends_at IS NULL`,
		first.Format(isoDate), last.Format(isoDate), ubyport.UTCNow(), owner)
	if err != nil {
		return false, err
	}
	if tag.RowsAffected() == 0 {
		return false, nil
	}
	if err := audit(ctx, r.Pool, "system", "billing_status", "trial_pending->trialing", &owner); err != nil {
		return true, err
	}
	return true, nil
}

// activationDates is billing_trial.activation_dates: the local date of the stamp,
// and the local date containing the stamp plus thirty days in UTC.
func activationDates(stamp string) (first, last time.Time, err error) {
	moment, err := parseStamp(stamp)
	if err != nil {
		return first, last, err
	}
	zone, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		return first, last, err
	}
	return Today(moment.In(zone)), Today(moment.UTC().AddDate(0, 0, trialDays).In(zone)), nil
}

// parseStamp is datetime.fromisoformat; a stamp without an offset is UTC.
func parseStamp(stamp string) (time.Time, error) {
	text := strings.Replace(strings.TrimSpace(stamp), " ", "T", 1)
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02T15:04:05.999999999", isoDate} {
		if t, err := time.Parse(layout, text); err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("invalid isoformat string %q", stamp)
}

// finishTrial is billing_trial.finish: active on the ordered plan, else paused.
func (r *Runner) finishTrial(ctx context.Context, owner int64) (string, error) {
	acc, err := loadAccount(ctx, r.Pool, owner)
	if err != nil {
		return "", err
	}
	if acc == nil {
		return "", errors.New("billing account vanished")
	}
	ends, err := parseDate(acc.TrialEndsAt)
	if err != nil {
		return "", err
	}
	if acc.Plan != nil && *acc.Plan != "" && acc.Interval != nil && *acc.Interval != "" {
		start := ends.AddDate(0, 0, 1)
		if _, err := r.Pool.Exec(ctx,
			`UPDATE billing_account SET period_start = $1, period_end = $2, updated_at = $3 WHERE owner_user_id = $4`,
			start.Format(isoDate), periodEnd(start, *acc.Interval).Format(isoDate), ubyport.UTCNow(), owner); err != nil {
			return "", err
		}
		_, err := setStatus(ctx, r.Pool, owner, "active", "system")
		return "active", err
	}
	_, err = setStatus(ctx, r.Pool, owner, "paused", "system")
	return "paused", err
}

// billingTrialMail is mail_notify.billing_trial: one reminder per stage, key
// billing-trial-<owner>-<end>-<days>; true when a mail row exists or was queued.
func (r *Runner) billingTrialMail(ctx context.Context, owner int64, daysLeft int, ends string) (bool, error) {
	content := mail.BuildBillingTrial(AppBaseURL(), PublicBaseURL(), OperatorEmail(), daysLeft, fmtDate(ends))
	return r.queueServiceMail(ctx, "billing_trial", fmt.Sprintf("billing-trial-%d-%s-%d", owner, ends, daysLeft), owner, content)
}

// queueServiceMail is mail.enqueue for the trial and overdue mails: to the billing
// recipient, a copy to the operator, payload {text, html, lang, reply_to}. Python
// returns None (not counted) when mail is off or there is no recipient, and logs and
// carries on when the insert fails; so does this.
func (r *Runner) queueServiceMail(ctx context.Context, kind, key string, owner int64, content mail.Content) (bool, error) {
	if !MailEnabled() {
		return false, nil
	}
	to, err := r.invoicer().Recipient(ctx, owner)
	if err != nil {
		return false, err
	}
	to = ubyport.NormaliseEmail(to)
	if to == "" {
		return false, nil
	}
	payload := fmt.Sprintf(`{"text": %s, "html": %s, "lang": "cs", "reply_to": %s}`,
		ubyport.PyString(content.Text), ubyport.PyString(content.HTML), ubyport.PyString(OperatorEmail()))
	id, err := ubyport.EnqueueMail(ctx, r.Pool, ubyport.OutboxMail{
		Kind: kind, Key: key, OwnerUserID: &owner, To: to,
		CC: ubyport.NormaliseEmail(OperatorEmail()), Subject: content.Subject, Payload: payload,
	})
	if err != nil {
		slog.Error("billing mail not queued", "kind", kind, "owner_user_id", owner, "error", err)
		return false, nil
	}
	return id > 0, nil
}
