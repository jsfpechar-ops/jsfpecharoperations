package lifecyclemail

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"slices"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// errDB is every database failure: the cause can carry an address, so it is dropped.
var errDB = errors.New("lifecyclemail: database error")

const (
	// maxLateDays is MAX_LATE_DAYS.
	maxLateDays = 30
	// sendHourLocal is SEND_HOUR_LOCAL.
	sendHourLocal = 9
	// LastRunKey is LAST_RUN_KEY, the settings row holding the last local day run.
	LastRunKey = "lifecycle_mail_last_day"
	// suppressionScope is SUPPRESSION_SCOPE.
	suppressionScope = "onboarding"
)

// trigger is one entry of TRIGGERS: the kind and the days after its anchor.
type trigger struct {
	kind string
	days int
}

var triggers = []trigger{
	{"lifecycle_no_property", 3},
	{"lifecycle_no_calendar", 3},
	{"lifecycle_no_guest", 14},
}

const (
	firstLogin = "COALESCE((SELECT MIN(au.at) FROM audit au WHERE au.owner_user_id = u.id " +
		"AND au.action IN ('login', 'two_factor_login')), u.last_login_at)"
	firstProperty = "(SELECT MIN(a.created_at) FROM apartment a WHERE a.owner_user_id = u.id)"
	firstCalendar = "(SELECT MIN(f.created_at) FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id " +
		"WHERE a.owner_user_id = u.id AND f.last_status = 'ok')"
)

// rule is one _RULES entry: the anchor timestamp and the condition that makes the tip moot.
type rule struct{ anchor, moot string }

var rules = map[string]rule{
	"lifecycle_no_property": {
		firstLogin,
		"NOT EXISTS (SELECT 1 FROM apartment a WHERE a.owner_user_id = u.id)",
	},
	"lifecycle_no_calendar": {
		firstProperty,
		"NOT EXISTS (SELECT 1 FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id " +
			"WHERE a.owner_user_id = u.id AND f.active = 1)",
	},
	"lifecycle_no_guest": {
		firstCalendar,
		"NOT EXISTS (SELECT 1 FROM reservation r JOIN apartment a ON a.id = r.apartment_id " +
			"WHERE a.owner_user_id = u.id AND r.registration_completed_at IS NOT NULL " +
			"AND COALESCE(r.source, '') != 'demo')",
	},
}

// iso is _iso: UTC, whole seconds, "+00:00".
func iso(moment time.Time) string {
	return moment.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// getSetting is db.get_setting.
func getSetting(ctx context.Context, pool *pgxpool.Pool, key string) (string, bool, error) {
	var value *string
	err := pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, key).Scan(&value)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	if err != nil {
		return "", false, errDB
	}
	if value == nil {
		return "", true, nil
	}
	return *value, true, nil
}

// setSetting is db.set_setting.
func setSetting(ctx context.Context, pool *pgxpool.Pool, key, value string) error {
	if _, err := pool.Exec(ctx,
		`INSERT INTO settings (key, value) VALUES ($1, $2)
		 ON CONFLICT(key) DO UPDATE SET value = excluded.value`, key, value); err != nil {
		return errDB
	}
	return nil
}

// WorkspaceContactEmails is mail_notify.workspace_contact_emails: every
// distinct normalised contact address on the workspace's legal entities.
func WorkspaceContactEmails(ctx context.Context, pool *pgxpool.Pool, ownerUserID int64) ([]string, error) {
	rows, err := pool.Query(ctx,
		`SELECT contact_email FROM legal_entity WHERE owner_user_id = $1 ORDER BY id`, ownerUserID)
	if err != nil {
		return nil, errDB
	}
	defer rows.Close()
	found := []string{}
	for rows.Next() {
		var raw *string
		if err := rows.Scan(&raw); err != nil {
			return nil, errDB
		}
		if raw == nil {
			continue
		}
		address := ubyport.NormaliseEmail(*raw)
		if address == "" {
			continue
		}
		if !slices.Contains(found, address) {
			found = append(found, address)
		}
	}
	if err := rows.Err(); err != nil {
		return nil, errDB
	}
	return found, nil
}

// IsOptedOut is lifecycle_mail.is_opted_out.
func IsOptedOut(ctx context.Context, pool *pgxpool.Pool, userID int64) (bool, error) {
	var flag *int64
	err := pool.QueryRow(ctx,
		`SELECT onboarding_emails_opt_out FROM user_account WHERE id = $1`, userID).Scan(&flag)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, errDB
	}
	return flag != nil && *flag != 0, nil
}

// IsSuppressed is lifecycle_mail.is_suppressed.
func (c Config) IsSuppressed(ctx context.Context, pool *pgxpool.Pool, address string) (bool, error) {
	digest := EmailHash(c.SecretKey, address)
	if digest == "" {
		return false, nil
	}
	var one int
	err := pool.QueryRow(ctx,
		`SELECT 1 AS x FROM mail_suppression WHERE email_hash = $1 AND scope = $2`,
		digest, suppressionScope).Scan(&one)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, errDB
	}
	return true, nil
}

// Candidates is lifecycle_mail.candidates: host accounts due for kind at now.
func Candidates(ctx context.Context, pool *pgxpool.Pool, kind string, now time.Time) ([]int64, error) {
	r, ok := rules[kind]
	if !ok {
		return nil, fmt.Errorf("%w %s", ErrKind, kind)
	}
	days := 0
	for _, t := range triggers {
		if t.kind == kind {
			days = t.days
		}
	}
	dueBefore := iso(now.Add(-time.Duration(days) * 24 * time.Hour))
	tooLateBefore := iso(now.Add(-time.Duration(days+maxLateDays) * 24 * time.Hour))
	rows, err := pool.Query(ctx,
		"SELECT u.id FROM user_account u WHERE u.role = 'host' AND u.active = 1 "+
			"AND u.deletion_due_at IS NULL AND COALESCE(u.onboarding_emails_opt_out, 0) = 0 "+
			"AND NOT EXISTS (SELECT 1 FROM lifecycle_mail_sent m "+
			"WHERE m.user_account_id = u.id AND m.kind = $1) "+
			"AND "+r.moot+" "+
			"AND "+r.anchor+" <= $2 AND "+r.anchor+" >= $3 "+
			"ORDER BY u.id LIMIT 500",
		kind, dueBefore, tooLateBefore)
	if err != nil {
		return nil, errDB
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, errDB
		}
		ids = append(ids, id)
	}
	if err := rows.Err(); err != nil {
		return nil, errDB
	}
	return ids, nil
}

// claim is _claim: write the sent marker first; false when a run already did.
func claim(ctx context.Context, pool *pgxpool.Pool, userID int64, kind string) (bool, error) {
	tag, err := pool.Exec(ctx,
		`INSERT INTO lifecycle_mail_sent (user_account_id, kind, sent_at) VALUES ($1, $2, $3)
		 ON CONFLICT (user_account_id, kind) DO NOTHING`, userID, kind, ubyport.UTCNow())
	if err != nil {
		return false, errDB
	}
	return tag.RowsAffected() == 1, nil
}

// release is _release.
func release(ctx context.Context, pool *pgxpool.Pool, userID int64, kind string) error {
	if _, err := pool.Exec(ctx,
		`DELETE FROM lifecycle_mail_sent WHERE user_account_id = $1 AND kind = $2`, userID, kind); err != nil {
		return errDB
	}
	return nil
}

// pyPayload is json.dumps of the tip's payload: text, html, lang, reply_to,
// list_unsubscribe, in that order, default separators, ensure_ascii.
func pyPayload(text, html, lang, replyTo, listUnsubscribe string) string {
	return `{"text": ` + ubyport.PyString(text) +
		`, "html": ` + ubyport.PyString(html) +
		`, "lang": ` + ubyport.PyString(lang) +
		`, "reply_to": ` + ubyport.PyString(replyTo) +
		`, "list_unsubscribe": ` + ubyport.PyString(listUnsubscribe) + `}`
}

// enqueue is mail.enqueue for a lifecycle kind: nothing when the backend is
// off or the address does not normalise, otherwise the outbox row (an
// existing idempotency key returns the row already there). It reports whether
// a row exists.
func (c Config) enqueue(ctx context.Context, pool *pgxpool.Pool, kind, key, to, subject, payload string, ownerUserID int64) bool {
	if !c.mailEnabled() {
		return false
	}
	to = ubyport.NormaliseEmail(to)
	if to == "" {
		return false
	}
	owner := ownerUserID
	id, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:        kind,
		Key:         key,
		OwnerUserID: &owner,
		To:          to,
		Subject:     subject,
		Payload:     payload,
	})
	if err != nil {
		slog.Error("lifecycle mail enqueue failed", "kind", kind, "user", ownerUserID)
		return false
	}
	return id != 0
}

// sendOne is send_one: queue kind to every contact address of the account.
func (c Config) sendOne(ctx context.Context, pool *pgxpool.Pool, userID int64, kind string) (int, error) {
	opted, err := IsOptedOut(ctx, pool, userID)
	if err != nil || opted {
		return 0, err
	}
	contacts, err := WorkspaceContactEmails(ctx, pool, userID)
	if err != nil {
		return 0, err
	}
	var addresses []string
	for _, address := range contacts {
		suppressed, err := c.IsSuppressed(ctx, pool, address)
		if err != nil {
			return 0, err
		}
		if !suppressed {
			addresses = append(addresses, address)
		}
	}
	if len(addresses) == 0 {
		// Nowhere to send yet. No marker, so a later run can still reach them.
		return 0, nil
	}
	won, err := claim(ctx, pool, userID, kind)
	if err != nil || !won {
		return 0, err
	}
	queued := 0
	for _, address := range addresses {
		link, err := c.UnsubscribeURL(userID, address, hostMailLanguage)
		if err != nil {
			return queued, errDB
		}
		content, err := c.BuildLifecycle(kind, link, hostMailLanguage)
		if err != nil {
			return queued, err
		}
		payload := pyPayload(content.Text, content.HTML, hostMailLanguage, c.OperatorEmail, link)
		if c.enqueue(ctx, pool, kind, fmt.Sprintf("lifecycle:%s:%d:%s", kind, userID, address),
			address, content.Subject, payload, userID) {
			queued++
		}
	}
	if queued == 0 {
		if err := release(ctx, pool, userID, kind); err != nil {
			return 0, err
		}
	}
	return queued, nil
}

// run is run(): evaluate every trigger once. Empty while the switch is off.
func (c Config) run(ctx context.Context, pool *pgxpool.Pool, now time.Time) (map[string]int, error) {
	summary := map[string]int{}
	if !c.LifecycleMail || !c.mailEnabled() {
		return summary, nil
	}
	if !c.senderIdentified() {
		slog.Warn("lifecycle mail skipped: UBYHOST_OPERATOR_NAME, _ICO or _ADDRESS is empty")
		return summary, nil
	}
	if strings.TrimSpace(c.SecretKey) == "" {
		return summary, errors.New("lifecyclemail: no secret key (UBYHOST_SECRET_KEY or the key file)")
	}
	for _, t := range triggers {
		summary[t.kind] = 0
	}
	for _, t := range triggers {
		ids, err := Candidates(ctx, pool, t.kind, now)
		if err != nil {
			return summary, err
		}
		for _, userID := range ids {
			n, err := c.sendOne(ctx, pool, userID, t.kind)
			if err != nil {
				slog.Error("lifecycle mail failed", "kind", t.kind, "user", userID, "err", err.Error())
				continue
			}
			if n > 0 {
				summary[t.kind]++
			}
		}
	}
	return summary, nil
}

// RunDaily is run_daily: the mail job's step. At most one run per local day,
// after 09:00 Europe/Prague. It returns an empty map when it did nothing.
func RunDaily(ctx context.Context, pool *pgxpool.Pool, cfg Config, now time.Time) (map[string]int, error) {
	if !cfg.LifecycleMail || !cfg.mailEnabled() {
		return map[string]int{}, nil
	}
	loc, err := time.LoadLocation(Timezone)
	if err != nil {
		return nil, errors.New("lifecyclemail: time zone unavailable")
	}
	local := now.In(loc)
	today := local.Format("2006-01-02")
	if local.Hour() < sendHourLocal {
		return map[string]int{}, nil
	}
	last, _, err := getSetting(ctx, pool, LastRunKey)
	if err != nil {
		return nil, err
	}
	if last == today {
		return map[string]int{}, nil
	}
	if cfg.senderIdentified() && strings.TrimSpace(cfg.SecretKey) == "" {
		// Before the marker, so a missing key does not use up the day.
		return nil, errors.New("lifecyclemail: no secret key (UBYHOST_SECRET_KEY or the key file)")
	}
	if err := setSetting(ctx, pool, LastRunKey, today); err != nil {
		return nil, err
	}
	return cfg.run(ctx, pool, now)
}
