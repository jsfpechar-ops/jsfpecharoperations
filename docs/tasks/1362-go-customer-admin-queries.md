# 1362: Go customer admin part 2 of 3: the read-only queries

<<<<<<< HEAD
Status: todo
=======
Status: review
>>>>>>> go-customer-admin-pages
Depends on: 1360 | Base commit: a83df5412638cc7ae1c64810e5b0b59fc68997cc | Branch: go-customer-admin (already checked out; do not create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B

## 1. Objective

Add `go/internal/web/customers/query.go`, an exact port of `App/app/admin_customers.py` (PAGE_SIZE, STATES, STATE_SQL, filters, `_where` with `LIKE ... ESCAPE '!'`, seek pagination with older/newer and active_properties, summary, detail with invoices, buyer_prefill, activity, operator_log) and of the route-level reads in `App/app/routes/admin_customers.py` (`_cursor`, `_kc`, missing e-mail count, consent counts, `billing.account`). The tests seed PostgreSQL from the golden file of brief 1360 and compare every result with the Python one.

## 2. Context

- Split: this task is three briefs run in order on one branch, one executor session each: 1360 (Python golden fixture), 1362 (Go queries), 1363 (Go guard, funnel, toggle, routes). Brief 1361 (HTML pages) comes later. The orchestrator opens one draft PR after 1363.
- Plan: `docs/plans/go-full-move.md` §2 (parity first: a Python golden script writes fixtures, the Go code reproduces them) and §7 row "Port customer admin pages" (Tier B, own package `go/internal/web/customers/`). You do not need to open it.
- Every file in this brief is NEW and given in full. Create it byte for byte from its block in §4 (everything between the `~~~~` fence lines, ending with one newline) and check its sha256. If the sha256 differs: compare with the block once, fix, check again; still different: STOP (§8). Never edit an existing file.
- The port stays switched off: no Caddy, env, `UBYHOST_GO_PATHS` or `docs/ENVIRONMENT.md` change. No new dependency (rule 4). SQL Postgres-portable (rule 5). Never push to `main` (rule 8).
- Needs `go/internal/web/customers/testdata/admin_customers_golden.json` from brief 1360 on this branch: `test -f go/internal/web/customers/testdata/admin_customers_golden.json && echo ok`. Missing: STOP.
- pgx `*pgxpool.Pool`, `$n` placeholders. `go/internal/validation` has no exported ZIP helper, so `normaliseZip` is local.
- The DB tests create and drop their own database from `UBYHOST_TEST_DATABASE_URL` and apply `App/migrations_pg/*.sql` (as `go/internal/calendar/dsr_due_test.go` does).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/customers/query.go` | create | the queries |
| `go/internal/web/customers/query_test.go` | create | golden loader, throwaway Postgres DB, query parity tests |
| `docs/tasks/1362-go-customer-admin-queries.md` | edit | `Status:` line only |
| `docs/tasks/1362-report.md` | create | your report |

No other file may change.

## 4. Steps

Commit after each step with the message `1362 step k`.

### Step 1: start Postgres (no commit)

```bash
PGBIN=/usr/lib/postgresql/16/bin; mkdir -p /var/tmp/pg1360 && chown postgres /var/tmp/pg1360
[ -f /var/tmp/pg1360/data/PG_VERSION ] || su postgres -c "$PGBIN/initdb -D /var/tmp/pg1360/data -A trust -U postgres" | tail -3
$PGBIN/pg_isready -h 127.0.0.1 -p 55436 || { rm -f /var/tmp/pg1360/data/postmaster.pid /var/tmp/pg1360/.s.PGSQL.55436 /var/tmp/pg1360/.s.PGSQL.55436.lock; su postgres -c "$PGBIN/pg_ctl -D /var/tmp/pg1360/data -l /var/tmp/pg1360/log -o '-p 55436 -k /var/tmp/pg1360 -c listen_addresses=127.0.0.1' -w start" 2>&1 | tail -3; }
$PGBIN/pg_isready -h 127.0.0.1 -p 55436
```

Expected last line: `127.0.0.1:55436 - accepting connections`.

### Step 2: query.go

Create `go/internal/web/customers/query.go`:

~~~~go
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
~~~~

Check: `sha256sum go/internal/web/customers/query.go 2>&1 | tail -30` must print `7b95391aafee191c2da73f2acd00960650452c1ac0149ae9bba8c1c9fe879e69`.

Run from `go/`: `/usr/local/go/bin/go build ./internal/web/... 2>&1 | tail -30` (no output). Commit `1362 step 2`.

### Step 3: query_test.go

Create `go/internal/web/customers/query_test.go`:

~~~~go
package customers

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// goldenFile is what App/scripts/admin_customers_golden.py wrote from the real
// Python. Fields are kept raw and compared as normalised JSON.
type goldenFile struct {
	Today    string                       `json:"today"`
	Versions map[string]string            `json:"versions"`
	Seed     []seedTable                  `json:"seed"`
	Filters  []json.RawMessage            `json:"filters_check"`
	List     []listCase                   `json:"list"`
	Summary  json.RawMessage              `json:"summary"`
	Missing  json.RawMessage              `json:"missing_email_count"`
	Detail   map[string]json.RawMessage   `json:"detail"`
	Account  map[string]json.RawMessage   `json:"account"`
	Consent  map[string]json.RawMessage   `json:"consent"`
	I18N     map[string]map[string]string `json:"i18n"`
	Cursor   [][2]json.RawMessage         `json:"cursor"`
	KC       [][2]json.RawMessage         `json:"kc"`
	Toggle   struct {
		Steps []toggleStep `json:"steps"`
	} `json:"toggle"`
}

type seedTable struct {
	Table string                       `json:"table"`
	Rows  []map[string]json.RawMessage `json:"rows"`
}

type listCase struct {
	Name   string          `json:"name"`
	Q      string          `json:"q"`
	State  string          `json:"state"`
	Plan   string          `json:"plan"`
	After  int64           `json:"after"`
	Before int64           `json:"before"`
	Values json.RawMessage `json:"values"`
	Result json.RawMessage `json:"result"`
}

type toggleStep struct {
	Name       string            `json:"name"`
	Method     string            `json:"method"`
	Path       string            `json:"path"`
	Lang       string            `json:"lang"`
	Target     int64             `json:"target"`
	Role       string            `json:"role"`
	Status     int               `json:"status"`
	Location   *string           `json:"location"`
	Body       *string           `json:"body"`
	CType      *string           `json:"content_type"`
	UserBefore json.RawMessage   `json:"user_before"`
	UserAfter  json.RawMessage   `json:"user_after"`
	AuditAdded []json.RawMessage `json:"audit_added"`
}

func loadGolden(t *testing.T) goldenFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/admin_customers_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g goldenFile
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.List) < 40 || len(g.Seed) == 0 || len(g.Toggle.Steps) < 8 {
		t.Fatal("golden file is too small")
	}
	return g
}

// norm decodes JSON (numbers kept as written) and encodes it again, so two
// documents compare equal when they hold the same values.
func norm(t *testing.T, raw []byte) string {
	t.Helper()
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		t.Fatalf("bad JSON %q: %v", raw, err)
	}
	out, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return string(out)
}

func normValue(t *testing.T, v any) string {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return norm(t, raw)
}

func same(t *testing.T, what string, got any, want json.RawMessage) {
	t.Helper()
	if g, w := normValue(t, got), norm(t, want); g != w {
		t.Errorf("%s differs from Python\n got: %s\nwant: %s", what, g, w)
	}
}

// dbPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies the
// goose Up sections of App/migrations_pg and drops it at the end.
func dbPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_customers_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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
	files, _ := filepath.Glob("../../../../App/migrations_pg/*.sql")
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

// seedValue turns one JSON value into a query argument.
func seedValue(t *testing.T, raw json.RawMessage) any {
	t.Helper()
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		t.Fatal(err)
	}
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			t.Fatalf("seed number %s is not an integer", n)
		}
		return i
	}
	return v
}

// seed inserts the golden rows, each with only the columns it lists.
func seed(t *testing.T, pool *pgxpool.Pool, g goldenFile) {
	t.Helper()
	for _, table := range g.Seed {
		for _, row := range table.Rows {
			cols := make([]string, 0, len(row))
			for c := range row {
				cols = append(cols, c)
			}
			sort.Strings(cols)
			marks := make([]string, len(cols))
			args := make([]any, len(cols))
			for i, c := range cols {
				marks[i] = "$" + strconv.Itoa(i+1)
				args[i] = seedValue(t, row[c])
			}
			sql := "INSERT INTO " + table.Table + " (" + strings.Join(cols, ", ") +
				") VALUES (" + strings.Join(marks, ", ") + ")"
			if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
}

func goldenToday(t *testing.T, g goldenFile) time.Time {
	t.Helper()
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	return today
}

func TestFiltersCursorKCMatchPython(t *testing.T) {
	g := loadGolden(t)
	for _, raw := range g.Filters {
		var c [4]json.RawMessage
		if err := json.Unmarshal(raw, &c); err != nil {
			t.Fatal(err)
		}
		var q, s, p string
		_ = json.Unmarshal(c[0], &q)
		_ = json.Unmarshal(c[1], &s)
		_ = json.Unmarshal(c[2], &p)
		same(t, "filters("+s+")", NewFilters(q, s, p), c[3])
	}
	for _, c := range g.List {
		same(t, "filters of "+c.Name, NewFilters(c.Q, c.State, c.Plan), c.Values)
	}
	for _, c := range g.Cursor {
		var in string
		var want int64
		_ = json.Unmarshal(c[0], &in)
		if err := json.Unmarshal(c[1], &want); err != nil {
			t.Fatal(err)
		}
		if got := Cursor(in); got != want {
			t.Errorf("Cursor(%q) = %d, Python gives %d", in, got, want)
		}
	}
	for _, c := range g.KC {
		var in int64
		var want string
		if err := json.Unmarshal(c[0], &in); err != nil {
			t.Fatal(err)
		}
		_ = json.Unmarshal(c[1], &want)
		if got := KC(in); got != want {
			t.Errorf("KC(%d) = %q, Python gives %q", in, got, want)
		}
	}
}

func TestQueriesMatchPython(t *testing.T) {
	g := loadGolden(t)
	pool := dbPool(t)
	seed(t, pool, g)
	ctx := context.Background()
	today := goldenToday(t, g)

	for _, c := range g.List {
		got, err := Customers(ctx, pool, NewFilters(c.Q, c.State, c.Plan), c.After, c.Before, today)
		if err != nil {
			t.Fatalf("%s: %v", c.Name, err)
		}
		same(t, "list "+c.Name, got, c.Result)
	}
	sum, err := Summary(ctx, pool, today)
	if err != nil {
		t.Fatal(err)
	}
	same(t, "summary", sum, g.Summary)
	missing, err := MissingEmailCount(ctx, pool)
	if err != nil {
		t.Fatal(err)
	}
	same(t, "missing_email_count", missing, g.Missing)
	for id, want := range g.Detail {
		uid := int64(0)
		for _, ch := range id {
			uid = uid*10 + int64(ch-'0')
		}
		got, err := Detail(ctx, pool, uid)
		if err != nil {
			t.Fatalf("detail %s: %v", id, err)
		}
		same(t, "detail "+id, got, want)
		acct, err := BillingAccount(ctx, pool, uid)
		if err != nil {
			t.Fatalf("account %s: %v", id, err)
		}
		same(t, "account "+id, acct, g.Account[id])
		cons, err := ConsentCounts(ctx, pool, uid)
		if err != nil {
			t.Fatal(err)
		}
		if w, ok := g.Consent[id]; ok {
			same(t, "consent "+id, cons, w)
		}
	}
}
~~~~

Check: `sha256sum go/internal/web/customers/query_test.go 2>&1 | tail -30` must print `38c9fc86d2160b34d2d9e44cbb6cdd210f49ef8827db27c014cbd244813625a2`.

Run §6. Commit `1362 step 3`.

### Step 4: report

Write the report (§9), set `Status: review`, commit `1362 step 4`.

## 5. Do not touch

- Read-only: `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, `App/tests/conftest.py`, every existing file under `App/app/` and `App/scripts/`.
- `docs/context/*`, `docs/ENVIRONMENT.md`, Caddy, compose and `.env` files: no change.
- `go/internal/web/customers/testdata/admin_customers_golden.json` is written only by the golden script, never by hand.
- Never print the session secret or cookies. No push, merge or deploy.

## 6. Commands

1. Postgres: step 1 block.
2. Go, from the repo root:

```bash
cd go && export PATH=$PATH:/usr/local/go/bin
test -z "$(gofmt -l ./internal/web ./cmd)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/customers/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55436/postgres go test ./internal/web/customers/ -count=1 -v 2>&1 | grep -E -c 'SKIP'
```

Expected: `ok` for both packages; the last command prints `0` (the DB tests run; none skip).

3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5` ends `context lint: OK`.

## 7. Acceptance

- [ ] The 2 files exist with the sha256 values in §4.
- [ ] `TestFiltersCursorKCMatchPython` and `TestQueriesMatchPython` pass; `grep -c SKIP` prints `0`.
- [ ] Context lint OK.
- [ ] `git diff --stat <start commit>` lists only the §3 paths.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 differs twice for the same file;
- a test fails twice;
- Postgres does not start, or a DB test skips;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1362-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat <start commit>`; `<start commit>` is the commit you started from: `git rev-parse HEAD` before step 1, write it down).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/customers/query.go`: LIKE escaping, `before` wins over `after`, `ORDER BY at DESC, detail` in `Activity` (Postgres sorts a NULL detail after the others on an `at` tie; SQLite first; production Python runs on Postgres, so Go matches production).

## Owner steps

None. Next: brief 1363 on the same branch.
