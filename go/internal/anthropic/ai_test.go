package anthropic

import (
	"bytes"
	"context"
	_ "embed"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"
	"time"
)

//go:embed testdata/golden.json
var goldenRaw []byte

func dec(t *testing.T, raw []byte, v any) {
	t.Helper()
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	if err := d.Decode(v); err != nil {
		t.Fatal(err)
	}
}

type msg struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type result struct {
	OK    map[string]any `json:"ok"`
	Error string         `json:"error"`
}

type golden struct {
	Estimate []struct {
		System   []string `json:"system"`
		Messages []msg    `json:"messages"`
		Out      int      `json:"out"`
	} `json:"estimate"`
	Budget []struct {
		Name       string            `json:"name"`
		Env        map[string]string `json:"env"`
		Rows       []ledgerRow       `json:"rows"`
		Key        *string           `json:"key"`
		Day        string            `json:"day"`
		MonthUSD   float64           `json:"month_usd"`
		DayUSD     float64           `json:"day_usd"`
		KeyUSD     *float64          `json:"key_usd"`
		Allowance  float64           `json:"allowance"`
		Fraction   float64           `json:"fraction"`
		State      string            `json:"state"`
		MonthlyCap float64           `json:"monthly_cap"`
		KeyCap     float64           `json:"key_cap"`
	} `json:"budget"`
	Model struct {
		System        []string        `json:"system"`
		Messages      []msg           `json:"messages"`
		Schema        json.RawMessage `json:"schema"`
		AnthropicBody any             `json:"anthropic_body"`
		TwoBody       any             `json:"anthropic_two_blocks_body"`
		TwoInput      struct {
			System    []string        `json:"system"`
			Messages  []msg           `json:"messages"`
			Schema    json.RawMessage `json:"schema"`
			MaxTokens int             `json:"max_tokens"`
		} `json:"anthropic_two_blocks_input"`
		Answers        []namedResult      `json:"anthropic_answers"`
		MistralBody    any                `json:"mistral_body"`
		MistralTwo     any                `json:"mistral_two_blocks_body"`
		MistralAnswers []namedResult      `json:"mistral_answers"`
		TooLarge       result             `json:"too_large"`
		MaxInput       int                `json:"max_input_tokens"`
		MaxTokens      int                `json:"max_tokens"`
		Model          string             `json:"model"`
		MistralModel   string             `json:"mistral_model"`
		Prices         map[string]float64 `json:"prices"`
	} `json:"model"`
}

type namedResult struct {
	Name   string `json:"name"`
	Result result `json:"result"`
}

type ledgerRow struct {
	Day     string `json:"day"`
	Feature string `json:"feature"`
	Key     string `json:"key"`
	In      int64  `json:"input_tokens"`
	CW      int64  `json:"cache_write_tokens"`
	CR      int64  `json:"cache_read_tokens"`
	Out     int64  `json:"output_tokens"`
}

func load(t *testing.T) golden {
	var g golden
	dec(t, goldenRaw, &g)
	return g
}

func lookupOf(env map[string]string) func(string) (string, bool) {
	return func(n string) (string, bool) { v, ok := env[n]; return v, ok }
}

func TestEstimateMatchesPython(t *testing.T) {
	for i, c := range load(t).Estimate {
		var ms []Message
		for _, m := range c.Messages {
			ms = append(ms, Message{m.Role, m.Content})
		}
		if got := EstimateInputTokens(c.System, ms); got != c.Out {
			t.Errorf("case %d: %d, want %d", i, got, c.Out)
		}
	}
}

func TestBudgetMatchesPython(t *testing.T) {
	ctx := context.Background()
	for _, c := range load(t).Budget {
		env := map[string]string{"UBYHOST_AI_FEATURES": "guide_import", "UBYHOST_ANTHROPIC_API_KEY": "k"}
		for k, v := range c.Env {
			env[k] = v
		}
		rows := c.Rows
		s := &Service{Cfg: ConfigFromEnv(lookupOf(env))}
		s.sum = func(_ context.Context, feature, from, to string, key *string) (Tokens, error) {
			var t Tokens
			for _, r := range rows {
				if r.Feature != feature || r.Day < from || r.Day > to || (key != nil && r.Key != *key) {
					continue
				}
				t.In += r.In
				t.CacheWrite += r.CW
				t.CacheRead += r.CR
				t.Out += r.Out
			}
			return t, nil
		}
		day, _ := time.Parse("2006-01-02", c.Day)
		eq := func(what string, got, want float64) {
			if got != want {
				t.Errorf("%s %s: %v, want %v", c.Name, what, got, want)
			}
		}
		m, _ := s.MonthSpendUSD(ctx, "guide_import", day)
		d, _ := s.DaySpendUSD(ctx, "guide_import", day)
		a, _ := s.DailyAllowanceUSD(ctx, "guide_import", day)
		f, _ := s.BudgetFraction(ctx, "guide_import", day)
		eq("month", m, c.MonthUSD)
		eq("day", d, c.DayUSD)
		eq("allowance", a, c.Allowance)
		eq("fraction", f, c.Fraction)
		eq("monthly cap", s.Cfg.MonthlyUSD("guide_import"), c.MonthlyCap)
		eq("key cap", s.Cfg.KeyDailyUSD("guide_import"), c.KeyCap)
		if c.Key != nil {
			k, _ := s.KeyDaySpendUSD(ctx, "guide_import", *c.Key, day)
			eq("key", k, *c.KeyUSD)
		}
		st, err := s.BudgetState(ctx, "guide_import", c.Key, day)
		if err != nil || st != c.State {
			t.Errorf("%s: state %q (%v), want %q", c.Name, st, err, c.State)
		}
	}
}

func TestConfigDefaultsMatchPython(t *testing.T) {
	g := load(t).Model
	c := ConfigFromEnv(lookupOf(nil))
	p := g.Prices
	if c.Model != g.Model || c.MistralModel != g.MistralModel || c.MaxTokens != g.MaxTokens || c.MaxInputTokens != g.MaxInput ||
		c.Prices != (Prices{p["input"], p["output"], p["cache_read"], p["cache_write"]}) {
		t.Errorf("defaults differ: %+v", c)
	}
}

type fakeDoer struct {
	req  []Request
	resp Response
	err  error
}

func (f *fakeDoer) Create(_ context.Context, r Request) (Response, error) {
	f.req = append(f.req, r)
	return f.resp, f.err
}

type fakeMistral struct {
	req  []MistralRequest
	resp MistralResponse
	err  error
}

func (f *fakeMistral) Post(_ context.Context, r MistralRequest) (MistralResponse, error) {
	f.req = append(f.req, r)
	return f.resp, f.err
}

func svc(provider string) (*Service, *fakeDoer, *fakeMistral) {
	env := map[string]string{"UBYHOST_AI_FEATURES": "guide_import", "UBYHOST_ANTHROPIC_API_KEY": "k", "UBYHOST_MISTRAL_API_KEY": "m", "UBYHOST_AI_PROVIDER": provider}
	d, m := &fakeDoer{}, &fakeMistral{}
	s := &Service{Cfg: ConfigFromEnv(lookupOf(env)), Anthropic: d, Mistral: m}
	s.sum = func(context.Context, string, string, string, *string) (Tokens, error) { return Tokens{}, nil }
	s.rec = func(context.Context, string, string, Usage) error { return nil }
	return s, d, m
}

func msgs(in []msg) []Message {
	var out []Message
	for _, m := range in {
		out = append(out, Message{m.Role, m.Content})
	}
	return out
}

func sameJSON(t *testing.T, what string, body []byte, want any) {
	t.Helper()
	var got any
	dec(t, body, &got)
	if !reflect.DeepEqual(got, want) {
		t.Errorf("%s differs from Python\n got %s", what, body)
	}
}

func TestAnthropicBodyMatchesPython(t *testing.T) {
	g := load(t).Model
	s, d, _ := svc("anthropic")
	key := "7"
	if _, err := s.Call(context.Background(), "guide_import", g.System, msgs(g.Messages), g.Schema, &key, 0); err == nil {
		t.Fatal("fake returned no text: want an error")
	}
	body, _ := MarshalBody(d.req[0])
	sameJSON(t, "anthropic body", body, g.AnthropicBody)
	in := g.TwoInput
	s.Call(context.Background(), "guide_import", in.System, msgs(in.Messages), in.Schema, nil, in.MaxTokens)
	body, _ = MarshalBody(d.req[1])
	sameJSON(t, "two block body", body, g.TwoBody)
}

func TestMistralBodyMatchesPython(t *testing.T) {
	g := load(t).Model
	s, _, m := svc("mistral")
	key := "7"
	s.Call(context.Background(), "guide_import", g.System, msgs(g.Messages), g.Schema, &key, 0)
	body, _ := MarshalMistralBody(m.req[0])
	sameJSON(t, "mistral body", body, g.MistralBody)
	in := g.TwoInput
	s.Call(context.Background(), "guide_import", in.System, msgs(in.Messages), in.Schema, nil, in.MaxTokens)
	body, _ = MarshalMistralBody(m.req[1])
	sameJSON(t, "mistral two block body", body, g.MistralTwo)
}

func outcome(got map[string]any, err error) result {
	if e := AsError(err); e != nil {
		return result{Error: e.Reason}
	}
	return result{OK: got}
}

func answerFor(name string) Response {
	r := Response{HasText: true, StopReason: "end_turn", Usage: Usage{10, 2, 3, 4}}
	switch name {
	case "ok":
		r.Text = `{"cards": [{"kind": "wifi"}], "n": 1.5}`
	case "ok_whitespace":
		r.Text = " {\"cards\": []}\n"
	case "refusal":
		r.StopReason = "refusal"
	case "max_tokens":
		r.StopReason = "max_tokens"
	case "no_text_block", "no_blocks":
		r.HasText = false
	case "empty_text":
	case "bad_json":
		r.Text = "nope"
	case "trailing_text":
		r.Text = `{"a": 1} x`
	case "json_list":
		r.Text = "[1]"
	case "json_string":
		r.Text = `"x"`
	case "second_block_text":
		r.Text = `{"a": 2}`
	}
	return r
}

func TestAnthropicAnswersMatchPython(t *testing.T) {
	for _, c := range load(t).Model.Answers {
		s, d, _ := svc("anthropic")
		if c.Name == "api_error" {
			d.err = errors.New("boom")
		} else {
			d.resp = answerFor(c.Name)
		}
		key := "1"
		got, err := s.Call(context.Background(), "guide_import", []string{"s"}, []Message{{"user", "u"}}, json.RawMessage(`{"type": "object"}`), &key, 0)
		if r := outcome(got, err); !reflect.DeepEqual(r, c.Result) {
			t.Errorf("%s: %+v, want %+v", c.Name, r, c.Result)
		}
	}
}

func TestMistralAnswersMatchPython(t *testing.T) {
	contents := map[string]any{"ok": `{"cards": []}`, "length": "{}", "model_length": "{}", "blank_content": "  ", "list_content": []any{1},
		"bad_json": "nope", "json_list": "[1]"}
	finish := map[string]string{"length": "length", "model_length": "model_length"}
	for _, c := range load(t).Model.MistralAnswers {
		s, _, m := svc("mistral")
		if c.Name == "post_error" {
			m.err = errors.New("boom")
		} else if c.Name != "no_choices" {
			f := "stop"
			if v, ok := finish[c.Name]; ok {
				f = v
			}
			m.resp = MistralResponse{FinishReason: f, Content: contents[c.Name]}
		}
		key := "1"
		got, err := s.Call(context.Background(), "guide_import", []string{"s"}, []Message{{"user", "u"}}, json.RawMessage(`{"type": "object"}`), &key, 0)
		if r := outcome(got, err); !reflect.DeepEqual(r, c.Result) {
			t.Errorf("%s: %+v, want %+v", c.Name, r, c.Result)
		}
	}
}

func TestRefusalsBeforeTheRequest(t *testing.T) {
	g := load(t).Model
	s, d, _ := svc("anthropic")
	got, err := s.Call(context.Background(), "guide_import", []string{string(bytes.Repeat([]byte("x"), 120002))}, []Message{{"user", "u"}}, json.RawMessage(`{}`), nil, 0)
	if r := outcome(got, err); !reflect.DeepEqual(r, g.TooLarge) || len(d.req) != 0 {
		t.Errorf("too large: %+v", r)
	}
	s.Cfg.Features = map[string]bool{}
	_, err = s.Call(context.Background(), "guide_import", []string{"s"}, nil, json.RawMessage(`{}`), nil, 0)
	if e := AsError(err); e == nil || !e.Disabled {
		t.Errorf("want disabled, got %v", err)
	}
	s2, _, _ := svc("anthropic")
	s2.sum = func(context.Context, string, string, string, *string) (Tokens, error) {
		return Tokens{In: 1_000_000_000}, nil
	}
	_, err = s2.Call(context.Background(), "guide_import", []string{"s"}, nil, json.RawMessage(`{}`), nil, 0)
	if e := AsError(err); e == nil || !e.Budget || e.Reason != "month" {
		t.Errorf("want month budget error, got %v", err)
	}
}

func TestClientRetriesOnceAndSendsHeaders(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Header.Get("x-api-key") != "k" || r.Header.Get("anthropic-version") != "2023-06-01" || r.URL.Path != "/v1/messages" {
			t.Errorf("bad request: %v %s", r.Header, r.URL.Path)
		}
		if calls == 1 {
			w.WriteHeader(529)
			return
		}
		w.Header().Set("request-id", "req_9")
		w.Write([]byte(`{"content":[{"type":"text","text":"{}"}],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":2}}`))
	}))
	defer srv.Close()
	c := NewClient("k")
	c.BaseURL = srv.URL
	c.Sleep = func(time.Duration) {}
	resp, err := c.Create(context.Background(), Request{Model: "m", MaxTokens: 5, System: []string{"s"}, Messages: []Message{{"user", "u"}}, Schema: json.RawMessage(`{}`)})
	if err != nil || calls != 2 || resp.Text != "{}" || resp.RequestID != "req_9" || resp.Usage.OutputTokens != 2 {
		t.Errorf("resp %+v err %v calls %d", resp, err, calls)
	}
	calls = -10
	var se *StatusError
	srv2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(400) }))
	defer srv2.Close()
	c.BaseURL = srv2.URL
	if _, err := c.Create(context.Background(), Request{Schema: json.RawMessage(`{}`)}); !errors.As(err, &se) || se.Status != 400 {
		t.Errorf("want 400 status error, got %v", err)
	}
}

func TestMistralClientRetriesOn5xx(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Header.Get("Authorization") != "Bearer m" {
			t.Error("missing bearer")
		}
		if calls == 1 {
			w.WriteHeader(503)
			return
		}
		w.Write([]byte(`{"choices":[{"finish_reason":"stop","message":{"content":"{}"}}],"usage":{"prompt_tokens":3,"completion_tokens":4}}`))
	}))
	defer srv.Close()
	c := NewMistralClient("m")
	c.URL = srv.URL
	resp, err := c.Post(context.Background(), MistralRequest{Schema: json.RawMessage(`{}`)})
	if err != nil || calls != 2 || resp.Content != "{}" || resp.PromptTokens != 3 {
		t.Errorf("resp %+v err %v calls %d", resp, err, calls)
	}
}
