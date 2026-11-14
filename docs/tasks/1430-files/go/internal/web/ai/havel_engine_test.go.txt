package ai

// Tests for havel_engine.go, havel_topics.go and havel_data.go against the
// answers of the real Python in testdata/havel_golden.json (written by
// App/scripts/havel_golden.py). No database, no network.

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

const havelTestSecret = "havel-golden-secret-0123456789-abcdef"

type havelGoldenHost struct {
	UserID     int64  `json:"user_id"`
	Lang       string `json:"lang"`
	Device     string `json:"device"`
	Properties []struct {
		ID   int64  `json:"id"`
		Name string `json:"name"`
		City string `json:"city"`
	} `json:"properties"`
	Page     string   `json:"page"`
	Topic    string   `json:"topic"`
	ReadKeys []string `json:"read_keys"`
}

func (g havelGoldenHost) host() HavelHost {
	h := HavelHost{UserID: g.UserID, Lang: g.Lang, Device: g.Device, Page: g.Page, Topic: g.Topic, ReadKeys: g.ReadKeys}
	for _, p := range g.Properties {
		h.Properties = append(h.Properties, HavelProperty{p.ID, p.Name, p.City})
	}
	return h
}

type havelGoldenExchange struct {
	Host  string `json:"host"`
	Havel string `json:"havel"`
}

func havelExchanges(in []havelGoldenExchange) []HavelExchange {
	out := []HavelExchange{}
	for _, e := range in {
		out = append(out, HavelExchange{e.Host, e.Havel})
	}
	return out
}

type havelGoldenFile struct {
	Redact []struct {
		In      string            `json:"in"`
		Out     string            `json:"out"`
		Mapping map[string]string `json:"mapping"`
	} `json:"redact"`
	Restore []struct {
		Text    string            `json:"text"`
		Mapping map[string]string `json:"mapping"`
		Out     string            `json:"out"`
	} `json:"restore"`
	LocalReply []struct {
		In  string  `json:"in"`
		Out *string `json:"out"`
	} `json:"local_reply"`
	History struct {
		Sign []struct {
			User    int64                 `json:"user"`
			In      []havelGoldenExchange `json:"in"`
			Payload string                `json:"payload"`
			Sig     string                `json:"sig"`
		} `json:"sign"`
		Read []struct {
			Name    string                `json:"name"`
			User    int64                 `json:"user"`
			Payload string                `json:"payload"`
			Sig     string                `json:"sig"`
			Out     []havelGoldenExchange `json:"out"`
		} `json:"read"`
	} `json:"history"`
	PagesBlock    map[string]string `json:"pages_block"`
	GuideBlockSha map[string][2]any `json:"guide_block_sha"`
	PromptSha     string            `json:"prompt_sha"`
	PageIDs       []string          `json:"page_ids"`
	PageURL       []struct {
		Page  string  `json:"page"`
		PID   *int64  `json:"pid"`
		Owned []int64 `json:"owned"`
		Out   *string `json:"out"`
	} `json:"page_url"`
	Label []struct {
		Lang, Key, Out string
	} `json:"label"`
	Messages []struct {
		Host    havelGoldenHost                  `json:"host"`
		History []havelGoldenExchange            `json:"history"`
		Message string                           `json:"message"`
		Today   string                           `json:"today"`
		Msgs    []struct{ Role, Content string } `json:"messages"`
		Mapping map[string]string                `json:"mapping"`
		Context string                           `json:"context"`
	} `json:"messages"`
	ModelHistory struct {
		In  []havelGoldenExchange `json:"in"`
		Out []havelGoldenExchange `json:"out"`
	} `json:"model_history"`
	Validate []struct {
		Name    string                `json:"name"`
		Host    havelGoldenHost       `json:"host"`
		Message string                `json:"message"`
		History []havelGoldenExchange `json:"history"`
		Today   string                `json:"today"`
		Data    json.RawMessage       `json:"data"`
		Reply   json.RawMessage       `json:"reply"`
	} `json:"validate"`
	Ask []struct {
		Name    string                `json:"name"`
		Host    havelGoldenHost       `json:"host"`
		History []havelGoldenExchange `json:"history"`
		Message string                `json:"message"`
		Today   string                `json:"today"`
		Script  []json.RawMessage     `json:"script"`
		Calls   []struct {
			Feature   string                           `json:"feature"`
			SystemSha []string                         `json:"system_sha"`
			Messages  []struct{ Role, Content string } `json:"messages"`
			Schema    json.RawMessage                  `json:"schema"`
			Key       *string                          `json:"key"`
			MaxTokens int                              `json:"max_tokens"`
		} `json:"calls"`
		Stats  []string        `json:"stats"`
		Reply  json.RawMessage `json:"reply"`
		Raised string          `json:"raised"`
		Reason string          `json:"reason"`
	} `json:"ask"`
	Schema        json.RawMessage `json:"schema"`
	SchemaCompact string          `json:"schema_compact"`
	Limits        map[string]int  `json:"limits"`
	Topics        struct {
		Ordered map[string][]string `json:"ordered"`
		Answers []struct {
			Lang  string `json:"lang"`
			Topic string `json:"topic"`
			Q     string `json:"q"`
			Out   *struct {
				Paragraphs []string `json:"paragraphs"`
				Page       *string  `json:"page"`
				Support    bool     `json:"support"`
				Question   struct {
					ID    string `json:"id"`
					Label string `json:"label"`
				} `json:"question"`
			} `json:"out"`
		} `json:"answers"`
		ReadKeys []struct {
			Topic string   `json:"topic"`
			Q     string   `json:"q"`
			Out   []string `json:"out"`
		} `json:"read_keys"`
		All []struct {
			ID, Icon, Label string
			Questions       []struct {
				ID, Label string
				Short     string   `json:"short"`
				Keys      []string `json:"keys"`
				Page      *string  `json:"page"`
				Support   bool     `json:"support"`
			} `json:"questions"`
		} `json:"all"`
		IDs []string `json:"ids"`
	} `json:"topics"`
	I18n map[string]map[string]string `json:"i18n"`
}

func havelLoadGolden(t *testing.T) havelGoldenFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/havel_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g havelGoldenFile
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func havelSha(s string) string { h := sha256.Sum256([]byte(s)); return hex.EncodeToString(h[:]) }

func havelDay(t *testing.T, s string) time.Time {
	t.Helper()
	d, err := time.Parse("2006-01-02", s)
	if err != nil {
		t.Fatal(err)
	}
	return d
}

// havelDecode reads model JSON the way anthropic.decodeObject does (numbers stay json.Number).
func havelDecode(t *testing.T, raw []byte) any {
	t.Helper()
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		t.Fatal(err)
	}
	return v
}

// havelReplyJSON is the Python reply_json of the golden script.
func havelReplyJSON(r HavelReply) any {
	links := [][]string{}
	for _, l := range r.Links {
		links = append(links, []string{l.Label, l.URL})
	}
	sources, next := r.Sources, r.Next
	if sources == nil {
		sources = []string{}
	}
	if next == nil {
		next = []string{}
	}
	var action any
	if r.Action != nil {
		action = r.Action
	}
	var summary any
	if r.SupportSummary != nil {
		summary = *r.SupportSummary
	}
	raw, _ := json.Marshal(map[string]any{"kind": r.Kind, "text": r.Text, "links": links, "action": action,
		"support_summary": summary, "fail_reason": r.FailReason, "sources": sources, "next": next})
	var out any
	_ = json.Unmarshal(raw, &out)
	return out
}

func havelSameMap(a map[string]string, m *HavelMapping) bool {
	if len(a) != len(m.Real) {
		return false
	}
	for k, v := range a {
		if m.Real[k] != v {
			return false
		}
	}
	return true
}

func TestHavelRedactMatchesPython(t *testing.T) {
	for _, c := range havelLoadGolden(t).Redact {
		m := NewHavelMapping()
		if got := HavelRedact(c.In, m); got != c.Out || !havelSameMap(c.Mapping, m) {
			t.Errorf("redact(%q) = %q %v, Python %q %v", c.In, got, m.Real, c.Out, c.Mapping)
		}
	}
	for _, c := range havelLoadGolden(t).Restore {
		m := NewHavelMapping()
		for _, name := range []string{"[email 1]", "[phone 1]"} {
			if v, ok := c.Mapping[name]; ok {
				m.Names, m.Real[name] = append(m.Names, name), v
			}
		}
		if got := HavelRestore(c.Text, m); got != c.Out {
			t.Errorf("restore(%q) = %q, Python %q", c.Text, got, c.Out)
		}
	}
}

func TestHavelLocalReplyMatchesPython(t *testing.T) {
	for _, c := range havelLoadGolden(t).LocalReply {
		want := ""
		if c.Out != nil {
			want = *c.Out
		}
		if got := HavelLocalReply(c.In); got != want {
			t.Errorf("local_reply(%q) = %q, Python %q", c.In, got, want)
		}
	}
}

func TestHavelHistoryMatchesPython(t *testing.T) {
	g := havelLoadGolden(t)
	for _, c := range g.History.Sign {
		payload, sig := HavelSignHistory(havelTestSecret, c.User, havelExchanges(c.In))
		if payload != c.Payload || sig != c.Sig {
			t.Errorf("sign_history user %d: %q %s, Python %q %s", c.User, payload, sig, c.Payload, c.Sig)
		}
	}
	for _, c := range g.History.Read {
		got := HavelReadHistory(havelTestSecret, c.User, c.Payload, c.Sig)
		if !reflect.DeepEqual(got, havelExchanges(c.Out)) {
			t.Errorf("read_history %s: %v, Python %v", c.Name, got, c.Out)
		}
	}
}

func TestHavelBlocksMatchPython(t *testing.T) {
	g := havelLoadGolden(t)
	if havelSha(havelSystemPrompt) != g.PromptSha {
		t.Error("prompt differs from Python")
	}
	for lang, want := range g.PagesBlock {
		if got := havelPagesBlock(lang); got != want {
			t.Errorf("pages_block(%s) differs from Python", lang)
		}
	}
	for lang, want := range g.GuideBlockSha {
		block := havelGuideBlock(lang)
		if havelSha(block) != want[0].(string) || float64(havelLen(block)) != want[1].(float64) {
			t.Errorf("guide_block(%s) differs from Python", lang)
		}
	}
	var ids []string
	for _, p := range havelPages {
		ids = append(ids, p.ID)
	}
	if !reflect.DeepEqual(ids, g.PageIDs) {
		t.Errorf("page ids differ: %v", ids)
	}
	for _, c := range g.PageURL {
		want := ""
		if c.Out != nil {
			want = *c.Out
		}
		if got := HavelPageURL(c.Page, c.PID, c.Owned); got != want {
			t.Errorf("page_url(%s) = %q, Python %q", c.Page, got, want)
		}
	}
	for _, c := range g.Label {
		if got := havelLabel(c.Lang, c.Key); got != c.Out {
			t.Errorf("label(%s, %s) = %q, Python %q", c.Lang, c.Key, got, c.Out)
		}
	}
	for lang, keys := range g.I18n {
		for k, want := range keys {
			if got := havelCatalog.T(lang, k, nil); got != want {
				t.Errorf("i18n %s %s = %q, Python %q", lang, k, got, want)
			}
		}
	}
}

func TestHavelSchemaMatchesPython(t *testing.T) {
	g := havelLoadGolden(t)
	var buf bytes.Buffer
	if err := json.Compact(&buf, HavelSchema()); err != nil {
		t.Fatal(err)
	}
	if buf.String() != g.SchemaCompact {
		t.Errorf("schema differs in text or key order:\n%s\n%s", buf.String(), g.SchemaCompact)
	}
	if HavelMaxTokens != g.Limits["max_tokens"] || HavelMaxMessageChars != g.Limits["max_message"] ||
		HavelMaxReplyChars != g.Limits["max_reply"] || HavelMaxSummaryChars != g.Limits["max_summary"] || HavelMaxExchanges != g.Limits["max_exchanges"] {
		t.Error("limits differ from Python")
	}
}

func TestHavelMessagesMatchPython(t *testing.T) {
	for _, c := range havelLoadGolden(t).Messages {
		h := c.Host.host()
		today := havelDay(t, c.Today)
		if got := HavelHostContext(h, today); got != c.Context {
			t.Errorf("host_context = %q, Python %q", got, c.Context)
		}
		m := NewHavelMapping()
		msgs := HavelBuildMessages(h, havelExchanges(c.History), c.Message, today, m)
		if len(msgs) != len(c.Msgs) {
			t.Fatalf("build_messages gave %d messages, Python %d", len(msgs), len(c.Msgs))
		}
		for i := range msgs {
			if msgs[i].Role != c.Msgs[i].Role || msgs[i].Content != c.Msgs[i].Content {
				t.Errorf("message %d = %q, Python %q", i, msgs[i].Content, c.Msgs[i].Content)
			}
		}
		if !havelSameMap(c.Mapping, m) {
			t.Errorf("mapping %v, Python %v", m.Real, c.Mapping)
		}
	}
	g := havelLoadGolden(t)
	if got := HavelModelHistory(havelExchanges(g.ModelHistory.In)); !reflect.DeepEqual(got, havelExchanges(g.ModelHistory.Out)) {
		t.Error("model_history differs from Python")
	}
}

func TestHavelValidateMatchesPython(t *testing.T) {
	g := havelLoadGolden(t)
	if len(g.Validate) < 70 {
		t.Fatalf("only %d validate cases", len(g.Validate))
	}
	for _, c := range g.Validate {
		h := c.Host.host()
		today := havelDay(t, c.Today)
		history := havelExchanges(c.History)
		m := NewHavelMapping()
		HavelBuildMessages(h, history, c.Message, today, m)
		got := havelReplyJSON(HavelValidate(havelDecode(t, c.Data), h, c.Message, history, m, today))
		var want any
		_ = json.Unmarshal(c.Reply, &want)
		if !reflect.DeepEqual(got, want) {
			gj, _ := json.Marshal(got)
			t.Errorf("validate %q (%s): Go %s, Python %s", c.Name, h.Lang, gj, c.Reply)
		}
	}
}

// havelFakeModel plays a script of replies and errors and records every call.
type havelFakeModel struct {
	t     *testing.T
	queue []json.RawMessage
	calls []havelFakeCall
}

type havelFakeCall struct {
	feature  string
	system   []string
	messages []anthropic.Message
	schema   json.RawMessage
	key      *string
	max      int
}

func (f *havelFakeModel) Call(_ context.Context, feature string, system []string, messages []anthropic.Message, schema json.RawMessage, key *string, maxTokens int) (map[string]any, error) {
	f.calls = append(f.calls, havelFakeCall{feature, system, messages, schema, key, maxTokens})
	item := f.queue[0]
	f.queue = f.queue[1:]
	var probe struct {
		Error *string
		Kind  string
	}
	if json.Unmarshal(item, &probe) == nil && probe.Error != nil {
		switch probe.Kind {
		case "AIDisabled":
			return nil, &anthropic.Error{Reason: "disabled", Disabled: true}
		case "AIBudgetError":
			return nil, &anthropic.Error{Reason: *probe.Error, Budget: true}
		default:
			return nil, &anthropic.Error{Reason: *probe.Error}
		}
	}
	return havelDecode(f.t, item).(map[string]any), nil
}

func TestHavelAskMatchesPython(t *testing.T) {
	for _, c := range havelLoadGolden(t).Ask {
		fake := &havelFakeModel{t: t, queue: c.Script}
		var stats []string
		stat := func(_ context.Context, kind string, _ time.Time) error { stats = append(stats, kind); return nil }
		reply, err := HavelAsk(context.Background(), fake, stat, c.Host.host(), havelExchanges(c.History), c.Message, havelDay(t, c.Today))
		switch c.Raised {
		case "disabled":
			if e := anthropic.AsError(err); e == nil || !e.Disabled {
				t.Errorf("%s: want a disabled error, got %v", c.Name, err)
			}
		case "budget":
			if e := anthropic.AsError(err); e == nil || !e.Budget || e.Reason != c.Reason {
				t.Errorf("%s: want a budget error %q, got %v", c.Name, c.Reason, err)
			}
		default:
			if err != nil {
				t.Fatalf("%s: %v", c.Name, err)
			}
			got, _ := json.Marshal(havelReplyJSON(reply))
			var a, b any
			_ = json.Unmarshal(got, &a)
			_ = json.Unmarshal(c.Reply, &b)
			if !reflect.DeepEqual(a, b) {
				t.Errorf("%s: reply %s, Python %s", c.Name, got, c.Reply)
			}
		}
		if !reflect.DeepEqual(stats, append([]string(nil), c.Stats...)) && !(len(stats) == 0 && len(c.Stats) == 0) {
			t.Errorf("%s: stats %v, Python %v", c.Name, stats, c.Stats)
		}
		if len(fake.calls) != len(c.Calls) {
			t.Fatalf("%s: %d model calls, Python %d", c.Name, len(fake.calls), len(c.Calls))
		}
		for i, call := range fake.calls {
			want := c.Calls[i]
			if call.feature != want.Feature || call.max != want.MaxTokens || call.key != nil || want.Key != nil {
				t.Errorf("%s call %d: feature, max tokens or key differ", c.Name, i)
			}
			for j, block := range call.system {
				if havelSha(block) != want.SystemSha[j] {
					t.Errorf("%s call %d: system block %d differs", c.Name, i, j)
				}
			}
			if len(call.system) != len(want.SystemSha) {
				t.Errorf("%s call %d: %d system blocks, Python %d", c.Name, i, len(call.system), len(want.SystemSha))
			}
			for j, msg := range call.messages {
				if j >= len(want.Messages) || msg.Role != want.Messages[j].Role || msg.Content != want.Messages[j].Content {
					t.Errorf("%s call %d: message %d differs", c.Name, i, j)
				}
			}
			var a, b any
			_ = json.Unmarshal(call.schema, &a)
			_ = json.Unmarshal(want.Schema, &b)
			if !reflect.DeepEqual(a, b) {
				t.Errorf("%s call %d: schema differs", c.Name, i)
			}
		}
	}
}

func TestHavelAskPassesDatabaseErrorsOn(t *testing.T) {
	boom := context.DeadlineExceeded
	_, err := HavelAsk(context.Background(), havelErrModel{boom}, func(context.Context, string, time.Time) error { return nil },
		HavelHost{Lang: "en", Device: "computer"}, nil, "x", time.Now())
	if err != boom {
		t.Errorf("a non-AI error must come back unchanged, got %v", err)
	}
}

type havelErrModel struct{ err error }

func (m havelErrModel) Call(context.Context, string, []string, []anthropic.Message, json.RawMessage, *string, int) (map[string]any, error) {
	return nil, m.err
}

func TestHavelTopicsMatchPython(t *testing.T) {
	g := havelLoadGolden(t)
	if !reflect.DeepEqual(HavelTopicIDs(), g.Topics.IDs) {
		t.Error("topic ids differ")
	}
	for i, want := range g.Topics.All {
		got := havelTopics[i]
		if got.ID != want.ID || got.Icon != want.Icon || got.Label != want.Label || len(got.Questions) != len(want.Questions) {
			t.Fatalf("topic %s differs", want.ID)
		}
		for j, q := range want.Questions {
			gq := got.Questions[j]
			page := ""
			if q.Page != nil {
				page = *q.Page
			}
			if gq.ID != q.ID || gq.Label != q.Label || gq.Short != q.Short || !reflect.DeepEqual(gq.Keys, q.Keys) || gq.Page != page || gq.Support != q.Support {
				t.Errorf("question %s.%s differs", want.ID, q.ID)
			}
		}
	}
	for nav, want := range g.Topics.Ordered {
		var ids []string
		for _, tp := range HavelOrderedTopics(nav) {
			ids = append(ids, tp.ID)
		}
		if !reflect.DeepEqual(ids, want) {
			t.Errorf("ordered(%q) = %v, Python %v", nav, ids, want)
		}
	}
	for _, c := range g.Topics.ReadKeys {
		if got := HavelReadKeys(c.Topic, c.Q); !reflect.DeepEqual(got, c.Out) {
			t.Errorf("read_keys(%s, %s) = %v, Python %v", c.Topic, c.Q, got, c.Out)
		}
	}
	for _, c := range g.Topics.Answers {
		got := HavelTopicAnswer(c.Lang, c.Topic, c.Q)
		if c.Out == nil {
			if got != nil {
				t.Errorf("answer(%s, %s) should be nil", c.Topic, c.Q)
			}
			continue
		}
		page := ""
		if c.Out.Page != nil {
			page = *c.Out.Page
		}
		if got == nil || !reflect.DeepEqual(got.Paragraphs, c.Out.Paragraphs) || got.Page != page || got.Support != c.Out.Support || got.Question.ID != c.Out.Question.ID {
			t.Errorf("answer(%s, %s, %s) differs from Python", c.Lang, c.Topic, c.Q)
		}
	}
}

func TestHavelSystemBlocksAreConstantPerLanguage(t *testing.T) {
	a, b := HavelSystemBlocks("cs"), HavelSystemBlocks("cs")
	if len(a) != 3 || !reflect.DeepEqual(a, b) || !strings.HasPrefix(a[1], `<guide lang="cs">`) {
		t.Error("system blocks must be the prompt, the guide and the pages, the same on every call")
	}
	if !strings.HasPrefix(HavelSystemBlocks("de")[1], `<guide lang="en">`) {
		t.Error("an unknown language reads the English guide")
	}
}
