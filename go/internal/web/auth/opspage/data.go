package opspage

// data.go: every read of GET /admin/operations, the port of
// App/app/admin_ops.py (overview and its sections), incidents.list_all,
// incidents.controller_notification_draft, incidents.open_review_alerts and
// the owners list of routes/admin_accounts.py operations_admin (lines
// 929-950). Aggregate SQL with a LIMIT; no guest field is read, nothing is
// decrypted, no feed URL and no mail recipient is selected. Read only.

import (
	"context"
	"encoding/json"
	"errors"
	"math"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	rowLimit             = 50 // ROW_LIMIT
	feedStaleHours       = 3  // FEED_STALE_HOURS
	runningStuckMinutes  = 30 // RUNNING_STUCK_MINUTES
	mailStuckMinutes     = 30 // MAIL_STUCK_MINUTES
	lastOKWriteMinutes   = 15 // scheduler.LAST_OK_WRITE_MINUTES
	jobLastOKPrefix      = "job_last_ok:"
	submitStateSent      = "sent"    // reporting.SENT
	submitStateError     = "error"   // reporting.ERROR
	submitStateBlocked   = "blocked" // reporting.BLOCKED
	defaultTTLockMonthly = 30000     // config.TTLOCK_MONTHLY_CALLS default
)

// incidentTimestamps is incidents.TIMESTAMP_FIELDS with the template's labels.
var incidentTimestamps = [][2]string{
	{"contained_at", "incidents.contained"},
	{"controllers_notified_at", "incidents.controllers_notified"},
	{"authority_notified_at", "incidents.authority_notified"},
	{"subjects_notified_at", "incidents.subjects_notified"},
	{"closed_at", "incidents.closed"},
}

// pySpace is str.isspace: Unicode White_Space plus 0x1c-0x1f.
func pySpace(c rune) bool { return unicode.IsSpace(c) || (c >= 0x1c && c <= 0x1f) }

// pyInt is int(text) for the env values: surrounding spaces allowed, else ok is false.
func pyInt(text string) (int64, bool) {
	n, err := strconv.ParseInt(strings.TrimFunc(text, pySpace), 10, 64)
	return n, err == nil
}

// envInt is int(os.environ.get(name, def)). A value Python could not read
// (it stops at import) falls back to the default.
func envInt(getenv func(string) string, name string, def int64) int64 {
	if v := getenv(name); v != "" {
		if n, ok := pyInt(v); ok {
			return n
		}
	}
	return def
}

// envFlag is os.environ.get(name, "0") in ("1", "true", "yes").
func envFlag(getenv func(string) string, name string) bool {
	switch getenv(name) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// isoSeconds is admin_ops._iso: UTC, whole seconds, "+00:00".
func isoSeconds(t time.Time) string { return t.UTC().Format("2006-01-02T15:04:05") + "+00:00" }

// parseTime is admin_ops.parse_time: the ISO timestamps the app writes, with
// or without an offset (none means UTC), a trailing Z, a date alone, a space
// or T between date and time, fractions of a second. ok is false for what
// datetime.fromisoformat refuses among those shapes.
func parseTime(value string) (time.Time, bool) {
	text := strings.TrimFunc(value, pySpace)
	if text == "" {
		return time.Time{}, false
	}
	if strings.HasSuffix(text, "Z") {
		text = text[:len(text)-1] + "+00:00"
	}
	if len(text) > 10 && text[10] == ' ' {
		text = text[:10] + "T" + text[11:]
	}
	for _, layout := range []string{"2006-01-02T15:04:05.999999999Z07:00", "2006-01-02T15:04:05.999999999",
		"2006-01-02T15:04Z07:00", "2006-01-02T15:04", "2006-01-02"} {
		if t, err := time.ParseInLocation(layout, text, time.UTC); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}

// ageMinutes is admin_ops.age_minutes: whole minutes since value, never
// negative; nil when value is empty or unreadable.
func ageMinutes(value *string, now time.Time) *int64 {
	if value == nil {
		return nil
	}
	t, ok := parseTime(*value)
	if !ok {
		return nil
	}
	// total_seconds() // 60 on microseconds, then max(0, ...).
	us := now.Sub(t).Microseconds()
	m := int64(math.Floor(float64(us) / 60e6))
	if m < 0 {
		m = 0
	}
	return &m
}

// lateAfterMinutes is scheduler.late_after_minutes.
func lateAfterMinutes(interval int64) int64 {
	slack := int64(0)
	if interval < lastOKWriteMinutes {
		slack = lastOKWriteMinutes
	}
	return 2*interval + slack
}

// job is one entry of scheduler.job_intervals(), in its order.
type job struct {
	ID      string
	Minutes int64
}

// jobIntervals is scheduler.job_intervals().
func jobIntervals(getenv func(string) string) []job {
	return []job{
		{"ical", envInt(getenv, "UBYHOST_ICAL_POLL_MINUTES", 60)},
		{"submit", envInt(getenv, "UBYHOST_SUBMIT_SWEEP_MINUTES", 10)},
		{"deadlines", 30}, {"mail", 5}, {"photo_sweep", 12 * 60}, {"meta_capi", 10}, {"retention", 24 * 60},
		{"door_codes", 5}, {"posthog", 15}, {"push", 1}, {"guide_import", 60}, {"stay_fee_mail", 24 * 60},
		{"stripe_sweep", 24 * 60}, {"billing_snapshot", 24 * 60},
	}
}

// FilingRow is one stay of filings_needing_attention.
type FilingRow struct {
	StayID, ApartmentID int64
	Property            string
	OwnerUserID         *int64
	Workspace           string
	State               string // outcome_unknown, rejected, retry_cap, error
	AgeMinutes          *int64
}

// StuckRow is one batch of stuck_submissions.
type StuckRow struct {
	SubmissionID int64
	Property     string
	OwnerUserID  *int64
	Workspace    string
	AgeMinutes   *int64
}

// FeedRow is one calendar of feeds_needing_attention.
type FeedRow struct {
	FeedID      int64
	Label       string
	Status      string
	Property    string
	OwnerUserID *int64
	Workspace   string
	AgeMinutes  *int64
}

// JobRow is one job of job_health.
type JobRow struct {
	JobID            string
	IntervalMinutes  int64
	LastOK           *string
	AgeMinutes       *int64
	Late, Failed     bool
	FailedAgeMinutes *int64
}

// MailRow is one message of mail_problems.
type MailRow struct {
	OutboxID   int64
	Kind       string
	State      string
	Attempts   int64
	AgeMinutes *int64
}

// AlertRow is one kind and level of open_alerts.
type AlertRow struct {
	Kind, Level string
	Count       int64
	AgeMinutes  *int64
}

// TTLock is the ttlock block of overview().
type TTLock struct {
	Used, Limit, Issued, Failed int64
	Enabled, Live               bool
}

// Overview is admin_ops.overview(): every section, in the page's order.
type Overview struct {
	FilingsCount int64
	Filings      []FilingRow
	StuckCount   int64
	Stuck        []StuckRow
	FeedsCount   int64
	Feeds        []FeedRow
	JobsCount    int64
	Jobs         []JobRow
	MailCount    int64
	Mail         []MailRow
	AlertsCount  int64
	Alerts       []AlertRow
	TTLock       TTLock
}

func isNoRows(err error) bool { return errors.Is(err, pgx.ErrNoRows) }

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// filingFrom is admin_ops._FILING_FROM with the user join of the list query
// (join is "" for the count); $a, $b, $c are ERROR, BLOCKED, SENT.
func filingFrom(join, a, b, c string) string {
	return "FROM guest g JOIN reservation r ON r.id = g.reservation_id " +
		"JOIN apartment a ON a.id = r.apartment_id " + join +
		"LEFT JOIN submission s ON s.id = g.submission_id " +
		"WHERE g.archived_at IS NULL AND r.archived_at IS NULL " +
		"AND (g.submit_state IN (" + a + ", " + b + ") " +
		"OR (s.state = 'outcome_unknown' AND g.submit_state <> " + c + "))"
}

func loadFilings(ctx context.Context, pool *pgxpool.Pool, now time.Time, o *Overview) error {
	if err := pool.QueryRow(ctx, "SELECT COUNT(DISTINCT r.id) "+filingFrom("", "$1", "$2", "$3"),
		submitStateError, submitStateBlocked, submitStateSent).Scan(&o.FilingsCount); err != nil {
		return err
	}
	rows, err := pool.Query(ctx, "SELECT r.id, a.id, a.internal_name, a.owner_user_id, u.username, "+
		"MAX(CASE WHEN s.state = 'outcome_unknown' THEN 3 WHEN g.submit_state = $1 THEN 2 "+
		"WHEN g.submit_attempts >= $2 THEN 1 ELSE 0 END) AS severity, "+
		"MIN(COALESCE(s.finished_at, s.created_at, g.updated_at)) AS since "+
		filingFrom("LEFT JOIN user_account u ON u.id = a.owner_user_id ", "$3", "$4", "$5")+
		" GROUP BY r.id, a.id, a.internal_name, a.owner_user_id, u.username "+
		"ORDER BY severity DESC, since ASC LIMIT $6",
		submitStateBlocked, int64(ubyport.SubmissionMaxAutoAttempts), submitStateError, submitStateBlocked, submitStateSent, rowLimit)
	if err != nil {
		return err
	}
	defer rows.Close()
	states := map[int64]string{3: "outcome_unknown", 2: "rejected", 1: "retry_cap", 0: "error"}
	for rows.Next() {
		var f FilingRow
		var workspace, since *string
		var severity *int64
		if err := rows.Scan(&f.StayID, &f.ApartmentID, &f.Property, &f.OwnerUserID, &workspace, &severity, &since); err != nil {
			return err
		}
		f.Workspace = str(workspace)
		sev := int64(0)
		if severity != nil {
			sev = *severity
		}
		if f.State = states[sev]; f.State == "" {
			f.State = "error"
		}
		f.AgeMinutes = ageMinutes(since, now)
		o.Filings = append(o.Filings, f)
	}
	return rows.Err()
}

func loadStuck(ctx context.Context, pool *pgxpool.Pool, now time.Time, o *Overview) error {
	cutoff := isoSeconds(now.Add(-runningStuckMinutes * time.Minute))
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM submission WHERE state = 'running' AND created_at < $1`,
		cutoff).Scan(&o.StuckCount); err != nil {
		return err
	}
	rows, err := pool.Query(ctx, `SELECT s.id, s.created_at, a.internal_name, a.owner_user_id, u.username
		FROM submission s JOIN apartment a ON a.id = s.apartment_id
		LEFT JOIN user_account u ON u.id = a.owner_user_id
		WHERE s.state = 'running' AND s.created_at < $1 ORDER BY s.created_at LIMIT $2`, cutoff, rowLimit)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var s StuckRow
		var created string
		var workspace *string
		if err := rows.Scan(&s.SubmissionID, &created, &s.Property, &s.OwnerUserID, &workspace); err != nil {
			return err
		}
		s.Workspace = str(workspace)
		s.AgeMinutes = ageMinutes(&created, now)
		o.Stuck = append(o.Stuck, s)
	}
	return rows.Err()
}

func loadFeeds(ctx context.Context, pool *pgxpool.Pool, now time.Time, o *Overview) error {
	cutoff := isoSeconds(now.Add(-feedStaleHours * time.Hour))
	const where = `FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id
		WHERE f.active = 1 AND a.active = 1 AND a.archived_at IS NULL
		AND (f.last_status IS NULL OR f.last_status <> 'ok'
		OR COALESCE(f.last_checked_at, f.last_sync_at) IS NULL
		OR COALESCE(f.last_checked_at, f.last_sync_at) < $1)`
	if err := pool.QueryRow(ctx, "SELECT COUNT(*) "+where, cutoff).Scan(&o.FeedsCount); err != nil {
		return err
	}
	rows, err := pool.Query(ctx, `SELECT f.id, f.label, f.last_status,
		COALESCE(f.last_checked_at, f.last_sync_at) AS last_checked, a.internal_name, a.owner_user_id,
		(SELECT username FROM user_account u WHERE u.id = a.owner_user_id) AS workspace `+where+`
		ORDER BY (COALESCE(f.last_checked_at, f.last_sync_at) IS NOT NULL), last_checked LIMIT $2`, cutoff, rowLimit)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var f FeedRow
		var label, status, checked, workspace *string
		if err := rows.Scan(&f.FeedID, &label, &status, &checked, &f.Property, &f.OwnerUserID, &workspace); err != nil {
			return err
		}
		f.Label, f.Workspace = str(label), str(workspace)
		if f.Status = str(status); f.Status == "" {
			f.Status = "never"
		}
		f.AgeMinutes = ageMinutes(checked, now)
		o.Feeds = append(o.Feeds, f)
	}
	return rows.Err()
}

func loadJobs(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now time.Time, o *Overview) error {
	jobs := jobIntervals(getenv)
	keys := make([]string, len(jobs))
	for i, j := range jobs {
		keys[i] = jobLastOKPrefix + j.ID
	}
	stored := map[string]*string{}
	rows, err := pool.Query(ctx, `SELECT key, value FROM settings WHERE key = ANY($1)`, keys)
	if err != nil {
		return err
	}
	for rows.Next() {
		var k string
		var v *string
		if err := rows.Scan(&k, &v); err != nil {
			rows.Close()
			return err
		}
		stored[k] = v
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	failed := map[string]string{}
	rows, err = pool.Query(ctx, `SELECT dedupe_key, created_at FROM alert
		WHERE kind = 'job_failed' AND resolved_at IS NULL LIMIT $1`, rowLimit)
	if err != nil {
		return err
	}
	for rows.Next() {
		var k *string
		var at string
		if err := rows.Scan(&k, &at); err != nil {
			rows.Close()
			return err
		}
		if k != nil {
			failed[*k] = at
		}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, j := range jobs {
		last := stored[jobLastOKPrefix+j.ID]
		age := ageMinutes(last, now)
		row := JobRow{JobID: j.ID, IntervalMinutes: j.Minutes, LastOK: last, AgeMinutes: age}
		row.Late = age == nil || *age > lateAfterMinutes(j.Minutes)
		if at, ok := failed["job_failed:"+j.ID]; ok {
			row.Failed = true
			row.FailedAgeMinutes = ageMinutes(&at, now)
		}
		if row.Late || row.Failed {
			o.JobsCount++
		}
		o.Jobs = append(o.Jobs, row)
	}
	return nil
}

func loadMail(ctx context.Context, pool *pgxpool.Pool, now time.Time, o *Overview) error {
	cutoff := isoSeconds(now.Add(-mailStuckMinutes * time.Minute))
	const where = `FROM email_outbox WHERE state IN ('failed', 'bounced', 'complained')
		OR (state = 'queued' AND created_at < $1)
		OR (state = 'sending' AND updated_at < $2)`
	if err := pool.QueryRow(ctx, "SELECT COUNT(*) "+where, cutoff, cutoff).Scan(&o.MailCount); err != nil {
		return err
	}
	rows, err := pool.Query(ctx, "SELECT id, kind, state, attempts, created_at "+where+" ORDER BY created_at LIMIT $3",
		cutoff, cutoff, rowLimit)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var m MailRow
		var created string
		if err := rows.Scan(&m.OutboxID, &m.Kind, &m.State, &m.Attempts, &created); err != nil {
			return err
		}
		m.AgeMinutes = ageMinutes(&created, now)
		o.Mail = append(o.Mail, m)
	}
	return rows.Err()
}

func loadAlerts(ctx context.Context, pool *pgxpool.Pool, now time.Time, o *Overview) error {
	rows, err := pool.Query(ctx, `SELECT kind, level, COUNT(*) AS n, MIN(created_at) AS oldest
		FROM alert WHERE resolved_at IS NULL
		GROUP BY kind, level ORDER BY n DESC, kind LIMIT $1`, rowLimit)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var a AlertRow
		var oldest *string
		if err := rows.Scan(&a.Kind, &a.Level, &a.Count, &oldest); err != nil {
			return err
		}
		a.AgeMinutes = ageMinutes(oldest, now)
		o.AlertsCount += a.Count
		o.Alerts = append(o.Alerts, a)
	}
	return rows.Err()
}

func loadTTLock(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now time.Time, o *Overview) error {
	u := now.UTC()
	t := TTLock{Limit: envInt(getenv, "UBYHOST_TTLOCK_MONTHLY_CALLS", defaultTTLockMonthly),
		Enabled: envFlag(getenv, "UBYHOST_DOOR_CODES"), Live: envFlag(getenv, "UBYHOST_DOOR_CODES_LIVE")}
	var calls *int64
	err := pool.QueryRow(ctx, `SELECT calls FROM lock_api_usage WHERE month = $1 AND provider = 'ttlock'`,
		u.Format("2006-01")).Scan(&calls)
	if err != nil && !isNoRows(err) {
		return err
	}
	if calls != nil {
		t.Used = *calls
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM door_code WHERE state = 'issued' AND issued_at >= $1`,
		u.Format("2006-01")+"-01T00:00:00+00:00").Scan(&t.Issued); err != nil {
		return err
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM door_code WHERE state IN ('failed', 'revoke_failed')`).
		Scan(&t.Failed); err != nil {
		return err
	}
	o.TTLock = t
	return nil
}

// LoadOverview is admin_ops.overview() at now.
func LoadOverview(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now time.Time) (Overview, error) {
	var o Overview
	for _, step := range []func() error{
		func() error { return loadFilings(ctx, pool, now, &o) },
		func() error { return loadStuck(ctx, pool, now, &o) },
		func() error { return loadFeeds(ctx, pool, now, &o) },
		func() error { return loadJobs(ctx, pool, getenv, now, &o) },
		func() error { return loadMail(ctx, pool, now, &o) },
		func() error { return loadAlerts(ctx, pool, now, &o) },
		func() error { return loadTTLock(ctx, pool, getenv, now, &o) },
	} {
		if err := step(); err != nil {
			return Overview{}, err
		}
	}
	return o, nil
}

// Incident is a security_incident row with the columns the page reads.
type Incident struct {
	ID                        int64
	DetectedAt, Summary       string
	DataCategories, RiskLevel *string
	ApproxSubjects            *int64
	AffectedOwnerIDs          *string
	Stamps                    map[string]*string // the TIMESTAMP_FIELDS
	ContactsForDraft          []string
}

// ownerIDs is incidents.affected_owner_ids: the JSON list as ints, [] when
// it does not read. A JSON string is iterated character by character, as
// Python does; a JSON object gives [] (Python would iterate its keys).
func ownerIDs(raw *string) []int64 {
	text := "[]"
	if raw != nil && *raw != "" {
		text = *raw
	}
	dec := json.NewDecoder(strings.NewReader(text))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil || dec.More() {
		return []int64{}
	}
	var items []any
	switch x := v.(type) {
	case []any:
		items = x
	case string:
		for _, r := range x {
			items = append(items, string(r))
		}
	default:
		return []int64{}
	}
	out := make([]int64, 0, len(items))
	for _, item := range items {
		switch x := item.(type) {
		case json.Number:
			if n, err := x.Int64(); err == nil {
				out = append(out, n)
			} else if f, err := x.Float64(); err == nil && !math.IsInf(f, 0) && !math.IsNaN(f) {
				out = append(out, int64(f)) // int(3.9) == 3
			} else {
				return []int64{}
			}
		case string:
			n, ok := pyInt(x)
			if !ok {
				return []int64{}
			}
			out = append(out, n)
		case bool:
			if x {
				out = append(out, 1)
			} else {
				out = append(out, 0)
			}
		default: // None, a list or an object: TypeError
			return []int64{}
		}
	}
	return out
}

// LoadIncidents is incidents.list_all() with each incident's controller
// contacts (controller_notification_draft reads them per affected owner).
func LoadIncidents(ctx context.Context, pool *pgxpool.Pool) ([]Incident, error) {
	rows, err := pool.Query(ctx, `SELECT id, detected_at, summary, data_categories, approx_subjects, risk_level,
		affected_owner_ids, contained_at, controllers_notified_at, authority_notified_at, subjects_notified_at, closed_at
		FROM security_incident ORDER BY detected_at DESC, id DESC`)
	if err != nil {
		return nil, err
	}
	var out []Incident
	for rows.Next() {
		var in Incident
		s := make([]*string, len(incidentTimestamps))
		if err := rows.Scan(&in.ID, &in.DetectedAt, &in.Summary, &in.DataCategories, &in.ApproxSubjects, &in.RiskLevel,
			&in.AffectedOwnerIDs, &s[0], &s[1], &s[2], &s[3], &s[4]); err != nil {
			rows.Close()
			return nil, err
		}
		in.Stamps = map[string]*string{}
		for i, f := range incidentTimestamps {
			in.Stamps[f[0]] = s[i]
		}
		out = append(out, in)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for i := range out {
		for _, owner := range ownerIDs(out[i].AffectedOwnerIDs) {
			// Python has no ORDER BY here; id order is the order it returns in practice.
			crow, err := pool.Query(ctx, `SELECT name, contact_email FROM legal_entity
				WHERE owner_user_id = $1 AND contact_email IS NOT NULL ORDER BY id`, owner)
			if err != nil {
				return nil, err
			}
			for crow.Next() {
				var name, email string
				if err := crow.Scan(&name, &email); err != nil {
					crow.Close()
					return nil, err
				}
				out[i].ContactsForDraft = append(out[i].ContactsForDraft, name+" <"+email+">")
			}
			crow.Close()
			if err := crow.Err(); err != nil {
				return nil, err
			}
		}
	}
	return out, nil
}

// Draft is incidents.controller_notification_draft: the notice to copy.
func Draft(in Incident) string {
	dash := func(p *string) string {
		if p == nil || *p == "" {
			return "-"
		}
		return *p
	}
	approx := "-"
	if in.ApproxSubjects != nil {
		approx = strconv.FormatInt(*in.ApproxSubjects, 10)
	}
	to := "(no controller contact on file)"
	if len(in.ContactsForDraft) > 0 {
		to = strings.Join(in.ContactsForDraft, "; ")
	}
	return strings.Join([]string{
		"Subject: Notification of a personal-data incident (Art 33(2) GDPR)",
		"",
		"Detected: " + in.DetectedAt,
		"Summary: " + in.Summary,
		"Data categories: " + dash(in.DataCategories),
		"Approximate data subjects: " + approx,
		"Risk: " + dash(in.RiskLevel),
		"",
		"To: " + to,
		"",
		"We are notifying you without undue delay as your processor. As controller you must",
		"assess the incident and, where required, notify the supervisory authority (UOOU)",
		"within 72 hours of becoming aware. Please confirm receipt and tell us what you need.",
	}, "\n")
}

// ReviewAlert is one open incident_review alert.
type ReviewAlert struct {
	Message string
	Detail  *string
}

// LoadReviewAlerts is incidents.open_review_alerts().
func LoadReviewAlerts(ctx context.Context, pool *pgxpool.Pool) ([]ReviewAlert, error) {
	rows, err := pool.Query(ctx, `SELECT message, detail FROM alert
		WHERE kind = 'incident_review' AND resolved_at IS NULL ORDER BY id DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []ReviewAlert
	for rows.Next() {
		var a ReviewAlert
		if err := rows.Scan(&a.Message, &a.Detail); err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// Owner is one entry of the "Affected hosts" checklist.
type Owner struct {
	ID       int64
	Username string
}

// LoadOwners is db.query("SELECT id, username FROM user_account ORDER BY username").
func LoadOwners(ctx context.Context, pool *pgxpool.Pool) ([]Owner, error) {
	rows, err := pool.Query(ctx, `SELECT id, username FROM user_account ORDER BY username`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Owner
	for rows.Next() {
		var o Owner
		if err := rows.Scan(&o.ID, &o.Username); err != nil {
			return nil, err
		}
		out = append(out, o)
	}
	return out, rows.Err()
}
