package ai

// Tests of leon_core.go, leon_try.go and the try route against the real Python
// (testdata/leon_try_golden.json, written by App/scripts/leon_try_golden.py),
// on PostgreSQL with a fake model (the real API is never called).

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"os"
	"reflect"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

type leonRow struct {
	ID         int64  `json:"id"`
	Kind       string `json:"kind"`
	Title      string `json:"title"`
	Location   string `json:"location"`
	Steps      string `json:"steps"`
	WatchOut   string `json:"watch_out"`
	VideoURL   string `json:"video_url"`
	Visibility string `json:"visibility"`
	State      string `json:"state"`
	Photos     int64  `json:"photos"`
}

type leonGoldenCard struct {
	ID       int64    `json:"id"`
	Kind     string   `json:"kind"`
	Title    string   `json:"title"`
	Location string   `json:"location"`
	Steps    string   `json:"steps"`
	WatchOut string   `json:"watch_out"`
	VideoURL string   `json:"video_url"`
	Photos   int64    `json:"photos"`
	Facts    []string `json:"facts"`
}

func (c leonGoldenCard) card() LeonCard {
	return LeonCard{ID: c.ID, Kind: c.Kind, Title: c.Title, Location: c.Location, Steps: c.Steps, WatchOut: c.WatchOut, VideoURL: c.VideoURL, Photos: c.Photos, Facts: c.Facts}
}

type leonTryGolden struct {
	Redact []struct{ In, Out string } `json:"redact"`
	Fold   []struct {
		In, Fold string
		Small    *string `json:"small"`
	} `json:"fold"`
	Noise []struct {
		In  string
		Out bool
	} `json:"noise"`
	FirstName []struct{ In, Out string } `json:"first_name"`
	Named     []struct {
		Lang, Key, Host, Out string
	} `json:"named"`
	Fixed         map[string]map[string]string `json:"fixed"`
	TooLong       map[string]string            `json:"too_long"`
	SchemaCompact string                       `json:"schema_compact"`
	Constants     map[string]any               `json:"constants"`
	ForGuest      []struct {
		Name      string                         `json:"name"`
		Rows      []leonRow                      `json:"rows"`
		Facts     []struct{ Fact, Value string } `json:"facts"`
		Cards     []leonGoldenCard               `json:"cards"`
		Block     string                         `json:"guide_block"`
		Sha       []string                       `json:"system_sha"`
		Emergency map[string]string              `json:"emergency"`
	} `json:"for_guest"`
	UserTurn []struct {
		In, Lang, Out string
	} `json:"user_turn"`
	Validate []struct {
		Name      string           `json:"name"`
		Data      json.RawMessage  `json:"data"`
		GuestText string           `json:"guest_text"`
		Cards     []leonGoldenCard `json:"cards"`
		Out       struct {
			Kind    string  `json:"kind"`
			Text    string  `json:"text"`
			Sources []int64 `json:"sources"`
			Summary string  `json:"summary"`
			Upset   bool    `json:"upset"`
			Reason  string  `json:"reason"`
		} `json:"out"`
	} `json:"validate"`
	Try []struct {
		Name     string            `json:"name"`
		Text     string            `json:"text"`
		Scenario string            `json:"scenario"`
		Lang     string            `json:"lang"`
		Host     string            `json:"host_name"`
		Mult     int               `json:"mult"`
		Count    int               `json:"count"`
		Script   []json.RawMessage `json:"script"`
		Result   struct {
			Kind     string `json:"kind"`
			Text     string `json:"text"`
			WouldAsk bool   `json:"would_ask"`
			Left     int64  `json:"left"`
		} `json:"result"`
		Recorded int `json:"recorded"`
		Calls    []struct {
			Feature   string                           `json:"feature"`
			SystemSha []string                         `json:"system_sha"`
			Messages  []struct{ Role, Content string } `json:"messages"`
			Schema    json.RawMessage                  `json:"schema"`
			Key       *string                          `json:"key"`
			MaxTokens int                              `json:"max_tokens"`
		} `json:"calls"`
	} `json:"try"`
}

func leonLoadTryGolden(t *testing.T) leonTryGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/leon_try_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g leonTryGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestLeonTextRulesMatchPython(t *testing.T) {
	g := leonLoadTryGolden(t)
	for _, c := range g.Redact {
		if got := LeonRedact(c.In); got != c.Out {
			t.Errorf("redact(%q) = %q, Python %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Fold {
		want := ""
		if c.Small != nil {
			want = *c.Small
		}
		if got := leonFold(c.In); got != c.Fold {
			t.Errorf("fold(%q) = %q, Python %q", c.In, got, c.Fold)
		}
		if got := LeonSmalltalkKind(c.In); got != want {
			t.Errorf("smalltalk(%q) = %q, Python %q", c.In, got, want)
		}
	}
	for _, c := range g.Noise {
		if got := LeonIsNoise(c.In); got != c.Out {
			t.Errorf("is_noise(%q) = %v, Python %v", c.In, got, c.Out)
		}
	}
	for _, c := range g.FirstName {
		if got := leonHostFirstName(c.In); got != c.Out {
			t.Errorf("host_first_name(%q) = %q, Python %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Named {
		if got := leonNamed(c.Lang, c.Key, c.Host); got != c.Out {
			t.Errorf("named(%s, %s, %q) = %q, Python %q", c.Lang, c.Key, c.Host, got, c.Out)
		}
	}
	for lang, keys := range g.Fixed {
		for k, want := range keys {
			if got := leonFixed(lang, k, nil); got != want {
				t.Errorf("fixed(%s, %s) = %q, Python %q", lang, k, got, want)
			}
		}
	}
	for lang, want := range g.TooLong {
		if got := leonFixed(lang, "leon_too_long", map[string]any{"n": LeonMaxMessageChars}); got != want {
			t.Errorf("too_long(%s) = %q, Python %q", lang, got, want)
		}
	}
	for _, c := range g.UserTurn {
		if got := LeonUserTurn(c.In, c.Lang); got != c.Out {
			t.Errorf("user_turn(%q) = %q, Python %q", c.In, got, c.Out)
		}
	}
	if len(g.Redact) < 15 || len(g.Fold) < 10 || len(g.Noise) < 10 {
		t.Fatal("golden cases missing: run App/scripts/leon_try_golden.py")
	}
}

func TestLeonSchemaPromptAndConstantsMatchPython(t *testing.T) {
	g := leonLoadTryGolden(t)
	if string(LeonSchema()) != g.SchemaCompact {
		t.Errorf("schema differs in text or key order:\n%s\n%s", LeonSchema(), g.SchemaCompact)
	}
	if havelSha(leonCharacter) != g.Constants["prompt_sha"] || float64(LeonMaxTokens) != g.Constants["max_tokens"] || float64(LeonMaxMessageChars) != g.Constants["max_message"] ||
		float64(LeonMaxReplyChars) != g.Constants["max_reply"] || float64(LeonMaxSummaryChars) != g.Constants["max_summary"] || float64(leonTryMax) != g.Constants["try_max"] {
		t.Error("prompt or limits differ from Python")
	}
}

func TestLeonValidateMatchesPython(t *testing.T) {
	g := leonLoadTryGolden(t)
	for _, c := range g.Validate {
		var cards []LeonCard
		for _, gc := range c.Cards {
			cards = append(cards, gc.card())
		}
		data := havelDecode(t, c.Data).(map[string]any)
		v := LeonValidate(data, cards, c.GuestText)
		w := c.Out
		if v.Kind != w.Kind || v.Text != w.Text || v.Summary != w.Summary || v.Upset != w.Upset || v.Reason != w.Reason || !reflect.DeepEqual(append([]int64{}, v.Sources...), append([]int64{}, w.Sources...)) {
			t.Errorf("validate %q: %+v, Python %+v", c.Name, v, w)
		}
	}
	if len(g.Validate) < 30 {
		t.Fatal("golden cases missing")
	}
}

// seedLeon puts the golden rows and quick-answer facts of a scenario into apartment 11.
func seedLeon(t *testing.T, pool *pgxpool.Pool, rows []leonRow, facts []struct{ Fact, Value string }) {
	t.Helper()
	ctx := context.Background()
	for _, r := range rows {
		if _, err := pool.Exec(ctx, `INSERT INTO guide_item (id, apartment_id, topic, kind, title, location, steps, watch_out, video_url, visibility, state, source, sort_order, created_at, updated_at)
VALUES ($1, 11, 'custom', $2, $3, $4, $5, $6, $7, $8, $9, 'host', 0, 'x', 'x')`, r.ID, r.Kind, r.Title, r.Location, r.Steps, r.WatchOut, r.VideoURL, r.Visibility, r.State); err != nil {
			t.Fatal(err)
		}
		for i := int64(0); i < r.Photos; i++ {
			if _, err := pool.Exec(ctx, `INSERT INTO guide_photo (item_id, file_name, created_at) VALUES ($1, $2, 'x')`, r.ID, "p"+strconv.FormatInt(i, 10)+".jpg"); err != nil {
				t.Fatal(err)
			}
		}
	}
	for _, f := range facts {
		if _, err := pool.Exec(ctx, `INSERT INTO guide_fact (apartment_id, fact, value, updated_at) VALUES (11, $1, $2, 'x')`, f.Fact, f.Value); err != nil {
			t.Fatal(err)
		}
	}
}

func leonSeedOwner(t *testing.T, pool *pgxpool.Pool) {
	havelExec(t, pool,
		`INSERT INTO user_account (id, username, password_hash, role, created_at, email) VALUES (1, 'a', 'x', 'host', '2026-01-01', 'a@example.test')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, active, leon_enabled, leon_terms_version, created_at) VALUES (11, 1, 'Flat "A" <b>', 1, 1, '2026-10-25', '2026-01-01')`)
}

func TestLeonGuestCardsAndPromptMatchPython(t *testing.T) {
	g := leonLoadTryGolden(t)
	for _, sc := range g.ForGuest {
		pool := havelTestPool(t)
		leonSeedOwner(t, pool)
		seedLeon(t, pool, sc.Rows, sc.Facts)
		store := LeonStore{HavelStore{Pool: pool, Env: havelMapEnv(nil)}}
		cards, err := store.GuestCards(context.Background(), 11)
		if err != nil {
			t.Fatal(err)
		}
		if len(cards) != len(sc.Cards) {
			t.Fatalf("%s: %d cards, Python %d", sc.Name, len(cards), len(sc.Cards))
		}
		for i, c := range cards {
			w := sc.Cards[i].card()
			if len(c.Facts) == 0 {
				c.Facts = nil
			}
			if len(w.Facts) == 0 {
				w.Facts = nil
			}
			if !reflect.DeepEqual(c, w) {
				t.Errorf("%s card %d: %+v, Python %+v", sc.Name, i, c, w)
			}
		}
		if len(cards) == 0 {
			continue
		}
		blocks := LeonSystemBlocks(cards, `Flat "A" <b>`)
		if blocks[1] != sc.Block || havelSha(blocks[0]) != sc.Sha[0] || havelSha(blocks[1]) != sc.Sha[1] {
			t.Errorf("%s: system blocks differ from Python", sc.Name)
		}
		for lang, want := range sc.Emergency {
			if got := LeonEmergencyText(lang, cards); got != want {
				t.Errorf("%s emergency(%s) = %q, Python %q", sc.Name, lang, got, want)
			}
		}
	}
}

func leonModelFor(t *testing.T, script []json.RawMessage) *havelScriptModel {
	m := &havelScriptModel{}
	for _, raw := range script {
		var probe struct{ Error *string }
		if json.Unmarshal(raw, &probe) == nil && probe.Error != nil {
			switch *probe.Error {
			case "disabled":
				m.script = append(m.script, &anthropic.Error{Reason: "disabled", Disabled: true})
			case "month":
				m.script = append(m.script, &anthropic.Error{Reason: "month", Budget: true})
			default:
				m.script = append(m.script, &anthropic.Error{Reason: *probe.Error})
			}
			continue
		}
		var data map[string]any
		_ = json.Unmarshal(raw, &data)
		m.script = append(m.script, data)
	}
	return m
}

func TestLeonTryReplyMatchesPython(t *testing.T) {
	g := leonLoadTryGolden(t)
	var scenarios = map[string]int{}
	for i, sc := range g.ForGuest {
		scenarios[sc.Name] = i
	}
	for _, c := range g.Try {
		pool := havelTestPool(t)
		leonSeedOwner(t, pool)
		sc := g.ForGuest[scenarios[c.Scenario]]
		seedLeon(t, pool, sc.Rows, sc.Facts)
		env := map[string]string{}
		if c.Mult == 0 {
			env["UBYHOST_BILLING_ENABLED"] = "1"
			havelExec(t, pool, `INSERT INTO billing_account (owner_user_id, status, plan, updated_at) VALUES (1, 'paused', 'standard', '2026-01-01')`)
		}
		store := LeonStore{HavelStore{Pool: pool, Env: havelMapEnv(env)}}
		now := time.Date(2026, 11, 13, 12, 0, 0, 0, time.UTC)
		for i := 0; i < c.Count; i++ {
			_ = store.Record(context.Background(), "leon_try", "11", now.Add(-time.Minute))
		}
		model := leonModelFor(t, c.Script)
		res, err := store.TryReply(context.Background(), model, LeonApartment{ID: 11, Name: `Flat "A" <b>`}, c.Text, c.Lang, c.Host, now)
		if err != nil {
			t.Fatalf("%s: %v", c.Name, err)
		}
		w := c.Result
		if res.Kind != w.Kind || res.Text != w.Text || res.WouldAsk != w.WouldAsk || res.Left != w.Left {
			t.Errorf("%s: %+v, Python %+v", c.Name, res, w)
		}
		var recorded int
		_ = pool.QueryRow(context.Background(), `SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'leon_try'`).Scan(&recorded)
		if recorded-c.Count != c.Recorded {
			t.Errorf("%s: recorded %d, Python %d", c.Name, recorded-c.Count, c.Recorded)
		}
		if len(model.calls) != len(c.Calls) {
			t.Errorf("%s: %d model calls, Python %d", c.Name, len(model.calls), len(c.Calls))
			continue
		}
		for i, call := range model.calls {
			wc := c.Calls[i]
			if call.feature != wc.Feature || call.max != wc.MaxTokens || call.key == nil || *call.key != *wc.Key || len(call.messages) != 1 ||
				call.messages[0].Role != wc.Messages[0].Role || call.messages[0].Content != wc.Messages[0].Content {
				t.Errorf("%s call %d differs from Python: %+v", c.Name, i, call)
			}
			for j, b := range call.system {
				if havelSha(b) != wc.SystemSha[j] {
					t.Errorf("%s call %d: system block %d differs", c.Name, i, j)
				}
			}
			var a, b any
			_ = json.Unmarshal(call.schema, &a)
			_ = json.Unmarshal(wc.Schema, &b)
			if !reflect.DeepEqual(a, b) {
				t.Errorf("%s call %d: schema differs", c.Name, i)
			}
		}
	}
	if len(g.Try) < 25 {
		t.Fatal("golden cases missing")
	}
}

func TestLeonTryRoute(t *testing.T) {
	g := leonNewRig(t, nil)
	g.leonOn()
	post := func(accept string, form url.Values) (int, string, http.Header) {
		rec := g.do(havelReq{method: "POST", path: leonBase + "/try", form: form, accept: accept})
		return rec.Code, rec.Body.String(), rec.Header()
	}
	if code, _, _ := post("", url.Values{"message": {"hi"}}); code != 404 {
		t.Errorf("a guide that is not live is a 404: %d", code)
	}
	g.live()
	havelExec(t, g.pool, `INSERT INTO guide_item (apartment_id, topic, kind, title, state, visibility, location, steps, created_at, updated_at) VALUES (11, 'arrival', 'parking', '', 'done', 'everyone', 'Garage 12', 'Ring 4711', 'x', 'x')`)
	g.model.script = []any{map[string]any{"kind": "answer", "reply": "Park in garage 12.", "sources": []string{"c6"}, "host_summary": nil, "upset": false}}
	code, body, h := post("", url.Values{"message": {"Where can I park? my phone is +420 777 123 456"}})
	if code != 200 || !strings.Contains(body, "Park in garage 12.") || !strings.Contains(body, `data-role="host"`) || h.Get("Cache-Control") != "no-store" {
		t.Fatalf("html reply: %d %.300s", code, body)
	}
	if len(g.model.calls) != 1 || strings.Contains(g.model.calls[0].messages[0].Content, "777 123 456") || !strings.Contains(g.model.calls[0].messages[0].Content, "[phone]") ||
		g.model.calls[0].key == nil || *g.model.calls[0].key != "11" || g.model.calls[0].feature != "leon" {
		t.Error("the model sees the redacted message with the property id as key")
	}
	g.model.script = []any{map[string]any{"kind": "ask_host", "reply": "", "sources": []string{}, "host_summary": "horse", "upset": false}}
	code, body, h = post("application/json", url.Values{"message": {"Can I bring a horse?"}})
	if code != 200 || h.Get("Content-Type") != "application/json" || h.Get("Cache-Control") != "no-store" {
		t.Fatalf("json reply: %d %s", code, body)
	}
	var out struct {
		Kind, Text, Note, Cap string
		WouldAsk              bool `json:"would_ask"`
		Blocked               bool
	}
	_ = json.Unmarshal([]byte(body), &out)
	if out.Kind != "ask_host" || !out.WouldAsk || out.Blocked || out.Note != leonStrings.T("en", "leon_setup.try.would_ask", nil) || !strings.HasPrefix(body, `{"kind":"ask_host","text":`) {
		t.Errorf("json: %s", body)
	}
	// Five test messages a day: the fifth blocks, the sixth is the cap text.
	for i := 0; i < 3; i++ {
		g.model.script = []any{map[string]any{"kind": "unclear", "reply": "", "sources": []string{}, "host_summary": nil, "upset": false}}
		post("application/json", url.Values{"message": {"hmm what"}})
	}
	code, body, _ = post("application/json", url.Values{"message": {"one more"}})
	if code != 200 || !strings.Contains(body, `"kind":"cap"`) || !strings.Contains(body, `"blocked":true`) || !strings.Contains(body, leonStrings.T("en", "leon_setup.try.cap", nil)) {
		t.Errorf("cap: %s", body)
	}
	if len(g.model.calls) != 5 {
		t.Errorf("%d model calls, want 5", len(g.model.calls))
	}
	// Leon switched off: 404. CSRF is required.
	havelExec(t, g.pool, `UPDATE apartment SET leon_enabled = 0 WHERE id = 11`)
	if code, _, _ := post("", url.Values{"message": {"hi"}}); code != 404 {
		t.Errorf("Leon off: %d", code)
	}
	rec := g.do(havelReq{method: "POST", path: leonBase + "/try", form: url.Values{"message": {"x"}}, noToken: true})
	if rec.Code != 303 || rec.Header().Get("Location") != "/login?notice=form_expired" {
		t.Errorf("no token: %d", rec.Code)
	}
}
