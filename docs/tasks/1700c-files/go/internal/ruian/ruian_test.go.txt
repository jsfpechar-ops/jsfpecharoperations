package ruian

import (
	"archive/zip"
	"bytes"
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func TestFold(t *testing.T) {
	for in, want := range map[string]string{
		"Václavské náměstí":        "vaclavske namesti",
		"ŘŽČĚŮĎŤŇ":                 "rzceudtn",
		"  Praha   1 ":             "praha 1",
		"Želechovice nad Dřevnicí": "zelechovice nad drevnici",
		"":                         "",
	} {
		if got := Fold(in); got != want {
			t.Errorf("Fold(%q) = %q, want %q", in, got, want)
		}
	}
	if got := SearchText("Varšavská", "200", "12a", "Vinohrady", "Praha", "12000"); got != "varsavska 200/12a vinohrady praha 12000" {
		t.Errorf("SearchText = %q", got)
	}
	if got := SearchText("", "1", "", "Petrov nad Desnou", "Petrov nad Desnou", "78814"); got != "1 petrov nad desnou petrov nad desnou 78814" {
		t.Errorf("SearchText without street = %q", got)
	}
}

func TestOkres(t *testing.T) {
	for code, want := range map[int]string{554782: "Hlavní město Praha", 500020: "Šumperk", 500011: "Zlín", 1: ""} {
		if got := Okres(code); got != want {
			t.Errorf("Okres(%d) = %q, want %q", code, got, want)
		}
	}
	if n := strings.Count(okresCSV, "\n"); n != 6258 {
		t.Errorf("okres.csv has %d lines, want 6258", n)
	}
}

func TestCandidates(t *testing.T) {
	for now, want := range map[string][2]string{
		"2026-11-17": {"20261031", "20260930"},
		"2026-03-01": {"20260228", "20260131"},
		"2026-01-05": {"20251231", "20251130"},
	} {
		tm, _ := time.Parse("2006-01-02", now)
		got := candidates(tm)
		if got[0].Format("20060102") != want[0] || got[1].Format("20060102") != want[1] {
			t.Errorf("%s: got %s %s, want %v", now, got[0].Format("20060102"), got[1].Format("20060102"), want)
		}
	}
}

func fixtureBytes(t *testing.T) []byte {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "20261031_OB_999991_ADR.csv"))
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

// zipOf builds a zip with the first n data lines of the fixture (header kept).
func zipOf(t *testing.T, n int) []byte {
	t.Helper()
	lines := strings.SplitAfter(string(fixtureBytes(t)), "\n")
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	w, err := zw.Create("CSV/20261031_OB_999991_ADR.csv")
	if err != nil {
		t.Fatal(err)
	}
	w.Write([]byte(strings.Join(lines[:n+1], "")))
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func TestParseLineAndStream(t *testing.T) {
	zr, err := zip.NewReader(bytes.NewReader(zipOf(t, 13)), int64(len(zipOf(t, 13))))
	if err != nil {
		t.Fatal(err)
	}
	src := newZipRows(context.Background(), zr)
	var rows [][]any
	for src.Next() {
		v, _ := src.Values()
		rows = append(rows, v)
	}
	if src.Err() != nil || len(rows) != 12 || src.Skipped != 1 {
		t.Fatalf("rows %d skipped %d err %v, want 12 1 nil", len(rows), src.Skipped, src.Err())
	}
	want1 := []any{int64(9000001), "", "1", "", true, "78814", "Petrov nad Desnou", int32(500020),
		"Petrov nad Desnou", "", "Šumperk", "1 petrov nad desnou petrov nad desnou 78814"}
	if !reflect.DeepEqual(rows[0], want1) {
		t.Errorf("row 1 = %#v\nwant   %#v", rows[0], want1)
	}
	want5 := []any{int64(9000005), "Varšavská", "201", "12a", false, "12000", "Praha", int32(554782),
		"Vinohrady", "Praha 2", "Hlavní město Praha", "varsavska 201/12a vinohrady praha 12000"}
	if !reflect.DeepEqual(rows[4], want5) {
		t.Errorf("row 5 = %#v\nwant   %#v", rows[4], want5)
	}
}

// fakeCUZK serves the given zips by date and counts GET requests; other dates 404.
func fakeCUZK(t *testing.T, zips map[string][]byte) (*httptest.Server, *atomic.Int32) {
	t.Helper()
	var gets atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		date := strings.TrimSuffix(strings.TrimPrefix(r.URL.Path, "/"), "_OB_ADR_csv.zip")
		body, ok := zips[date]
		if !ok {
			http.NotFound(w, r)
			return
		}
		if r.Method == http.MethodGet {
			gets.Add(1)
		}
		w.Header().Set("Content-Type", "application/zip")
		w.Write(body)
	}))
	t.Cleanup(srv.Close)
	return srv, &gets
}

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_ruian_%d", time.Now().UnixNano())
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
	// Only the 00021 migration: the ruian tables need no other table.
	raw, err := os.ReadFile("../../../App/migrations_pg/00021_ruian_address.sql")
	if err != nil {
		t.Fatal(err)
	}
	up := string(raw)
	up = up[strings.Index(up, "-- +goose Up")+len("-- +goose Up") : strings.Index(up, "-- +goose Down")]
	if _, err := pool.Exec(ctx, up); err != nil {
		t.Fatalf("00021: %v", err)
	}
	return pool
}

func count(t *testing.T, pool *pgxpool.Pool, sql string) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), sql).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestImport(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	srv, gets := fakeCUZK(t, map[string][]byte{"20261031": zipOf(t, 13)})
	opts := Options{BaseURL: srv.URL, Dir: t.TempDir(), MinRows: 10,
		Now: func() time.Time { return time.Date(2026, 11, 17, 4, 45, 0, 0, time.UTC) }}

	// 1. First run loads the 12 good rows of 13 lines.
	n, err := Run(ctx, pool, opts)
	if err != nil || n != 12 || gets.Load() != 1 {
		t.Fatalf("first run: n=%d err=%v gets=%d, want 12 nil 1", n, err, gets.Load())
	}
	if got := count(t, pool, "SELECT count(*) FROM ruian_address"); got != 12 {
		t.Fatalf("rows = %d, want 12", got)
	}
	if got := count(t, pool, "SELECT count(*) FROM ruian_import WHERE id = 1 AND data_date = '2026-10-31' AND rows = 12"); got != 1 {
		t.Fatal("ruian_import row missing or wrong")
	}
	if got := count(t, pool, "SELECT count(*) FROM pg_class WHERE relname = 'ruian_address' AND relpersistence = 'u'"); got != 1 {
		t.Fatal("ruian_address is not UNLOGGED after the swap")
	}
	var idx []string
	rows, _ := pool.Query(ctx, "SELECT indexname FROM pg_indexes WHERE tablename = 'ruian_address' ORDER BY 1")
	for rows.Next() {
		var s string
		rows.Scan(&s)
		idx = append(idx, s)
	}
	rows.Close()
	if !reflect.DeepEqual(idx, []string{"ruian_address_pkey", "ruian_address_search_trgm"}) {
		t.Fatalf("indexes after swap = %v", idx)
	}
	if got := count(t, pool, "SELECT count(*) FROM ruian_address WHERE search LIKE '%vaclavske%' AND okres = 'Hlavní město Praha' AND district = 'Praha 1'"); got != 1 {
		t.Fatal("Václavské náměstí not found by folded search")
	}
	if got := count(t, pool, "SELECT count(*) FROM ruian_address WHERE is_evid AND okres = 'Šumperk'"); got != 1 {
		t.Fatal("the č.ev. row is missing")
	}
	if got := count(t, pool, "SELECT count(*) FROM pg_class WHERE relname = 'ruian_address_new'"); got != 0 {
		t.Fatal("staging table left behind")
	}
	if entries, _ := os.ReadDir(opts.Dir); len(entries) != 0 {
		t.Fatalf("zip not removed: %v", entries)
	}

	// 2. Same month again: no download.
	if n, err := Run(ctx, pool, opts); err != nil || n != 0 || gets.Load() != 1 {
		t.Fatalf("second run: n=%d err=%v gets=%d, want 0 nil 1", n, err, gets.Load())
	}

	// 3. Empty table (crash): same month is loaded again.
	pool.Exec(ctx, "TRUNCATE ruian_address")
	if n, err := Run(ctx, pool, opts); err != nil || n != 12 || gets.Load() != 2 {
		t.Fatalf("after truncate: n=%d err=%v gets=%d, want 12 nil 2", n, err, gets.Load())
	}

	// 4. A newer month with 2 rows fails the gate: error, old rows kept.
	srv2, _ := fakeCUZK(t, map[string][]byte{"20261130": zipOf(t, 2)})
	bad := opts
	bad.BaseURL = srv2.URL
	bad.Now = func() time.Time { return time.Date(2026, 12, 5, 4, 45, 0, 0, time.UTC) }
	if n, err := Run(ctx, pool, bad); err == nil || n != 0 || !strings.Contains(err.Error(), "old table kept") {
		t.Fatalf("gate run: n=%d err=%v, want the old-table-kept error", n, err)
	}
	if got := count(t, pool, "SELECT count(*) FROM ruian_address"); got != 12 {
		t.Fatalf("rows after the gate failure = %d, want 12", got)
	}
	if got := count(t, pool, "SELECT count(*) FROM ruian_import WHERE data_date = '2026-10-31'"); got != 1 {
		t.Fatal("ruian_import changed after the gate failure")
	}
	if got := count(t, pool, "SELECT count(*) FROM pg_class WHERE relname = 'ruian_address_new'"); got != 0 {
		t.Fatal("staging table left behind after the gate failure")
	}

	// 5. 404 for every date: no error, no change.
	srv3, gets3 := fakeCUZK(t, map[string][]byte{})
	none := opts
	none.BaseURL = srv3.URL
	none.Now = bad.Now
	if n, err := Run(ctx, pool, none); err != nil || n != 0 || gets3.Load() != 0 {
		t.Fatalf("404 run: n=%d err=%v gets=%d, want 0 nil 0", n, err, gets3.Load())
	}
	if got := count(t, pool, "SELECT count(*) FROM ruian_address"); got != 12 {
		t.Fatalf("rows after 404 = %d, want 12", got)
	}
}

// The advisory lock keeps a second run out while one is going.
func TestImportLock(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	c, err := pool.Acquire(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Release()
	c.Exec(ctx, "SELECT pg_advisory_lock($1)", lockKey)
	srv, gets := fakeCUZK(t, map[string][]byte{"20261031": zipOf(t, 13)})
	n, err := Run(ctx, pool, Options{BaseURL: srv.URL, Dir: t.TempDir(), MinRows: 10,
		Now: func() time.Time { return time.Date(2026, 11, 17, 0, 0, 0, 0, time.UTC) }})
	if err != nil || n != 0 || gets.Load() != 0 {
		t.Fatalf("locked run: n=%d err=%v gets=%d, want 0 nil 0", n, err, gets.Load())
	}
}
