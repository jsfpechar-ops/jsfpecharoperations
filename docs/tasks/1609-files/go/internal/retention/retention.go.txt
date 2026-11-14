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
	actor *Actor // nil in the job; the signed-in user in a request (RunAs)
}

// Actor is the signed-in user of a request, what db.set_current_actor and
// db.set_current_owner hold there (brief 1609). Inside a request db.audit
// fills owner_user_id, actor_user_id and impersonator_user_id from it and
// writes the username where the caller named the actor "host".
type Actor struct {
	UserID         int64  // the signed-in account
	Username       string // its username
	ImpersonatorID *int64 // the account again while it supports a workspace, else nil
	OwnerUserID    *int64 // the workspace (db.set_current_owner)
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
	return RunAs(ctx, pool, cfg, today, now, owner, nil)
}

// RunAs is Run inside a request (brief 1609: the Settings button, which calls
// retention.run(..., dry_run=False, owner_user_id=owner) as the signed-in
// host). It is Run exactly, except that the rows db.audit writes (retention_run
// and the purge lines of the steps) carry actor as Python's request context
// does. The retention_delete rows (db.audit_retention) stay without user ids,
// as in Python. A nil actor is Run.
func RunAs(ctx context.Context, pool *pgxpool.Pool, cfg Config, today, now time.Time, owner *int64, actor *Actor) (Summary, error) {
	r := &runner{
		pool:  pool,
		cfg:   cfg,
		today: time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC),
		now:   now.UTC(),
		owner: owner,
		dry:   cfg.DryRun,
		actor: actor,
	}
	sum := Summary{DryRun: r.dry, OwnerUserID: owner, Counts: []Count{}}
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

// audit is db.audit(action, detail, actor). In the job's context there is no
// current owner and no signed-in actor, so owner_user_id, actor_user_id and
// impersonator_user_id are NULL. In a request (RunAs) they come from the
// actor, and the placeholder actor "host" becomes the username.
func (r *runner) audit(ctx context.Context, action, detail, actor string) error {
	var owner, actorID, impersonator any
	if a := r.actor; a != nil {
		if a.OwnerUserID != nil {
			owner = *a.OwnerUserID
		}
		actorID = a.UserID
		if a.ImpersonatorID != nil {
			impersonator = *a.ImpersonatorID
		}
		if actor == "host" {
			actor = a.Username
		}
	}
	_, err := r.pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		pyISO(r.now), actor, action, detail, owner, actorID, impersonator)
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
