// Package customers ports the operator's customer pages of
// App/app/routes/admin_customers.py and App/app/admin_customers.py: the bounded
// read-only queries (this file), the admin guard, the funnel redirect and the
// account on/off toggle (handlers.go). The Python files are the reference; each
// function names its source. HTML pages are not here: they wait for the Go host
// layout.
package customers

import (
	"context"
	"errors"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PageSize is admin_customers.PAGE_SIZE.
const PageSize = 25

// States is admin_customers.STATES.
var States = []string{"legacy", "unverified", "disabled", "trial_pending", "trialing",
	"active", "overdue", "canceling", "paused"}

// stateSQL is admin_customers.STATE_SQL.
const stateSQL = "CASE WHEN u.signup_at IS NOT NULL AND u.email_verified_at IS NULL AND u.active = 0 " +
	"THEN 'unverified' WHEN u.active = 0 THEN 'disabled' " +
	"WHEN b.owner_user_id IS NULL THEN 'legacy' ELSE b.status END"

// fromSQL is admin_customers.FROM_SQL.
const fromSQL = " FROM user_account u LEFT JOIN billing_account b ON b.owner_user_id = u.id "

// fieldsSQL is admin_customers.FIELDS.
const fieldsSQL = "u.id, u.username, u.display_name, u.email, u.active, u.created_at, " +
	"u.email_verified_at, u.last_login_at, b.plan, b.billing_interval, " +
	"b.trial_started_at, b.trial_ends_at, b.period_start, b.period_end, " +
	"b.addon_ttlock, b.addon_whitelabel, b.apartments_billed, " +
	stateSQL + " AS customer_state"

// Filters is the dict admin_customers.filters returns.
type Filters struct {
	Q     string `json:"q"`
	State string `json:"state"`
	Plan  string `json:"plan"`
}

// Page is the dict admin_customers.customers returns. Customers holds one map
// per row, keyed by column name, so the JSON matches the Python dicts.
type Page struct {
	Customers []map[string]any `json:"customers"`
	Older     bool             `json:"older"`
	Newer     bool             `json:"newer"`
}

// Consent is the two counts customer_detail reads from ad_click.
type Consent struct {
	Google int64 `json:"google_consent"`
	Meta   int64 `json:"meta_consent"`
}

// pySpace is Python's str.isspace for the characters that occur in text input.
func pySpace(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) }

// pyStrip is Python's str.strip().
func pyStrip(s string) string { return strings.TrimFunc(s, pySpace) }

// NewFilters is admin_customers.filters.
func NewFilters(q, state, plan string) Filters {
	q = pyStrip(q)
	if r := []rune(q); len(r) > 120 {
		q = string(r[:120])
	}
	out := Filters{Q: q}
	if state == "ending" {
		out.State = state
	}
	for _, s := range States {
		if state == s {
			out.State = state
		}
	}
	if plan == "standard" || plan == "max" {
		out.Plan = plan
	}
	return out
}

// Cursor is routes/admin_customers._cursor: ASCII digits only, 1 to 18 of them,
// else 0.
func Cursor(value string) int64 {
	if value == "" || len(value) > 18 {
		return 0
	}
	for i := 0; i < len(value); i++ {
		if value[i] < '0' || value[i] > '9' {
			return 0
		}
	}
	n, err := strconv.ParseInt(value, 10, 64)
	if err != nil {
		return 0
	}
	return n
}

// KC is routes/admin_customers._kc: whole crowns from haler (floor division),
// thousands separated by a space.
func KC(haler int64) string {
	crowns := haler / 100
	if haler%100 < 0 {
		crowns--
	}
	sign := ""
	if crowns < 0 {
		sign, crowns = "-", -crowns
	}
	digits := strconv.FormatInt(crowns, 10)
	var b strings.Builder
	for i, c := range digits {
		if i > 0 && (len(digits)-i)%3 == 0 {
			b.WriteByte(' ')
		}
		b.WriteRune(c)
	}
	return sign + b.String()
}

// where is admin_customers._where with numbered placeholders.
func where(v Filters, today time.Time) (string, []any) {
	clauses := []string{"u.role = 'host'"}
	var args []any
	add := func(value any) string {
		args = append(args, value)
		return "$" + strconv.Itoa(len(args))
	}
	if v.Q != "" {
		term := strings.ToLower(v.Q)
		term = strings.ReplaceAll(term, "!", "!!")
		term = strings.ReplaceAll(term, "%", "!%")
		term = strings.ReplaceAll(term, "_", "!_")
		p := add("%" + term + "%")
		clauses = append(clauses, "(LOWER(COALESCE(u.email, '')) LIKE "+p+" ESCAPE '!' OR "+
			"LOWER(COALESCE(u.display_name, '')) LIKE "+p+" ESCAPE '!' OR "+
			"LOWER(u.username) LIKE "+p+" ESCAPE '!')")
	}
	if v.State == "ending" {
		from := add(today.Format("2006-01-02"))
		to := add(today.AddDate(0, 0, 7).Format("2006-01-02"))
		clauses = append(clauses, "u.active = 1 AND b.status = 'trialing' AND b.trial_ends_at >= "+
			from+" AND b.trial_ends_at <= "+to)
	} else if v.State != "" {
		clauses = append(clauses, "("+stateSQL+") = "+add(v.State))
	}
	if v.Plan != "" {
		clauses = append(clauses, "b.plan = "+add(v.Plan))
	}
	return strings.Join(clauses, " AND "), args
}

// rowMaps reads every row into a map keyed by column name. Values keep their
// database type: text is string, bigint is int64, NULL is nil.
func rowMaps(rows pgx.Rows) ([]map[string]any, error) {
	defer rows.Close()
	names := rows.FieldDescriptions()
	out := []map[string]any{}
	for rows.Next() {
		values, err := rows.Values()
		if err != nil {
			return nil, err
		}
		row := make(map[string]any, len(names))
		for i, n := range names {
			row[n.Name] = values[i]
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func queryMaps(ctx context.Context, pool *pgxpool.Pool, sql string, args ...any) ([]map[string]any, error) {
	rows, err := pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	return rowMaps(rows)
}

// Customers is admin_customers.customers: seek by unique account id; filtering
// happens before the fixed-size LIMIT. before wins over after in the SQL.
func Customers(ctx context.Context, pool *pgxpool.Pool, v Filters, after, before int64, today time.Time) (Page, error) {
	clause, args := where(v, today)
	if before != 0 {
		args = append(args, before)
		clause += " AND u.id > $" + strconv.Itoa(len(args))
	} else if after != 0 {
		args = append(args, after)
		clause += " AND u.id < $" + strconv.Itoa(len(args))
	}
	ordering := "DESC"
	if before != 0 {
		ordering = "ASC"
	}
	args = append(args, int64(PageSize+1))
	rows, err := queryMaps(ctx, pool, "SELECT "+fieldsSQL+fromSQL+"WHERE "+clause+
		" ORDER BY u.id "+ordering+" LIMIT $"+strconv.Itoa(len(args)), args...)
	if err != nil {
		return Page{}, err
	}
	more := len(rows) > PageSize
	if more {
		rows = rows[:PageSize]
	}
	if before != 0 {
		for i, j := 0, len(rows)-1; i < j; i, j = i+1, j-1 {
			rows[i], rows[j] = rows[j], rows[i]
		}
	}
	if len(rows) > 0 {
		ids := make([]int64, len(rows))
		for i, r := range rows {
			ids[i] = r["id"].(int64)
		}
		counted, err := queryMaps(ctx, pool,
			"SELECT owner_user_id, COUNT(*) AS n FROM apartment "+
				"WHERE active = 1 AND owner_user_id = ANY($1) GROUP BY owner_user_id", ids)
		if err != nil {
			return Page{}, err
		}
		counts := map[int64]int64{}
		for _, c := range counted {
			counts[c["owner_user_id"].(int64)] = c["n"].(int64)
		}
		for _, r := range rows {
			r["active_properties"] = counts[r["id"].(int64)]
		}
	}
	has := len(rows) > 0
	return Page{
		Customers: rows,
		Older:     has && (before != 0 || more),
		Newer:     has && (after != 0 || (before != 0 && more)),
	}, nil
}

// Summary is admin_customers.summary: one count per state present, plus "ending".
func Summary(ctx context.Context, pool *pgxpool.Pool, today time.Time) (map[string]int64, error) {
	rows, err := queryMaps(ctx, pool, "SELECT "+stateSQL+" AS customer_state, COUNT(*) AS n"+
		fromSQL+"WHERE u.role = 'host' GROUP BY "+stateSQL)
	if err != nil {
		return nil, err
	}
	counts := map[string]int64{}
	for _, r := range rows {
		counts[r["customer_state"].(string)] = r["n"].(int64)
	}
	clause, args := where(NewFilters("", "ending", ""), today)
	var n int64
	if err := pool.QueryRow(ctx, "SELECT COUNT(*) AS n"+fromSQL+"WHERE "+clause, args...).Scan(&n); err != nil {
		return nil, err
	}
	counts["ending"] = n
	return counts, nil
}

// Detail is admin_customers.detail. It returns a nil map when there is no host
// with this id (the page answers 404).
func Detail(ctx context.Context, pool *pgxpool.Pool, userID int64) (map[string]any, error) {
	rows, err := queryMaps(ctx, pool, "SELECT "+fieldsSQL+fromSQL+"WHERE u.role = 'host' AND u.id = $1", userID)
	if err != nil || len(rows) == 0 {
		return nil, err
	}
	customer := rows[0]
	var n int64
	if err := pool.QueryRow(ctx,
		"SELECT COUNT(*) FROM apartment WHERE owner_user_id = $1 AND active = 1", userID).Scan(&n); err != nil {
		return nil, err
	}
	customer["active_properties"] = n
	if customer["invoices"], err = queryMaps(ctx, pool,
		"SELECT id, number, issue_date, due_date, total_haler, paid_on, voided, kind "+
			"FROM platform_invoice WHERE owner_user_id = $1 ORDER BY id DESC LIMIT 10", userID); err != nil {
		return nil, err
	}
	if customer["buyer_prefill"], err = BuyerPrefill(ctx, pool, userID); err != nil {
		return nil, err
	}
	if customer["activity"], err = Activity(ctx, pool, userID); err != nil {
		return nil, err
	}
	if customer["operator_log"], err = OperatorLog(ctx, pool, userID); err != nil {
		return nil, err
	}
	return customer, nil
}

// Activity is admin_customers.activity: logins, mails and billing actions,
// latest 20. Rows that share an instant sort by detail, as Postgres sorts it.
func Activity(ctx context.Context, pool *pgxpool.Pool, userID int64) ([]map[string]any, error) {
	return queryMaps(ctx, pool,
		"SELECT 'login' AS kind, a.at AS at, NULL AS detail, a.actor AS actor, "+
			"COALESCE(a.detail, '') AS extra FROM audit a "+
			"WHERE a.owner_user_id = $1 AND a.action = 'login' "+
			"UNION ALL "+
			"SELECT 'mail' AS kind, e.created_at AS at, e.kind AS detail, NULL AS actor, "+
			"COALESCE(e.subject, '') AS extra FROM email_outbox e WHERE e.owner_user_id = $1 "+
			"UNION ALL "+
			"SELECT 'billing' AS kind, a.at AS at, a.action AS detail, a.actor AS actor, "+
			"COALESCE(a.detail, '') AS extra FROM audit a "+
			"WHERE a.owner_user_id = $1 AND a.action LIKE 'billing%' "+
			"ORDER BY at DESC, detail LIMIT 20", userID)
}

// OperatorLog is admin_customers.operator_log: the operator's latest 20 actions.
func OperatorLog(ctx context.Context, pool *pgxpool.Pool, userID int64) ([]map[string]any, error) {
	return queryMaps(ctx, pool,
		"SELECT action, actor, detail, at FROM audit "+
			"WHERE owner_user_id = $1 AND actor LIKE 'operator:%' "+
			"ORDER BY id DESC LIMIT 20", userID)
}

// normaliseZip is validation.normalise_zip: the digits of the value.
func normaliseZip(s string) string {
	var b strings.Builder
	for _, r := range s {
		if unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return pyStrip(*p)
}

// BuyerPrefill is admin_customers.buyer_prefill: blanks only. Keys appear only
// when the source row exists (and, for street, city and zip, is not empty).
func BuyerPrefill(ctx context.Context, pool *pgxpool.Pool, userID int64) (map[string]string, error) {
	prefill := map[string]string{}
	var name, ico, dic, email *string
	err := pool.QueryRow(ctx,
		"SELECT name, ico, dic, contact_email FROM legal_entity "+
			"WHERE owner_user_id = $1 ORDER BY id LIMIT 1", userID).Scan(&name, &ico, &dic, &email)
	switch {
	case err == nil:
		prefill["buyer_name"] = str(name)
		prefill["buyer_ico"] = str(ico)
		prefill["buyer_dic"] = str(dic)
		prefill["buyer_email"] = str(email)
	case !errors.Is(err, pgx.ErrNoRows):
		return nil, err
	}
	var street, house, obec, zip *string
	err = pool.QueryRow(ctx,
		"SELECT addr_street, addr_house_no, addr_obec, addr_zip FROM apartment "+
			"WHERE owner_user_id = $1 AND active = 1 AND archived_at IS NULL ORDER BY id LIMIT 1",
		userID).Scan(&street, &house, &obec, &zip)
	switch {
	case err == nil:
		var parts []string
		for _, p := range []string{str(street), str(house)} {
			if p != "" {
				parts = append(parts, p)
			}
		}
		if len(parts) > 0 {
			prefill["buyer_street"] = strings.Join(parts, " ")
		}
		if c := str(obec); c != "" {
			prefill["buyer_city"] = c
		}
		if z := normaliseZip(derefOrEmpty(zip)); z != "" {
			prefill["buyer_zip"] = z
		}
	case !errors.Is(err, pgx.ErrNoRows):
		return nil, err
	}
	return prefill, nil
}

func derefOrEmpty(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// MissingEmailCount is the count customer_list reads for its banner.
func MissingEmailCount(ctx context.Context, pool *pgxpool.Pool) (int64, error) {
	var n int64
	err := pool.QueryRow(ctx, "SELECT COUNT(*) FROM user_account WHERE active = 1 "+
		"AND (email IS NULL OR TRIM(email) = '')").Scan(&n)
	return n, err
}

// ConsentCounts is the query customer_detail runs for the two ad consents.
func ConsentCounts(ctx context.Context, pool *pgxpool.Pool, userID int64) (Consent, error) {
	var c Consent
	err := pool.QueryRow(ctx,
		"SELECT (SELECT COUNT(*) FROM ad_click c WHERE c.user_account_id = $1 "+
			"AND c.platform = 'google' AND c.withdrawn_at IS NULL), "+
			"(SELECT COUNT(*) FROM ad_click c WHERE c.user_account_id = $1 "+
			"AND c.platform = 'meta' AND c.withdrawn_at IS NULL)", userID).Scan(&c.Google, &c.Meta)
	return c, err
}

// BillingAccount is billing.account: the whole billing_account row of a host,
// or nil. The Python detail page receives it and its template reads no column
// of it yet, so every column is returned.
func BillingAccount(ctx context.Context, pool *pgxpool.Pool, ownerID int64) (map[string]any, error) {
	rows, err := queryMaps(ctx, pool, "SELECT * FROM billing_account WHERE owner_user_id = $1", ownerID)
	if err != nil || len(rows) == 0 {
		return nil, err
	}
	return rows[0], nil
}
