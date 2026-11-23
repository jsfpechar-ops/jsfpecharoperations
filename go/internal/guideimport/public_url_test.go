package guideimport

import (
	"context"
	"strings"
	"testing"
	"time"
)

func TestActorBodyURLGolden(t *testing.T) {
	u := "https://www.notion.so/host/Guide-abc123"
	got := ActorBody("url", u)
	want := `{"startUrls": [{"url": "https://www.notion.so/host/Guide-abc123"}], "maxCrawlDepth": 0, "maxCrawlPages": 1, "crawlerType": "playwright:firefox"}`
	if got != want {
		t.Errorf("ActorBody(url)\n got: %s\nwant: %s", got, want)
	}
}

func TestTrimURLKeepsTextOnly(t *testing.T) {
	item := map[string]any{"text": "Hello", "markdown": "# Hi", "url": "https://x.test/p"}
	data := Trim("url", item)
	if data.Get("text") != "Hello" {
		t.Fatalf("text %v", data.Get("text"))
	}
	if v := data.Get("markdown"); v != nil {
		t.Errorf("markdown kept: %v", v)
	}
	if data.Get("source") != "url" {
		t.Errorf("source %v", data.Get("source"))
	}
}

func TestTrimURLEmptyFails(t *testing.T) {
	data := Trim("url", map[string]any{"text": "   "})
	if len(data) > 1 {
		t.Fatalf("non-empty trim: %+v", data)
	}
}

func TestURLImportFiltersCodesEndToEnd(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	for _, q := range []string{
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'o@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at) VALUES (7, 1, 'Flat', 'Brno', 'UBY', 'tok7', '2026-01-01')`,
	} {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	now := "2026-11-13T10:00:00+00:00"
	item := map[string]any{"text": "Welcome. door code 4827. Wifi password: Sunny22. Check in at 15:00."}
	ai := &fakeAI{reply: map[string]any{"cards": []any{
		map[string]any{"kind": "checkin", "topic": "", "title": "", "location": "Lobby", "steps": "Check in at 15:00.", "watch_out": "",
			"quotes": []any{"Check in at 15:00."}},
	}}}
	nowT := time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)
	j := &Job{Pool: pool, Apify: fakeFetch{item: item}, AI: ai, Cfg: Config{Token: "t"}, Now: func() time.Time { return nowT }}
	pool.Exec(context.Background(), `INSERT INTO guide_import (id, apartment_id, source, url, status, created_at) VALUES (9, 7, 'url', 'https://guide.example.test/p', 'queued', $1)`, now)
	if n, err := j.ProcessQueue(ctx, 1); err != nil || n != 1 {
		t.Fatalf("queue n=%d err=%v", n, err)
	}
	if strings.Contains(ai.turn, "4827") || strings.Contains(ai.turn, "Sunny22") {
		t.Errorf("model saw a code in:\n%s", ai.turn)
	}
	raw := str(t, pool, "SELECT raw_json FROM guide_import WHERE id = 9")
	if strings.Contains(raw, "4827") || strings.Contains(raw, "Sunny22") {
		t.Errorf("stored raw_json has code: %s", raw)
	}
	if n, err := j.ProcessPending(ctx, 3); err != nil || n != 1 {
		t.Fatalf("pending n=%d err=%v", n, err)
	}
	left := str(t, pool, "SELECT codes_left_out::text FROM guide_import WHERE id = 9")
	if left != "2" {
		t.Errorf("codes_left_out %q want 2", left)
	}
	steps := str(t, pool, "SELECT steps FROM guide_item WHERE apartment_id = 7 AND source = 'url' LIMIT 1")
	if strings.Contains(steps, "4827") || strings.Contains(steps, "9911") {
		t.Errorf("card still has code: %q", steps)
	}
	state := str(t, pool, "SELECT state FROM guide_item WHERE apartment_id = 7 AND source = 'url' LIMIT 1")
	if state != "check" {
		t.Errorf("state %q", state)
	}
	card := map[string]any{"steps": "PIN 9911"}
	if n := FilterCardFields(card); n != 1 || strings.Contains(card["steps"].(string), "9911") {
		t.Errorf("output filter n=%d steps=%q", n, card["steps"])
	}
}
