package booking

import (
	"context"
	"errors"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type sessionRecorder struct {
	mu    sync.Mutex
	calls []SessionInput
	err   error
}

func (s *sessionRecorder) fn(_ context.Context, in SessionInput) (string, string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.calls = append(s.calls, in)
	if s.err != nil {
		return "", "", s.err
	}
	return "cs_test_77", "https://checkout.stripe.test/c/pay/cs_test_77", nil
}

func checkoutMux(t *testing.T, rec *sessionRecorder, direct DirectFunc, mutate func(pool *pgxpool.Pool)) (*http.ServeMux, *pgxpool.Pool) {
	t.Helper()
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	if mutate != nil {
		mutate(pool)
	}
	env := map[string]string{"UBYHOST_SECRET_KEY": g.Secret, "UBYHOST_STRIPE_MODE": "test", "UBYHOST_PUBLIC_BASE_URL": "https://book.example.test/"}
	now := mustTime(t, g.Now)
	c := Checkout{Pool: pool, Getenv: func(k string) string { return env[k] }, Now: func() time.Time { return now },
		Session: rec.fn, Direct: direct}
	mux := http.NewServeMux()
	mux.Handle("POST /p/{slug}/checkout", c.Handler())
	return mux, pool
}

func goodForm() url.Values {
	return url.Values{"date_from": {"2026-12-01"}, "date_to": {"2026-12-04"}, "guests": {"2"}, "lang": {"en"},
		"guest_name": {"  Ada   Lovelace "}, "guest_email": {" ada@example.test "}, "terms": {"1"},
		"terms_version": {TermsVersion}, "pay_mode": {"stripe"}}
}

func count(t *testing.T, pool *pgxpool.Pool, q string, args ...any) int64 {
	t.Helper()
	var n int64
	if err := pool.QueryRow(context.Background(), q, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestCheckoutCardHappyPath(t *testing.T) {
	rec := &sessionRecorder{}
	mux, pool := checkoutMux(t, rec, nil, nil)
	res := post(mux, "/p/old-town/checkout", goodForm())
	body := res.Body.String()
	if res.Code != 200 || !strings.Contains(body, `href="https://checkout.stripe.test/c/pay/cs_test_77"`) || !strings.Contains(body, "6500 CZK") {
		t.Fatalf("pay page: %d", res.Code)
	}
	if res.Header().Get("Cache-Control") != "no-store" || res.Header().Get("X-Robots-Tag") != "noindex" {
		t.Error("the pay page must be no-store and noindex")
	}
	if len(rec.calls) != 1 {
		t.Fatalf("%d Stripe sessions, want 1", len(rec.calls))
	}
	in := rec.calls[0]
	// 3 nights x 2000 + 500 cleaning = 6500 CZK; Stripe is told 6500 whole koruna.
	if in.AmountCZK != 6500 || in.Account != "acct_one" || in.Email != "ada@example.test" || in.Lang != "en" ||
		in.SuccessURL != "https://book.example.test/p/old-town/thanks?lang=en" ||
		in.CancelURL != "https://book.example.test/p/old-town?book=cancelled&lang=en" ||
		!strings.HasPrefix(in.ProductName, "Stay at ") || !strings.HasSuffix(in.ProductName, ", 2026-12-01 – 2026-12-04") {
		t.Errorf("session input: %+v", in)
	}
	var status, name, session, policy, tv string
	var total, nights, guests, hold int64
	err := pool.QueryRow(context.Background(), `SELECT status, guest_name, stripe_session_id, cancellation_policy, terms_version,
		total_czk, nights, guests, hold_id FROM site_booking WHERE id = $1`, in.BookingID).Scan(&status, &name, &session, &policy, &tv, &total, &nights, &guests, &hold)
	if err != nil || status != "pending" || name != "Ada Lovelace" || session != "cs_test_77" || policy != "moderate" ||
		tv != TermsVersion || total != 6500 || nights != 3 || guests != 2 {
		t.Errorf("booking row: %v %s %s %s %d %d %d", err, status, name, session, total, nights, guests)
	}
	var expires string
	if err := pool.QueryRow(context.Background(), `SELECT expires_at FROM booking_hold WHERE id = $1`, hold).Scan(&expires); err != nil || expires != "2026-11-28T10:15:00Z" {
		t.Errorf("hold expires %q %v, want 15 minutes after the clock", expires, err)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_checkout' AND detail = $1`, "id="+itoa(in.BookingID)+" session=cs_test_77"); n != 1 {
		t.Errorf("audit rows %d, want 1", n)
	}
	// The same nights are now held: a second guest is told they are taken.
	again := post(mux, "/p/old-town/checkout", goodForm())
	if again.Code != 303 || !strings.Contains(again.Header().Get("Location"), "book=taken") {
		t.Errorf("second guest: %d %q", again.Code, again.Header().Get("Location"))
	}
	if len(rec.calls) != 1 {
		t.Error("no Stripe session for a taken date")
	}
}

func itoa(n int64) string { return strconv.FormatInt(n, 10) }

func TestCheckoutValidation(t *testing.T) {
	rec := &sessionRecorder{}
	mux, pool := checkoutMux(t, rec, nil, nil)
	long := strings.Repeat("a", 121)
	cases := []struct {
		name   string
		mutate func(url.Values)
		code   int
		want   string // Location (303) or a body fragment (200)
	}{
		{"short name", func(f url.Values) { f.Set("guest_name", " ab ") }, 200, "Enter your full name."},
		{"long name", func(f url.Values) { f.Set("guest_name", long) }, 200, "That name is too long."},
		{"bad email", func(f url.Values) { f.Set("guest_email", "ada@example") }, 200, "Enter a valid e-mail."},
		{"nbsp in email", func(f url.Values) { f.Set("guest_email", "a da@example.test") }, 200, "Enter a valid e-mail."},
		{"no terms", func(f url.Values) { f.Del("terms") }, 200, "Tick the box to agree to the terms."},
		{"old terms", func(f url.Values) { f.Set("terms_version", "2026-01-01") }, 303, "/p/old-town?book=terms&lang=en&date_from=2026-12-01&date_to=2026-12-04&guests=2#book"},
		{"unknown mode", func(f url.Values) { f.Set("pay_mode", "bitcoin") }, 303, "/p/old-town?book=unavailable&lang=en&date_from=2026-12-01&date_to=2026-12-04&guests=2#book"},
		{"bad dates", func(f url.Values) { f.Set("date_from", "nope") }, 303, "/p/old-town?book=bad_dates&lang=en&date_from=nope&date_to=2026-12-04&guests=2#book"},
		{"no guests", func(f url.Values) { f.Del("guests") }, 303, "book="},
		{"min nights", func(f url.Values) { f.Set("date_to", "2026-12-02") }, 303, "/p/old-town?book=min_nights&lang=en&date_from=2026-12-01&date_to=2026-12-02&guests=2#book"},
	}
	for _, c := range cases {
		f := goodForm()
		c.mutate(f)
		res := post(mux, "/p/old-town/checkout", f)
		if res.Code != c.code {
			t.Errorf("%s: %d, want %d", c.name, res.Code, c.code)
			continue
		}
		if c.code == 303 && !strings.Contains(res.Header().Get("Location"), c.want) {
			t.Errorf("%s: Location %q, want it to contain %q", c.name, res.Header().Get("Location"), c.want)
		}
		if c.code == 200 {
			body := res.Body.String()
			if !strings.Contains(body, c.want) || res.Header().Get("Cache-Control") != "no-store" || res.Header().Get("X-Robots-Tag") != "noindex" {
				t.Errorf("%s: field error page wrong", c.name)
			}
			if c.name == "bad email" && (!strings.Contains(body, `value="Ada Lovelace"`) || !strings.Contains(body, `value="ada@example"`)) {
				t.Error("typed name and e-mail must come back in the form")
			}
			if strings.Contains(res.Header().Get("Location"), "ada") {
				t.Error("the e-mail must never be in a URL")
			}
		}
	}
	if len(rec.calls) != 0 || count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE guest_name IS NOT NULL AND id > 1000`) != 0 {
		t.Error("a refused form must create no booking and call no Stripe")
	}
}

func TestCheckoutStripeFailureFreesTheDates(t *testing.T) {
	rec := &sessionRecorder{err: errors.New("stripe: down")}
	mux, pool := checkoutMux(t, rec, nil, nil)
	holds := count(t, pool, `SELECT COUNT(*) FROM booking_hold`)
	res := post(mux, "/p/old-town/checkout", goodForm())
	if res.Code != 303 || !strings.Contains(res.Header().Get("Location"), "book=unavailable") {
		t.Fatalf("failure answer: %d %q", res.Code, res.Header().Get("Location"))
	}
	if count(t, pool, `SELECT COUNT(*) FROM booking_hold`) != holds {
		t.Error("the hold must be deleted")
	}
	if count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE status = 'expired' AND guest_email = 'ada@example.test'`) != 1 {
		t.Error("the booking must be expired")
	}
	if count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_checkout'`) != 0 {
		t.Error("no checkout audit line without a session")
	}
	rec.err = nil
	if post(mux, "/p/old-town/checkout", goodForm()).Code != 200 {
		t.Error("the dates are free again")
	}
}

func TestCheckoutGuards(t *testing.T) {
	rec := &sessionRecorder{}
	mux, _ := checkoutMux(t, rec, nil, nil)
	for _, slug := range []string{"draft", "nope", "old-town-2025"} {
		if res := post(mux, "/p/"+slug+"/checkout", goodForm()); res.Code != 404 {
			t.Errorf("%s: %d, want 404", slug, res.Code)
		}
	}
	demo, _ := checkoutMux(t, rec, nil, func(pool *pgxpool.Pool) {
		if _, err := pool.Exec(context.Background(), `UPDATE apartment SET internal_name = 'Vinohrady Studio (demo)' WHERE id = 1`); err != nil {
			t.Fatal(err)
		}
	})
	if res := post(demo, "/p/old-town/checkout", goodForm()); res.Code != 303 || !strings.Contains(res.Header().Get("Location"), "book=unavailable") {
		t.Errorf("demo property: %d", res.Code)
	}
	if len(rec.calls) != 0 {
		t.Error("no Stripe session for a demo property or a missing page")
	}
}

func TestCheckoutRateLimit(t *testing.T) {
	mux, _ := checkoutMux(t, &sessionRecorder{}, nil, nil)
	f := goodForm()
	f.Set("date_from", "nope")
	var last int
	for i := 0; i < checkoutMax+1; i++ {
		last = post(mux, "/p/old-town/checkout", f).Code
		if i < checkoutMax && last != 303 {
			t.Fatalf("request %d: %d, want 303", i+1, last)
		}
	}
	if last != http.StatusTooManyRequests {
		t.Errorf("request %d: %d, want 429", checkoutMax+1, last)
	}
}

func TestCheckoutDirect(t *testing.T) {
	f := goodForm()
	f.Set("pay_mode", "direct")
	none, _ := checkoutMux(t, &sessionRecorder{}, nil, nil)
	if res := post(none, "/p/old-town/checkout", f); res.Code != 303 || !strings.Contains(res.Header().Get("Location"), "book=unavailable") {
		t.Errorf("no direct starter: %d %q", res.Code, res.Header().Get("Location"))
	}
	var got DirectInput
	ok := func(_ context.Context, in DirectInput) (int64, string, error) { got = in; return 5, "", nil }
	mux, _ := checkoutMux(t, &sessionRecorder{}, ok, nil)
	res := post(mux, "/p/old-town/checkout", f)
	if res.Code != 303 || !strings.HasPrefix(res.Header().Get("Location"), "/p/old-town/b/5/") {
		t.Errorf("direct: %d %q", res.Code, res.Header().Get("Location"))
	}
	if got.Name != "Ada Lovelace" || got.Q.TotalCZK != 6500 || got.Lang != "en" {
		t.Errorf("direct input: %+v", got)
	}
	taken := func(context.Context, DirectInput) (int64, string, error) { return 0, "taken", nil }
	mux, _ = checkoutMux(t, &sessionRecorder{}, taken, nil)
	if res := post(mux, "/p/old-town/checkout", f); !strings.Contains(res.Header().Get("Location"), "book=taken") {
		t.Errorf("direct taken: %q", res.Header().Get("Location"))
	}
}

func TestHoldDatesSerialises(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	now := mustTime(t, g.Now)
	var won int32
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, ok, err := HoldDates(context.Background(), pool, 1, "2026-12-24", "2026-12-27", 15, now); err != nil {
				t.Error(err)
			} else if ok {
				atomic.AddInt32(&won, 1)
			}
		}()
	}
	wg.Wait()
	if won != 1 {
		t.Errorf("%d holds won, want exactly 1", won)
	}
	// Overlap by one night is taken; a stay starting on the check-out day is free.
	if _, ok, _ := HoldDates(context.Background(), pool, 1, "2026-12-26", "2026-12-29", 15, now); ok {
		t.Error("overlapping dates must be refused")
	}
	if _, ok, _ := HoldDates(context.Background(), pool, 1, "2026-12-27", "2026-12-29", 15, now); !ok {
		t.Error("back-to-back dates must be allowed")
	}
	// An expired hold frees its nights.
	later := now.Add(16 * time.Minute)
	if _, ok, _ := HoldDates(context.Background(), pool, 1, "2026-12-24", "2026-12-27", 15, later); !ok {
		t.Error("an expired hold must not block")
	}
}

func TestPureCheckoutHelpers(t *testing.T) {
	if got := ProductName("Garden", "2026-12-01", "2026-12-04", "cs"); got != "Ubytování Garden, 1. 12. 2026 – 4. 12. 2026" {
		t.Errorf("cs name %q", got)
	}
	if got := ProductName("Garden", "2026-12-01", "2026-12-04", "en"); got != "Stay at Garden, 2026-12-01 – 2026-12-04" {
		t.Errorf("en name %q", got)
	}
	valid := []string{"a@b.cz", strings.Repeat("a", 64) + "@x.example", "a@" + strings.Repeat("b", 100) + ".museum", "ě@é.cz"}
	invalid := []string{"a@b.c", strings.Repeat("a", 65) + "@x.example", "a@@b.cz", "a b@c.cz", "a@b.c z", "@b.cz", "a@.cz",
		"a@b." + strings.Repeat("c", 31), "a　b@c.cz", "a@b.cz\n"}
	for _, e := range valid {
		if !emailPattern.MatchString(e) {
			t.Errorf("%q must be valid", e)
		}
	}
	for _, e := range invalid {
		if emailPattern.MatchString(e) {
			t.Errorf("%q must be invalid", e)
		}
	}
}
