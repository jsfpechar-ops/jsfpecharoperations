package billingjob

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const isoDate = "2006-01-02"

// jobAccount is the billing_account row the run reads (billing.account). Text
// columns the run tests for truthiness are COALESCEd to "".
type jobAccount struct {
	Owner                        int64
	Status                       string
	Plan, Interval               *string
	AddonTTLock, AddonWhitelabel bool
	ApartmentsBilled             int64
	DiscountPercent              int64
	PeriodStart, PeriodEnd       string
	PendingJSON                  string
	TrialEndsAt                  string
}

const accountColumns = `owner_user_id, status, plan, billing_interval, addon_ttlock, addon_whitelabel,
	apartments_billed, discount_percent, COALESCE(period_start, ''), COALESCE(period_end, ''),
	COALESCE(pending_change_json, ''), COALESCE(trial_ends_at, '')`

type scanner interface{ Scan(dest ...any) error }

func scanAccount(row scanner) (jobAccount, error) {
	var a jobAccount
	var ttlock, whitelabel int64
	err := row.Scan(&a.Owner, &a.Status, &a.Plan, &a.Interval, &ttlock, &whitelabel,
		&a.ApartmentsBilled, &a.DiscountPercent, &a.PeriodStart, &a.PeriodEnd, &a.PendingJSON, &a.TrialEndsAt)
	a.AddonTTLock, a.AddonWhitelabel = ttlock != 0, whitelabel != 0
	return a, err
}

type rowQuerier interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// loadAccount is billing.account: nil when the owner has no row.
func loadAccount(ctx context.Context, q rowQuerier, owner int64) (*jobAccount, error) {
	a, err := scanAccount(q.QueryRow(ctx,
		`SELECT `+accountColumns+` FROM billing_account WHERE owner_user_id = $1`, owner))
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// billedAccounts is _accounts(BILLED): hosts with an ordered plan in a billed
// status, in owner order, read before the loop starts as Python reads them.
func (r *Runner) billedAccounts(ctx context.Context) ([]jobAccount, error) {
	rows, err := r.Pool.Query(ctx,
		`SELECT `+accountColumns+` FROM billing_account
		 WHERE status IN ('active', 'overdue', 'canceling') AND plan IS NOT NULL
		   AND ($1::bigint = 0 OR owner_user_id = $1)
		 ORDER BY owner_user_id`, r.Owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []jobAccount
	for rows.Next() {
		a, err := scanAccount(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

// parseDate is date.fromisoformat(value[:10]).
func parseDate(value string) (time.Time, error) {
	if len(value) > 10 {
		value = value[:10]
	}
	t, err := time.Parse(isoDate, value)
	if err != nil {
		return time.Time{}, fmt.Errorf("invalid date %q", value)
	}
	return t, nil
}

func pyOptional(s *string) string {
	if s == nil {
		return "None"
	}
	return *s
}

// apartments is billing_order.apartments: the active apartments, at least one.
func apartments(ctx context.Context, q rowQuerier, owner int64) (int64, error) {
	var n int64
	if err := q.QueryRow(ctx,
		`SELECT COUNT(*) FROM apartment WHERE owner_user_id = $1 AND active = 1`, owner).Scan(&n); err != nil {
		return 0, err
	}
	if n < 1 {
		n = 1
	}
	return n, nil
}

// periodEnd is billing_trial.period_end: the last day of the month or year that
// starts on start (31 January runs to the end of February).
func periodEnd(start time.Time, interval string) time.Time {
	year, month := start.Year()+int(start.Month())/12, int(start.Month())%12+1
	if interval == "year" {
		year, month = start.Year()+1, int(start.Month())
	}
	last := time.Date(year, time.Month(month)+1, 0, 0, 0, 0, 0, time.UTC).Day()
	if start.Day() > last {
		return time.Date(year, time.Month(month), last, 0, 0, 0, 0, time.UTC)
	}
	return time.Date(year, time.Month(month), start.Day(), 0, 0, 0, 0, time.UTC).AddDate(0, 0, -1)
}

var transitions = map[string][]string{
	"trial_pending": {"trialing"},
	"trialing":      {"active", "paused"},
	"active":        {"overdue", "canceling"},
	"overdue":       {"active", "paused"},
	"canceling":     {"paused", "active"},
	"paused":        {"active"},
}

// setStatus is billing.set_status: move the account if the state machine allows
// it, under the same advisory lock as Python; false otherwise. The audit row
// (billing_status, "old->new") follows the commit.
func setStatus(ctx context.Context, pool *pgxpool.Pool, owner int64, next, actor string) (bool, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck // no-op after commit
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "billing_account", int32(owner)); err != nil {
		return false, err
	}
	var old string
	err = tx.QueryRow(ctx, `SELECT status FROM billing_account WHERE owner_user_id = $1`, owner).Scan(&old)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	allowed := false
	for _, s := range transitions[old] {
		allowed = allowed || s == next
	}
	if !allowed {
		return false, nil
	}
	if _, err := tx.Exec(ctx, `UPDATE billing_account SET status = $1, updated_at = $2 WHERE owner_user_id = $3`,
		next, ubyport.UTCNow(), owner); err != nil {
		return false, err
	}
	if err := tx.Commit(ctx); err != nil {
		return false, err
	}
	if err := audit(ctx, pool, actor, "billing_status", old+"->"+next, &owner); err != nil {
		return true, err
	}
	return true, nil
}

// audit is db.audit for a background caller: no signed-in user, so both user ids
// are NULL.
func audit(ctx context.Context, pool *pgxpool.Pool, actor, action, detail string, owner *int64) error {
	_, err := pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		 VALUES ($1, $2, $3, $4, $5, NULL, NULL)`, ubyport.UTCNow(), actor, action, detail, owner)
	return err
}

// pending is the decoded pending_change_json of an account.
type pending struct {
	values map[string]any
}

// parsePending is json.loads(text or "{}"); numbers stay json.Number.
func parsePending(text string) (pending, error) {
	if strings.TrimSpace(text) == "" {
		return pending{values: map[string]any{}}, nil
	}
	dec := json.NewDecoder(strings.NewReader(text))
	dec.UseNumber()
	var m map[string]any
	if err := dec.Decode(&m); err != nil {
		return pending{}, fmt.Errorf("pending_change_json: %w", err)
	}
	if m == nil {
		return pending{}, errors.New("pending_change_json is not an object")
	}
	return pending{values: m}, nil
}

// text is pending.get(key, fallback) for a text column.
func (p pending) text(key string, fallback *string) (*string, error) {
	v, ok := p.values[key]
	if !ok {
		return fallback, nil
	}
	switch s := v.(type) {
	case string:
		return &s, nil
	case nil:
		return nil, nil
	}
	return nil, fmt.Errorf("pending_change_json: %s is not text", key)
}

// flag is int(pending.get(key, fallback)) for an add-on column.
func (p pending) flag(key string, fallback bool) (int64, error) {
	v, ok := p.values[key]
	if !ok {
		if fallback {
			return 1, nil
		}
		return 0, nil
	}
	switch n := v.(type) {
	case bool:
		if n {
			return 1, nil
		}
		return 0, nil
	case json.Number:
		i, err := n.Int64()
		if err != nil {
			return 0, fmt.Errorf("pending_change_json: %s is not a whole number", key)
		}
		return i, nil
	}
	return 0, fmt.Errorf("pending_change_json: %s is not a number", key)
}

// equalsInt is pending.get(key) == n.
func (p pending) equalsInt(key string, n int64) bool {
	switch v := p.values[key].(type) {
	case json.Number:
		f, err := v.Float64()
		return err == nil && f == float64(n)
	case bool:
		return (v && n == 1) || (!v && n == 0)
	}
	return false
}

// dump is json.dumps(pending, sort_keys=True): keys sorted, ", " and ": ", ASCII only.
func (p pending) dump() string {
	keys := make([]string, 0, len(p.values))
	for k := range p.values {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var b bytes.Buffer
	b.WriteByte('{')
	for i, k := range keys {
		if i > 0 {
			b.WriteString(", ")
		}
		b.WriteString(ubyport.PyString(k))
		b.WriteString(": ")
		b.WriteString(dumpValue(p.values[k]))
	}
	b.WriteByte('}')
	return b.String()
}

// jsonNumber is an integer as a decoded JSON number.
func jsonNumber(n int64) json.Number { return json.Number(strconv.FormatInt(n, 10)) }

func dumpValue(v any) string {
	switch x := v.(type) {
	case nil:
		return "null"
	case bool:
		if x {
			return "true"
		}
		return "false"
	case json.Number:
		return x.String()
	case string:
		return ubyport.PyString(x)
	}
	raw, _ := json.Marshal(v) // nested values do not occur in practice
	return string(raw)
}
