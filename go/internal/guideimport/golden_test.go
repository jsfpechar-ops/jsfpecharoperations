package guideimport

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"reflect"
	"strings"
	"testing"
)

//go:embed testdata/golden.json
var goldenRaw []byte

// dec decodes JSON with numbers kept as text, like DecodeItem.
func dec(t *testing.T, raw []byte, v any) {
	t.Helper()
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	if err := d.Decode(v); err != nil {
		t.Fatal(err)
	}
}

type golden struct {
	SystemRules string         `json:"system_rules"`
	Schema      any            `json:"schema"`
	Kinds       [][2]string    `json:"kinds"`
	Topics      []string       `json:"topics"`
	Limits      map[string]int `json:"limits"`
	StaleSecs   int            `json:"stale_running_seconds"`
	Trim        []trimCase     `json:"trim"`
	Normalise   []inOut        `json:"normalise"`
	Names       []namesCase    `json:"names"`
	LanguageOf  []dataOut      `json:"language_of"`
	ListingText []dataOut      `json:"listing_text"`
	UserTurn    []turnCase     `json:"user_turn"`
	Verify      []verifyCase   `json:"verify"`
	Clean       []cleanCase    `json:"clean"`
	Attempts    []attemptCase  `json:"attempts"`
	Apify       apifyGolden    `json:"apify"`
}

type inOut struct{ In, Out string }
type namesCase struct {
	In  string   `json:"in"`
	Out []string `json:"out"`
}
type dataOut struct {
	Data map[string]any `json:"data"`
	Out  string         `json:"out"`
}
type trimCase struct {
	Name       string `json:"name"`
	Source     string `json:"source"`
	Item       any    `json:"item"`
	ExpectJSON string `json:"expect_json"`
	PhotosTrim []any  `json:"photo_urls_of_trimmed"`
	PhotosRaw  []any  `json:"photo_urls_of_raw_item"`
}
type turnCase struct {
	Source      string           `json:"source"`
	Data        map[string]any   `json:"data"`
	Earlier     []map[string]any `json:"earlier"`
	Lang        string           `json:"lang"`
	Out         string           `json:"out"`
	EarlierText string           `json:"earlier_text"`
}
type verifyCase struct {
	Name      string         `json:"name"`
	Card      map[string]any `json:"card"`
	Corpus    string         `json:"corpus"`
	Reason    *string        `json:"reason"`
	CardAfter map[string]any `json:"card_after"`
}
type cleanCase struct {
	Name    string           `json:"name"`
	Cards   []any            `json:"cards"`
	Corpus  string           `json:"corpus"`
	Kept    []map[string]any `json:"kept"`
	Dropped map[string]int   `json:"dropped"`
}
type attemptCase struct {
	In  *string `json:"in"`
	Out int     `json:"out"`
}

func load(t *testing.T) golden {
	var g golden
	dec(t, goldenRaw, &g)
	return g
}

func TestConstantsMatchPython(t *testing.T) {
	g := load(t)
	if SystemRules() != g.SystemRules {
		t.Error("system_rules.txt differs from Python SYSTEM_RULES")
	}
	var got any
	dec(t, Schema(), &got)
	if !reflect.DeepEqual(got, g.Schema) {
		t.Error("schema.json differs from Python SCHEMA")
	}
	var kinds [][2]string
	for _, k := range Kinds {
		kinds = append(kinds, [2]string{k.Kind, k.Topic})
	}
	if !reflect.DeepEqual(kinds, g.Kinds) || !reflect.DeepEqual(Topics, g.Topics) || !reflect.DeepEqual(Limits, g.Limits) {
		t.Error("kinds, topics or limits differ from Python")
	}
	if int(staleRunning.Seconds()) != g.StaleSecs {
		t.Errorf("stale running = %v", staleRunning)
	}
}

func TestTrimMatchesPython(t *testing.T) {
	for _, c := range load(t).Trim {
		item, _ := c.Item.(map[string]any)
		got := Trim(c.Source, item)
		if _, isDict := c.Item.(map[string]any); !isDict {
			got = Trim(c.Source, nil)
		}
		if got.JSON() != c.ExpectJSON {
			t.Errorf("%s: trim JSON differs\n got %.200s\nwant %.200s", c.Name, got.JSON(), c.ExpectJSON)
		}
		// Python stores no photos: its list for the trimmed data is empty, and
		// the trimmed data has no photo or image key to read.
		if len(c.PhotosTrim) != 0 {
			t.Errorf("%s: Python found photos in trimmed data", c.Name)
		}
		if got.Get("photos") != nil || got.Get("images") != nil {
			t.Errorf("%s: trimmed data holds photo keys", c.Name)
		}
	}
	found := false
	for _, c := range load(t).Trim {
		if len(c.PhotosRaw) > 0 {
			found = true
		}
	}
	if !found {
		t.Error("no fixture has raw photos")
	}
}

func TestNormaliseNamesLanguageListing(t *testing.T) {
	g := load(t)
	for _, c := range g.Normalise {
		if got := normalise(c.In); got != c.Out {
			t.Errorf("normalise(%q) = %q, want %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Names {
		got := names(c.In)
		if len(got) != len(c.Out) || (len(got) > 0 && !reflect.DeepEqual(got, c.Out)) {
			t.Errorf("names(%q) = %q, want %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.LanguageOf {
		if got := languageOf(c.Data); got != c.Out {
			t.Errorf("languageOf = %s, want %s", got, c.Out)
		}
	}
	for _, c := range g.ListingText {
		if got := listingText(c.Data); got != c.Out {
			t.Errorf("listingText = %q, want %q", got, c.Out)
		}
	}
}

func cards(in []map[string]any) []Card {
	var out []Card
	for _, m := range in {
		s := func(k string) string { v, _ := m[k].(string); return v }
		out = append(out, Card{Kind: s("kind"), Topic: s("topic"), Title: s("title"), Location: s("location"), Steps: s("steps"), WatchOut: s("watch_out"), Source: s("source")})
	}
	return out
}

func TestUserTurnMatchesPython(t *testing.T) {
	for i, c := range load(t).UserTurn {
		e := cards(c.Earlier)
		if got := earlierText(e); got != c.EarlierText {
			t.Errorf("case %d: earlierText differs", i)
		}
		if got := userTurn(c.Source, c.Data, e, c.Lang); got != c.Out {
			t.Errorf("case %d: userTurn differs", i)
		}
		if languageOf(c.Data) != c.Lang {
			t.Errorf("case %d: language differs", i)
		}
	}
}

func TestVerifyAndCleanMatchPython(t *testing.T) {
	g := load(t)
	for _, c := range g.Verify {
		got := verify(c.Card, c.Corpus)
		want := ""
		if c.Reason != nil {
			want = *c.Reason
		}
		if got != want {
			t.Errorf("%s: reason %q, want %q", c.Name, got, want)
		}
		if !reflect.DeepEqual(c.Card, c.CardAfter) {
			t.Errorf("%s: card after verify differs\n got %v\nwant %v", c.Name, c.Card, c.CardAfter)
		}
	}
	for _, c := range g.Clean {
		kept, dropped := clean(c.Cards, c.Corpus)
		if len(kept) != len(c.Kept) || (len(kept) > 0 && !reflect.DeepEqual(kept, c.Kept)) {
			t.Errorf("%s: kept differs\n got %v\nwant %v", c.Name, kept, c.Kept)
		}
		if !reflect.DeepEqual(dropped, c.Dropped) && !(len(dropped) == 0 && len(c.Dropped) == 0) {
			t.Errorf("%s: dropped %v, want %v", c.Name, dropped, c.Dropped)
		}
	}
}

func TestAttempts(t *testing.T) {
	for _, c := range load(t).Attempts {
		in := ""
		if c.In != nil {
			in = *c.In
		}
		if got := attempts(in); got != c.Out {
			t.Errorf("attempts(%q) = %d, want %d", in, got, c.Out)
		}
	}
}

func TestPyFloat(t *testing.T) {
	for in, want := range map[string]string{"4.5": "4.5", "100000.0": "100000.0", "1e+22": "1e+22", "1e-05": "1e-05", "0.0001": "0.0001", "1e16": "1e+16", "1e15": "1000000000000000.0", "123456.789": "123456.789", "1.50": "1.5", "-0": "0"} {
		if got := pyNumber(in); got != want {
			t.Errorf("pyNumber(%s) = %s, want %s", in, got, want)
		}
	}
	if !strings.Contains(SystemRules(), `{"cards": []}`) {
		t.Error("rules lost the empty answer example")
	}
}
