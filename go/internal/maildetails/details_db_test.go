package maildetails_test

import (
	"context"
	"encoding/json"
	"errors"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/maildetails"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// recorder wraps the real renderer and keeps the last block it returned, so a
// test can compare what the drain filled in without reading the sent mail.
type recorder struct {
	inner    maildetails.Renderer
	lastText string
	lastHTML string
}

func (r *recorder) GuestDetails(ctx context.Context, pool *pgxpool.Pool, id int64, lang string, asHTML bool) (string, error) {
	return r.inner.GuestDetails(ctx, pool, id, lang, asHTML)
}

func (r *recorder) ReceiptDetails(ctx context.Context, pool *pgxpool.Pool, id int64, lang string, asHTML bool) (string, error) {
	out, err := r.inner.ReceiptDetails(ctx, pool, id, lang, asHTML)
	if asHTML {
		r.lastHTML = out
	} else {
		r.lastText = out
	}
	return out, err
}

// drainConfig is the real mail.Config with the console backend (no network).
func drainConfig(t *testing.T, key string, d mail.DetailsRenderer) mail.Config {
	t.Helper()
	keys, err := secure.NewMultiFernet([]byte(key))
	if err != nil {
		t.Fatal(err)
	}
	return mail.Config{
		Backend: mail.BackendConsole, Deployment: "staging", From: "noreply@mail.example.test",
		Keys: keys, Details: d,
		Now: func() time.Time { return time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC) },
	}
}

// queueRow inserts a queued outbox row like the 2065 completion path does and
// removes it at the end of the test.
func queueRow(t *testing.T, pool *pgxpool.Pool, key, kind string, payload map[string]any) int64 {
	t.Helper()
	raw, _ := json.Marshal(payload)
	var id int64
	err := pool.QueryRow(context.Background(),
		`INSERT INTO email_outbox (idempotency_key, kind, to_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		 VALUES ($1, $2, 'guest@example.test', 'Subject', $3, 'queued', 0, '2026-11-13T09:00:00Z', '2026-11-13T09:00:00+00:00', '2026-11-13T09:00:00+00:00')
		 RETURNING id`, key, kind, string(raw)).Scan(&id)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if _, err := pool.Exec(context.Background(), `DELETE FROM email_outbox WHERE id = $1`, id); err != nil {
			t.Fatal(err)
		}
	})
	return id
}

func outboxState(t *testing.T, pool *pgxpool.Pool, id int64) (string, int) {
	t.Helper()
	var state string
	var attempts int
	if err := pool.QueryRow(context.Background(),
		`SELECT state, attempts FROM email_outbox WHERE id = $1`, id).Scan(&state, &attempts); err != nil {
		t.Fatal(err)
	}
	return state, attempts
}

func goldenNamed(t *testing.T, g golden, name string) goldenCase {
	t.Helper()
	for _, c := range g.Cases {
		if c.Name == name {
			return c
		}
	}
	t.Fatalf("golden case %q missing", name)
	return goldenCase{}
}

func TestDrainFillsReceiptDetails(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	c := goldenNamed(t, g, "lead_typed_here_9_chars")
	seedStay(t, pool, c)
	rec := &recorder{inner: maildetails.Renderer{Getenv: goldenEnv(g.FernetKey)}}
	id := queueRow(t, pool, "2067-receipt-filled", "completion", map[string]any{
		"text": "Thanks\n{{receipt_details}}", "html": "<p>Thanks</p>{{receipt_details}}",
		"receipt_details_reservation_id": c.ReservationID, "lang": "en",
	})
	if _, err := mail.Drain(context.Background(), pool, drainConfig(t, g.FernetKey, rec), 8); err != nil {
		t.Fatalf("drain: %v", err)
	}
	if state, _ := outboxState(t, pool, id); state != "sent" {
		t.Fatalf("state %q, want sent", state)
	}
	if rec.lastText != c.ExpectText || rec.lastHTML != c.ExpectHTML {
		t.Fatalf("filled block differs\ntext: %q\nhtml: %q", rec.lastText, rec.lastHTML)
	}
}

func TestDrainDeletedStayIsSentWithEmptyBlock(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	rec := &recorder{inner: maildetails.Renderer{Getenv: goldenEnv(g.FernetKey)}}
	id := queueRow(t, pool, "2067-deleted-stay", "completion", map[string]any{
		"text": "Thanks\n{{receipt_details}}", "html": "<p>Thanks</p>{{receipt_details}}",
		"receipt_details_reservation_id": int64(555001), "lang": "en",
	})
	if _, err := mail.Drain(context.Background(), pool, drainConfig(t, g.FernetKey, rec), 8); err != nil {
		t.Fatalf("drain: %v", err)
	}
	if state, _ := outboxState(t, pool, id); state != "sent" {
		t.Fatalf("state %q, want sent", state)
	}
	if rec.lastText != "" || rec.lastHTML != "" {
		t.Fatalf("block must be empty for a deleted stay: %q %q", rec.lastText, rec.lastHTML)
	}
}

func TestDrainReceiptWithoutStayIDCountsDecryptionFailure(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	id := queueRow(t, pool, "2067-receipt-no-id", "completion", map[string]any{
		"text": "Thanks\n{{receipt_details}}", "lang": "en",
	})
	rec := &recorder{inner: maildetails.Renderer{Getenv: goldenEnv(g.FernetKey)}}
	sum, err := mail.Drain(context.Background(), pool, drainConfig(t, g.FernetKey, rec), 8)
	if err != nil || sum.Failed != 1 || sum.Sent != 0 {
		t.Fatalf("drain: want one failed attempt (ErrDecryption path), got %+v %v", sum, err)
	}
	state, attempts := outboxState(t, pool, id)
	if state == "sent" || attempts != 1 {
		t.Fatalf("row must not be sent and must count one attempt: %s %d", state, attempts)
	}
}

func TestGuestDetailsStillNoRenderer(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	id := queueRow(t, pool, "2067-guest-details", "guest_details_host", map[string]any{
		"text": "{{guest_details}}", "guest_details_reservation_id": int64(101), "lang": "en",
	})
	// 2068 replaces this: once the guest list renders, this row is sent.
	_, err := mail.Drain(context.Background(), pool, drainConfig(t, g.FernetKey, maildetails.Renderer{}), 8)
	if !errors.Is(err, mail.ErrNoDetailsRenderer) {
		t.Fatalf("drain: want ErrNoDetailsRenderer, got %v", err)
	}
	if state, _ := outboxState(t, pool, id); state != "queued" {
		t.Fatalf("state %q, want queued", state)
	}
}
