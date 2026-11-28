package booking

import (
	"bytes"
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/invoices"
)

func TestInvoicePDFHandlerIssuesOnDemandWhenUnset(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 15, 12, 0, 0, 0, time.UTC)
	ts := "2026-07-01T10:00:00+00:00"
	secret := "booking-invoice-ondemand-test-secret-0123456789"
	getenv := func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return secret
		}
		return ""
	}
	must := func(q string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, q, args...); err != nil {
			t.Fatalf("seed %q: %v", q, err)
		}
	}

	must(`INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (801, 'host801@example.test', 'x', 'host', 1, $1)`, ts)
	must(`INSERT INTO legal_entity (id, name, seat, ico, vat_status, registry_entry, invoice_prefix, invoice_due_days, owner_user_id, created_at)
		VALUES (802, 'Mountain Stays s.r.o.', 'Prague 2, Vinohradska 10', '12345678', 'non_payer',
		        'C 99999 vedená u Městského soudu v Praze', '2026', 14, 801, $1)`, ts)
	must(`INSERT INTO apartment (id, owner_user_id, legal_entity_id, internal_name, permalink_token, active, created_at)
		VALUES (803, 801, 802, 'Cabin Sumava', 'sumava-tok', 1, $1)`, ts)
	must(`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, created_at, updated_at)
		VALUES (804, 803, 'direct', 'sb-804', '2026-09-01', '2026-09-04', 'active', $1, $1)`, ts)

	var bookingID int64
	if err := pool.QueryRow(ctx, `INSERT INTO site_booking (
		apartment_id, owner_user_id, reservation_id, status, date_from, date_to, guests,
		guest_name, guest_email, lang, nights, nightly_czk, cleaning_fee_czk, total_czk,
		refunded_czk, cancellation_policy, terms_version, paid_at, created_at, updated_at)
		VALUES (803, 801, 804, 'paid', '2026-09-01', '2026-09-04', 2,
		        'Eva Guest', 'eva@example.test', 'cs', 3, 2000, 0, 6000,
		        0, 'flexible', '1.0', $1, $1, $1) RETURNING id`, ts).Scan(&bookingID); err != nil {
		t.Fatal(err)
	}

	mux := http.NewServeMux()
	RegisterCancelPDFs(mux, pool, getenv, func() time.Time { return now }, func(_ string, h http.HandlerFunc) http.Handler { return h })

	token := ManageToken(secret, bookingID)
	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/p/sumava/b/%d/%s/invoice.pdf", bookingID, token), nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body=%q)", rec.Code, rec.Body.String())
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/pdf" {
		t.Fatalf("Content-Type = %q, want application/pdf", ct)
	}
	if !bytes.HasPrefix(rec.Body.Bytes(), []byte("%PDF-")) {
		t.Fatalf("response body is not a PDF (len=%d)", rec.Body.Len())
	}
	var invID *int64
	if err := pool.QueryRow(ctx, `SELECT invoice_id FROM site_booking WHERE id = $1`, bookingID).Scan(&invID); err != nil {
		t.Fatal(err)
	}
	if invID == nil || *invID == 0 {
		t.Fatal("expected invoice_id to be persisted after on-demand download")
	}
}

func TestGuestCancelIssuesStornoOnFullRefund(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 15, 12, 0, 0, 0, time.UTC)
	ts := "2026-07-01T10:00:00+00:00"
	must := func(q string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, q, args...); err != nil {
			t.Fatalf("seed %q: %v", q, err)
		}
	}

	must(`INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (821, 'host821@example.test', 'x', 'host', 1, $1)`, ts)
	must(`INSERT INTO legal_entity (id, name, seat, ico, vat_status, registry_entry, invoice_prefix, invoice_due_days, owner_user_id, created_at)
		VALUES (822, 'River Stays s.r.o.', 'Prague 2, Vinohradska 10', '12345678', 'non_payer',
		        'C 99999 vedená u Městského soudu v Praze', '2026', 14, 821, $1)`, ts)
	must(`INSERT INTO apartment (id, owner_user_id, legal_entity_id, internal_name, permalink_token, active, created_at)
		VALUES (823, 821, 822, 'Cabin Otava', 'otava-tok', 1, $1)`, ts)
	must(`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, created_at, updated_at)
		VALUES (824, 823, 'direct', 'sb-824', '2026-09-01', '2026-09-04', 'active', $1, $1)`, ts)

	var bookingID int64
	if err := pool.QueryRow(ctx, `INSERT INTO site_booking (
		apartment_id, owner_user_id, reservation_id, status, date_from, date_to, guests,
		guest_name, guest_email, lang, nights, nightly_czk, cleaning_fee_czk, total_czk,
		refunded_czk, cancellation_policy, terms_version, paid_at, created_at, updated_at)
		VALUES (823, 821, 824, 'paid', '2026-09-01', '2026-09-04', 2,
		        'Eva Guest', 'eva@example.test', 'cs', 3, 2000, 0, 6000,
		        0, 'flexible', '1.0', $1, $1, $1) RETURNING id`, ts).Scan(&bookingID); err != nil {
		t.Fatal(err)
	}

	invID, ok, err := invoices.EnsureSiteBooking(ctx, pool, bookingID, now)
	if err != nil || !ok || invID == 0 {
		t.Fatalf("EnsureSiteBooking: id=%d ok=%v err=%v", invID, ok, err)
	}

	res, err := GuestCancel(ctx, pool, bookingID, now, nil)
	if err != nil {
		t.Fatal(err)
	}
	if res.Error != "" || res.RefundCZK != 6000 {
		t.Fatalf("GuestCancel = %+v, want full 6000 refund", res)
	}

	var kind string
	var corrID int64
	if err := pool.QueryRow(ctx, `SELECT id, kind FROM invoice WHERE corrects_invoice_id = $1`, invID).
		Scan(&corrID, &kind); err != nil {
		t.Fatalf("storno lookup: %v", err)
	}
	if kind != "storno" && kind != "corrective" {
		t.Fatalf("correction kind = %q, want storno or corrective", kind)
	}

	secret := "booking-cancel-storno-test-secret-0123456789"
	mux := http.NewServeMux()
	RegisterCancelPDFs(mux, pool, func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return secret
		}
		return ""
	}, func() time.Time { return now }, func(_ string, h http.HandlerFunc) http.Handler { return h })

	token := ManageToken(secret, bookingID)
	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/p/otava/b/%d/%s/correction.pdf", bookingID, token), nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("correction.pdf status = %d, want 200 (body=%q)", rec.Code, rec.Body.String())
	}
	if !bytes.HasPrefix(rec.Body.Bytes(), []byte("%PDF-")) {
		t.Fatalf("correction.pdf is not a PDF (len=%d)", rec.Body.Len())
	}
}
