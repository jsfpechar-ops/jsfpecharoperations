package guest

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

func TestGroupCardsFollowsTopicOrderInPageLanguage(t *testing.T) {
	cards := []ai.GuideCard{
		{Card: ai.LeonCard{ID: 3, Kind: "checkout"}, Topic: "checkout"},
		{Card: ai.LeonCard{ID: 1, Kind: "wifi"}, Topic: "wifi"},
		{Card: ai.LeonCard{ID: 2, Kind: "checkin"}, Topic: "arrival"},
	}
	var want []string
	for _, topic := range ai.GuideTopics() {
		switch topic {
		case "arrival", "wifi", "checkout":
			want = append(want, ai.GuideTopicTitle(topic, "cs"))
		}
	}
	groups := groupCards(cards, "cs")
	if len(groups) != len(want) {
		t.Fatalf("got %d groups, want %d", len(groups), len(want))
	}
	for i, g := range groups {
		if g.Title != want[i] {
			t.Fatalf("group %d title = %q, want %q", i, g.Title, want[i])
		}
		if len(g.Cards) != 1 {
			t.Fatalf("group %d has %d cards, want 1", i, len(g.Cards))
		}
	}
}

// seedGuideApartment inserts a host, a legal entity, an apartment with a guide
// token and the five must-have guide cards done. It returns the guide token.
func seedGuideApartment(t *testing.T, pool *pgxpool.Pool, leonOn bool) string {
	t.Helper()
	ctx := t.Context()
	stamp := "2026-01-01T00:00:00Z"
	aptID := int64(82000000 + time.Now().UnixNano()%1000000)
	tok := fmt.Sprintf("guidetokenqrtest%d", aptID)
	leonFlag, terms := 0, ""
	if leonOn {
		leonFlag, terms = 1, ai.LeonTermsVersion()
	}
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, aptID, fmt.Sprintf("g%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO legal_entity (id, owner_user_id, name, contact_email, created_at) VALUES ($1, $1, 'Host Jana Guide', 'guide@example.test', $2) ON CONFLICT DO NOTHING`, aptID, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, legal_entity_id, internal_name, city_en, active, created_at, guide_token, leon_enabled, leon_terms_version)
		VALUES ($1, $1, $1, 'Guide Flat', 'Prague', 1, $2, $3, $4, $5)`, aptID, stamp, tok, leonFlag, terms)
	add := func(id int64, kind string) {
		mustExecGuest(t, ctx, pool, `INSERT INTO guide_item (id, apartment_id, topic, kind, title, steps, visibility, state, source, sort_order, created_at, updated_at)
			VALUES ($1, $2, 'custom', $3, $3, '[]', 'everyone', 'done', 'host', $1, $4, $4) ON CONFLICT DO NOTHING`, id, aptID, kind, stamp)
	}
	for i, kind := range []string{"checkin", "wifi", "heating", "checkout", "emergency"} {
		add(aptID*10+int64(i)+1, kind)
	}
	return tok
}

func getQRGuide(t *testing.T, pool *pgxpool.Pool, env map[string]string, path string) string {
	t.Helper()
	mux := http.NewServeMux()
	getenv := func(k string) string { return env[k] }
	RegisterGuideView(mux, pool, getenv, time.Now, func(_ string, f http.HandlerFunc) http.Handler { return f })
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("GET %s = %d, want 200: %.300s", path, rec.Code, rec.Body.String())
	}
	return rec.Body.String()
}

func TestQRGuideCsTitlesAndNameWithLeonOff(t *testing.T) {
	pool := testPoolOptional(t)
	tok := seedGuideApartment(t, pool, false)
	body := getQRGuide(t, pool, map[string]string{}, "/g/"+tok+"?lang=cs")
	if !strings.Contains(body, "Příjezd a ubytování") {
		t.Fatal("cs page lacks the Czech checkin card title")
	}
	if !strings.Contains(body, "data-guide-topic") {
		t.Fatal("cs page lacks a topic heading")
	}
	if strings.Contains(body, "Check-in and arrival") {
		t.Fatal("cs page shows the English card title")
	}
	if !strings.Contains(body, "Guide Flat") {
		t.Fatal("QR page lacks the property name")
	}
	if !strings.Contains(body, "Host Jana Guide") {
		t.Fatal("QR page lacks the host name")
	}
	if strings.Contains(body, `id="leon"`) {
		t.Fatal("Leon block rendered while Leon is off")
	}
}

func TestQRGuideLeonBlockWhenGateTrue(t *testing.T) {
	pool := testPoolOptional(t)
	tok := seedGuideApartment(t, pool, true)
	env := map[string]string{"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "test-key"}
	body := getQRGuide(t, pool, env, "/g/"+tok)
	if !strings.Contains(body, `id="leon"`) {
		t.Fatal("Leon block missing while the gate is true")
	}
	if !strings.Contains(body, `data-leon-url="/g/`+tok+`/leon"`) {
		t.Fatal("Leon URL on the QR door is wrong")
	}
}
