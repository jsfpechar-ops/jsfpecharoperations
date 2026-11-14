package booking

import (
	"context"
	"net/http"
	"strings"
	"testing"
	"time"
)

func manageMux(t *testing.T, mutate func(pool DB)) (*http.ServeMux, golden) {
	t.Helper()
	g := loadGolden(t)
	pool := testPool(t)
	seed(t, pool, g)
	if mutate != nil {
		mutate(pool)
	}
	env := map[string]string{"UBYHOST_SECRET_KEY": g.Secret, "UBYHOST_STRIPE_MODE": "test", "UBYHOST_PUBLIC_BASE_URL": "https://book.example.test/"}
	now := mustTime(t, g.Now)
	mux := http.NewServeMux()
	mux.Handle("GET /p/{slug}/b/{booking_id}/{token}", ManageHandler(pool, func(k string) string { return env[k] },
		func() time.Time { return now }, func(p string) (string, error) { return "data:image/png;base64,QQ==", nil }))
	return mux, g
}

func managePath(g golden, id int64) string {
	return "/p/old-town/b/" + itoa(id) + "/" + ManageToken(g.Secret, id)
}

func TestManagePaidBooking(t *testing.T) {
	mux, g := manageMux(t, nil)
	rec := get(mux, managePath(g, 501))
	body := rec.Body.String()
	if rec.Code != 200 || rec.Header().Get("Cache-Control") != "no-store" || rec.Header().Get("X-Robots-Tag") != "noindex" {
		t.Fatalf("%d %v", rec.Code, rec.Header())
	}
	// Booking 501: moderate, check-in 10 Dec 15:00, clock 28 Nov. Full refund until 5 Dec 15:00;
	// refund now 6 500; city tax 50 x 2 guests x 3 nights = 300; language from the booking (cs).
	for _, want := range []string{
		`<html lang="cs">`, `data-tone="done"`, "10. 12. 2026", "13. 12. 2026", "6 500 Kč",
		"5. 12. 2026 15:00", "6500 Kč", "300 Kč",
		`action="/p/old-town/b/501/` + ManageToken(g.Secret, 501) + `/cancel?lang=cs"`,
		`/calendar.ics"`, `aria-current="true">CS`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("missing %q", want)
		}
	}
	if strings.Contains(body, "invoice.pdf") || strings.Contains(body, "correction.pdf") {
		t.Error("no invoice yet, no invoice link")
	}
	en := get(mux, managePath(g, 501)+"?lang=en").Body.String()
	if !strings.Contains(en, `<html lang="en">`) || !strings.Contains(en, "2026-12-05 15:00") || !strings.Contains(en, "6 500 CZK") {
		t.Error("English page wrong")
	}
	if !strings.Contains(get(mux, managePath(g, 501)+"?e=refund_failed").Body.String(), `role="alert"`) ||
		strings.Contains(get(mux, managePath(g, 501)+"?e=<x>").Body.String(), `role="alert"`) {
		t.Error("only the three listed errors show")
	}
}

func TestManageAccessRules(t *testing.T) {
	mux, g := manageMux(t, nil)
	cases := map[string]string{
		"wrong token":      "/p/old-town/b/501/" + strings.Repeat("0", 40),
		"pending booking":  managePath(g, 503),
		"unknown booking":  managePath(g, 999999),
		"not a number":     "/p/old-town/b/x/" + ManageToken(g.Secret, 501),
		"token of another": "/p/old-town/b/502/" + ManageToken(g.Secret, 501),
	}
	for name, path := range cases {
		if rec := get(mux, path); rec.Code != 404 {
			t.Errorf("%s: %d, want 404", name, rec.Code)
		}
	}
	// A cancelled card booking is shown, without the cancel form.
	rec := get(mux, managePath(g, 502))
	if rec.Code != 200 || strings.Contains(rec.Body.String(), "/cancel?") {
		t.Errorf("cancelled: %d", rec.Code)
	}
}

func TestManageDirectStates(t *testing.T) {
	mux, g := manageMux(t, func(db DB) {
		for _, q := range []string{
			`UPDATE site_booking SET pay_method = 'direct', status = 'requested' WHERE id = 503`,
			`UPDATE site_booking SET pay_method = 'direct' WHERE id = 502`,
		} {
			if _, err := db.Exec(context.Background(), q); err != nil {
				t.Fatal(err)
			}
		}
	})
	reqRec := get(mux, managePath(g, 503)+"?lang=en")
	body := reqRec.Body.String()
	for _, want := range []string{`class="pp-bk pp-bk-page pp-bk-req"`, "CZ65 0800 0000 1920 0014 5399", `src="data:image/png;base64,QQ=="`,
		"https://revolut.me/host1", "At the desk", "2027-02-01 – 2027-02-03", "4500"} {
		if !strings.Contains(body, want) {
			t.Errorf("requested page missing %q", want)
		}
	}
	if reqRec.Header().Get("Cache-Control") != "no-store" {
		t.Error("no-store")
	}
	// A direct booking the host declined (cancelled, never paid) is "declined".
	if body := get(mux, managePath(g, 502)).Body.String(); !strings.Contains(body, `data-tone="neutral"`) || strings.Contains(body, "/cancel?") {
		t.Error("declined direct booking page wrong")
	}
}

func TestManageExpiredRequest(t *testing.T) {
	mux, g := manageMux(t, func(db DB) {
		if _, err := db.Exec(context.Background(), `UPDATE site_booking SET pay_method = 'direct', status = 'expired' WHERE id = 503`); err != nil {
			t.Fatal(err)
		}
	})
	exp := get(mux, managePath(g, 503)+"?lang=en").Body.String()
	hold := Guest{Lang: "en"}.T("pp.book.req_hold")
	expired := Guest{Lang: "en"}.T("pp.book.req_expired")
	if !strings.Contains(exp, expired) || strings.Contains(exp, hold) {
		t.Error("an expired request says so")
	}
}

func TestManageRateLimitSharedWithCalendar(t *testing.T) {
	mux, g := manageMux(t, nil)
	var last int
	for i := 0; i < rateMax+1; i++ {
		last = get(mux, "/p/old-town/b/501/"+strings.Repeat("1", 40)).Code
	}
	if last != http.StatusTooManyRequests {
		t.Errorf("%d, want 429", last)
	}
	_ = g
}

func TestManagePureHelpers(t *testing.T) {
	if MaskEmail("ada@example.test") != "a***@example.test" || MaskEmail("nope") != "" || MaskEmail("@x") != "" || MaskEmail("ě@x.cz") != "ě***@x.cz" {
		t.Error("MaskEmail")
	}
	b := SiteBooking{DateFrom: "2026-12-10", Policy: "moderate"}
	if got, _ := DeadlineLabel(b, 15, "cs"); got != "5. 12. 2026 15:00" {
		t.Errorf("moderate cs %q", got)
	}
	b.Policy = "flexible"
	if got, _ := DeadlineLabel(b, 15, "en"); got != "2026-12-09 15:00" {
		t.Errorf("flexible en %q", got)
	}
	b.Policy = "non_refundable"
	if got, _ := DeadlineLabel(b, 15, "en"); got != "" {
		t.Errorf("non_refundable %q", got)
	}
	// 25 Oct 2026 is the end of DST: wall-clock subtraction, as Python does.
	b = SiteBooking{DateFrom: "2026-10-26", Policy: "flexible"}
	if got, _ := DeadlineLabel(b, 15, "en"); got != "2026-10-25 15:00" {
		t.Errorf("DST wall clock %q", got)
	}
	now := time.Date(2026, 12, 10, 14, 0, 0, 0, time.UTC) // 15:00 Prague: check-in has begun
	if s, _ := Started(SiteBooking{DateFrom: "2026-12-10"}, 15, now); !s {
		t.Error("check-in at 15:00 Prague has started at 14:00 UTC")
	}
	if s, _ := Started(SiteBooking{DateFrom: "2026-12-10"}, 15, now.Add(-time.Second)); s {
		t.Error("not started a second earlier")
	}
	if DayLabel("2026-12-05", "cs") != "5. 12. 2026" || DayLabel("2026-12-05", "en") != "2026-12-05" {
		t.Error("DayLabel")
	}
}
