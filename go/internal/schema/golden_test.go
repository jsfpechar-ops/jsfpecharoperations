package schema

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

// outcome is the {"ok": ...} or {"error": "..."} shape pg_schema_golden.py writes.
type outcome struct {
	OK    json.RawMessage `json:"ok"`
	Error *string         `json:"error"`
}

const regen = "regenerate with: cd App && .venv/bin/python scripts/pg_schema_golden.py"

func loadJSON(t *testing.T, name string, into any) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", name))
	if err != nil {
		t.Fatalf("%v (%s)", err, regen)
	}
	if err := json.Unmarshal(raw, into); err != nil {
		t.Fatal(err)
	}
}

func checkOutcome[T any](t *testing.T, label string, want outcome, got T, err error) {
	t.Helper()
	if want.Error != nil {
		if err == nil || err.Error() != *want.Error {
			t.Errorf("%s: want error %q, got %v, %v", label, *want.Error, got, err)
		}
		return
	}
	if err != nil {
		t.Errorf("%s: unexpected error %v", label, err)
		return
	}
	var w T
	if err := json.Unmarshal(want.OK, &w); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(normalize(w), normalize(got)) {
		t.Errorf("%s:\nwant %#v\ngot  %#v", label, w, got)
	}
}

// normalize treats a nil and an empty slice alike, as JSON [] and Go nil.
func normalize(v any) any {
	if s, ok := v.([]string); ok && len(s) == 0 {
		return []string{}
	}
	return v
}

type gooseGolden struct {
	Files    map[string]outcome `json:"files"`
	Complete [][2]any           `json:"complete"`
	Split    []json.RawMessage  `json:"split"`
	Goose    []json.RawMessage  `json:"goose"`
}

func pairs(t *testing.T, raw []json.RawMessage) []struct {
	text string
	want outcome
} {
	t.Helper()
	var out []struct {
		text string
		want outcome
	}
	for _, r := range raw {
		var pair []json.RawMessage
		if err := json.Unmarshal(r, &pair); err != nil || len(pair) != 2 {
			t.Fatalf("bad golden pair %s", r)
		}
		var item struct {
			text string
			want outcome
		}
		if err := json.Unmarshal(pair[0], &item.text); err != nil {
			t.Fatal(err)
		}
		if err := json.Unmarshal(pair[1], &item.want); err != nil {
			t.Fatal(err)
		}
		out = append(out, item)
	}
	return out
}

func TestGooseFilesMatchPython(t *testing.T) {
	var g gooseGolden
	loadJSON(t, "goose_statements_golden.json", &g)
	dir := filepath.Join("..", "..", "..", "App", "migrations_pg")
	versions, err := Files(dir)
	if err != nil {
		t.Fatal(err)
	}
	entries, _ := filepath.Glob(filepath.Join(dir, "*.sql"))
	if len(entries) != len(g.Files) || len(versions) != len(g.Files) {
		t.Fatalf("golden has %d goose files, App/migrations_pg has %d; %s", len(g.Files), len(entries), regen)
	}
	for _, path := range entries {
		name := filepath.Base(path)
		want, ok := g.Files[name]
		if !ok {
			t.Fatalf("%s is not in the golden; %s", name, regen)
		}
		text, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		statements, err := UpStatements(string(text))
		var hashes []string
		for _, s := range statements {
			sum := sha256.Sum256([]byte(s))
			hashes = append(hashes, hex.EncodeToString(sum[:]))
		}
		checkOutcome(t, name, want, hashes, err)
	}
}

func TestCompleteStatementMatchesSQLite(t *testing.T) {
	var g gooseGolden
	loadJSON(t, "goose_statements_golden.json", &g)
	if len(g.Complete) < 20 {
		t.Fatalf("too few complete cases: %d", len(g.Complete))
	}
	for _, c := range g.Complete {
		text, want := c[0].(string), c[1].(bool)
		if got := completeStatement(text); got != want {
			t.Errorf("completeStatement(%q) = %v, Python sqlite3 says %v", text, got, want)
		}
	}
}

func TestSplitAndGooseCasesMatchPython(t *testing.T) {
	var g gooseGolden
	loadJSON(t, "goose_statements_golden.json", &g)
	for _, c := range pairs(t, g.Split) {
		got, err := splitStatements(c.text)
		checkOutcome(t, "split "+c.text, c.want, got, err)
	}
	for _, c := range pairs(t, g.Goose) {
		got, err := UpStatements(c.text)
		checkOutcome(t, "goose "+c.text, c.want, got, err)
	}
}

func TestFingerprintMatchesPython(t *testing.T) {
	var g struct {
		Cases []json.RawMessage `json:"cases"`
	}
	loadJSON(t, "fingerprint_golden.json", &g)
	cases := pairs(t, g.Cases)
	if len(cases) < 30 {
		t.Fatalf("too few fingerprint cases: %d", len(cases))
	}
	for _, c := range cases {
		got, err := Fingerprint(c.text)
		checkOutcome(t, "fingerprint "+c.text, c.want, got, err)
	}
}

func TestPyHelpers(t *testing.T) {
	if got := pySplitLines("a\r\nb\rc\nd"); !reflect.DeepEqual(got, []string{"a\r\n", "b\r", "c\n", "d"}) {
		t.Errorf("pySplitLines: %q", got)
	}
	if got := pyStrip("\x1c a \x1f\t"); got != "a" {
		t.Errorf("pyStrip: %q", got)
	}
	if got := posixNormpath("//a/../b/"); got != "//b" {
		t.Errorf("posixNormpath: %q", got)
	}
	if got := pyJSONString("é\"\x7f😀"); got != `"\u00e9\"\u007f\ud83d\ude00"` {
		t.Errorf("pyJSONString: %s", got)
	}
	if got := pyList([]int{15, 16}); got != "[15, 16]" {
		t.Errorf("pyList: %s", got)
	}
	if got := pyList(nil); got != "none" {
		t.Errorf("pyList(nil): %s", got)
	}
}
