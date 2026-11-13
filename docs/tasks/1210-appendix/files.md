# 1210 appendix: file contents

Read by the extractor of [the brief](../1210-go-retention-job.md); do not retype. Deleted in the report step.

<!-- file: go/internal/retention/retention.go -->
````go
// Package retention is App/app/retention.py run() in Go: everything the
// retention schedule says may no longer be held. It is a dry run unless both
// UBYHOST_RETENTION_AUTOPURGE (the Python switch) and
// UBYHOST_GO_RETENTION_APPLY are on. In a dry run it counts exactly the rows
// it would delete or null, audits the counts and changes nothing else.
//
// Never logs personal data: counts and ids only.
package retention

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Windows of retention.py and the modules it calls.
const (
	claimEmailGraceDays    = 30  // retention.CLAIM_EMAIL_GRACE_DAYS
	submitterIPGraceDays   = 90  // retention.SUBMITTER_IP_GRACE_DAYS
	havelLimitDays         = 32  // retention.HAVEL_LIMIT_DAYS
	havelGapDays           = 90  // retention.HAVEL_GAP_DAYS
	workspaceReminderDays  = 7   // retention.WORKSPACE_REMINDER_DAYS
	housebookRetentionYear = 6   // housebook.RETENTION_YEARS
	cleaningDays           = 30  // cleaning.purge
	pushOutboxKeepDays     = 30  // push.OUTBOX_KEEP_DAYS
	pushUnseenDays         = 180 // push.UNSEEN_DAYS
	guideRawDays           = 7   // guest_guide_import.RAW_DAYS
	guideRowDays           = 60  // guest_guide_import.ROW_DAYS
	leonRetentionDays      = 30  // leon.RETENTION_DAYS
)

// errApplyNotPorted fails a run with both apply switches on: this build only counts.
var errApplyNotPorted = errors.New("retention: deleting is not ported to Go yet (brief 1211); nothing deleted")

// Config holds the switches and windows the Python job reads from config.py.
type Config struct {
	DryRun         bool
	AuditDays      int // UBYHOST_AUDIT_RETENTION_DAYS, default 1095
	AlertDays      int // UBYHOST_ALERT_RETENTION_DAYS, default 365
	RateLimitHours int // UBYHOST_RATE_LIMIT_RETENTION_HOURS, default 24
	NoticeDays     int // UBYHOST_RETENTION_NOTICE_DAYS, default 30
	DataDir        string
}

// ConfigFromEnv reads the same variables as config.py. DryRun is false only
// when UBYHOST_RETENTION_AUTOPURGE and UBYHOST_GO_RETENTION_APPLY are both
// "1", "true" or "yes".
func ConfigFromEnv(lookup func(string) (string, bool)) (Config, error) {
	on := func(name string) bool {
		v, _ := lookup(name)
		return v == "1" || v == "true" || v == "yes"
	}
	num := func(name string, def int) (int, error) {
		v, ok := lookup(name)
		if !ok {
			return def, nil
		}
		n, err := strconv.Atoi(strings.TrimSpace(v))
		if err != nil {
			return 0, fmt.Errorf("retention: %s is not a whole number", name)
		}
		return n, nil
	}
	cfg := Config{DryRun: !(on("UBYHOST_RETENTION_AUTOPURGE") && on("UBYHOST_GO_RETENTION_APPLY"))}
	cfg.DataDir, _ = lookup("UBYHOST_DATA_DIR")
	var err error
	if cfg.AuditDays, err = num("UBYHOST_AUDIT_RETENTION_DAYS", 1095); err != nil {
		return cfg, err
	}
	if cfg.AlertDays, err = num("UBYHOST_ALERT_RETENTION_DAYS", 365); err != nil {
		return cfg, err
	}
	if cfg.RateLimitHours, err = num("UBYHOST_RATE_LIMIT_RETENTION_HOURS", 24); err != nil {
		return cfg, err
	}
	if cfg.NoticeDays, err = num("UBYHOST_RETENTION_NOTICE_DAYS", 30); err != nil {
		return cfg, err
	}
	return cfg, nil
}

// Count is one step's result, in the order the steps ran.
type Count struct {
	Name  string
	Count int
}

// Summary is retention.run()'s return value.
type Summary struct {
	DryRun      bool
	OwnerUserID *int64
	Counts      []Count
}

// Total is the sum of all counts.
func (s Summary) Total() int {
	n := 0
	for _, c := range s.Counts {
		n += c.Count
	}
	return n
}

type runner struct {
	pool  *pgxpool.Pool
	cfg   Config
	today time.Time // the calendar date (date.today()), at 00:00 UTC
	now   time.Time // the instant (datetime.now(timezone.utc)), UTC
	owner *int64
	dry   bool
}

type step struct {
	name string
	fn   func(ctx context.Context, r *runner) (int, error)
}

// steps is retention.STEPS, in the same order.
var steps = []step{
	{"guests", stepGuests},
	{"invoices", stepInvoices},
	{"platform_invoices", stepPlatformInvoices},
	{"claim_emails", stepClaimEmails},
	{"reservation_contacts", stepReservationContacts},
	{"submitter_ips", stepSubmitterIPs},
	{"empty_reservations", stepEmptyReservations},
	{"stay_fee_records", stepStayFeeRecords},
	{"audit_rows", stepAuditRows},
	{"alerts", stepAlerts},
	{"rate_limit_events", stepRateLimitEvents},
	{"havel_gap", stepHavelGap},
	{"login_tokens", stepLoginTokens},
	{"webauthn_challenges", stepWebauthnChallenges},
	{"door_code_pins", stepDoorCodePins},
	{"cleaning", stepCleaning},
	{"push", stepPush},
	{"guide_imports", stepGuideImports},
	{"guest_chats", stepGuestChats},
	{"legal_acceptance", stepLegalAcceptance},
	{"workspaces", stepWorkspaces},
}

// Run is retention.run(today, owner_user_id=owner) with dry_run from cfg.
// today is the server-local calendar date (only its year, month and day are
// used); now is the current instant. Each step runs even when an earlier one
// failed; the first step failure is returned at the end, after the summary
// audit row, the retention_last_run setting and (global run only) the
// retention_due notices were written. A failure writing an audit row or the
// setting returns at once, as the Python exception would.
func Run(ctx context.Context, pool *pgxpool.Pool, cfg Config, today, now time.Time, owner *int64) (Summary, error) {
	r := &runner{
		pool:  pool,
		cfg:   cfg,
		today: time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC),
		now:   now.UTC(),
		owner: owner,
		dry:   cfg.DryRun,
	}
	sum := Summary{DryRun: r.dry, OwnerUserID: owner, Counts: []Count{}}
	if !r.dry {
		// Brief 1211 adds the deleting half; until then Go only counts.
		return sum, errApplyNotPorted
	}
	var first error
	cut := r.cutoffs()
	for _, s := range steps {
		n, err := s.fn(ctx, r)
		if err != nil {
			if first == nil {
				first = fmt.Errorf("retention step %s: %w", s.name, err)
			}
			continue
		}
		sum.Counts = append(sum.Counts, Count{s.name, n})
		if err := r.auditRetention(ctx, s.name, n, cut[s.name]); err != nil {
			return sum, err
		}
	}
	if err := r.audit(ctx, "retention_run", summaryJSON(sum, ""), "system"); err != nil {
		return sum, err
	}
	if err := setSetting(ctx, pool, "retention_last_run", summaryJSON(sum, pyISO(r.now))); err != nil {
		return sum, err
	}
	if owner == nil {
		if err := r.raiseDueNotices(ctx); err != nil && first == nil {
			first = fmt.Errorf("retention due notices: %w", err)
		}
	}
	return sum, first
}

// --- dates and times, formatted as the Python code formats them ------------

// isoDate is date.isoformat().
func isoDate(t time.Time) string { return t.Format("2006-01-02") }

// pyISO is an aware UTC datetime .replace(microsecond=0).isoformat(),
// as db.utcnow(), retention._days_ago_iso, login_link._iso and push._stamp.
func pyISO(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// pyISOMicro is an aware UTC datetime .isoformat() with its microseconds
// (passkeys._iso): no fraction when they are zero.
func pyISOMicro(t time.Time) string {
	t = t.UTC()
	us := t.Nanosecond() / 1000
	if us == 0 {
		return pyISO(t)
	}
	return t.Format("2006-01-02T15:04:05") + fmt.Sprintf(".%06d", us) + "+00:00"
}

func (r *runner) daysAgo(days int) time.Time { return r.today.AddDate(0, 0, -days) }

// daysAgoISO is retention._days_ago_iso.
func (r *runner) daysAgoISO(days int) string {
	return pyISO(r.now.Add(-time.Duration(days) * 24 * time.Hour))
}

// housebookCutoff is housebook.retention_cutoff.
func housebookCutoff(today time.Time) time.Time {
	last := today.Year() - housebookRetentionYear - 2
	if !today.Before(time.Date(today.Year(), time.January, 31, 0, 0, 0, 0, time.UTC)) {
		last = today.Year() - housebookRetentionYear - 1
	}
	return time.Date(last+1, time.January, 1, 0, 0, 0, 0, time.UTC)
}

// invoiceCutoff is invoices.retention_cutoff.
func invoiceCutoff(today time.Time) time.Time {
	return time.Date(today.Year()-10, time.January, 1, 0, 0, 0, 0, time.UTC)
}

// cutoffs is retention._cutoffs.
func (r *runner) cutoffs() map[string]string {
	guests := isoDate(housebookCutoff(r.today))
	contact := isoDate(r.daysAgo(claimEmailGraceDays))
	inv := isoDate(invoiceCutoff(r.today))
	return map[string]string{
		"guests":               "stay ended before " + guests,
		"invoices":             "issued before " + inv,
		"platform_invoices":    "issued before " + inv,
		"claim_emails":         "stay ended before " + contact,
		"reservation_contacts": "stay ended before " + contact,
		"submitter_ips":        "stay ended before " + isoDate(r.daysAgo(submitterIPGraceDays)),
		"empty_reservations":   "stay ended before " + guests,
		"stay_fee_records":     "period before " + guests,
		"audit_rows":           "logged before " + r.daysAgoISO(r.cfg.AuditDays),
		"alerts":               "resolved before " + r.daysAgoISO(r.cfg.AlertDays),
		"rate_limit_events":    fmt.Sprintf("older than %d hours, Havel limits %d days", r.cfg.RateLimitHours, havelLimitDays),
		"havel_gap":            "created before " + isoDate(r.daysAgo(havelGapDays)),
		"login_tokens":         "expired more than 1 day ago",
		"webauthn_challenges":  "expired more than 1 day ago",
		"door_code_pins":       "valid_to more than 1 day ago",
		"cleaning":             "event or link expiry before " + isoDate(r.daysAgo(cleaningDays)),
		"push":                 "alert queued over 30 days ago, or device unseen for 180 days",
		"guide_imports": "listing text fetched before " + isoDate(r.daysAgo(guideRawDays)) +
			", failed request rows before " + isoDate(r.daysAgo(guideRowDays)),
		"guest_chats":      "stay ended, or QR chat last used, before " + isoDate(r.daysAgo(leonRetentionDays)),
		"legal_acceptance": "inactive account, last login before " + r.daysAgoISO(r.cfg.AuditDays),
		"workspaces":       "deletion due on or before " + pyISO(r.now),
	}
}

// --- JSON as Python's json.dumps writes it --------------------------------

// pyQuote is json.dumps(s) with ensure_ascii=True.
func pyQuote(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, c := range s {
		switch {
		case c == '"':
			b.WriteString(`\"`)
		case c == '\\':
			b.WriteString(`\\`)
		case c == '\n':
			b.WriteString(`\n`)
		case c == '\r':
			b.WriteString(`\r`)
		case c == '\t':
			b.WriteString(`\t`)
		case c == '\b':
			b.WriteString(`\b`)
		case c == '\f':
			b.WriteString(`\f`)
		case c < 0x20 || (c >= 0x7f && c <= 0xffff):
			fmt.Fprintf(&b, `\u%04x`, c)
		case c > 0xffff:
			c -= 0x10000
			fmt.Fprintf(&b, `\u%04x\u%04x`, 0xd800+(c>>10), 0xdc00+(c&0x3ff))
		default:
			b.WriteRune(c)
		}
	}
	b.WriteByte('"')
	return b.String()
}

func pyBool(v bool) string {
	if v {
		return "true"
	}
	return "false"
}

func pyIntOrNull(v *int64) string {
	if v == nil {
		return "null"
	}
	return strconv.FormatInt(*v, 10)
}

// summaryJSON is json.dumps(summary) (at == "") or
// json.dumps({**summary, "at": at}): keys in insertion order.
func summaryJSON(s Summary, at string) string {
	var b strings.Builder
	b.WriteString(`{"dry_run": ` + pyBool(s.DryRun) + `, "owner_user_id": ` + pyIntOrNull(s.OwnerUserID) + `, "counts": {`)
	for i, c := range s.Counts {
		if i > 0 {
			b.WriteString(", ")
		}
		b.WriteString(pyQuote(c.Name) + ": " + strconv.Itoa(c.Count))
	}
	b.WriteString("}")
	if at != "" {
		b.WriteString(`, "at": ` + pyQuote(at))
	}
	b.WriteString("}")
	return b.String()
}

// --- audit, settings, alerts ------------------------------------------------

// audit is db.audit(action, detail, actor) in the job's context: no current
// owner and no signed-in actor, so owner_user_id, actor_user_id and
// impersonator_user_id are NULL.
func (r *runner) audit(ctx context.Context, action, detail, actor string) error {
	_, err := r.pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		 VALUES ($1, $2, $3, $4, NULL, NULL, NULL)`,
		pyISO(r.now), actor, action, detail)
	return err
}

// auditRetention is db.audit_retention: json.dumps(..., sort_keys=True).
func (r *runner) auditRetention(ctx context.Context, class string, count int, cutoff string) error {
	detail := `{"class": ` + pyQuote(class) + `, "count": ` + strconv.Itoa(count) +
		`, "cutoff": ` + pyQuote(cutoff) + `, "dry_run": ` + pyBool(r.dry) +
		`, "owner_user_id": ` + pyIntOrNull(r.owner) + `}`
	_, err := r.pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail) VALUES ($1, 'system', 'retention_delete', $2)`,
		pyISO(r.now), detail)
	return err
}

// setSetting is db.set_setting.
func setSetting(ctx context.Context, pool *pgxpool.Pool, key, value string) error {
	_, err := pool.Exec(ctx,
		`INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = excluded.value`,
		key, value)
	return err
}

// raiseDueNotices is retention._raise_due_notices with housebook.due_guest_counts.
func (r *runner) raiseDueNotices(ctx context.Context) error {
	days := r.cfg.NoticeDays
	month := r.today.Format("2006-01")
	start := isoDate(housebookCutoff(r.today))
	end := isoDate(housebookCutoff(r.today.AddDate(0, 0, days)))
	rows, err := r.pool.Query(ctx,
		`SELECT a.owner_user_id, COUNT(*) FROM guest g
		 JOIN reservation r ON r.id = g.reservation_id
		 JOIN apartment a ON a.id = r.apartment_id
		 WHERE COALESCE(ubyhost_sqlite_date(g.stay_to), ubyhost_sqlite_date(r.date_to)) >= $1
		 AND COALESCE(ubyhost_sqlite_date(g.stay_to), ubyhost_sqlite_date(r.date_to)) < $2
		 GROUP BY a.owner_user_id ORDER BY a.owner_user_id`, start, end)
	if err != nil {
		return err
	}
	type due struct {
		owner *int64
		n     int
	}
	var list []due
	for rows.Next() {
		var d due
		if err := rows.Scan(&d.owner, &d.n); err != nil {
			rows.Close()
			return err
		}
		list = append(list, d)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, d := range list {
		ownerText := "None"
		if d.owner != nil {
			ownerText = strconv.FormatInt(*d.owner, 10)
		}
		message := fmt.Sprintf("%d guest record(s) reach the end of their retention period within %d days.", d.n, days)
		params := fmt.Sprintf(`{"count": %d, "days": %d}`, d.n, days)
		if err := r.raiseAlert(ctx, "warning", "retention_due", message,
			"Review the house book and export anything you still need: /housebook",
			"retention_due:"+ownerText+":"+month, d.owner, params); err != nil {
			return err
		}
	}
	return nil
}

// raiseAlert is alerts.raise_alert for an alert with an owner and a dedupe
// key but no apartment or reservation.
func (r *runner) raiseAlert(ctx context.Context, level, kind, message, detail, key string, owner *int64, params string) error {
	now := pyISO(r.now)
	var id int64
	err := r.pool.QueryRow(ctx, `SELECT id FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key).Scan(&id)
	if err == nil {
		_, err = r.pool.Exec(ctx,
			`UPDATE alert SET level = $1, message = $2, detail = $3, params = $4, created_at = $5 WHERE id = $6`,
			level, message, detail, params, now, id)
		return err
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	_, err = r.pool.Exec(ctx,
		`INSERT INTO alert (level, kind, apartment_id, reservation_id, owner_user_id, dedupe_key, message, detail, params, created_at)
		 VALUES ($1, $2, NULL, NULL, $3, $4, $5, $6, $7, $8)`,
		level, kind, owner, key, message, detail, params, now)
	if err != nil && isUniqueViolation(err) {
		// idx_alert_dedupe: another writer opened the same key first; refresh it.
		_, err = r.pool.Exec(ctx,
			`UPDATE alert SET level = $1, message = $2, detail = $3, params = $4, created_at = $5
			 WHERE dedupe_key = $6 AND resolved_at IS NULL`,
			level, message, detail, params, now, key)
	}
	return err
}
````

<!-- file: go/internal/retention/steps.go -->
````go
package retention

// The steps of retention.STEPS, counting half. Each returns the count the
// Python step returns in a dry run. Brief 1211 adds the deleting half. SQL
// mirrors the Python statements on PostgreSQL: db.sqlite_date_expr(x) is
// ubyhost_sqlite_date(x), and "(? IS NULL OR col = ?)" is
// "($n::bigint IS NULL OR col = $n)".

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

func isUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

func (r *runner) scalar(ctx context.Context, sql string, args ...any) (int, error) {
	var n int64
	if err := r.pool.QueryRow(ctx, sql, args...).Scan(&n); err != nil {
		return 0, err
	}
	return int(n), nil
}

func (r *runner) ids(ctx context.Context, sql string, args ...any) ([]int64, error) {
	rows, err := r.pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	return pgx.CollectRows(rows, pgx.RowTo[int64])
}

// --- guests: housebook.expired_guest_ids -------------------------------------

const expiredGuestsSQL = `SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE COALESCE(ubyhost_sqlite_date(g.stay_to), ubyhost_sqlite_date(r.date_to)) < $1
	AND ($2::bigint IS NULL OR a.owner_user_id = $2) ORDER BY g.id`

func stepGuests(ctx context.Context, r *runner) (int, error) {
	ids, err := r.ids(ctx, expiredGuestsSQL, isoDate(housebookCutoff(r.today)), r.owner)
	return len(ids), err
}

// --- invoices: invoices.expired_ids -------------------------------------------

func stepInvoices(ctx context.Context, r *runner) (int, error) {
	ids, err := r.ids(ctx, `SELECT id FROM invoice WHERE issue_date < $1
		AND ($2::bigint IS NULL OR owner_user_id = $2)
		AND NOT EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = invoice.id AND c.issue_date >= $1)
		ORDER BY CASE WHEN corrects_invoice_id IS NULL THEN 1 ELSE 0 END, id`, isoDate(invoiceCutoff(r.today)), r.owner)
	return len(ids), err
}

// --- platform_invoices: billing_invoices.expired_ids (global run only) --------

func stepPlatformInvoices(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	ids, err := r.ids(ctx, `SELECT id FROM platform_invoice WHERE issue_date < $1
		AND NOT EXISTS (SELECT 1 FROM platform_invoice c WHERE c.corrects_id = platform_invoice.id AND c.issue_date >= $1)
		ORDER BY CASE WHEN corrects_id IS NULL THEN 1 ELSE 0 END, id`, isoDate(invoiceCutoff(r.today)))
	return len(ids), err
}

// --- contact minimisation ----------------------------------------------------

func stepClaimEmails(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM reservation_claim WHERE email IS NOT NULL
		AND reservation_id IN (SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE ubyhost_sqlite_date(r.date_to) < $1 AND ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		isoDate(r.daysAgo(claimEmailGraceDays)), r.owner)
}

func stepReservationContacts(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM reservation WHERE (guest_email IS NOT NULL OR phone_last4 IS NOT NULL)
		AND ubyhost_sqlite_date(date_to) < $1
		AND apartment_id IN (SELECT id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		isoDate(r.daysAgo(claimEmailGraceDays)), r.owner)
}

func stepSubmitterIPs(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM guest WHERE filled_ip IS NOT NULL
		AND COALESCE(ubyhost_sqlite_date(stay_to), (SELECT ubyhost_sqlite_date(date_to) FROM reservation r2
			WHERE r2.id = guest.reservation_id)) < $1
		AND reservation_id IN (SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id
			WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		isoDate(r.daysAgo(submitterIPGraceDays)), r.owner)
}

func stepEmptyReservations(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM reservation WHERE ubyhost_sqlite_date(date_to) < $1
		AND NOT EXISTS (SELECT 1 FROM guest g WHERE g.reservation_id = reservation.id)
		AND apartment_id IN (SELECT id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		isoDate(housebookCutoff(r.today)), r.owner)
}

func stepStayFeeRecords(ctx context.Context, r *runner) (int, error) {
	year := fmt.Sprintf("%04d", housebookCutoff(r.today).Year())
	where := `substr(period_key, 1, 4) < $1
		AND apartment_id IN (SELECT id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`
	adjustments, err := r.scalar(ctx, `SELECT COUNT(*) FROM stay_fee_adjustment WHERE `+where, year, r.owner)
	if err != nil {
		return 0, err
	}
	filings, err := r.scalar(ctx, `SELECT COUNT(*) FROM stay_fee_filing WHERE `+where, year, r.owner)
	if err != nil {
		return 0, err
	}
	return adjustments + filings, nil
}

// --- logs and evidence -------------------------------------------------------

func stepAuditRows(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM audit WHERE at < $1
		AND action NOT IN ('legal_accepted', 'door_code_terms_accepted', 'leon_terms_accepted',
		'payments_terms_accepted') AND ($2::bigint IS NULL OR owner_user_id = $2)`,
		r.daysAgoISO(r.cfg.AuditDays), r.owner)
}

func stepAlerts(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM alert WHERE resolved_at IS NOT NULL AND resolved_at < $1
		AND ($2::bigint IS NULL OR owner_user_id = $2)`, r.daysAgoISO(r.cfg.AlertDays), r.owner)
}

func stepRateLimitEvents(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	epoch := float64(r.now.UnixNano()) / 1e9 // time.time()
	return r.scalar(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE at < $1
		AND (substr(scope, 1, 6) <> 'havel_' OR at < $2)`,
		epoch-float64(r.cfg.RateLimitHours*3600), epoch-float64(havelLimitDays*86400))
}

func stepHavelGap(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM havel_gap WHERE created_at < $1`, isoDate(r.daysAgo(havelGapDays)))
}

// stepLoginTokens is login_link.purge (global run only).
func stepLoginTokens(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM login_token WHERE expires_at < $1`, pyISO(r.now.Add(-24*time.Hour)))
}

// stepWebauthnChallenges is passkeys.purge (global run only). Its cutoff keeps
// the microseconds, as passkeys._iso does.
func stepWebauthnChallenges(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM webauthn_challenge WHERE expires_at < $1`,
		pyISOMicro(r.now.Add(-24*time.Hour)))
}

func stepDoorCodePins(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM door_code WHERE pin_enc IS NOT NULL
		AND valid_to IS NOT NULL AND valid_to < $1`, r.daysAgoISO(1))
}

// stepCleaning is cleaning.purge.
func stepCleaning(ctx context.Context, r *runner) (int, error) {
	cutoff := isoDate(r.daysAgo(cleaningDays))
	notes, err := r.scalar(ctx, `SELECT COUNT(*) FROM cleaning_event WHERE notes_enc IS NOT NULL
		AND scheduled_date < $1
		AND apartment_id IN (SELECT a.id FROM apartment a WHERE ($2::bigint IS NULL OR a.owner_user_id = $2))`,
		cutoff, r.owner)
	if err != nil {
		return 0, err
	}
	shares, err := r.scalar(ctx, `SELECT COUNT(*) FROM cleaning_share WHERE expires_at < $1
		AND ($2::bigint IS NULL OR owner_user_id = $2)`, cutoff, r.owner)
	if err != nil {
		return 0, err
	}
	return notes + shares, nil
}

// stepPush is push.purge (owner-scoped runs included).
func stepPush(ctx context.Context, r *runner) (int, error) {
	scope := ` AND ($2::bigint IS NULL OR user_account_id = $2)`
	alerts, err := r.scalar(ctx, `SELECT COUNT(*) FROM push_outbox WHERE created_at < $1`+scope,
		pyISO(r.now.AddDate(0, 0, -pushOutboxKeepDays)), r.owner)
	if err != nil {
		return 0, err
	}
	devices, err := r.ids(ctx, `SELECT id FROM push_subscription WHERE last_seen_at < $1`+scope+` ORDER BY id`,
		pyISO(r.now.AddDate(0, 0, -pushUnseenDays)), r.owner)
	if err != nil {
		return 0, err
	}
	return alerts + len(devices), nil
}

// stepGuideImports is guest_guide_import.purge (global run only).
func stepGuideImports(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	stale, err := r.scalar(ctx, `SELECT COUNT(*) FROM guide_import WHERE raw_json IS NOT NULL AND created_at < $1`,
		isoDate(r.daysAgo(guideRawDays)))
	if err != nil {
		return 0, err
	}
	old, err := r.scalar(ctx, `SELECT COUNT(*) FROM guide_import WHERE status = 'failed' AND created_at < $1`,
		isoDate(r.daysAgo(guideRowDays)))
	if err != nil {
		return 0, err
	}
	return stale + old, nil
}

// stepGuestChats is leon.purge.
func stepGuestChats(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM (SELECT c.id FROM guest_chat c JOIN apartment a ON a.id = c.apartment_id
		LEFT JOIN reservation r ON r.id = c.reservation_id
		WHERE ($1::bigint IS NULL OR a.owner_user_id = $1) AND ((c.door = 'stay' AND (r.id IS NULL OR r.date_to < $2))
		OR (c.door = 'qr' AND substr(c.last_message_at, 1, 10) < $2))) x`,
		r.owner, isoDate(r.daysAgo(leonRetentionDays)))
}

func stepLegalAcceptance(ctx context.Context, r *runner) (int, error) {
	return r.scalar(ctx, `SELECT COUNT(*) FROM legal_acceptance WHERE user_account_id IN (SELECT id FROM user_account
		WHERE active = 0 AND last_login_at IS NOT NULL AND last_login_at < $1)
		AND ($2::bigint IS NULL OR user_account_id = $2)`, r.daysAgoISO(r.cfg.AuditDays), r.owner)
}

// stepWorkspaces is retention._workspace_deletion_step in a dry run (global
// run only): workspaces whose deletion date has passed.
func stepWorkspaces(ctx context.Context, r *runner) (int, error) {
	if r.owner != nil {
		return 0, nil
	}
	return r.scalar(ctx, `SELECT COUNT(*) FROM user_account
		WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= $1`, pyISO(r.now))
}
````

<!-- file: go/internal/retention/retention_test.go -->
````go
package retention

import (
	"testing"
	"time"
)

func env(m map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v, ok := m[k]
		return v, ok
	}
}

func TestConfigFromEnvSwitches(t *testing.T) {
	for _, c := range []struct {
		vars map[string]string
		dry  bool
	}{
		{map[string]string{}, true},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "1"}, true},
		{map[string]string{"UBYHOST_GO_RETENTION_APPLY": "1"}, true},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "1", "UBYHOST_GO_RETENTION_APPLY": "0"}, true},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "TRUE", "UBYHOST_GO_RETENTION_APPLY": "1"}, true},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "1", "UBYHOST_GO_RETENTION_APPLY": "1"}, false},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "yes", "UBYHOST_GO_RETENTION_APPLY": "true"}, false},
	} {
		cfg, err := ConfigFromEnv(env(c.vars))
		if err != nil || cfg.DryRun != c.dry {
			t.Errorf("%v: DryRun %v (%v), want %v", c.vars, cfg.DryRun, err, c.dry)
		}
	}
	cfg, err := ConfigFromEnv(env(map[string]string{}))
	if err != nil || cfg.AuditDays != 1095 || cfg.AlertDays != 365 || cfg.RateLimitHours != 24 || cfg.NoticeDays != 30 {
		t.Fatalf("defaults %+v %v", cfg, err)
	}
	if _, err := ConfigFromEnv(env(map[string]string{"UBYHOST_AUDIT_RETENTION_DAYS": "x"})); err == nil {
		t.Fatal("a bad number must be an error")
	}
}

func TestStepsOrderMatchesPython(t *testing.T) {
	want := []string{"guests", "invoices", "platform_invoices", "claim_emails", "reservation_contacts",
		"submitter_ips", "empty_reservations", "stay_fee_records", "audit_rows", "alerts",
		"rate_limit_events", "havel_gap", "login_tokens", "webauthn_challenges", "door_code_pins",
		"cleaning", "push", "guide_imports", "guest_chats", "legal_acceptance", "workspaces"}
	if len(steps) != len(want) {
		t.Fatalf("%d steps, want %d", len(steps), len(want))
	}
	for i, s := range steps {
		if s.name != want[i] {
			t.Errorf("step %d is %s, want %s", i, s.name, want[i])
		}
	}
}

func TestFormats(t *testing.T) {
	at := time.Date(2026, 1, 20, 3, 0, 0, 250000999, time.UTC)
	if got := pyISO(at); got != "2026-01-20T03:00:00+00:00" {
		t.Errorf("pyISO %s", got)
	}
	if got := pyISOMicro(at); got != "2026-01-20T03:00:00.250000+00:00" {
		t.Errorf("pyISOMicro %s", got)
	}
	if got := pyISOMicro(at.Truncate(time.Second)); got != "2026-01-20T03:00:00+00:00" {
		t.Errorf("pyISOMicro whole second %s", got)
	}
	for in, want := range map[string]string{"2026-01-30": "2019-01-01", "2026-01-31": "2020-01-01", "2026-12-31": "2020-01-01"} {
		d, _ := time.Parse("2006-01-02", in)
		if got := isoDate(housebookCutoff(d)); got != want {
			t.Errorf("housebookCutoff(%s) = %s, want %s", in, got, want)
		}
	}
	if got := pyQuote("a\"b\\c\n" + string(rune(0xe9)) + string(rune(0x1F600)) + "\x7f"); got != "\"a\\\"b\\\\c\\n\\u00e9\\ud83d\\ude00\\u007f\"" {
		t.Errorf("pyQuote %s", got)
	}
	owner := int64(7)
	s := Summary{DryRun: true, OwnerUserID: &owner, Counts: []Count{{"guests", 2}, {"invoices", 0}}}
	if got := summaryJSON(s, ""); got != `{"dry_run": true, "owner_user_id": 7, "counts": {"guests": 2, "invoices": 0}}` {
		t.Errorf("summaryJSON %s", got)
	}
	if got := summaryJSON(Summary{Counts: []Count{}}, "T"); got != `{"dry_run": false, "owner_user_id": null, "counts": {}, "at": "T"}` {
		t.Errorf("summaryJSON at %s", got)
	}
}
````

<!-- file: go/cmd/ubyhost-web/register_job_retention.go -->
````go
package main

// Job kind retention: App/app/scheduler.py _job_retention in Go
// (go/internal/retention). A dry run unless UBYHOST_RETENTION_AUTOPURGE and
// UBYHOST_GO_RETENTION_APPLY are both on. Brief 1210.

import (
	"context"
	"log/slog"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/retention"
)

func init() {
	registerJob("retention", 24*60, retentionHandler)
}

// retentionHandler builds the handler without touching the pool. A failed
// run raises the job_failed alert at once, as Python's _job_failed does, and
// returns the error so the queue records no success. Counts only in the log.
func retentionHandler(pool *pgxpool.Pool) jobs.Handler {
	return func(ctx context.Context) (int, error) {
		cfg, err := retention.ConfigFromEnv(os.LookupEnv)
		if err == nil {
			now := time.Now()
			// Python's date.today() is the server's local date.
			var sum retention.Summary
			sum, err = retention.Run(ctx, pool, cfg, now.Local(), now, nil)
			if err == nil {
				if sum.Total() > 0 {
					args := []any{"dry_run", sum.DryRun}
					for _, c := range sum.Counts {
						args = append(args, c.Name, c.Count)
					}
					slog.Info("retention run", args...)
				}
				return sum.Total(), nil
			}
		}
		if raiseErr := jobs.RaiseFailed(ctx, pool, "retention"); raiseErr != nil {
			slog.Warn("retention job_failed alert not raised")
		}
		return 0, err
	}
}
````

<!-- file: go/internal/retention/testdata/fixture.sql -->
````sql
-- Synthetic retention fixture (no real person). Loaded after App/migrations_pg
-- by App/scripts/retention_golden.py and by golden_test.go. The run instant is
-- 2026-01-20T03:00:00.250000Z, today 2026-01-20: guests before 2019-01-01 are
-- due, stays ending in 2019 get the retention_due notice. Each step has rows
-- that are due and rows that are not, for owner 1 and owner 2.
INSERT INTO user_account (id, username, password_hash, created_at, active, last_login_at, deletion_due_at) VALUES
 (1, 'host-one', 'x', '2017-01-01T00:00:00+00:00', 1, '2026-01-19T08:00:00+00:00', NULL),
 (2, 'host-two', 'x', '2017-01-01T00:00:00+00:00', 1, '2026-01-18T08:00:00+00:00', NULL),
 (3, 'gone-inactive', 'x', '2017-01-01T00:00:00+00:00', 0, '2022-01-01T00:00:00+00:00', NULL),
 (4, 'due-now', 'x', '2017-01-01T00:00:00+00:00', 1, NULL, '2026-01-19T00:00:00+00:00'),
 (5, 'due-in-3-days', 'x', '2017-01-01T00:00:00+00:00', 1, NULL, '2026-01-23T00:00:00+00:00'),
 (6, 'due-in-march', 'x', '2017-01-01T00:00:00+00:00', 1, NULL, '2026-03-01T00:00:00+00:00'),
 (7, 'recent-inactive', 'x', '2017-01-01T00:00:00+00:00', 0, '2025-06-01T00:00:00+00:00', NULL);

INSERT INTO apartment (id, internal_name, created_at, owner_user_id) VALUES
 (10, 'Flat A', '2017-01-01T00:00:00+00:00', 1),
 (20, 'Flat B', '2017-01-01T00:00:00+00:00', 2);

INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, guest_email, phone_last4, created_at, updated_at) VALUES
 (100, 10, 'r100', '2018-05-01', '2018-05-05', 'g100@example.test', '1001', '2018-01-01T00:00:00+00:00', '2018-01-01T00:00:00+00:00'),
 (101, 10, 'r101', '2019-06-01', '2019-06-03', NULL, NULL, '2019-01-01T00:00:00+00:00', '2019-01-01T00:00:00+00:00'),
 (102, 10, 'r102', '2025-12-01', '2025-12-10', 'g102@example.test', NULL, '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (103, 10, 'r103', '2026-01-10', '2026-01-15', 'g103@example.test', '1003', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (104, 10, 'r104', '2017-01-01', '2017-01-02', NULL, NULL, '2017-01-01T00:00:00+00:00', '2017-01-01T00:00:00+00:00'),
 (105, 10, 'r105', '2025-01-01', '2025-01-02', NULL, '1005', '2024-12-01T00:00:00+00:00', '2024-12-01T00:00:00+00:00'),
 (106, 10, 'r106', '2025-08-01', '2025-08-05', NULL, NULL, '2025-07-01T00:00:00+00:00', '2025-07-01T00:00:00+00:00'),
 (107, 10, 'r107', '2018-07-01', '2018-07-07T12:00:00', NULL, NULL, '2018-06-01T00:00:00+00:00', '2018-06-01T00:00:00+00:00'),
 (200, 20, 'r200', '2018-03-01', '2018-03-02', NULL, '2001', '2018-01-01T00:00:00+00:00', '2018-01-01T00:00:00+00:00'),
 (201, 20, 'r201', '2019-02-01', '2019-02-02', NULL, NULL, '2019-01-01T00:00:00+00:00', '2019-01-01T00:00:00+00:00'),
 (202, 20, 'r202', '2016-01-01', '2016-01-02', NULL, NULL, '2016-01-01T00:00:00+00:00', '2016-01-01T00:00:00+00:00');

INSERT INTO submission (id, apartment_id, created_at) VALUES
 (500, 10, '2018-05-06T00:00:00+00:00'),
 (501, 10, '2018-01-01T00:00:00+00:00'),
 (502, 10, '2025-01-01T00:00:00+00:00'),
 (503, 20, '2018-03-03T00:00:00+00:00');

INSERT INTO guest (id, reservation_id, stay_to, filled_ip, submission_id, receipt_submission_id, created_at, updated_at) VALUES
 (1000, 100, '2018-05-05', '192.0.2.1', 500, NULL, '2018-05-01T00:00:00+00:00', '2018-05-01T00:00:00+00:00'),
 (1001, 100, 'not-a-date', NULL, NULL, NULL, '2018-05-01T00:00:00+00:00', '2018-05-01T00:00:00+00:00'),
 (1002, 101, NULL, NULL, NULL, NULL, '2019-06-01T00:00:00+00:00', '2019-06-01T00:00:00+00:00'),
 (1003, 102, NULL, '192.0.2.3', NULL, NULL, '2025-12-01T00:00:00+00:00', '2025-12-01T00:00:00+00:00'),
 (1004, 106, '2025-08-05', '192.0.2.4', NULL, NULL, '2025-08-01T00:00:00+00:00', '2025-08-01T00:00:00+00:00'),
 (1005, 106, '2025-11-30', '192.0.2.5', NULL, NULL, '2025-08-01T00:00:00+00:00', '2025-08-01T00:00:00+00:00'),
 (1006, 107, NULL, NULL, NULL, NULL, '2018-07-01T00:00:00+00:00', '2018-07-01T00:00:00+00:00'),
 (2000, 200, NULL, '192.0.2.20', NULL, 503, '2018-03-01T00:00:00+00:00', '2018-03-01T00:00:00+00:00'),
 (2001, 201, NULL, NULL, NULL, NULL, '2019-02-01T00:00:00+00:00', '2019-02-01T00:00:00+00:00'),
 (2002, 103, NULL, NULL, NULL, NULL, '2026-01-10T00:00:00+00:00', '2026-01-10T00:00:00+00:00');

INSERT INTO reservation_claim (reservation_id, email, created_at, updated_at) VALUES
 (100, NULL, '2018-01-01T00:00:00+00:00', '2018-01-01T00:00:00+00:00'),
 (102, 'c102@example.test', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (103, 'c103@example.test', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (200, 'c200@example.test', '2018-01-01T00:00:00+00:00', '2018-01-01T00:00:00+00:00');

INSERT INTO stay_fee_filing (id, apartment_id, period_key, cadence, rate_czk, liable_days, exempt_days, total_due_czk, total_collected_czk, created_at) VALUES
 (300, 10, '2018-03', 'monthly', 50, 1, 0, 50, 50, '2018-04-01T00:00:00+00:00'),
 (301, 10, '2019-Q1', 'quarterly', 50, 1, 0, 50, 50, '2019-04-01T00:00:00+00:00'),
 (302, 20, '2017-Q4', 'quarterly', 50, 1, 0, 50, 50, '2018-01-01T00:00:00+00:00');

INSERT INTO stay_fee_adjustment (id, apartment_id, period_key, direction, mode, bed_days, reason_enc, created_at) VALUES
 (310, 10, '2018-03', 'add', 'bed_days', 1, 'x', '2018-04-01T00:00:00+00:00'),
 (311, 10, '2020-01', 'add', 'bed_days', 1, 'x', '2020-02-01T00:00:00+00:00');

INSERT INTO legal_entity (id, name, created_at, owner_user_id) VALUES
 (30, 'Entity A', '2017-01-01T00:00:00+00:00', 1),
 (40, 'Entity B', '2017-01-01T00:00:00+00:00', 2);

INSERT INTO invoice (id, legal_entity_id, owner_user_id, kind, corrects_invoice_id, seq_year, seq_no, number, vs, lang, vat_status, issue_date, seller_name, seller_seat, buyer_name, total_haler, created_at) VALUES
 (600, 30, 1, 'invoice', NULL, 2015, 1, 'A2015-1', '20151', 'cs', 'non_payer', '2015-03-01', 'S', 'S', 'B', 100, '2015-03-01T00:00:00+00:00'),
 (601, 30, 1, 'invoice', NULL, 2015, 2, 'A2015-2', '20152', 'cs', 'non_payer', '2015-06-01', 'S', 'S', 'B', 100, '2015-06-01T00:00:00+00:00'),
 (602, 30, 1, 'storno', 601, 2016, 1, 'A2016-1', '20161', 'cs', 'non_payer', '2016-02-01', 'S', 'S', 'B', -100, '2016-02-01T00:00:00+00:00'),
 (603, 30, 1, 'invoice', NULL, 2015, 3, 'A2015-3', '20153', 'cs', 'non_payer', '2015-01-10', 'S', 'S', 'B', 100, '2015-01-10T00:00:00+00:00'),
 (604, 30, 1, 'storno', 603, 2015, 4, 'A2015-4', '20154', 'cs', 'non_payer', '2015-12-01', 'S', 'S', 'B', -100, '2015-12-01T00:00:00+00:00'),
 (605, 40, 2, 'invoice', NULL, 2014, 1, 'B2014-1', '20141', 'cs', 'non_payer', '2014-01-01', 'S', 'S', 'B', 100, '2014-01-01T00:00:00+00:00'),
 (606, 30, 1, 'invoice', NULL, 2020, 1, 'A2020-1', '20201', 'cs', 'non_payer', '2020-01-01', 'S', 'S', 'B', 100, '2020-01-01T00:00:00+00:00');

INSERT INTO invoice_item (id, invoice_id, position, kind, description, gross_haler) VALUES
 (650, 600, 1, 'accommodation', 'Stay', 100),
 (651, 603, 1, 'accommodation', 'Stay', 100),
 (652, 606, 1, 'accommodation', 'Stay', 100);

UPDATE invoice SET issued_at = issue_date || 'T12:00:00+00:00';

INSERT INTO platform_invoice (id, owner_user_id, kind, corrects_id, seq_year, seq_no, number, vs, issue_date, due_date, period_from, period_to, total_haler, snapshot_json, created_at) VALUES
 (700, 1, 'invoice', NULL, 2015, 1, 'U2015-1', '9001', '2015-02-01', '2015-02-15', '2015-02-01', '2015-02-28', 100, '{}', '2015-02-01T00:00:00+00:00'),
 (701, 1, 'invoice', NULL, 2015, 2, 'U2015-2', '9002', '2015-05-01', '2015-05-15', '2015-05-01', '2015-05-31', 100, '{}', '2015-05-01T00:00:00+00:00'),
 (702, 1, 'storno', 701, 2016, 1, 'U2016-1', '9003', '2016-01-05', '2016-01-19', '2015-05-01', '2015-05-31', -100, '{}', '2016-01-05T00:00:00+00:00'),
 (703, 1, 'invoice', NULL, 2020, 1, 'U2020-1', '9004', '2020-03-01', '2020-03-15', '2020-03-01', '2020-03-31', 100, '{}', '2020-03-01T00:00:00+00:00');

INSERT INTO bank_payment (bank_tx_id, received_on, amount_haler, status, matched_invoice_id) VALUES
 ('tx-700', '2015-02-10', 100, 'matched', 700),
 ('tx-old-unmatched', '2015-01-01', 100, 'unmatched', NULL),
 ('tx-new-unmatched', '2020-01-01', 100, 'unmatched', NULL),
 ('tx-703', '2020-03-10', 100, 'matched', 703);

INSERT INTO audit (id, at, actor, action, detail, owner_user_id) VALUES
 (1, '2022-01-01T00:00:00+00:00', 'host-one', 'login', '', 1),
 (2, '2022-01-01T00:00:00+00:00', 'host-one', 'legal_accepted', '', 1),
 (3, '2025-01-01T00:00:00+00:00', 'host-one', 'login', '', 1),
 (4, '2021-01-01T00:00:00+00:00', 'host-two', 'login', '', 2),
 (5, '2021-01-01T00:00:00+00:00', 'system', 'backup', '', NULL),
 (6, '2021-01-01T00:00:00+00:00', 'host-two', 'door_code_terms_accepted', '', 2),
 (7, '2023-01-21T02:59:59+00:00', 'host-one', 'login', '', 1),
 (8, '2023-01-21T03:00:00+00:00', 'host-one', 'login', '', 1);
SELECT setval('audit_id_seq', 100);

INSERT INTO alert (id, level, kind, message, created_at, resolved_at, owner_user_id, dedupe_key, params) VALUES
 (1, 'warning', 'x', 'm', '2024-05-01T00:00:00+00:00', '2024-06-01T00:00:00+00:00', 1, 'x:1', NULL),
 (2, 'warning', 'x', 'm', '2025-05-01T00:00:00+00:00', '2025-06-01T00:00:00+00:00', 1, 'x:2', NULL),
 (3, 'warning', 'x', 'm', '2020-05-01T00:00:00+00:00', NULL, 1, 'x:3', NULL),
 (4, 'warning', 'x', 'm', '2023-05-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00', NULL, 'x:4', NULL),
 (5, 'warning', 'retention_due', 'old copy', '2026-01-01T00:00:00+00:00', NULL, 2, 'retention_due:2:2026-01', '{"count": 9, "days": 30}');
SELECT setval('alert_id_seq', 100);

-- Run instant E = 1768878000.25 (epoch seconds).
INSERT INTO rate_limit_event (id, scope, key, at) VALUES
 (1, 'login', 'k', 1768788000.25),
 (2, 'login', 'k', 1768874400.25),
 (3, 'havel_week', 'k', 1768788000.25),
 (4, 'havel_month', 'k', 1765422000.25),
 (5, 'login', 'k', 1768791600.25);

INSERT INTO havel_gap (id, created_at, lang, kind, question) VALUES
 (1, '2025-09-01T00:00:00+00:00', 'en', 'gap', 'q'),
 (2, '2025-12-01T00:00:00+00:00', 'en', 'gap', 'q');

INSERT INTO login_token (id, token_hash, user_account_id, purpose, email, created_at, expires_at) VALUES
 (1, 'h1', 1, 'login', 'host-one@example.test', '2026-01-17T00:00:00+00:00', '2026-01-18T00:00:00+00:00'),
 (2, 'h2', 1, 'login', 'host-one@example.test', '2026-01-18T03:00:00+00:00', '2026-01-19T03:00:00+00:00');

INSERT INTO webauthn_challenge (id, challenge_hash, purpose, user_account_id, created_at, expires_at) VALUES
 (1, 'c1', 'login', 1, '2026-01-19T02:55:00+00:00', '2026-01-19T03:00:00+00:00'),
 (2, 'c2', 'login', 1, '2026-01-19T02:55:01+00:00', '2026-01-19T03:00:01+00:00');

INSERT INTO door_code (id, reservation_id, apartment_id, lock_id, pin_enc, valid_to, created_at, updated_at) VALUES
 (1, 102, 10, 'L', 'pin-a', '2026-01-18T10:00:00+00:00', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (2, 103, 10, 'L', 'pin-b', '2026-01-19T12:00:00+00:00', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (3, 105, 10, 'L', NULL, '2025-01-02T10:00:00+00:00', '2024-12-01T00:00:00+00:00', '2024-12-01T00:00:00+00:00');

INSERT INTO cleaning_event (id, apartment_id, scheduled_date, notes_enc, created_at, updated_at) VALUES
 (1, 10, '2025-12-01', 'n1', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (2, 10, '2026-01-10', 'n2', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (3, 20, '2025-11-01', 'n3', '2025-10-01T00:00:00+00:00', '2025-10-01T00:00:00+00:00'),
 (4, 10, '2025-11-01', NULL, '2025-10-01T00:00:00+00:00', '2025-10-01T00:00:00+00:00');

INSERT INTO cleaning_share (id, owner_user_id, token_hash, expires_at, created_at) VALUES
 (1, 1, 's1', '2025-12-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00'),
 (2, 1, 's2', '2026-02-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'),
 (3, 2, 's3', '2025-12-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00');

INSERT INTO push_subscription (id, user_account_id, endpoint_hash, endpoint_enc, p256dh_enc, auth_enc, created_at, last_seen_at) VALUES
 (1, 1, 'e1', 'x', 'x', 'x', '2025-01-01T00:00:00+00:00', '2025-06-01T00:00:00+00:00'),
 (2, 1, 'e2', 'x', 'x', 'x', '2025-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'),
 (3, 2, 'e3', 'x', 'x', 'x', '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00');

INSERT INTO push_outbox (id, idempotency_key, subscription_id, user_account_id, kind, next_attempt_at, created_at) VALUES
 (1, 'p1', 2, 1, 'k', '2025-12-01T00:00:00+00:00', '2025-12-01T00:00:00+00:00'),
 (2, 'p2', 2, 1, 'k', '2026-01-10T00:00:00+00:00', '2026-01-10T00:00:00+00:00'),
 (3, 'p3', 1, 1, 'k', '2026-01-15T00:00:00+00:00', '2026-01-15T00:00:00+00:00'),
 (4, 'p4', 3, 2, 'k', '2025-11-01T00:00:00+00:00', '2025-11-01T00:00:00+00:00');

INSERT INTO guide_import (id, apartment_id, source, url, status, raw_json, created_at) VALUES
 (1, 10, 'booking', 'https://example.test/1', 'done', '{}', '2026-01-01T00:00:00+00:00'),
 (2, 10, 'booking', 'https://example.test/2', 'failed', NULL, '2025-10-01T00:00:00+00:00'),
 (3, 10, 'booking', 'https://example.test/3', 'failed', NULL, '2025-12-01T00:00:00+00:00'),
 (4, 10, 'airbnb', 'https://example.test/4', 'queued', '{}', '2026-01-15T00:00:00+00:00'),
 (5, 20, 'airbnb', 'https://example.test/5', 'failed', '{}', '2025-09-01T00:00:00+00:00');

INSERT INTO guest_chat (id, apartment_id, door, reservation_id, cookie_id, created_at, last_message_at) VALUES
 (1, 10, 'stay', 102, NULL, '2025-12-01T00:00:00+00:00', '2025-12-05T00:00:00+00:00'),
 (2, 10, 'stay', 103, NULL, '2026-01-10T00:00:00+00:00', '2026-01-12T00:00:00+00:00'),
 (3, 10, 'qr', NULL, 'k1', '2025-11-01T00:00:00+00:00', '2025-12-01T10:00:00+00:00'),
 (4, 10, 'qr', NULL, 'k2', '2025-11-01T00:00:00+00:00', '2026-01-10T10:00:00+00:00'),
 (5, 20, 'stay', NULL, NULL, '2026-01-10T00:00:00+00:00', '2026-01-10T00:00:00+00:00');

INSERT INTO guest_chat_message (id, chat_id, role, text, created_at) VALUES
 (1, 1, 'guest', 't', '2025-12-01T00:00:00+00:00'),
 (2, 2, 'guest', 't', '2026-01-10T00:00:00+00:00'),
 (3, 3, 'guest', 't', '2025-12-01T00:00:00+00:00');

INSERT INTO guest_question (id, chat_id, apartment_id, message_id, summary, created_at) VALUES
 (1, 1, 10, 1, 's', '2025-12-01T00:00:00+00:00'),
 (2, 2, 10, 2, 's', '2026-01-10T00:00:00+00:00');

INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) VALUES
 (1, 3, 'terms', 'v1', '2017-01-01T00:00:00+00:00', 'clickwrap'),
 (2, 1, 'terms', 'v1', '2017-01-01T00:00:00+00:00', 'clickwrap'),
 (3, 7, 'terms', 'v1', '2017-01-01T00:00:00+00:00', 'clickwrap');

INSERT INTO settings (key, value) VALUES ('retention_last_run', 'old');
````

<!-- file: go/internal/retention/golden_test.go -->
````go
package retention

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// golden is testdata/golden.json, written by App/scripts/retention_golden.py
// from the real Python retention.run() on the same fixture.
type golden struct {
	Today     string            `json:"today"`
	Now       string            `json:"now"`
	Photos    []string          `json:"photos"`
	Queries   map[string]string `json:"queries"`
	Scenarios []struct {
		Name   string              `json:"name"`
		Owner  *int64              `json:"owner_user_id"`
		DryRun bool                `json:"dry_run"`
		Error  *string             `json:"error"`
		Counts [][2]any            `json:"counts"`
		Photos []string            `json:"photos"`
		State  map[string][]string `json:"state"`
	} `json:"scenarios"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// TestRunMatchesPythonGolden replays every scenario of golden.json: same
// fixture, same instant, same switches; counts, first failure, every touched
// table and the photo directory must match Python.
func TestRunMatchesPythonGolden(t *testing.T) {
	g := loadGolden(t)
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	now, err := time.Parse("2006-01-02T15:04:05.000000Z", g.Now)
	if err != nil {
		t.Fatal(err)
	}
	fixture, err := os.ReadFile("testdata/fixture.sql")
	if err != nil {
		t.Fatal(err)
	}
	if len(g.Scenarios) != 2 {
		t.Fatalf("golden has %d scenarios, want 2", len(g.Scenarios))
	}
	for _, sc := range g.Scenarios {
		t.Run(sc.Name, func(t *testing.T) {
			pool := testPool(t)
			ctx := context.Background()
			if _, err := pool.Exec(ctx, string(fixture)); err != nil {
				t.Fatal(err)
			}
			dataDir := t.TempDir()
			photos := filepath.Join(dataDir, "passport_photos")
			if err := os.MkdirAll(photos, 0o700); err != nil {
				t.Fatal(err)
			}
			for _, p := range g.Photos {
				if err := os.WriteFile(filepath.Join(photos, p), []byte("x"), 0o600); err != nil {
					t.Fatal(err)
				}
			}
			cfg := Config{DryRun: sc.DryRun, AuditDays: 1095, AlertDays: 365, RateLimitHours: 24, NoticeDays: 30, DataDir: dataDir}
			sum, err := Run(ctx, pool, cfg, today, now, sc.Owner)
			if sc.Error != nil || err != nil || !sc.DryRun {
				t.Fatalf("Run: %v; golden error %v, dry run %v", err, sc.Error, sc.DryRun)
			}
			var want, got []string
			for _, c := range sc.Counts {
				want = append(want, fmt.Sprintf("%v=%v", c[0], c[1]))
			}
			for _, c := range sum.Counts {
				got = append(got, fmt.Sprintf("%s=%d", c.Name, c.Count))
			}
			if !reflect.DeepEqual(got, want) {
				t.Errorf("counts\n got %v\nwant %v", got, want)
			}
			names := make([]string, 0, len(g.Queries))
			for k := range g.Queries {
				names = append(names, k)
			}
			sort.Strings(names)
			for _, name := range names {
				rows, err := pool.Query(ctx, g.Queries[name])
				if err != nil {
					t.Fatalf("%s: %v", name, err)
				}
				gotRows, err := pgx.CollectRows(rows, pgx.RowTo[string])
				if err != nil {
					t.Fatalf("%s: %v", name, err)
				}
				wantRows := sc.State[name]
				if wantRows == nil {
					wantRows = []string{}
				}
				if gotRows == nil {
					gotRows = []string{}
				}
				if !reflect.DeepEqual(gotRows, wantRows) {
					t.Errorf("%s\n got %s\nwant %s", name, strings.Join(gotRows, "\n     "), strings.Join(wantRows, "\n     "))
				}
			}
			entries, err := os.ReadDir(photos)
			if err != nil {
				t.Fatal(err)
			}
			left := []string{}
			for _, e := range entries {
				left = append(left, e.Name())
			}
			sort.Strings(left)
			if !reflect.DeepEqual(left, sc.Photos) {
				t.Errorf("photos left %v, want %v", left, sc.Photos)
			}
		})
	}
}

// TestApplyIsRefusedUntil1211: with both apply switches on this build fails
// closed before any step runs and writes nothing.
func TestApplyIsRefusedUntil1211(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	fixture, err := os.ReadFile("testdata/fixture.sql")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, string(fixture)); err != nil {
		t.Fatal(err)
	}
	cfg := Config{AuditDays: 1095, AlertDays: 365, RateLimitHours: 24, NoticeDays: 30, DataDir: t.TempDir()}
	now := time.Date(2026, 1, 20, 3, 0, 0, 0, time.UTC)
	if _, err := Run(ctx, pool, cfg, now, now, nil); !errors.Is(err, errApplyNotPorted) {
		t.Fatalf("Run error %v, want errApplyNotPorted", err)
	}
	var audits, guests int
	if err := pool.QueryRow(ctx, `SELECT (SELECT COUNT(*) FROM audit), (SELECT COUNT(*) FROM guest)`).Scan(&audits, &guests); err != nil {
		t.Fatal(err)
	}
	if audits != 8 || guests != 10 {
		t.Fatalf("audit rows %d, guests %d: want 8 and 10 (nothing written)", audits, guests)
	}
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops the database at the end.
// It skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_retention_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}
````

<!-- file: App/scripts/retention_golden.py -->
````python
"""Write go/internal/retention/testdata/golden.json from the real Python retention job.

Needs a disposable PostgreSQL server (the Go port runs on PostgreSQL only).
Run from App/ with the venv (create it first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg&port=5433' \
        .venv/bin/python scripts/retention_golden.py [--check]

The script creates its own database (ubyhost_retention_golden_<pid>) on that
server and drops it at the end. For each scenario it rebuilds the schema from
App/migrations_pg, loads go/internal/retention/testdata/fixture.sql, creates
the photo files, runs retention.run() at a frozen instant and records the
counts, the first failure and the state of every table the job touches.
--check compares with the committed file instead of writing it (exit 1 on a
difference). The Go test in go/internal/retention/ replays the same scenarios.

Brief 1210 ports the counting half only, so only the dry-run scenarios are
recorded; brief 1211 adds the apply scenarios.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
PKG = REPO / "go" / "internal" / "retention" / "testdata"
OUT = PKG / "golden.json"
FIXTURE = PKG / "fixture.sql"

TODAY = date(2026, 1, 20)
NOW = datetime(2026, 1, 20, 3, 0, 0, 250000, tzinfo=UTC)
PHOTOS = ["1000.jpg.enc", "1001.png", "1002.jpg", "2000.pdf.enc", "notes.txt"]
SCENARIOS = [
    ("global_dry", None, True),
    ("owner1_dry", 1, True),
]
# One text column per row, so Go and Python compare plain strings.
QUERIES = {
    "guest": "SELECT id::text || '|' || COALESCE(filled_ip, '~') FROM guest ORDER BY id",
    "submission": "SELECT id::text FROM submission ORDER BY id",
    "reservation": (
        "SELECT id::text || '|' || COALESCE(guest_email, '~') || '|' || COALESCE(phone_last4, '~')"
        " || '|' || updated_at FROM reservation ORDER BY id"
    ),
    "reservation_claim": (
        "SELECT reservation_id::text || '|' || COALESCE(email, '~') || '|' || updated_at"
        " FROM reservation_claim ORDER BY reservation_id"
    ),
    "stay_fee_filing": "SELECT id::text FROM stay_fee_filing ORDER BY id",
    "stay_fee_adjustment": "SELECT id::text FROM stay_fee_adjustment ORDER BY id",
    "invoice": "SELECT id::text FROM invoice ORDER BY id",
    "invoice_item": "SELECT id::text FROM invoice_item ORDER BY id",
    "platform_invoice": "SELECT id::text FROM platform_invoice ORDER BY id",
    "bank_payment": "SELECT bank_tx_id FROM bank_payment ORDER BY bank_tx_id",
    "audit": (
        "SELECT id::text || '|' || at || '|' || COALESCE(actor, '~') || '|' || action || '|'"
        " || COALESCE(detail, '~') || '|' || COALESCE(owner_user_id::text, '~')"
        " || '|' || COALESCE(actor_user_id::text, '~') || '|' || COALESCE(impersonator_user_id::text, '~')"
        " FROM audit ORDER BY id"
    ),
    "alert": (
        "SELECT id::text || '|' || level || '|' || kind || '|' || COALESCE(owner_user_id::text, '~') || '|'"
        " || COALESCE(apartment_id::text, '~') || '|' || COALESCE(reservation_id::text, '~') || '|'"
        " || COALESCE(dedupe_key, '~') || '|' || message || '|' || COALESCE(detail, '~') || '|'"
        " || COALESCE(params, '~') || '|' || created_at || '|' || COALESCE(resolved_at, '~')"
        " FROM alert ORDER BY id"
    ),
    "rate_limit_event": "SELECT id::text FROM rate_limit_event ORDER BY id",
    "havel_gap": "SELECT id::text FROM havel_gap ORDER BY id",
    "login_token": "SELECT id::text FROM login_token ORDER BY id",
    "webauthn_challenge": "SELECT id::text FROM webauthn_challenge ORDER BY id",
    "door_code": (
        "SELECT id::text || '|' || COALESCE(pin_enc, '~') || '|' || updated_at FROM door_code ORDER BY id"
    ),
    "cleaning_event": "SELECT id::text || '|' || COALESCE(notes_enc, '~') FROM cleaning_event ORDER BY id",
    "cleaning_share": "SELECT id::text FROM cleaning_share ORDER BY id",
    "push_outbox": "SELECT id::text FROM push_outbox ORDER BY id",
    "push_subscription": "SELECT id::text FROM push_subscription ORDER BY id",
    "guide_import": (
        "SELECT id::text || '|' || status || '|' || COALESCE(raw_json, '~') FROM guide_import ORDER BY id"
    ),
    "guest_chat": "SELECT id::text FROM guest_chat ORDER BY id",
    "guest_chat_message": "SELECT id::text FROM guest_chat_message ORDER BY id",
    "guest_question": "SELECT id::text FROM guest_question ORDER BY id",
    "legal_acceptance": "SELECT id::text FROM legal_acceptance ORDER BY id",
    "user_account": "SELECT id::text FROM user_account ORDER BY id",
    "settings": "SELECT key || '=' || COALESCE(value, '~') FROM settings ORDER BY key",
    "email_outbox": "SELECT COUNT(*)::text FROM email_outbox",
}
RETENTION_ENV = (
    "UBYHOST_RETENTION_AUTOPURGE",
    "UBYHOST_RETENTION_NOTICE_DAYS",
    "UBYHOST_AUDIT_RETENTION_DAYS",
    "UBYHOST_ALERT_RETENTION_DAYS",
    "UBYHOST_RATE_LIMIT_RETENTION_HOURS",
)


def _url_for(base: str, name: str) -> str:
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


def _migrations_sql() -> list[str]:
    out = []
    for path in sorted((APP / "migrations_pg").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        i = text.find("-- +goose Up")
        if i >= 0:
            text = text[i + len("-- +goose Up"):]
        j = text.find("-- +goose Down")
        if j >= 0:
            text = text[:j]
        out.append(text)
    return out


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.astimezone().replace(tzinfo=None)


def _freeze() -> None:
    from app import db, login_link, passkeys, push, retention

    db.datetime = _Frozen
    retention.datetime = _Frozen
    retention.time = SimpleNamespace(time=lambda: NOW.timestamp(), perf_counter=time.perf_counter)
    for module in (login_link, passkeys, push):
        module._now = lambda: NOW


def _scenario(psycopg, url: str, photos_dir: Path, name: str, owner, dry_run: bool) -> dict:
    from app import db, retention

    db.close_connections()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        for sql in _migrations_sql():
            conn.execute(sql)
        conn.execute(FIXTURE.read_text(encoding="utf-8"))
    photos_dir.mkdir(parents=True, exist_ok=True)
    for old in photos_dir.iterdir():
        old.unlink()
    for photo in PHOTOS:
        (photos_dir / photo).write_bytes(b"x")
    error = None
    try:
        retention.run(TODAY, dry_run=dry_run, owner_user_id=owner)
    except Exception as exc:  # noqa: BLE001 - recorded; the Go test must fail the same way
        error = type(exc).__name__
    db.close_connections()
    state = {}
    with psycopg.connect(url, autocommit=True) as conn:
        for key, sql in QUERIES.items():
            state[key] = [row[0] for row in conn.execute(sql).fetchall()]
        last = conn.execute("SELECT value FROM settings WHERE key = 'retention_last_run'").fetchone()[0]
    counts = [[k, v] for k, v in json.loads(last)["counts"].items()]
    return {
        "name": name,
        "owner_user_id": owner,
        "dry_run": dry_run,
        "error": error,
        "counts": counts,
        "photos": sorted(p.name for p in photos_dir.iterdir()),
        "state": state,
    }


def render() -> str:
    base = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL")
    if not base:
        raise SystemExit("set UBYHOST_TEST_DATABASE_URL to a disposable PostgreSQL server")
    import psycopg

    name = f"ubyhost_retention_golden_{os.getpid()}"
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = _url_for(base, name)
    data_dir = Path(tempfile.mkdtemp(prefix="ubyhost-retention-golden-"))
    os.environ.pop("UBYHOST_DB", None)
    for key in RETENTION_ENV:
        os.environ.pop(key, None)
    os.environ["UBYHOST_DATABASE_URL"] = url
    os.environ["UBYHOST_DATA_DIR"] = str(data_dir)
    os.environ.setdefault("UBYHOST_SECRET_KEY", "retention-golden-not-a-secret")
    os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
    sys.path.insert(0, str(APP))
    try:
        _freeze()
        scenarios = [
            _scenario(psycopg, url, data_dir / "passport_photos", n, owner, dry)
            for n, owner, dry in SCENARIOS
        ]
    finally:
        from app import db

        db.close_connections()
        with psycopg.connect(base, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    doc = {
        "today": TODAY.isoformat(),
        "now": NOW.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "photos": PHOTOS,
        "queries": QUERIES,
        "scenarios": scenarios,
    }
    return json.dumps(doc, indent=1, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv[1:]:
        if OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT} is out of date: rerun scripts/retention_golden.py")
            raise SystemExit(1)
        print("golden up to date")
    else:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}")
````

<!-- file: App/tests/test_go_retention_parity.py -->
````python
"""The Go retention job (go/internal/retention) replays golden.json, which
scripts/retention_golden.py writes from the real Python retention.run().

On PostgreSQL (UBYHOST_TEST_DATABASE_URL or UBYHOST_DATABASE_URL set, as in
the test-postgres-full CI row) this regenerates the golden in a throwaway
database and fails if the committed file is out of date: a change to
App/app/retention.py or a helper it calls must come with a new golden (and a
matching Go change). If this fails, rerun from App/:

    UBYHOST_TEST_DATABASE_URL=<disposable server> .venv/bin/python scripts/retention_golden.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "retention" / "testdata" / "golden.json"
SCRIPT = APP_DIR / "scripts" / "retention_golden.py"
PG_URL = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL")


def test_golden_lists_the_dry_run_scenarios():
    doc = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert [s["name"] for s in doc["scenarios"]] == ["global_dry", "owner1_dry"]
    assert '"queries": ' in GOLDEN.read_text(encoding="utf-8")
    assert all(s["error"] is None and s["dry_run"] for s in doc["scenarios"])


@pytest.mark.skipif(not PG_URL, reason="needs PostgreSQL (UBYHOST_TEST_DATABASE_URL or UBYHOST_DATABASE_URL)")
def test_golden_is_up_to_date_with_python_retention():
    env = {k: v for k, v in os.environ.items() if k not in ("UBYHOST_DB",)}
    env["UBYHOST_TEST_DATABASE_URL"] = PG_URL
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=str(APP_DIR),
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
    assert "golden up to date" in result.stdout
````
