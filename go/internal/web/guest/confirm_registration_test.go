package guest

import (
	"context"
	"database/sql"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestConfirmRegistration_StampsCompletesAndIdempotent(t *testing.T) {
	pool := testPoolOptional(t)
	ctx := context.Background()

	var ownerID, aptID, resID, g1ID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, created_at) VALUES ('conf2096@example.test', 'x', 'host', '2026-01-01T00:00:00Z') RETURNING id`).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, internal_name, uby_name, permalink_token, active, checkin_hour, created_at) VALUES ($1, 'Confirm Flat', 'Confirm Flat', 'tokconf2096', 1, 15, '2026-01-01T00:00:00Z') RETURNING id`, ownerID).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at) VALUES ($1, 'uidconf2096', '2026-06-01', '2026-06-04', 'active', 'manual', 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z') RETURNING id`, aptID).Scan(&resID); err != nil {
		t.Fatal(err)
	}

	secret := strings.Repeat("s", 32)
	now := func() time.Time { return time.Date(2026, 6, 1, 10, 0, 0, 0, time.UTC) }
	getenv := func(k string) string {
		if k == "UBYHOST_SECRET_KEY" || k == "SECRET_KEY" {
			return secret
		}
		return ""
	}
	hooks := &recordingHooks{}

	mux := http.NewServeMux()
	passWrap := func(_ string, h http.HandlerFunc) http.Handler { return h }
	RegisterParty(mux, pool, getenv, now, passWrap, hooks)

	postConfirm := func() *httptest.ResponseRecorder {
		seedReq := httptest.NewRequest(http.MethodGet, "/", nil)
		csrfTok, csrfCookie, err := guestCSRF(seedReq, secret, getenv, now())
		if err != nil {
			t.Fatalf("guestCSRF: %v", err)
		}
		form := url.Values{"_csrf": {csrfTok}}
		req := httptest.NewRequest(http.MethodPost, GuestLink("tokconf2096", resID, "/confirm-registration?lang=en"), strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		if csrfCookie != nil {
			req.AddCookie(csrfCookie)
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		return rec
	}

	// 1. Before any guest is filled, POST confirm redirects back without stamping registration_completed_at.
	rec1 := postConfirm()
	if rec1.Code != http.StatusSeeOther {
		t.Fatalf("incomplete confirm status=%d, want 303", rec1.Code)
	}
	var comp1 sql.NullString
	if err := pool.QueryRow(ctx, `SELECT registration_completed_at FROM reservation WHERE id = $1`, resID).Scan(&comp1); err != nil {
		t.Fatal(err)
	}
	if comp1.Valid && comp1.String != "" {
		t.Fatalf("expected registration_completed_at NULL when incomplete, got %q", comp1.String)
	}
	if len(hooks.calls) != 0 {
		t.Fatalf("expected 0 completion calls when incomplete, got %v", hooks.calls)
	}

	// 2. Insert a complete guest, then POST confirm -> stamps registration_completed_at and triggers completion.
	if err := pool.QueryRow(ctx, `
		INSERT INTO guest (reservation_id, surname, first_name, birth_date, nationality, res_country,
			res_street, res_city, doc_number, purpose, stay_from, stay_to, signature_png, submit_state,
			filled_at, created_at, updated_at)
		VALUES ($1, 'Novak', 'Jan', '04031988', 'DEU', 'DEU',
			'Main 1', 'Munich', 'SYNTH9001', '99', '2026-06-01', '2026-06-04', 'imported', 'pending',
			'2026-06-01T09:50:00Z', '2026-06-01T09:50:00Z', '2026-06-01T09:50:00Z')
		RETURNING id`, resID).Scan(&g1ID); err != nil {
		t.Fatal(err)
	}
	rec2 := postConfirm()
	if rec2.Code != http.StatusSeeOther {
		t.Fatalf("complete confirm status=%d, want 303", rec2.Code)
	}
	if loc := rec2.Header().Get("Location"); !strings.Contains(loc, "confirmed=1") {
		t.Fatalf("expected redirect with confirmed=1, got %q", loc)
	}
	var comp2 sql.NullString
	if err := pool.QueryRow(ctx, `SELECT registration_completed_at FROM reservation WHERE id = $1`, resID).Scan(&comp2); err != nil {
		t.Fatal(err)
	}
	if !comp2.Valid || comp2.String == "" {
		t.Fatal("expected registration_completed_at set after confirm")
	}
	if len(hooks.calls) == 0 {
		t.Fatal("expected completion hooks called after confirm")
	}

	// 3. loadOwnedGuestNames returns ONLY guests in owned list (cross-device privacy boundary).
	if names := loadOwnedGuestNames(ctx, pool, resID, nil); len(names) != 0 {
		t.Fatalf("expected 0 names for empty owned list, got %v", names)
	}
	if names := loadOwnedGuestNames(ctx, pool, resID, []int64{g1ID}); len(names) != 1 || names[0] != "Jan Novak" {
		t.Fatalf("expected [Jan Novak], got %v", names)
	}
}

func TestStayTemplate_NeedsConfirmVsConfirmed(t *testing.T) {
	baseView := func(confirmed bool) stayView {
		v := stayView{
			Page:         Page{Lang: "en", CSRFToken: "tok"},
			StayFrom:     "2026-06-01",
			StayTo:       "2026-06-04",
			HasExpected:  true,
			Expected:     1,
			Filled:       1,
			HasRemaining: true,
			Remaining:    0,
			Confirmed:    confirmed,
			NeedsConfirm: !confirmed,
			ConfirmURL:   "/l/tok/1/confirm-registration?lang=en",
			AnotherURL:   "/l/tok/1/another?lang=en",
			Base:         "/l/tok/1",
			LangQ:        "?lang=en",
			Mine: []stayPerson{{
				Index: 1, ID: 10, Mine: true, Complete: true, Removable: true, Name: "Jan Novak",
				Summary: &stayPersonSummary{BirthDate: "01.02.1990", Nationality: "Germany", DocNumber: "AB123", Purpose: "Tourism"},
			}},
		}
		return v
	}

	var buf1 strings.Builder
	if err := staySet.ExecuteTemplate(&buf1, "content", baseView(false)); err != nil {
		t.Fatalf("render NeedsConfirm: %v", err)
	}
	html1 := buf1.String()
	if !strings.Contains(html1, `id="review-confirm"`) || !strings.Contains(html1, `data-confirm-registration`) {
		t.Fatalf("NeedsConfirm missing review-confirm card/button: %s", html1)
	}
	if !strings.Contains(html1, `<details class="g-card g-summary" open>`) {
		t.Fatalf("NeedsConfirm must render guest details open by default")
	}
	if strings.Contains(html1, `class="g-big-ok"`) {
		t.Fatalf("NeedsConfirm must NOT render g-big-ok")
	}

	var buf2 strings.Builder
	if err := staySet.ExecuteTemplate(&buf2, "content", baseView(true)); err != nil {
		t.Fatalf("render Confirmed: %v", err)
	}
	html2 := buf2.String()
	if !strings.Contains(html2, `class="g-big-ok"`) {
		t.Fatalf("Confirmed missing g-big-ok")
	}
	if strings.Contains(html2, `id="review-confirm"`) {
		t.Fatalf("Confirmed must NOT render review-confirm card")
	}
}
