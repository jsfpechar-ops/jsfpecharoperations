package guest

import (
	"context"
	"fmt"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guideimport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// seedHandoffQuestions inserts one open urgent, one answered and one dismissed
// question on apartment 78 (chat 780). Rows are cleared first so reruns start clean.
func seedHandoffQuestions(t *testing.T) (*lqServer, *lqHostReq) {
	t.Helper()
	pool := testPoolOptional(t)
	ctx := context.Background()
	mustExecGuest(t, ctx, pool, `DELETE FROM guide_item WHERE apartment_id = 78`)
	mustExecGuest(t, ctx, pool, `DELETE FROM guest_question WHERE apartment_id = 78`)
	mustExecGuest(t, ctx, pool, `DELETE FROM guest_chat_message WHERE chat_id = 780`)
	mustExecGuest(t, ctx, pool, `DELETE FROM guest_chat WHERE id = 780`)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, created_at, email) VALUES (78, 'handofftest', 'x', 'host', '2026-01-01', 'owner78@example.test') ON CONFLICT DO NOTHING`)
	mustExecGuest(t, ctx, pool, `INSERT INTO legal_entity (id, owner_user_id, name, contact_email, created_at) VALUES (78, 78, 'Host Co 78', 'host78@example.test', '2026-01-01') ON CONFLICT DO NOTHING`)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, legal_entity_id, internal_name, active, leon_enabled, leon_terms_version, guide_token, created_at)
		VALUES (78, 78, 78, 'Handoff Flat', 1, 1, '2026-10-25', 'handofftoken78', '2026-01-01') ON CONFLICT DO NOTHING`)
	mustExecGuest(t, ctx, pool, `INSERT INTO guest_chat (id, apartment_id, door, cookie_id, lang, created_at, last_message_at) VALUES (780, 78, 'qr', 'cookie78', 'en', '2026-11-20', '2026-11-20')`)
	mustExecGuest(t, ctx, pool, `INSERT INTO guest_chat_message (id, chat_id, role, kind, text, sources, created_at) VALUES
		(7801, 780, 'guest', 'question', 'Where is the key?', '', '2026-11-20'),
		(7802, 780, 'guest', 'question', 'Kde je klíč od bytu? ' || repeat('Příliš žluťoučký kůň ', 8), '', '2026-11-20'),
		(7803, 780, 'guest', 'question', 'Is the heater on?', '', '2026-11-20')`)
	mustExecGuest(t, ctx, pool, `INSERT INTO guest_question (id, chat_id, apartment_id, message_id, summary, status, answer, urgent, triaged, created_at) VALUES
		(7901, 780, 78, 7801, 'Guest asks for the key', 'open', '', 1, 1, '2026-11-20'),
		(7902, 780, 78, 7802, 'Kde je klíč od bytu? ' || repeat('Příliš žluťoučký kůň ', 8), 'answered', 'Klíč je v boxu u dveří.', 0, 1, '2026-11-20'),
		(7903, 780, 78, 7803, 'Heater question', 'dismissed', '', 0, 1, '2026-11-20')`)
	now := func() time.Time { return time.Date(2026, 11, 24, 12, 0, 0, 0, time.UTC) }
	s := &lqServer{pool: pool, getenv: func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return "go-guest-test-only-secret-key-0123456789"
		}
		return ""
	}, now: now}
	host := &session.Host{Account: session.Account{ID: 78}, Workspace: session.Account{ID: 78}}
	return s, &lqHostReq{host: host, apt: 78, lang: "en", at: time.Date(2026, 11, 24, 12, 0, 0, 0, time.UTC)}
}

func renderHandoff(t *testing.T, s *lqServer, q *lqHostReq, qid int64) string {
	t.Helper()
	q.qid = qid
	rec := httptest.NewRecorder()
	r := httptest.NewRequest("GET", fmt.Sprintf("/apartments/78/guide/questions/%d", qid), nil)
	q.r = r
	s.renderQuestion(rec, r, q, "", 200)
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	return rec.Body.String()
}

func TestHandoffOpenUrgentShowsBanner(t *testing.T) {
	s, q := seedHandoffQuestions(t)
	body := renderHandoff(t, s, q, 7901)
	if !strings.Contains(body, "read this as an emergency") {
		t.Fatal("open urgent question: urgent banner missing")
	}
	if strings.Contains(body, "You dismissed this question.") {
		t.Fatal("open question shows dismissed banner")
	}
}

func TestHandoffAnsweredShowsAnswerAndShownToGuest(t *testing.T) {
	s, q := seedHandoffQuestions(t)
	body := renderHandoff(t, s, q, 7902)
	if !strings.Contains(body, "Klíč je v boxu u dveří.") {
		t.Fatal("answered question: answer text missing")
	}
	if !strings.Contains(body, "The guest sees this on the guide page, word for word.") {
		t.Fatal("answered question: shown_to_guest line missing")
	}
	if strings.Contains(body, "read this as an emergency") {
		t.Fatal("answered question shows urgent banner")
	}
}

func TestHandoffDismissedShowsDismissedBanner(t *testing.T) {
	s, q := seedHandoffQuestions(t)
	body := renderHandoff(t, s, q, 7903)
	if !strings.Contains(body, "You dismissed this question. You can still answer it.") {
		t.Fatal("dismissed question: dismissed banner missing")
	}
}

func TestHandoffAddGuideThenCardLinkFindsSameCard(t *testing.T) {
	s, q := seedHandoffQuestions(t)
	ctx := context.Background()
	itemID, err := s.handoffAddGuide(ctx, 78, 7902, "rules")
	if err != nil || itemID == 0 {
		t.Fatalf("add to guide: id %d err %v", itemID, err)
	}
	var sortOrder int64
	if err := s.pool.QueryRow(ctx, `SELECT sort_order FROM guide_item WHERE id = $1`, itemID).Scan(&sortOrder); err != nil {
		t.Fatal(err)
	}
	if want := int64(len(guideimport.Kinds) + 1); sortOrder != want {
		t.Fatalf("sort_order %d, want %d (len(Kinds)+1)", sortOrder, want)
	}
	row, err := s.handoffGet(ctx, 78, 7902)
	if err != nil {
		t.Fatal(err)
	}
	cardID, err := s.handoffCardID(ctx, 78, row)
	if err != nil || cardID != itemID {
		t.Fatalf("card lookup %d err %v, want %d", cardID, err, itemID)
	}
	body := renderHandoff(t, s, q, 7902)
	want := fmt.Sprintf(`href="/apartments/78/guide/%d"`, itemID)
	if !strings.Contains(body, want) {
		t.Fatalf("open-card link %s missing", want)
	}
}
