package invoices

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func TestBookingIssueForm(t *testing.T) {
	cs := BookingIssueForm(4500, 600, "Jan Novak", "jan@example.test", "cs")
	if cs.Get("lang") != "cs" || cs.Get("stay_price") != "4500" || cs.Get("stay_vat_rate") != "12" {
		t.Fatalf("cs core fields: %v", cs)
	}
	if cs.Get("paid_via") != "custom" || cs.Get("paid_via_custom") != "Kartou přes Stripe" {
		t.Fatalf("cs paid_via: %v", cs)
	}
	if cs.Get("note") != "V ceně je úklid 600 Kč." {
		t.Fatalf("cs note: %q", cs.Get("note"))
	}

	en := BookingIssueForm(3200, 0, "Ada Tester", "ada@example.test", "en")
	if en.Get("lang") != "en" || en.Get("paid_via_custom") != "Card via Stripe" || en.Get("note") != "" {
		t.Fatalf("en fields: %v", en)
	}

	fallback := BookingIssueForm(1000, 200, "Guest", "g@example.test", "de")
	if fallback.Get("lang") != "cs" || fallback.Get("paid_via_custom") != "Kartou přes Stripe" {
		t.Fatalf("unsupported lang must default to cs: %v", fallback)
	}
}

func seedSiteBookingFixture(t *testing.T, pool *pgxpool.Pool, withEntity bool, entitySeat string, status string) (bookingID, resID int64) {
	t.Helper()
	ctx := context.Background()
	ts := "2026-07-01T10:00:00+00:00"
	must := func(q string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, q, args...); err != nil {
			t.Fatalf("seed %q: %v", q, err)
		}
	}
	must(`INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (701, 'host@example.test', 'x', 'host', 1, $1) ON CONFLICT DO NOTHING`, ts)
	var leID *int64
	if withEntity {
		id := int64(702)
		leID = &id
		must(`INSERT INTO legal_entity (id, name, seat, ico, vat_status, registry_entry, invoice_prefix, invoice_due_days, owner_user_id, created_at)
			VALUES (702, 'Alpine Stays s.r.o.', $1, '12345678', 'non_payer', 'C 12345 vedená u Městského soudu v Praze', '2026', 14, 701, $2)
			ON CONFLICT (id) DO UPDATE SET seat = EXCLUDED.seat`, entitySeat, ts)
	}
	must(`INSERT INTO apartment (id, owner_user_id, legal_entity_id, internal_name, permalink_token, active, created_at)
		VALUES (703, 701, $1, 'Studio Lipa', 'lipa-tok', 1, $2)
		ON CONFLICT (id) DO UPDATE SET legal_entity_id = EXCLUDED.legal_entity_id`, leID, ts)
	resID = 704
	must(`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, created_at, updated_at)
		VALUES (704, 703, 'direct', 'sb-704', '2026-08-10', '2026-08-13', 'active', $1, $1)
		ON CONFLICT DO NOTHING`, ts)
	err := pool.QueryRow(ctx, `INSERT INTO site_booking (
		apartment_id, owner_user_id, reservation_id, status, date_from, date_to, guests,
		guest_name, guest_email, lang, nights, nightly_czk, cleaning_fee_czk, total_czk,
		refunded_czk, cancellation_policy, terms_version, paid_at, created_at, updated_at)
		VALUES (703, 701, 704, $1, '2026-08-10', '2026-08-13', 2,
		        'Ada Tester', 'ada@example.test', 'en', 3, 1500, 500, 5000,
		        0, 'flexible', '1.0', $2, $2, $2) RETURNING id`, status, ts).Scan(&bookingID)
	if err != nil {
		t.Fatal(err)
	}
	return bookingID, resID
}

func TestEnsureSiteBookingIssuesAndStoresPDF(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 15, 12, 0, 0, 0, time.UTC)
	bookingID, _ := seedSiteBookingFixture(t, pool, true, "Prague 1, Na Prikope 1", "paid")

	invID, ok, err := EnsureSiteBooking(ctx, pool, bookingID, now)
	if err != nil || !ok || invID == 0 {
		t.Fatalf("EnsureSiteBooking: id=%d ok=%v err=%v", invID, ok, err)
	}

	var storedID *int64
	if err := pool.QueryRow(ctx, `SELECT invoice_id FROM site_booking WHERE id = $1`, bookingID).Scan(&storedID); err != nil {
		t.Fatal(err)
	}
	if storedID == nil || *storedID != invID {
		t.Fatalf("site_booking.invoice_id = %v, want %d", storedID, invID)
	}

	var totalHaler int64
	var lang, paidVia, note, sha string
	var blob []byte
	if err := pool.QueryRow(ctx,
		`SELECT total_haler, lang, COALESCE(paid_via, ''), COALESCE(note, ''), COALESCE(pdf_sha256, ''), pdf_blob FROM invoice WHERE id = $1`,
		invID).Scan(&totalHaler, &lang, &paidVia, &note, &sha, &blob); err != nil {
		t.Fatal(err)
	}
	if totalHaler != 500000 || lang != "en" || paidVia != "Card via Stripe" {
		t.Fatalf("invoice fields: total=%d lang=%q paidVia=%q", totalHaler, lang, paidVia)
	}
	if !strings.Contains(note, "500 CZK") {
		t.Fatalf("invoice note missing cleaning fee: %q", note)
	}
	if !bytes.HasPrefix(blob, []byte("%PDF-")) {
		t.Fatalf("pdf_blob does not start with %%PDF- (len=%d)", len(blob))
	}
	sum := sha256.Sum256(blob)
	if hex.EncodeToString(sum[:]) != sha {
		t.Fatalf("pdf_sha256 mismatch")
	}

	// Idempotent second call returns the same invoice id without creating a duplicate.
	invID2, ok2, err2 := EnsureSiteBooking(ctx, pool, bookingID, now)
	if err2 != nil || !ok2 || invID2 != invID {
		t.Fatalf("second EnsureSiteBooking: id=%d ok=%v err=%v, want %d", invID2, ok2, err2, invID)
	}

	// Partial credit note & storno smoke check.
	partID, err := CorrectSiteBookingPartial(ctx, pool, invID, 2000, SiteBookingCancelReason("en"), now)
	if err != nil || partID == 0 {
		t.Fatalf("CorrectSiteBookingPartial: id=%d err=%v", partID, err)
	}
	var partTotal int64
	if err := pool.QueryRow(ctx, `SELECT total_haler FROM invoice WHERE id = $1`, partID).Scan(&partTotal); err != nil {
		t.Fatal(err)
	}
	if partTotal != -200000 {
		t.Fatalf("partial credit note total_haler = %d, want -200000", partTotal)
	}
}

func TestEnsureSiteBookingSkipsGracefully(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 15, 12, 0, 0, 0, time.UTC)

	// Unpaid booking: no invoice and no skip audit.
	pendingID, _ := seedSiteBookingFixture(t, pool, false, "", "pending")
	if id, ok, err := EnsureSiteBooking(ctx, pool, pendingID, now); err != nil || ok || id != 0 {
		t.Fatalf("pending booking: id=%d ok=%v err=%v", id, ok, err)
	}
	var audits int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM audit WHERE action = 'site_invoice_skipped'`).Scan(&audits); err != nil {
		t.Fatal(err)
	}
	if audits != 0 {
		t.Fatalf("expected 0 skip audits for pending booking, got %d", audits)
	}

	// Paid booking without legal entity: skips and logs audit.
	noEntID, _ := seedSiteBookingFixture(t, pool, false, "", "paid")
	if id, ok, err := EnsureSiteBooking(ctx, pool, noEntID, now); err != nil || ok || id != 0 {
		t.Fatalf("paid without entity: id=%d ok=%v err=%v", id, ok, err)
	}
	var detail string
	if err := pool.QueryRow(ctx, `SELECT detail FROM audit WHERE action = 'site_invoice_skipped' ORDER BY id DESC LIMIT 1`).Scan(&detail); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(detail, "reason=no_entity") {
		t.Fatalf("audit detail = %q, want reason=no_entity", detail)
	}
}

func TestAdjustAfterRefundIssuesStornoOnFullRefund(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 15, 12, 0, 0, 0, time.UTC)
	bookingID, _ := seedSiteBookingFixture(t, pool, true, "Prague 1, Na Prikope 1", "paid")
	invID, ok, err := EnsureSiteBooking(ctx, pool, bookingID, now)
	if err != nil || !ok || invID == 0 {
		t.Fatalf("EnsureSiteBooking: id=%d ok=%v err=%v", invID, ok, err)
	}

	AdjustAfterRefund(ctx, pool, bookingID, 5000, now)

	var kind string
	var totalHaler int64
	var corrID int64
	if err := pool.QueryRow(ctx, `SELECT id, kind, total_haler FROM invoice WHERE corrects_invoice_id = $1`, invID).
		Scan(&corrID, &kind, &totalHaler); err != nil {
		t.Fatalf("storno lookup: %v", err)
	}
	if kind != "storno" || totalHaler != -500000 {
		t.Fatalf("correction: kind=%q total=%d, want storno -500000", kind, totalHaler)
	}

	AdjustAfterRefund(ctx, pool, bookingID, 5000, now)
	var n int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM invoice WHERE corrects_invoice_id = $1`, invID).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Fatalf("second AdjustAfterRefund created extra invoice: count=%d", n)
	}
	var audits int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM audit WHERE action = 'site_invoice_needs_correction'`).Scan(&audits); err != nil {
		t.Fatal(err)
	}
	if audits < 1 {
		t.Fatal("expected site_invoice_needs_correction audit after already-corrected retry")
	}
}

func TestAdjustAfterRefundIssuesPartialCreditNote(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 7, 15, 12, 0, 0, 0, time.UTC)
	bookingID, _ := seedSiteBookingFixture(t, pool, true, "Prague 1, Na Prikope 1", "paid")
	invID, ok, err := EnsureSiteBooking(ctx, pool, bookingID, now)
	if err != nil || !ok || invID == 0 {
		t.Fatalf("EnsureSiteBooking: id=%d ok=%v err=%v", invID, ok, err)
	}

	AdjustAfterRefund(ctx, pool, bookingID, 2000, now)

	var kind string
	var totalHaler int64
	if err := pool.QueryRow(ctx, `SELECT kind, total_haler FROM invoice WHERE corrects_invoice_id = $1`, invID).
		Scan(&kind, &totalHaler); err != nil {
		t.Fatalf("credit note lookup: %v", err)
	}
	if (kind != "storno" && kind != "corrective") || totalHaler != -200000 {
		t.Fatalf("partial correction: kind=%q total=%d, want storno/corrective -200000", kind, totalHaler)
	}
}
