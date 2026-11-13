package stayfeemail

// Port of the daily stay_fee_mail job (brief 1242): App/app/stay_fee_auto.py
// due_month, run and _run_apartment, the two queue_stay_fee_* functions of
// App/app/mail_notify.py and stay_fee.reconcile_all_no_pay_way, run in the
// order of scheduler._job_stay_fee_mail. The PDF comes from Deps.Renderer;
// with none the job refuses to start (ErrNoRenderer) before it reads or
// writes anything, so the kind can be switched on before brief 1243 without
// sealing or mailing.

import (
	"context"
	"errors"
	"log/slog"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// ErrNoRenderer is the error of a job built without a PDF renderer.
var ErrNoRenderer = errors.New("stay_fee_mail: no PDF renderer configured (brief 1243); nothing sealed or mailed")

// Deps are what the job reads besides the database. Now nil is time.Now;
// Keys nil loads the data keys from Getenv when the job runs.
type Deps struct {
	Getenv   func(string) string
	Now      func() time.Time
	Renderer stayfee.PDFRenderer
	Keys     *secure.MultiFernet
}

// Counts is run()'s counts dict.
type Counts struct {
	Confirmed int `json:"confirmed"`
	Reports   int `json:"reports"`
	Blocked   int `json:"blocked"`
}

// demo.py names: the seeded demo apartments and legal entities.
const (
	demoApartment  = "Vinohrady Studio (demo)"
	demoLoft       = "Karlín Loft (demo)"
	demoEntity     = "Josef Novák (demo)"
	demoController = "Demo Controller s.r.o."
)

// hostMailLanguage is mail_notify.HOST_MAIL_LANGUAGE.
const hostMailLanguage = "en"

// DueMonth is stay_fee_auto.due_month: the first month of the period that
// ended most recently, when today is from the 2nd to the 15th day after its
// end; ok false otherwise.
func DueMonth(cadence string, today time.Time) (time.Time, bool) {
	var month time.Time
	if cadence == "quarterly" {
		thisQuarter := stayfee.Day(today.Year(), time.Month((int(today.Month())-1)/3*3+1), 1)
		month = stayfee.ShiftMonth(thisQuarter, -3)
	} else {
		month = stayfee.PreviousMonth(today)
	}
	_, last := stayfee.PeriodBounds(cadence, month)
	if !today.Before(last.AddDate(0, 0, 2)) && !today.After(last.AddDate(0, 0, 15)) {
		return month, true
	}
	return time.Time{}, false
}

// pragueToday is claim.prague_today for an instant.
func pragueToday(now time.Time) time.Time {
	l := deadlines.LocalNow(now)
	return stayfee.Day(l.Year(), l.Month(), l.Day())
}

// ubyportEnv is config.UBYPORT_ENV: lower case, "mock" when unset.
func ubyportEnv(getenv func(string) string) string {
	env := strings.ToLower(getenv("UBYHOST_UBYPORT_ENV"))
	if env == "" {
		return "mock"
	}
	return env
}

// isDemoApartment is demo.is_demo_apartment: the seeded names always; the
// legal entity's name only in the mock environment.
func isDemoApartment(ctx context.Context, q stayfee.Querier, getenv func(string) string, ap *stayfee.Apartment) (bool, error) {
	if ap.InternalName == demoApartment || ap.InternalName == demoLoft {
		return true, nil
	}
	if ubyportEnv(getenv) != "mock" || ap.LegalEntityID == 0 {
		return false, nil
	}
	rows, err := q.Query(ctx, `SELECT COALESCE(name, '') FROM legal_entity WHERE id = $1`, ap.LegalEntityID)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	if !rows.Next() {
		return false, rows.Err()
	}
	var name string
	if err := rows.Scan(&name); err != nil {
		return false, err
	}
	return name == demoEntity || name == demoController, nil
}

type runner struct {
	pool          *pgxpool.Pool
	deps          Deps
	save          stayfee.SaveDeps
	today         time.Time
	cutoff        string
	counts        Counts
	appBase       string
	publicBase    string
	mailOn        bool
	scheduleToday time.Time
}

// Run is stay_fee_auto.run: for every host who is not being deleted and has
// not opted out, and each of their apartments that is not archived, seal the
// period that is due, mail a blocked period, and mail the report of each live
// filing created in the last 3 days. An error in one apartment is logged and
// the next apartment runs, as in Python.
func Run(ctx context.Context, pool *pgxpool.Pool, deps Deps) (Counts, error) {
	if deps.Renderer == nil {
		return Counts{}, ErrNoRenderer
	}
	if deps.Now == nil {
		deps.Now = time.Now
	}
	keys := deps.Keys
	if keys == nil {
		var err error
		if keys, err = secure.LoadDataKeys(deps.Getenv); err != nil {
			return Counts{}, err
		}
	}
	now := deps.Now()
	r := &runner{pool: pool, deps: deps, today: pragueToday(now),
		cutoff:     stayfee.UTCStamp(now.Add(-72 * time.Hour)),
		appBase:    appBase(deps.Getenv),
		publicBase: publicBase(deps.Getenv),
		mailOn:     mailEnabled(deps.Getenv),
	}
	u := now.UTC()
	r.scheduleToday = stayfee.Day(u.Year(), u.Month(), u.Day())
	r.save = stayfee.SaveDeps{Dec: stayfee.FernetDecrypter(keys), Enc: stayfee.FernetEncrypter(keys),
		Renderer: deps.Renderer, Now: deps.Now, ScheduleToday: r.scheduleToday}
	hosts, err := queryIDs(ctx, pool, `SELECT id FROM user_account WHERE role = 'host' AND deletion_due_at IS NULL
		AND COALESCE(stay_fee_emails_opt_out, 0) = 0 ORDER BY id`)
	if err != nil {
		return Counts{}, err
	}
	for _, host := range hosts {
		aps, err := loadApartments(ctx, pool, host)
		if err != nil {
			return r.counts, err
		}
		for _, ap := range aps {
			if err := r.apartment(ctx, ap, host); err != nil {
				slog.Error("stay-fee mail failed for apartment", "apartment_id", ap.ID, "error", err)
			}
		}
	}
	return r.counts, nil
}

func queryIDs(ctx context.Context, q stayfee.Querier, sql string, args ...any) ([]int64, error) {
	rows, err := q.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	ids, err := pgx.CollectRows(rows, pgx.RowTo[int64])
	return ids, err
}

func loadApartments(ctx context.Context, q stayfee.Querier, owner int64) ([]*stayfee.Apartment, error) {
	rows, err := q.Query(ctx, stayfee.ApartmentSelect+` WHERE owner_user_id = $1 AND archived_at IS NULL ORDER BY id`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*stayfee.Apartment
	for rows.Next() {
		ap, err := stayfee.ScanApartment(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, ap)
	}
	return out, rows.Err()
}

// apartment is _run_apartment.
func (r *runner) apartment(ctx context.Context, ap *stayfee.Apartment, owner int64) error {
	if !stayfee.IsActive(ap) {
		return nil
	}
	demo, err := isDemoApartment(ctx, r.pool, r.deps.Getenv, ap)
	if err != nil || demo {
		return err
	}
	cadence := stayfee.CadenceOf(ap)
	if month, ok := DueMonth(cadence, r.today); ok {
		latest, err := stayfee.Latest(ctx, r.pool, ap.ID, stayfee.PeriodKey(cadence, month))
		if err != nil {
			return err
		}
		if latest == nil {
			id, err := stayfee.Confirm(ctx, r.pool, r.save, ap, month, r.today, stayfee.ConfirmOpts{})
			if err != nil {
				return err
			}
			if id != 0 {
				r.counts.Confirmed++
			} else {
				checked, err := stayfee.Check(ctx, r.pool, r.save.Dec, ap, month, r.today,
					stayfee.Opts{Cadence: cadence, ScheduleToday: r.scheduleToday})
				if err != nil {
					return err
				}
				if len(checked.Issues) > 0 {
					queued, err := r.queueBlocked(ctx, ap, owner, checked.Group, checked.Issues)
					if err != nil {
						return err
					}
					if queued != 0 {
						r.counts.Blocked++
					}
				}
			}
		}
	}
	// Live filings saved or sealed in the last 3 days. The mail key includes
	// the version, so a repeated run sends nothing twice and a correction
	// sends again.
	rows, err := stayfee.RecentLive(ctx, r.pool, ap.ID, r.cutoff)
	if err != nil {
		return err
	}
	for i := range rows {
		queued, err := r.queueReport(ctx, ap, owner, &rows[i])
		if err != nil {
			return err
		}
		if queued != 0 {
			r.counts.Reports++
		}
	}
	return nil
}

// Handler is the stay_fee_mail job (scheduler._job_stay_fee_mail): Run, then
// the no-pay-way sweep, whose failure is logged and does not fail the job.
// It returns confirmed + reports + blocked. Without a renderer it returns
// ErrNoRenderer before touching the pool, so a nil pool is safe in tests.
func Handler(pool *pgxpool.Pool, deps Deps) func(ctx context.Context) (int, error) {
	return func(ctx context.Context) (int, error) {
		if deps.Renderer == nil {
			return 0, ErrNoRenderer
		}
		counts, err := Run(ctx, pool, deps)
		if err != nil {
			return 0, err
		}
		if _, err := ReconcileAllNoPayWay(ctx, pool, deps.Getenv); err != nil {
			slog.Error("stay-fee no-pay-way sweep failed", "error", err)
		}
		slog.Info("stay fee mail", "confirmed", counts.Confirmed, "reports", counts.Reports, "blocked", counts.Blocked)
		return counts.Confirmed + counts.Reports + counts.Blocked, nil
	}
}
