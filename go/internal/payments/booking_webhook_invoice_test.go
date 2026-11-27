package payments

import (
	"bytes"
	"context"
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestBookingWebhookAutoIssuesInvoiceOnPaid(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)

	ctx := context.Background()
	// Ensure the operator entity has complete invoice seller fields (seat + registry).
	if _, err := pool.Exec(ctx,
		`UPDATE legal_entity SET seat = 'Na Prikope 1, Prague', ico = '12345678', vat_status = 'non_payer',
		        registry_entry = 'C 12345 vedená u Městského soudu v Praze', invoice_prefix = '2026', invoice_due_days = 14`); err != nil {
		t.Fatal(err)
	}

	// Pick the first checkout.session.completed event that transitions a pending booking to paid.
	var ev stripeEvent
	var targetSession string
	for _, raw := range g.Events {
		var cand stripeEvent
		if err := json.Unmarshal(raw, &cand); err != nil {
			t.Fatal(err)
		}
		if cand.Type == "checkout.session.completed" {
			sessID, _ := cand.Data.Object["id"].(string)
			var status string
			if err := pool.QueryRow(ctx, `SELECT status FROM site_booking WHERE stripe_session_id = $1`, sessID).Scan(&status); err == nil && status == "pending" {
				ev = cand
				targetSession = sessID
				break
			}
		}
	}
	if targetSession == "" {
		t.Fatal("no pending checkout.session.completed event in golden")
	}

	bw := NewBookingWebhook(pool, bookingEnv(g, nil), func() time.Time { return testNow })
	if bw.EnsureInvoice == nil {
		t.Fatal("NewBookingWebhook must wire EnsureInvoice by default")
	}
	if err := bw.Process(ctx, ev, "test"); err != nil {
		t.Fatalf("Process: %v", err)
	}

	var status string
	var totalCZK int64
	var invoiceID *int64
	if err := pool.QueryRow(ctx, `SELECT status, total_czk, invoice_id FROM site_booking WHERE stripe_session_id = $1`, targetSession).
		Scan(&status, &totalCZK, &invoiceID); err != nil {
		t.Fatal(err)
	}
	if status != "paid" {
		t.Fatalf("booking status = %q, want paid", status)
	}
	if invoiceID == nil || *invoiceID == 0 {
		t.Fatal("expected site_booking.invoice_id to be set automatically on paid webhook")
	}
	var totalHaler int64
	var blob []byte
	if err := pool.QueryRow(ctx, `SELECT total_haler, pdf_blob FROM invoice WHERE id = $1`, *invoiceID).Scan(&totalHaler, &blob); err != nil {
		t.Fatal(err)
	}
	if totalHaler != totalCZK*100 {
		t.Fatalf("invoice total_haler = %d, want %d", totalHaler, totalCZK*100)
	}
	if !bytes.HasPrefix(blob, []byte("%PDF-")) {
		t.Fatalf("invoice pdf_blob missing %%PDF- header (len=%d)", len(blob))
	}
}

func TestBookingWebhookInvoiceSkippedDoesNotFailWebhook(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)

	ctx := context.Background()
	// Strip legal_entity_id so booking_invoice.ensure skips with reason=no_entity.
	if _, err := pool.Exec(ctx, `UPDATE apartment SET legal_entity_id = NULL`); err != nil {
		t.Fatal(err)
	}

	var ev stripeEvent
	var targetSession string
	for _, raw := range g.Events {
		var cand stripeEvent
		if err := json.Unmarshal(raw, &cand); err != nil {
			t.Fatal(err)
		}
		if cand.Type == "checkout.session.completed" {
			sessID, _ := cand.Data.Object["id"].(string)
			var status string
			if err := pool.QueryRow(ctx, `SELECT status FROM site_booking WHERE stripe_session_id = $1`, sessID).Scan(&status); err == nil && status == "pending" {
				ev = cand
				targetSession = sessID
				break
			}
		}
	}
	if targetSession == "" {
		t.Fatal("no pending checkout.session.completed event in golden")
	}

	bw := NewBookingWebhook(pool, bookingEnv(g, nil), func() time.Time { return testNow })
	if err := bw.Process(ctx, ev, "test"); err != nil {
		t.Fatalf("webhook must still succeed when invoice is skipped: %v", err)
	}
	var status string
	var invoiceID *int64
	if err := pool.QueryRow(ctx, `SELECT status, invoice_id FROM site_booking WHERE stripe_session_id = $1`, targetSession).
		Scan(&status, &invoiceID); err != nil {
		t.Fatal(err)
	}
	if status != "paid" || invoiceID != nil {
		t.Fatalf("status=%q invoice_id=%v, want paid + nil", status, invoiceID)
	}
	var detail string
	if err := pool.QueryRow(ctx, `SELECT detail FROM audit WHERE action = 'site_invoice_skipped' ORDER BY id DESC LIMIT 1`).Scan(&detail); err != nil {
		t.Fatalf("expected site_invoice_skipped audit row: %v", err)
	}
	if !strings.Contains(detail, "reason=no_entity") {
		t.Fatalf("audit detail = %q, want reason=no_entity", detail)
	}
}
