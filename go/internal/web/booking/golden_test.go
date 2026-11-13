package booking

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type seedTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Rows    [][]any  `json:"rows"`
}

type golden struct {
	Secret     string      `json:"secret"`
	PublicBase string      `json:"public_base"`
	StripeMode string      `json:"stripe_mode"`
	Now        string      `json:"now"`
	Seed       []seedTable `json:"seed"`
	Settings   []struct {
		ApartmentID int64 `json:"apartment_id"`
		Result      any   `json:"result"`
	} `json:"settings"`
	ParseDates []struct {
		Value string  `json:"value"`
		ISO   *string `json:"iso"`
		Day   *string `json:"day"`
	} `json:"parse_dates"`
	Quotes []struct {
		ApartmentID int64  `json:"apartment_id"`
		DateFrom    string `json:"date_from"`
		DateTo      string `json:"date_to"`
		Guests      int    `json:"guests"`
		Now         string `json:"now"`
		Result      any    `json:"result"`
	} `json:"quotes"`
	Refunds []struct {
		Booking     RefundBooking `json:"booking"`
		CheckinHour int           `json:"checkin_hour"`
		Now         string        `json:"now"`
		ByHost      bool          `json:"by_host"`
		Result      int           `json:"result"`
	} `json:"refunds"`
	Tokens []struct {
		BookingID int64  `json:"booking_id"`
		Token     string `json:"token"`
		URL       string `json:"url"`
	} `json:"tokens"`
	TokenHash struct {
		Value  string `json:"value"`
		Result string `json:"result"`
	} `json:"token_hash"`
	Resolve []struct {
		Slug          string   `json:"slug"`
		Result        Resolved `json:"result"`
		FeedApartment *int64   `json:"feed_apartment"`
	} `json:"resolve"`
	Months []struct {
		ApartmentID int64  `json:"apartment_id"`
		Year        int    `json:"year"`
		Month       int    `json:"month"`
		DateFrom    string `json:"date_from"`
		DateTo      string `json:"date_to"`
		Now         string `json:"now"`
		Result      any    `json:"result"`
	} `json:"months"`
	RevolutLinks []struct {
		Link string `json:"link"`
		OK   bool   `json:"ok"`
	} `json:"revolut_links"`
	Rails []struct {
		ApartmentID int64    `json:"apartment_id"`
		OwnerUserID int64    `json:"owner_user_id"`
		Enabled     []string `json:"enabled"`
		Ready       bool     `json:"ready"`
		PayModes    []string `json:"pay_modes"`
	} `json:"rails"`
	ICal []struct {
		ApartmentID int64  `json:"apartment_id"`
		Today       string `json:"today"`
		Body        string `json:"body"`
	} `json:"ical"`
	StayICS []struct {
		BookingID int64  `json:"booking_id"`
		DateFrom  string `json:"date_from"`
		DateTo    string `json:"date_to"`
		Name      string `json:"name"`
		Body      string `json:"body"`
	} `json:"stay_ics"`
	FeedToken struct {
		Apartment1Good   bool   `json:"apartment_1_good"`
		Apartment1Bad    bool   `json:"apartment_1_bad"`
		Apartment2Bad    bool   `json:"apartment_2_bad"`
		Apartment2Length int    `json:"apartment_2_length"`
		Apartment2Stored string `json:"apartment_2_stored"`
		Apartment2Again  bool   `json:"apartment_2_again"`
	} `json:"feed_token"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g golden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Quotes) < 30 || len(g.Refunds) < 40 || len(g.Months) < 10 || len(g.Seed) == 0 {
		t.Fatal("golden file is missing cases")
	}
	return g
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL with
// the goose Up sections of App/migrations_pg; it skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_booking_%d", time.Now().UnixNano())
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
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
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

func seedValue(t *testing.T, v any) any {
	t.Helper()
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			t.Fatalf("seed value %s is not a whole number", n)
		}
		return i
	}
	return v
}

func seed(t *testing.T, pool *pgxpool.Pool, g golden) {
	t.Helper()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") +
			") VALUES (" + strings.Join(marks, ", ") + ")"
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(t, v)
			}
			if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
}

func mustTime(t *testing.T, s string) time.Time {
	t.Helper()
	v, err := time.Parse(time.RFC3339, s)
	if err != nil {
		t.Fatal(err)
	}
	return v
}

// sameJSON compares a Go value with a Python one by their JSON forms.
func sameJSON(t *testing.T, got, want any) (string, string, bool) {
	t.Helper()
	norm := func(v any) (any, string) {
		raw, err := json.Marshal(v)
		if err != nil {
			t.Fatal(err)
		}
		var out any
		if err := json.Unmarshal(raw, &out); err != nil {
			t.Fatal(err)
		}
		again, _ := json.Marshal(out)
		return out, string(again)
	}
	g, gs := norm(got)
	w, ws := norm(want)
	return gs, ws, reflect.DeepEqual(g, w)
}

func TestParseISODateMatchesPython(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.ParseDates {
		got, ok := ParseISODate(c.Value)
		if (c.ISO == nil) == ok || (ok && isoDay(got) != *c.ISO) {
			t.Errorf("ParseISODate(%q) = %v %v, Python %v", c.Value, got, ok, c.ISO)
		}
		day, ok := ParseDay(c.Value)
		if (c.Day == nil) == ok || (ok && isoDay(day) != *c.Day) {
			t.Errorf("ParseDay(%q) = %v %v, Python %v", c.Value, day, ok, c.Day)
		}
	}
}

func TestRefundMatchesPython(t *testing.T) {
	g := loadGolden(t)
	for i, c := range g.Refunds {
		got, err := RefundCZK(c.Booking, c.CheckinHour, mustTime(t, c.Now), c.ByHost)
		if err != nil {
			t.Fatal(err)
		}
		if got != c.Result {
			t.Errorf("refund %d %+v hour %d now %s host %v: got %d, Python %d",
				i, c.Booking, c.CheckinHour, c.Now, c.ByHost, got, c.Result)
		}
	}
}

func TestTokensAndLinksMatchPython(t *testing.T) {
	g := loadGolden(t)
	for _, c := range g.Tokens {
		if got := ManageToken(g.Secret, c.BookingID); got != c.Token {
			t.Errorf("ManageToken(%d) = %s, Python %s", c.BookingID, got, c.Token)
		}
		if !ManageTokenOK(g.Secret, c.BookingID, c.Token) || ManageTokenOK(g.Secret, c.BookingID, c.Token+"x") {
			t.Errorf("ManageTokenOK(%d) wrong", c.BookingID)
		}
	}
	if got := TokenHash(g.TokenHash.Value); got != g.TokenHash.Result {
		t.Errorf("TokenHash = %s, Python %s", got, g.TokenHash.Result)
	}
	for _, c := range g.RevolutLinks {
		if got := RevolutLinkOK(c.Link); got != c.OK {
			t.Errorf("RevolutLinkOK(%q) = %v, Python %v", c.Link, got, c.OK)
		}
	}
	for _, c := range g.StayICS {
		got, err := StayICS(c.BookingID, c.DateFrom, c.DateTo, c.Name, mustTime(t, g.Now))
		if err != nil || got != c.Body {
			t.Errorf("StayICS differs (%v)\n got: %q\nwant: %q", err, got, c.Body)
		}
	}
}

func TestDatabaseCasesMatchPython(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	ctx := context.Background()
	now := mustTime(t, g.Now)

	for _, c := range g.Settings {
		s, err := LoadSettings(ctx, pool, c.ApartmentID)
		if err != nil {
			t.Fatal(err)
		}
		if gs, ws, ok := sameJSON(t, s, c.Result); !ok {
			t.Errorf("settings %d\n got: %s\nwant: %s", c.ApartmentID, gs, ws)
		}
	}
	for _, c := range g.Quotes {
		q, err := GetQuote(ctx, pool, c.ApartmentID, c.DateFrom, c.DateTo, c.Guests, mustTime(t, c.Now))
		if err != nil {
			t.Fatal(err)
		}
		if gs, ws, ok := sameJSON(t, q.Map(), c.Result); !ok {
			t.Errorf("quote %d %q %q %d %s\n got: %s\nwant: %s", c.ApartmentID, c.DateFrom, c.DateTo,
				c.Guests, c.Now, gs, ws)
		}
	}
	for _, c := range g.Tokens {
		var aptID int64 = 1
		if c.BookingID == 999999 {
			aptID = 5
		}
		got, err := ManageURL(ctx, pool, g.PublicBase, g.Secret, aptID, c.BookingID)
		if err != nil || got != c.URL {
			t.Errorf("ManageURL(%d) = %s (%v), Python %s", c.BookingID, got, err, c.URL)
		}
	}
	for _, c := range g.Resolve {
		r, err := Resolve(ctx, pool, c.Slug)
		if err != nil {
			t.Fatal(err)
		}
		if r != c.Result {
			t.Errorf("Resolve(%q) = %+v, Python %+v", c.Slug, r, c.Result)
		}
		if (r.Kind == "redirect") != (RedirectPath(r) != "") {
			t.Errorf("RedirectPath(%+v) = %q", r, RedirectPath(r))
		}
		id, found, err := ApartmentForSlug(ctx, pool, c.Slug)
		if err != nil {
			t.Fatal(err)
		}
		if found != (c.FeedApartment != nil) || (found && id != *c.FeedApartment) {
			t.Errorf("ApartmentForSlug(%q) = %d %v, Python %v", c.Slug, id, found, c.FeedApartment)
		}
	}
	for _, c := range g.Months {
		grid, err := MonthGrid(ctx, pool, c.ApartmentID, c.Year, c.Month, c.DateFrom, c.DateTo, mustTime(t, c.Now))
		if err != nil {
			t.Fatal(err)
		}
		if gs, ws, ok := sameJSON(t, grid, c.Result); !ok {
			t.Errorf("month %d %d-%d %q %q %s\n got: %s\nwant: %s", c.ApartmentID, c.Year, c.Month,
				c.DateFrom, c.DateTo, c.Now, gs, ws)
		}
	}
	for _, c := range g.Rails {
		enabled, err := EnabledRails(ctx, pool, c.ApartmentID)
		if err != nil {
			t.Fatal(err)
		}
		ready, _ := RailsReady(ctx, pool, c.ApartmentID)
		modes, err := PayModes(ctx, pool, g.StripeMode, c.ApartmentID, c.OwnerUserID)
		if err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(enabled, c.Enabled) || ready != c.Ready || !reflect.DeepEqual(modes, c.PayModes) {
			t.Errorf("rails %d: %v %v %v, Python %v %v %v", c.ApartmentID, enabled, ready, modes,
				c.Enabled, c.Ready, c.PayModes)
		}
	}
	for _, c := range g.ICal {
		today, _ := ParseISODate(c.Today)
		body, err := ExportICS(ctx, pool, c.ApartmentID, today, now)
		if err != nil || body != c.Body {
			t.Errorf("ExportICS(%d, %s) differs (%v)\n got: %q\nwant: %q", c.ApartmentID, c.Today, err, body, c.Body)
		}
	}

	ft := g.FeedToken
	check := func(apt int64, token string, want bool) {
		ok, err := FeedTokenOK(ctx, pool, apt, token)
		if err != nil || ok != want {
			t.Errorf("FeedTokenOK(%d, %q) = %v (%v), Python %v", apt, token, ok, err, want)
		}
	}
	check(1, "tok-apt-1", ft.Apartment1Good)
	check(1, "tok-apt-2", ft.Apartment1Bad)
	check(2, "guess", ft.Apartment2Bad)
	var stored string
	if err := pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = 'booking_site:2'`).Scan(&stored); err != nil {
		t.Fatal(err)
	}
	s, err := LoadSettings(ctx, pool, 2)
	if err != nil {
		t.Fatal(err)
	}
	if len(s.ICalToken) != ft.Apartment2Length {
		t.Errorf("minted token length %d, Python %d", len(s.ICalToken), ft.Apartment2Length)
	}
	if got := strings.Replace(stored, s.ICalToken, "<token>", 1); got != ft.Apartment2Stored {
		t.Errorf("stored settings\n got: %s\nwant: %s", got, ft.Apartment2Stored)
	}
	check(2, s.ICalToken, ft.Apartment2Again)
}
