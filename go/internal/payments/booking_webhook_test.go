package payments

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// bookingGolden is testdata/booking_webhook/golden.json, written by
// App/scripts/booking_webhook_golden.py from the real Python handler.
type bookingGolden struct {
	Stamp   string `json:"stamp"`
	Secret  string `json:"secret"`
	BaseURL string `json:"base_url"`
	Seed    []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Events  []json.RawMessage `json:"events"`
	Results []string          `json:"results"`
	Refunds []map[string]any  `json:"refunds"`
	After   map[string]any    `json:"after"`
}

func loadBookingGolden(t *testing.T) bookingGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/booking_webhook/golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g bookingGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Events) == 0 || len(g.Events) != len(g.Results) {
		t.Fatal("golden file has no events or a result count mismatch")
	}
	return g
}

// seedBookingGolden inserts the golden seed, then moves each identity sequence
// past the seeded ids, as SQLite AUTOINCREMENT does.
func seedBookingGolden(t *testing.T, pool *pgxpool.Pool, g bookingGolden) {
	t.Helper()
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table,
			strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				if n, ok := v.(json.Number); ok {
					x, err := n.Int64()
					if err != nil {
						t.Fatal(err)
					}
					args[i] = x
				} else {
					args[i] = v
				}
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
		if table.Columns[0] == "id" {
			if _, err := pool.Exec(ctx, fmt.Sprintf(
				"SELECT setval(pg_get_serial_sequence('%s', 'id'), (SELECT MAX(id) FROM %s))",
				table.Table, table.Table)); err != nil {
				t.Fatalf("setval %s: %v", table.Table, err)
			}
		}
	}
}

func bookingEnv(g bookingGolden, extra map[string]string) func(string) string {
	env := map[string]string{
		"UBYHOST_STRIPE_MODE":           "test",
		"UBYHOST_STRIPE_SECRET_KEY":     "sk_test_golden",
		"UBYHOST_STRIPE_WEBHOOK_SECRET": "whsec_test",
		"UBYHOST_MAIL_BACKEND":          "console",
		"UBYHOST_PUBLIC_BASE_URL":       g.BaseURL,
		"UBYHOST_SECRET_KEY":            g.Secret,
	}
	for k, v := range extra {
		env[k] = v
	}
	return func(k string) string { return env[k] }
}

// fakeStripe records each refund request. Payment intent pi_fail gets a 402 on
// its first call only (Stripe then recovers), as the golden script's fake.
type fakeStripe struct {
	mu     sync.Mutex
	calls  []map[string]any
	failed int // refund calls answered with an error
}

func newFakeStripe(t *testing.T) (*fakeStripe, *httptest.Server) {
	t.Helper()
	f := &fakeStripe{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		form, _ := url.ParseQuery(string(raw))
		f.mu.Lock()
		if r.Method != http.MethodPost || r.URL.Path != "/v1/refunds" ||
			r.Header.Get("Authorization") != "Bearer sk_test_golden" {
			f.calls = append(f.calls, map[string]any{"unexpected": r.Method + " " + r.URL.Path})
		} else {
			f.calls = append(f.calls, map[string]any{
				"payment_intent":           form.Get("payment_intent"),
				"metadata_site_booking_id": form.Get("metadata[site_booking_id]"),
				"stripe_account":           r.Header.Get("Stripe-Account"),
				"idempotency_key":          r.Header.Get("Idempotency-Key"),
			})
		}
		fail := form.Get("payment_intent") == "pi_fail" && f.failed == 0
		if fail {
			f.failed++
		}
		f.mu.Unlock()
		if fail {
			w.WriteHeader(http.StatusPaymentRequired)
			_, _ = io.WriteString(w, `{"error":{"message":"fake Stripe error","code":"card_declined"}}`)
			return
		}
		_, _ = io.WriteString(w, `{"id":"re_1","status":"succeeded"}`)
	}))
	t.Cleanup(srv.Close)
	return f, srv
}

func bookingTS(v any, stamp string) any {
	if v == nil {
		return nil
	}
	if v == stamp {
		return "seed"
	}
	return "run"
}

// bookingRows reads rows as maps; ts columns become "seed", "run" or null.
func bookingRows(t *testing.T, pool *pgxpool.Pool, stamp, sql string, ts ...string) []any {
	t.Helper()
	rows, err := pool.Query(context.Background(), sql)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := []any{}
	for rows.Next() {
		vals, err := rows.Values()
		if err != nil {
			t.Fatal(err)
		}
		item := map[string]any{}
		for i, fd := range rows.FieldDescriptions() {
			item[fd.Name] = vals[i]
		}
		for _, c := range ts {
			item[c] = bookingTS(item[c], stamp)
		}
		out = append(out, item)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

// bookingSnapshot is _snapshot of the golden script, same queries.
func bookingSnapshot(t *testing.T, pool *pgxpool.Pool, stamp string) map[string]any {
	t.Helper()
	var calls int64
	if err := pool.QueryRow(context.Background(),
		`SELECT COALESCE(SUM(calls), 0)::bigint FROM lock_api_usage WHERE provider = 'stripe'`).Scan(&calls); err != nil {
		t.Fatal(err)
	}
	return map[string]any{
		"site_booking": bookingRows(t, pool, stamp,
			`SELECT id, status, reservation_id, hold_id, stripe_payment_intent_id, refunded_czk,
			 paid_at, updated_at FROM site_booking ORDER BY id`, "paid_at", "updated_at"),
		"reservation": bookingRows(t, pool, stamp,
			`SELECT id, apartment_id, source, uid, date_from, date_to, summary,
			 expected_guests_override, guest_email, status, created_at, updated_at
			 FROM reservation ORDER BY id`, "created_at", "updated_at"),
		"booking_hold": bookingRows(t, pool, stamp, `SELECT id FROM booking_hold ORDER BY id`),
		"email_outbox": bookingRows(t, pool, stamp,
			`SELECT idempotency_key, kind, reservation_id, apartment_id, owner_user_id, to_email,
			 cc_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at
			 FROM email_outbox ORDER BY id`, "next_attempt_at", "created_at", "updated_at"),
		"audit": bookingRows(t, pool, stamp,
			`SELECT at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id
			 FROM audit ORDER BY id`, "at"),
		"stripe_webhook_event": bookingRows(t, pool, stamp,
			`SELECT event_id, event_type, mode, created_at FROM stripe_webhook_event ORDER BY id`, "created_at"),
		"stripe_calls": calls,
	}
}

// canon round-trips a value through JSON so Go and golden values compare.
func canon(t *testing.T, v any) any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

func compareCanon(t *testing.T, what string, got, want any) {
	t.Helper()
	g, w := canon(t, got), canon(t, want)
	if reflect.DeepEqual(g, w) {
		return
	}
	gl, _ := json.MarshalIndent(g, "", " ")
	wl, _ := json.MarshalIndent(w, "", " ")
	t.Errorf("%s differs from Python\n got: %s\nwant: %s", what, gl, wl)
}

// TestBookingWebhookMatchesPython runs every golden event through Process and
// compares each outcome, the refund requests and the rows with Python's.
func TestBookingWebhookMatchesPython(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stripe, srv := newFakeStripe(t)
	now := func() time.Time { return testNow }
	bw := NewBookingWebhook(pool, bookingEnv(g, nil), now)
	bw.Stripe.APIBase = srv.URL
	for i, raw := range g.Events {
		var ev stripeEvent
		if err := json.Unmarshal(raw, &ev); err != nil {
			t.Fatal(err)
		}
		if !isBookingEvent(ev) {
			t.Fatalf("event %d is not a booking event", i)
		}
		got := "ok"
		if err := bw.Process(context.Background(), ev, "test"); err != nil {
			got = "error"
		}
		if got != g.Results[i] {
			t.Errorf("event %d (%s %s): Go %s, Python %s", i, ev.ID, ev.Type, got, g.Results[i])
		}
	}
	stripe.mu.Lock()
	refunds := stripe.calls
	stripe.mu.Unlock()
	compareCanon(t, "refund requests", refunds, g.Refunds)
	snap := bookingSnapshot(t, pool, g.Stamp)
	for key, want := range g.After {
		compareCanon(t, key, snap[key], want)
	}
}

// bookingPost signs and posts body to a handler built with extra env values.
func bookingPost(t *testing.T, pool *pgxpool.Pool, g bookingGolden, extra map[string]string, body []byte) (int, string) {
	t.Helper()
	h := WebhookHandler(pool, bookingEnv(g, extra), func() time.Time { return testNow })
	return fwdPost(h, body, fwdSigned(body), "")
}

func TestBookingSwitchOffForwards(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	body := []byte(`{"id":"evt_sw_off","type":"checkout.session.completed","data":{"object":{"id":"cs_1","payment_status":"paid","payment_intent":"pi_1","metadata":{"site_booking_id":"1"}}}}`)
	for _, v := range []string{"", "0", "true", "yes", "on"} {
		py, srv := newFakePy(t, http.StatusOK, "ok")
		code, out := bookingPost(t, pool, g, map[string]string{BookingSwitchEnv: v, "UBYHOST_PY_WEBHOOK_URL": srv.URL}, body)
		if code != 200 || out != "ok" || py.callCount() != 1 {
			t.Errorf("switch %q: got %d %q with %d python calls, want forwarded", v, code, out, py.callCount())
		}
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 1 AND status = 'pending'`); n != 1 {
		t.Errorf("switch off changed the booking")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event`); n != 0 {
		t.Errorf("switch off recorded %d events", n)
	}
}

func TestBookingSwitchOnHandlesInGo(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	py, srv := newFakePy(t, http.StatusOK, "ok")
	on := map[string]string{BookingSwitchEnv: " 1 ", "UBYHOST_PY_WEBHOOK_URL": srv.URL}

	paid := []byte(`{"id":"evt_sw_on","type":"checkout.session.completed","data":{"object":{"id":"cs_1","payment_status":"paid","payment_intent":"pi_1","metadata":{"site_booking_id":"1"}}}}`)
	if code, out := bookingPost(t, pool, g, on, paid); code != 200 || out != "ok" {
		t.Fatalf("paid: got %d %q, want 200 ok", code, out)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 1 AND status = 'paid' AND reservation_id IS NOT NULL`); n != 1 {
		t.Errorf("booking 1 not paid")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_sw_on'`); n != 1 {
		t.Errorf("event recorded %d times, want 1", n)
	}
	// The replay is a no-op that answers ok.
	if code, out := bookingPost(t, pool, g, on, paid); code != 200 || out != "ok" {
		t.Errorf("replay: got %d %q", code, out)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM reservation WHERE uid = 'site-1'`); n != 1 {
		t.Errorf("replay made %d stays, want 1", n)
	}

	// Booking 5 clashes and its host has no Stripe account: 500, not recorded.
	clash := []byte(`{"id":"evt_sw_err","type":"checkout.session.completed","data":{"object":{"id":"cs_5","payment_status":"paid","payment_intent":"pi_5","metadata":{"site_booking_id":"5"}}}}`)
	if code, _ := bookingPost(t, pool, g, on, clash); code != http.StatusInternalServerError {
		t.Errorf("refund impossible: got %d, want 500", code)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_sw_err'`); n != 0 {
		t.Errorf("failed event was recorded")
	}
	if py.callCount() != 0 {
		t.Errorf("switch on forwarded %d events to Python", py.callCount())
	}
}

func TestBookingDatesAndToken(t *testing.T) {
	bk := &siteBooking{id: 7, dateFrom: "2027-01-02", dateTo: "2027-12-31"}
	if got, _ := bookingDates(bk, "cs"); got != "2. 1. 2027 – 31. 12. 2027" {
		t.Errorf("cs dates: %q", got)
	}
	if got, _ := bookingDates(bk, "en"); got != "2027-01-02 – 2027-12-31" {
		t.Errorf("en dates: %q", got)
	}
	if _, err := bookingDates(&siteBooking{dateFrom: "bad", dateTo: "2027-01-01"}, "cs"); err == nil {
		t.Error("bad date accepted")
	}
	if NewBookingWebhook(nil, func(string) string { return "" }, time.Now) == nil {
		t.Error("constructor returned nil")
	}
}
