package billing

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// The subscription engine: a port of App/app/billing.py (account, status
// machine, plan changes, discount) and of App/app/billing_order.py (see
// order.go). Python is the oracle: testdata/engine_golden.json is written by
// App/scripts/billing_engine_golden.py and engine_test.go must match it.
// Nothing here is registered as a route or a job.

// Statuses is billing.STATUSES.
var Statuses = []string{"trial_pending", "trialing", "active", "overdue", "canceling", "paused"}

// Transitions is billing.TRANSITIONS: the moves SetStatus allows.
var Transitions = map[string][]string{
	"trial_pending": {"trialing"},
	"trialing":      {"active", "paused"},
	"active":        {"overdue", "canceling"},
	"overdue":       {"active", "paused"},
	"canceling":     {"paused", "active"},
	"paused":        {"active"},
}

// Plans is billing.PLANS, Intervals is billing.INTERVALS.
var (
	Plans     = []string{"standard", "max"}
	Intervals = []string{"month", "year"}
)

// SupplementaryMinCZK is billing.SUPPLEMENTARY_MIN_CZK: a smaller amount is
// carried to the next invoice instead.
const SupplementaryMinCZK = 50

// ChangeColumns is billing.CHANGE_COLUMNS: change field -> billing_account column.
var ChangeColumns = map[string]string{
	"apartments":       "apartments_billed",
	"plan":             "plan",
	"billing_interval": "billing_interval",
	"addon_ttlock":     "addon_ttlock",
	"addon_whitelabel": "addon_whitelabel",
}

// DB is what a read or a single statement needs; *pgxpool.Pool and pgx.Tx fit.
type DB interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// BillingAccount is one billing_account row. A NULL text column reads as "".
type BillingAccount struct {
	OwnerUserID       int64
	Status            string
	Plan              string // "" until a plan is ordered
	BillingInterval   string
	PaymentMethod     string
	Founder           bool
	AddonTTLock       bool
	AddonWhitelabel   bool
	ApartmentsBilled  int
	TrialStartedAt    string
	TrialEndsAt       string
	PeriodStart       string
	PeriodEnd         string
	CancelAtPeriodEnd bool
	PendingChangeJSON string
	CarryCZK          int
	BuyerName         string
	BuyerStreet       string
	BuyerCity         string
	BuyerZip          string
	BuyerICO          string
	BuyerDIC          string
	BuyerEmail        string
	UpdatedAt         string
	DiscountPercent   int
	DiscountReason    string
}

const accountSQL = `SELECT owner_user_id, status, COALESCE(plan, ''), COALESCE(billing_interval, ''),
	payment_method, founder, addon_ttlock, addon_whitelabel, apartments_billed,
	COALESCE(trial_started_at, ''), COALESCE(trial_ends_at, ''), COALESCE(period_start, ''),
	COALESCE(period_end, ''), cancel_at_period_end, COALESCE(pending_change_json, ''), carry_czk,
	COALESCE(buyer_name, ''), COALESCE(buyer_street, ''), COALESCE(buyer_city, ''),
	COALESCE(buyer_zip, ''), COALESCE(buyer_ico, ''), COALESCE(buyer_dic, ''),
	COALESCE(buyer_email, ''), updated_at, discount_percent, COALESCE(discount_reason, '')
	FROM billing_account WHERE owner_user_id = $1`

// Account is billing.account: the host's row, or nil when there is none.
func Account(ctx context.Context, q DB, owner int64) (*BillingAccount, error) {
	var a BillingAccount
	var founder, ttlock, white, cancel int
	err := q.QueryRow(ctx, accountSQL, owner).Scan(
		&a.OwnerUserID, &a.Status, &a.Plan, &a.BillingInterval, &a.PaymentMethod,
		&founder, &ttlock, &white, &a.ApartmentsBilled, &a.TrialStartedAt, &a.TrialEndsAt,
		&a.PeriodStart, &a.PeriodEnd, &cancel, &a.PendingChangeJSON, &a.CarryCZK,
		&a.BuyerName, &a.BuyerStreet, &a.BuyerCity, &a.BuyerZip, &a.BuyerICO, &a.BuyerDIC,
		&a.BuyerEmail, &a.UpdatedAt, &a.DiscountPercent, &a.DiscountReason)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	a.Founder, a.AddonTTLock, a.AddonWhitelabel = founder != 0, ttlock != 0, white != 0
	a.CancelAtPeriodEnd = cancel != 0
	return &a, nil
}

// EnsureAccount is billing.ensure_account: the row, created as trial_pending
// the first time.
func EnsureAccount(ctx context.Context, q DB, owner int64) (*BillingAccount, error) {
	if _, err := q.Exec(ctx, `INSERT INTO billing_account (owner_user_id, status, updated_at)
		VALUES ($1, 'trial_pending', $2) ON CONFLICT (owner_user_id) DO NOTHING`,
		owner, ubyport.UTCNow()); err != nil {
		return nil, err
	}
	return Account(ctx, q, owner)
}

// ApartmentCount is billing.apartment_count: the host's active apartments.
func ApartmentCount(ctx context.Context, q DB, owner int64) (int, error) {
	var n int
	err := q.QueryRow(ctx, `SELECT COUNT(*) FROM apartment WHERE owner_user_id = $1 AND active = 1`, owner).Scan(&n)
	return n, err
}

type auditActorKey struct{}

type auditActor struct {
	userID       int64
	username     string
	impersonator *int64
}

// WithAuditActor is db.set_current_actor for Go: it remembers who is acting so
// the audit rows written with the returned context carry actor_user_id and
// impersonator_user_id, and an actor "host" is replaced by username, exactly as
// db.audit does. impersonatorUserID is the acting user's own id only while they
// are inside another workspace (the page passes nil for an ordinary action).
// Without it the columns stay NULL and the actor string is written as given.
func WithAuditActor(ctx context.Context, userID int64, username string, impersonatorUserID *int64) context.Context {
	return context.WithValue(ctx, auditActorKey{}, auditActor{userID, username, impersonatorUserID})
}

func auditActorFrom(ctx context.Context) (auditActor, bool) {
	a, ok := ctx.Value(auditActorKey{}).(auditActor)
	return a, ok
}

// audit is db.audit. The engine always receives the owner, so Python's
// fallback to the request's current owner (db._current_owner_id) is never
// needed here.
func audit(ctx context.Context, q DB, actor, action, detail string, owner int64) error {
	var actorID, impersonatorID *int64
	if a, ok := auditActorFrom(ctx); ok {
		id := a.userID
		actorID, impersonatorID = &id, a.impersonator
		if actor == "host" {
			actor = a.username
		}
	}
	_, err := q.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`, ubyport.UTCNow(), actor, action, detail, owner, actorID, impersonatorID)
	return err
}

// lockKey is db.lock_key on PostgreSQL: serialise writers of one row.
func lockKey(ctx context.Context, tx pgx.Tx, name string, key int64) error {
	_, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2::int4)`, name, key)
	return err
}

func contains(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

// SetStatus is billing.set_status: move the account to new if Transitions
// allows it, false otherwise. The audit row is written after the commit.
func SetStatus(ctx context.Context, pool *pgxpool.Pool, owner int64, newStatus, actor string) (bool, error) {
	if !contains(Statuses, newStatus) {
		return false, fmt.Errorf("%w: %s", ErrUnknownStatus, newStatus)
	}
	old, moved, err := moveStatus(ctx, pool, owner, func(old string) bool {
		return contains(Transitions[old], newStatus)
	}, newStatus)
	if err != nil || !moved {
		return false, err
	}
	if err := audit(ctx, pool, actor, "billing_status", old+"->"+newStatus, owner); err != nil {
		return false, err
	}
	return true, nil
}

// moveStatus locks the account, reads its status and, when allowed(old), sets
// newStatus in the same transaction.
func moveStatus(ctx context.Context, pool *pgxpool.Pool, owner int64, allowed func(old string) bool, newStatus string) (string, bool, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return "", false, err
	}
	defer tx.Rollback(ctx)
	if err := lockKey(ctx, tx, "billing_account", owner); err != nil {
		return "", false, err
	}
	var old string
	err = tx.QueryRow(ctx, `SELECT status FROM billing_account WHERE owner_user_id = $1`, owner).Scan(&old)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	if !allowed(old) {
		return old, false, nil
	}
	if _, err := tx.Exec(ctx, `UPDATE billing_account SET status = $1, updated_at = $2 WHERE owner_user_id = $3`,
		newStatus, ubyport.UTCNow(), owner); err != nil {
		return "", false, err
	}
	if err := tx.Commit(ctx); err != nil {
		return "", false, err
	}
	return old, true, nil
}

// OperatorPause is billing.operator_pause: trial_pending or trialing -> paused,
// for PlaceForOperator only. trial_pending -> paused is the one move outside
// Transitions; SetStatus must keep refusing it. False means already paused or
// another state (Place then decides).
func OperatorPause(ctx context.Context, pool *pgxpool.Pool, owner int64, actor string) (bool, error) {
	old, moved, err := moveStatus(ctx, pool, owner, func(old string) bool {
		return old == "trial_pending" || old == "trialing"
	}, "paused")
	if err != nil || !moved {
		return false, err
	}
	if err := audit(ctx, pool, actor, "billing_status", old+"->paused", owner); err != nil {
		return false, err
	}
	return true, nil
}

// dayOf returns the civil date of t (Y-M-D only); a zero t means now.
func dayOf(t time.Time) time.Time {
	if t.IsZero() {
		t = time.Now()
	}
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC)
}

func isoDay(t time.Time) string { return t.Format("2006-01-02") }

// first10 is Python's s[:10] for an ASCII timestamp.
func first10(s string) string {
	if len(s) > 10 {
		return s[:10]
	}
	return s
}

func parseDay(s string) (time.Time, error) {
	return time.Parse("2006-01-02", first10(s))
}

func wholeMonths(start, end time.Time) int {
	months := (end.Year()-start.Year())*12 + int(end.Month()) - int(start.Month())
	if end.Day() < start.Day() {
		months--
	}
	if months < 0 {
		return 0
	}
	return months
}

// periodState is the dict billing._period_total takes.
type periodState struct {
	apartments int
	plan       string
	interval   string
	ttlock     int
	whitelabel int
	discount   int
}

func (s periodState) total() (int, error) {
	p, err := Quote(s.apartments, s.plan, s.interval, s.ttlock != 0, s.whitelabel != 0, s.discount)
	if err != nil {
		return 0, fmt.Errorf("%w: %v", ErrUnknownPlan, err)
	}
	return p.Total, nil
}

func stateOf(a *BillingAccount) periodState {
	return periodState{
		apartments: a.ApartmentsBilled, plan: a.Plan, interval: a.BillingInterval,
		ttlock: flag(a.AddonTTLock), whitelabel: flag(a.AddonWhitelabel), discount: a.DiscountPercent,
	}
}

// ChangeResult is the dict of billing.apply_change plus the invoice_id that
// billing_order.change adds (0 = none).
type ChangeResult struct {
	When              string `json:"when"` // now, next_period or none
	PeriodTotalBefore int    `json:"period_total_before"`
	PeriodTotalAfter  int    `json:"period_total_after"`
	Months            int    `json:"months"`
	SupplementaryCZK  int    `json:"supplementary_czk"`
	CarryCZK          int    `json:"carry_czk"`
	InvoiceID         int64  `json:"invoice_id"`
}

// normaliseValue turns a change value into what the column stores.
func normaliseValue(field string, value any) (any, error) {
	asInt := func() (int, bool) {
		switch v := value.(type) {
		case int:
			return v, true
		case int64:
			return int(v), true
		case bool:
			return flag(v), true
		}
		return 0, false
	}
	switch field {
	case "plan", "billing_interval":
		if s, ok := value.(string); ok {
			return s, nil
		}
	default:
		if n, ok := asInt(); ok {
			return n, nil
		}
	}
	return nil, fmt.Errorf("%w: %s %T", ErrBadValue, field, value)
}

// ApplyChange is billing.apply_change: preview (confirm false) or save one
// change to an ordered plan. field must be a key of ChangeColumns (anything
// else is ErrOneChange, as Python's "exactly one key" rule). value is an int
// (apartments, add-ons 0 or 1), a bool (add-ons) or a string (plan, interval).
// A rise starts now; on an annual plan it costs the difference for the
// remaining whole months (supplementary, or carried when under 50 Kc). Anything
// else waits for the next period. Issuing the invoice is not done here.
func ApplyChange(ctx context.Context, pool *pgxpool.Pool, owner int64, field string, value any,
	today time.Time, confirm bool, actor string) (ChangeResult, error) {
	column, ok := ChangeColumns[field]
	if !ok {
		return ChangeResult{}, ErrOneChange
	}
	acc, err := Account(ctx, pool, owner)
	if err != nil {
		return ChangeResult{}, err
	}
	if acc == nil || acc.Plan == "" {
		return ChangeResult{}, ErrNoOrderedPlan
	}
	val, err := normaliseValue(field, value)
	if err != nil {
		return ChangeResult{}, err
	}
	if field == "addon_whitelabel" && val.(int) != 0 && !acc.AddonWhitelabel {
		return ChangeResult{}, ErrWhitelabelUnavailable
	}
	current := stateOf(acc)
	target := current
	switch field {
	case "apartments":
		target.apartments = val.(int)
	case "plan":
		target.plan = val.(string)
	case "billing_interval":
		target.interval = val.(string)
	case "addon_ttlock":
		target.ttlock = val.(int)
	case "addon_whitelabel":
		target.whitelabel = val.(int)
	}
	before, err := current.total()
	if err != nil {
		return ChangeResult{}, err
	}
	after, err := target.total()
	if err != nil {
		return ChangeResult{}, err
	}
	when := "next_period"
	if field != "billing_interval" {
		if after == before {
			when = "none"
		} else if after > before {
			when = "now"
		}
	}
	day := dayOf(today)
	months, difference := 0, 0
	if when == "now" && acc.BillingInterval == "year" && acc.PeriodEnd != "" {
		end, err := parseDay(acc.PeriodEnd)
		if err != nil {
			return ChangeResult{}, err
		}
		months = wholeMonths(day, end)
		difference = int(math.RoundToEven(float64((after-before)*months) / 12))
	}
	supplementary := 0
	if difference >= SupplementaryMinCZK {
		supplementary = difference
	}
	result := ChangeResult{
		When: when, PeriodTotalBefore: before, PeriodTotalAfter: after, Months: months,
		SupplementaryCZK: supplementary, CarryCZK: difference - supplementary,
	}
	if !confirm || when == "none" {
		return result, nil
	}
	if when == "now" {
		// column comes from ChangeColumns, never from the caller.
		if _, err := pool.Exec(ctx, "UPDATE billing_account SET "+column+" = $1, carry_czk = carry_czk + $2, updated_at = $3 WHERE owner_user_id = $4",
			val, result.CarryCZK, ubyport.UTCNow(), owner); err != nil {
			return ChangeResult{}, err
		}
	} else {
		pending, err := pendingWith(acc.PendingChangeJSON, field, val)
		if err != nil {
			return ChangeResult{}, err
		}
		if _, err := pool.Exec(ctx, `UPDATE billing_account SET pending_change_json = $1, updated_at = $2 WHERE owner_user_id = $3`,
			pending, ubyport.UTCNow(), owner); err != nil {
			return ChangeResult{}, err
		}
	}
	if err := audit(ctx, pool, actor, "billing_change", field+" "+when, owner); err != nil {
		return ChangeResult{}, err
	}
	return result, nil
}

// pendingWith is json.dumps({**json.loads(raw or "{}"), field: val}, sort_keys=True):
// sorted keys, ", " and ": " separators, ASCII-only strings.
func pendingWith(raw, field string, val any) (string, error) {
	m := map[string]json.RawMessage{}
	if raw != "" {
		if err := json.Unmarshal([]byte(raw), &m); err != nil {
			return "", err
		}
	}
	switch v := val.(type) {
	case int:
		m[field] = json.RawMessage(strconv.Itoa(v))
	case string:
		m[field] = json.RawMessage(ubyport.PyString(v))
	}
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, k := range keys {
		parts = append(parts, ubyport.PyString(k)+": "+string(m[k]))
	}
	return "{" + strings.Join(parts, ", ") + "}", nil
}

// pyStrip is Python str.strip(): unicode.IsSpace plus the separators
// \x1c-\x1f that Python counts as white space.
func pyStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool {
		return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
	})
}

// DiscountResult is the dict of billing.apply_discount.
type DiscountResult struct {
	Percent            int     `json:"percent"`
	Reason             string  `json:"reason"`
	PeriodTotalBefore  int     `json:"period_total_before"`
	PeriodTotalAfter   int     `json:"period_total_after"`
	ReissuedInvoiceIDs []int64 `json:"reissued_invoice_ids"`
}

// ApplyDiscount is billing.apply_discount: set or clear the operator's
// discount (0443). An issued, unpaid, unvoided invoice-kind document is
// storno'd and reissued for the same period; paid or voided ones are never
// touched. The invoice calls go through inv, in Python's order.
func ApplyDiscount(ctx context.Context, pool *pgxpool.Pool, inv Invoicer, owner int64, percent int,
	reason, actor string, today time.Time) (DiscountResult, error) {
	day := dayOf(today)
	if percent < 0 || percent > 100 {
		return DiscountResult{}, ErrDiscountOutOfRange
	}
	reason = pyStrip(reason)
	if r := []rune(reason); len(r) > 200 {
		reason = string(r[:200])
	}
	if percent > 0 && reason == "" {
		return DiscountResult{}, ErrReasonMissing
	}
	acc, err := Account(ctx, pool, owner)
	if err != nil {
		return DiscountResult{}, err
	}
	if acc == nil || acc.Plan == "" {
		return DiscountResult{}, ErrNoPlan
	}
	before, err := stateOf(acc).total()
	if err != nil {
		return DiscountResult{}, err
	}
	var storedReason any
	if reason != "" {
		storedReason = reason
	}
	if _, err := pool.Exec(ctx, `UPDATE billing_account SET discount_percent = $1, discount_reason = $2, updated_at = $3
		WHERE owner_user_id = $4`, percent, storedReason, ubyport.UTCNow(), owner); err != nil {
		return DiscountResult{}, err
	}
	if err := audit(ctx, pool, actor, "billing_discount", fmt.Sprintf("%d %% %s", percent, reason), owner); err != nil {
		return DiscountResult{}, err
	}
	type period struct {
		id       int64
		from, to string
	}
	rows, err := pool.Query(ctx, `SELECT id, period_from, period_to FROM platform_invoice
		WHERE owner_user_id = $1 AND kind = 'invoice' AND voided = 0 AND paid_on IS NULL ORDER BY id`, owner)
	if err != nil {
		return DiscountResult{}, err
	}
	var open []period
	for rows.Next() {
		var p period
		if err := rows.Scan(&p.id, &p.from, &p.to); err != nil {
			rows.Close()
			return DiscountResult{}, err
		}
		open = append(open, p)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return DiscountResult{}, err
	}
	reissued := []int64{}
	for _, p := range open {
		if _, err := inv.Storno(ctx, p.id, fmt.Sprintf("sleva %d %% (%s)", percent, reason), day); err != nil {
			return DiscountResult{}, err
		}
		id, err := inv.IssueForPeriod(ctx, owner, p.from, p.to, day)
		if err != nil {
			return DiscountResult{}, err
		}
		reissued = append(reissued, id)
	}
	refreshed, err := Account(ctx, pool, owner)
	if err != nil {
		return DiscountResult{}, err
	}
	if refreshed == nil {
		return DiscountResult{}, fmt.Errorf("billing account %d vanished", owner)
	}
	st := stateOf(refreshed)
	st.discount = percent
	after, err := st.total()
	if err != nil {
		return DiscountResult{}, err
	}
	return DiscountResult{
		Percent: percent, Reason: reason, PeriodTotalBefore: before, PeriodTotalAfter: after,
		ReissuedInvoiceIDs: reissued,
	}, nil
}
