package billingjob

// Replays testdata/invoicer.golden.json (App/scripts/billing_invoice_golden.py)
// against Postgres and compares every result and every row the steps wrote.
// The PDF bytes and their sha256 are not compared (other writer than reportlab):
// has_pdf says the stored sha256 matches the stored bytes, and the bytes must be a
// PDF. Skipped without UBYHOST_TEST_DATABASE_URL.

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func dbPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := "ubyhost_go_billingjob_" + strings.ReplaceAll(time.Now().Format("150405.000000000"), ".", "")
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
	files, _ := filepath.Glob("../../../App/migrations_pg/*.sql")
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

type goldenStep struct {
	Name        string            `json:"name"`
	Op          string            `json:"op"`
	Owner       int64             `json:"owner"`
	From        string            `json:"from"`
	To          string            `json:"to"`
	Today       string            `json:"today"`
	Amount      int64             `json:"amount"`
	Description string            `json:"description"`
	Target      json.RawMessage   `json:"target"`
	Reason      string            `json:"reason"`
	Env         map[string]string `json:"env"`
}

type golden struct {
	Env  map[string]string `json:"env"`
	Seed []struct {
		Table   string          `json:"table"`
		Columns []string        `json:"columns"`
		Rows    [][]interface{} `json:"rows"`
	} `json:"seed"`
	Steps    []goldenStep             `json:"steps"`
	Results  []map[string]interface{} `json:"results"`
	Invoices []map[string]interface{} `json:"invoices"`
	Sequence []map[string]interface{} `json:"sequence"`
	Carry    []map[string]interface{} `json:"carry"`
	Audit    []map[string]interface{} `json:"audit"`
	Emails   []map[string]interface{} `json:"emails"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/invoicer.golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	return g
}

// param turns a decoded JSON value into a query argument (numbers to int64).
func param(v interface{}) interface{} {
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			panic(err)
		}
		return i
	}
	return v
}

// canon is the canonical JSON text of a value, for comparing Go and Python rows.
func canon(t *testing.T, v interface{}) string {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func compare(t *testing.T, what string, got, want []map[string]interface{}) {
	t.Helper()
	if len(got) != len(want) {
		t.Errorf("%s: %d rows, golden has %d", what, len(got), len(want))
	}
	for i := 0; i < len(got) && i < len(want); i++ {
		if canon(t, got[i]) != canon(t, want[i]) {
			t.Errorf("%s row %d differs:\n got %s\nwant %s", what, i, canon(t, got[i]), canon(t, want[i]))
		}
	}
}

func rowsOf(t *testing.T, pool *pgxpool.Pool, query string, post func(map[string]interface{})) []map[string]interface{} {
	t.Helper()
	rows, err := pool.Query(context.Background(), query)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []map[string]interface{}
	for rows.Next() {
		vals, err := rows.Values()
		if err != nil {
			t.Fatal(err)
		}
		rec := map[string]interface{}{}
		for i, f := range rows.FieldDescriptions() {
			rec[f.Name] = vals[i]
		}
		if post != nil {
			post(rec)
		}
		out = append(out, rec)
	}
	if rows.Err() != nil {
		t.Fatal(rows.Err())
	}
	return out
}

func TestInvoicerMatchesPython(t *testing.T) {
	g := loadGolden(t)
	pool := dbPool(t)
	ctx := context.Background()
	for k, v := range g.Env {
		t.Setenv(k, v)
	}
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		q := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
		for _, row := range table.Rows {
			args := make([]interface{}, len(row))
			for i, v := range row {
				args[i] = param(v)
			}
			if _, err := pool.Exec(ctx, q, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	// Seeded ids were explicit: let the identity continue after them, as SQLite does.
	if _, err := pool.Exec(ctx, `SELECT setval(pg_get_serial_sequence('platform_invoice', 'id'),
		(SELECT max(id) FROM platform_invoice))`); err != nil {
		t.Fatal(err)
	}

	v := &Invoicer{Pool: pool}
	ids := map[string]int64{}
	var results []map[string]interface{}
	for _, s := range g.Steps {
		for k, val := range s.Env {
			t.Setenv(k, val)
		}
		var target int64
		if len(s.Target) > 0 {
			var name string
			if json.Unmarshal(s.Target, &name) == nil {
				target = ids[name]
			} else if err := json.Unmarshal(s.Target, &target); err != nil {
				t.Fatal(err)
			}
		}
		var today time.Time
		if s.Today != "" {
			var err error
			if today, err = time.Parse("2006-01-02", s.Today); err != nil {
				t.Fatal(err)
			}
		}
		var id int64
		var err error
		switch s.Op {
		case "issue_for_period":
			id, err = v.IssueForPeriod(ctx, s.Owner, s.From, s.To, today)
		case "issue_supplementary":
			id, err = v.IssueSupplementary(ctx, s.Owner, s.Amount, s.Description, s.From, s.To, today)
		case "storno":
			id, err = v.Storno(ctx, target, s.Reason, today)
		case "send":
			err = v.Send(ctx, target)
		default:
			t.Fatalf("unknown op %q", s.Op)
		}
		rec := map[string]interface{}{"name": s.Name}
		switch {
		case s.Op == "send":
			if err != nil {
				t.Fatalf("step %s: %v", s.Name, err)
			}
			var n int
			if e := pool.QueryRow(ctx, `SELECT count(*) FROM email_outbox WHERE idempotency_key = $1`,
				"billing-invoice-"+itoa(target)).Scan(&n); e != nil {
				t.Fatal(e)
			}
			rec["mail_id"] = n > 0
		case err != nil:
			var known bool
			for _, sentinel := range []error{ErrBuyerMissing, ErrNoPlan, ErrBelowMinimum, ErrNotAnInvoice,
				ErrAlreadyVoided, ErrPaid, ErrWorkspaceDeleted} {
				known = known || errors.Is(err, sentinel)
			}
			if !known {
				t.Fatalf("step %s: unexpected error %v", s.Name, err)
			}
			rec["error"] = err.Error()
		default:
			rec["id"] = id
			ids[s.Name] = id
		}
		results = append(results, rec)
	}
	compare(t, "results", normalize(t, results), normalize(t, g.Results))

	invoices := rowsOf(t, pool,
		`SELECT id, owner_user_id, kind, corrects_id, seq_year, seq_no, number, vs, issue_date, due_date,
		        period_from, period_to, total_haler, voided, paid_on, paid_via, snapshot_json, pdf_blob, pdf_sha256
		 FROM platform_invoice ORDER BY id`,
		func(rec map[string]interface{}) {
			blob, _ := rec["pdf_blob"].([]byte)
			sum := sha256.Sum256(blob)
			hasPDF := len(blob) > 0 && hex.EncodeToString(sum[:]) == rec["pdf_sha256"]
			if hasPDF && !bytes.HasPrefix(blob, []byte("%PDF-")) {
				t.Errorf("invoice %v: stored bytes are not a PDF", rec["id"])
			}
			rec["has_pdf"] = hasPDF
			delete(rec, "pdf_blob")
			delete(rec, "pdf_sha256")
		})
	compare(t, "platform_invoice", normalize(t, invoices), normalize(t, g.Invoices))
	compare(t, "platform_invoice_sequence", normalize(t, rowsOf(t, pool,
		`SELECT year, last_no FROM platform_invoice_sequence ORDER BY year`, nil)), normalize(t, g.Sequence))
	compare(t, "billing_account carry", normalize(t, rowsOf(t, pool,
		`SELECT owner_user_id, carry_czk FROM billing_account ORDER BY owner_user_id`, nil)), normalize(t, g.Carry))
	compare(t, "audit", normalize(t, rowsOf(t, pool,
		`SELECT actor, action, detail, owner_user_id FROM audit ORDER BY id`, nil)), normalize(t, g.Audit))
	compare(t, "email_outbox", normalize(t, rowsOf(t, pool,
		`SELECT idempotency_key, kind, reservation_id, apartment_id, owner_user_id, to_email, cc_email,
		        subject, payload, state, attempts
		 FROM email_outbox ORDER BY idempotency_key COLLATE "C"`, nil)), normalize(t, g.Emails))
}

func itoa(n int64) string {
	b, _ := json.Marshal(n)
	return string(b)
}

// normalize round-trips rows through JSON so integers of every Go type, and the
// golden's json.Number, compare as the same text.
func normalize(t *testing.T, rows []map[string]interface{}) []map[string]interface{} {
	t.Helper()
	raw, err := json.Marshal(rows)
	if err != nil {
		t.Fatal(err)
	}
	var out []map[string]interface{}
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out
}
