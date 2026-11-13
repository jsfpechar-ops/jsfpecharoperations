package billingjob

// Replays testdata/run.golden.json (App/scripts/billing_run_golden.py) against
// Postgres: the same seed, the same runs on the same days, and every count and
// row the runs wrote compared with Python's. The PDF bytes and their sha256 are not
// compared (another writer than reportlab): has_pdf says the stored sha256 matches
// the stored bytes, and the bytes must be a PDF. Skipped without
// UBYHOST_TEST_DATABASE_URL. It uses dbPool, param, rowsOf, compare and normalize
// from invoicer_test.go.

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"
)

type goldenRun struct {
	Name string            `json:"name"`
	Day  string            `json:"day"`
	Env  map[string]string `json:"env"`
}

type runGolden struct {
	Env  map[string]string `json:"env"`
	Seed []struct {
		Table   string          `json:"table"`
		Columns []string        `json:"columns"`
		Rows    [][]interface{} `json:"rows"`
	} `json:"seed"`
	Runs    []goldenRun `json:"runs"`
	Results []struct {
		Name   string         `json:"name"`
		Counts map[string]int `json:"counts"`
	} `json:"results"`
	Accounts []map[string]interface{} `json:"accounts"`
	Invoices []map[string]interface{} `json:"invoices"`
	Sequence []map[string]interface{} `json:"sequence"`
	Audit    []map[string]interface{} `json:"audit"`
	Emails   []map[string]interface{} `json:"emails"`
}

func TestRunMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/run.golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g runGolden
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
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
	// Seeded ids were explicit: let the identities continue after them, as SQLite does.
	for _, table := range []string{"platform_invoice", "apartment"} {
		if _, err := pool.Exec(ctx, fmt.Sprintf(
			`SELECT setval(pg_get_serial_sequence('%[1]s', 'id'), (SELECT max(id) FROM %[1]s))`, table)); err != nil {
			t.Fatal(err)
		}
	}

	runner := &Runner{Pool: pool}
	if len(g.Runs) != len(g.Results) {
		t.Fatal("golden runs and results differ in length")
	}
	for i, run := range g.Runs {
		for k, v := range run.Env {
			t.Setenv(k, v)
		}
		today, err := time.Parse(isoDate, run.Day)
		if err != nil {
			t.Fatal(err)
		}
		counts, err := runner.Run(ctx, today)
		if err != nil {
			t.Fatalf("run %s: %v", run.Name, err)
		}
		// Python returns four keys while billing is off; the others read as zero.
		want := map[string]int{}
		for k := range counts.Map() {
			want[k] = g.Results[i].Counts[k]
		}
		for k := range g.Results[i].Counts {
			if _, ok := want[k]; !ok {
				t.Errorf("run %s: golden has an unknown count %q", run.Name, k)
			}
		}
		if canon(t, counts.Map()) != canon(t, want) {
			t.Errorf("run %s counts:\n got %s\nwant %s", run.Name, canon(t, counts.Map()), canon(t, want))
		}
	}

	compare(t, "billing_account", normalize(t, rowsOf(t, pool,
		`SELECT owner_user_id, status, plan, billing_interval, addon_ttlock, addon_whitelabel, apartments_billed,
		        trial_started_at, trial_ends_at, period_start, period_end, pending_change_json, carry_czk,
		        buyer_name, buyer_street, buyer_city, buyer_zip, buyer_ico, buyer_dic, buyer_email,
		        discount_percent, discount_reason
		 FROM billing_account ORDER BY owner_user_id`, nil)), normalize(t, g.Accounts))
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
	compare(t, "audit", normalize(t, rowsOf(t, pool,
		`SELECT actor, action, detail, owner_user_id FROM audit ORDER BY id`, nil)), normalize(t, g.Audit))
	compare(t, "email_outbox", normalize(t, rowsOf(t, pool,
		`SELECT idempotency_key, kind, reservation_id, apartment_id, owner_user_id, to_email, cc_email,
		        subject, payload, state, attempts
		 FROM email_outbox ORDER BY idempotency_key COLLATE "C"`, nil)), normalize(t, g.Emails))
}

// TestRunDisabledDoesNothing: with billing off the run writes no row and returns zeros.
func TestRunDisabledDoesNothing(t *testing.T) {
	pool := dbPool(t)
	t.Setenv("UBYHOST_BILLING_ENABLED", "0")
	counts, err := (&Runner{Pool: pool}).Run(context.Background(), time.Now())
	if err != nil || counts != (Counts{}) {
		t.Fatalf("counts %+v, err %v", counts, err)
	}
	var n int
	if err := pool.QueryRow(context.Background(), `SELECT count(*) FROM audit`).Scan(&n); err != nil || n != 0 {
		t.Fatalf("audit rows %d, err %v", n, err)
	}
}
