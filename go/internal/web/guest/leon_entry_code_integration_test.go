package guest

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

type entryCodeScriptModel struct{}

func (entryCodeScriptModel) Call(_ context.Context, feature string, _ []string, _ []anthropic.Message, _ json.RawMessage, _ *string, _ int) (map[string]any, error) {
	if feature != "leon" {
		return nil, &anthropic.Error{Reason: "disabled"}
	}
	return map[string]any{
		"kind": "ask_host", "reply": "", "sources": []any{},
		"host_summary": "Guest asked for an entry code", "upset": false,
	}, nil
}

func testEnvMap(m map[string]string) (func(string) string, func(string) (string, bool)) {
	getenv := func(k string) string { return m[k] }
	lookup := func(k string) (string, bool) {
		v, ok := m[k]
		return v, ok
	}
	return getenv, lookup
}

func seedEntryCodeLeon(t *testing.T, pool *pgxpool.Pool) (aptID, resID int64) {
	t.Helper()
	ctx := context.Background()
	aptID, resID = 77, 7701
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, created_at, email) VALUES (77, 'leontest', 'x', 'host', '2026-01-01', 'owner@example.test') ON CONFLICT DO NOTHING`)
	mustExecGuest(t, ctx, pool, `INSERT INTO legal_entity (id, owner_user_id, name, contact_email, created_at) VALUES (77, 77, 'Host Co', 'host@example.test', '2026-01-01') ON CONFLICT DO NOTHING`)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, legal_entity_id, internal_name, active, leon_enabled, leon_terms_version, guide_token, entry_code_enc, created_at)
		VALUES ($1, 77, 77, 'Gate Flat', 1, 1, '2026-10-25', 'qrtoken1234567890', 'SECRET99', '2026-01-01') ON CONFLICT DO NOTHING`, aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, date_from, date_to, archived_at, created_at, updated_at) VALUES ($1, $2, 'stay-uid', 'active', '2026-11-20', '2026-11-25', NULL, '2026-01-01', '2026-01-01') ON CONFLICT DO NOTHING`, resID, aptID)
	rows := []struct {
		id    int64
		kind  string
		steps string
	}{
		{7701, "checkin", "Ring the bell"},
		{7702, "wifi", "Network: Guest"},
		{7703, "heating", "Turn dial right"},
		{7704, "checkout", "Leave keys on table"},
		{7705, "emergency", "Call host"},
	}
	for _, r := range rows {
		mustExecGuest(t, ctx, pool, `INSERT INTO guide_item (id, apartment_id, topic, kind, title, steps, visibility, state, source, sort_order, created_at, updated_at)
			VALUES ($1, $2, 'custom', $3, $3, $4, 'everyone', 'done', 'host', $1, 'x', 'x') ON CONFLICT DO NOTHING`,
			r.id, aptID, r.kind, r.steps)
	}
	return aptID, resID
}

func TestLeonEntryCodeStayAndQRIntegration(t *testing.T) {
	pool := testPoolOptional(t)
	ctx := context.Background()
	aptID, resID := seedEntryCodeLeon(t, pool)
	getenv, lookup := testEnvMap(map[string]string{
		"UBYHOST_MAIL_BACKEND":      "console",
		"UBYHOST_AI_FEATURES":       "leon",
		"UBYHOST_ANTHROPIC_API_KEY": "test",
		"UBYHOST_AI_TEST_EMAILS":    "owner@example.test",
		"PUBLIC_BASE_URL":           "https://ubyhost.example",
		"APP_BASE_URL":              "https://ubyhost.example",
		"UBYHOST_PUBLIC_BASE_URL":   "https://ubyhost.example",
	})
	now := time.Date(2026, 11, 22, 12, 0, 0, 0, time.UTC)
	s := &lqServer{pool: pool, getenv: getenv, lookupEnv: lookup, now: func() time.Time { return now }, model: entryCodeScriptModel{}}

	body1, err := s.guestLeonPost(ctx, aptID, "stay", resID, "", "en", "what is the gate code?", "c1", "127.0.0.1", "booked", "Gate Flat")
	if err != nil {
		t.Fatal(err)
	}
	if body1["kind"] != "ask_host" || !strings.Contains(body1["text"].(string), "For your safety I don't share entry codes") {
		t.Fatalf("stay en: %+v", body1)
	}
	if body1["asked_host"] != true {
		t.Fatal("expected asked_host")
	}
	var openQ int
	_ = pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest_question WHERE apartment_id = $1 AND status = 'open'`, aptID).Scan(&openQ)
	if openQ != 1 {
		t.Fatalf("open questions %d", openQ)
	}
	var outbox int
	_ = pool.QueryRow(ctx, `SELECT COUNT(*) FROM email_outbox WHERE kind = 'guest_question'`).Scan(&outbox)
	if outbox != 1 {
		t.Fatalf("outbox after first %d", outbox)
	}

	_, err = s.guestLeonPost(ctx, aptID, "stay", resID, "", "en", "what is the building code?", "c2", "127.0.0.2", "booked", "Gate Flat")
	if err != nil {
		t.Fatal(err)
	}
	_ = pool.QueryRow(ctx, `SELECT COUNT(*) FROM email_outbox WHERE kind = 'guest_question'`).Scan(&outbox)
	if outbox != 1 {
		t.Fatalf("outbox after second %d", outbox)
	}
	var leaked string
	_ = pool.QueryRow(ctx, `SELECT COALESCE(string_agg(text,' '), '') FROM guest_chat_message m JOIN guest_chat c ON c.id = m.chat_id WHERE c.apartment_id = $1`, aptID).Scan(&leaked)
	if strings.Contains(leaked, "SECRET99") {
		t.Fatal("code in stored messages")
	}

	cookie := "abcdefghijklmnopqr"
	bodyQR, err := s.guestLeonPost(ctx, aptID, "qr", 0, cookie, "cs", "jaký je kód ke dveřím?", "c3", "127.0.0.3", "everyone", "Gate Flat")
	if err != nil {
		t.Fatal(err)
	}
	txt := bodyQR["text"].(string)
	if !strings.Contains(txt, "vstupní kódy") {
		t.Fatalf("qr cs: %q", txt)
	}
	store := ai.LeonStore{HavelStore: ai.HavelStore{Pool: pool, Env: lookup}}
	cards, err := store.GuestCards(ctx, aptID, "everyone")
	if err != nil || len(cards) == 0 {
		t.Fatal("cards")
	}
	blocks := ai.LeonSystemBlocks(cards, "Gate Flat")
	for _, b := range blocks {
		if strings.Contains(b, "SECRET99") {
			t.Fatal("code in system blocks")
		}
	}
}
