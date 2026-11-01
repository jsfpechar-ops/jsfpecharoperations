package ubyport

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"testing"
)

// respGoldenDir is the Python oracle folder, relative to this package.
const respGoldenDir = "../../../App/tests/golden/ubyport/responses"

type goldenDoc struct {
	Tables struct {
		KnownCodes          map[string]string `json:"known_codes"`
		KnownSeverity       map[string]int    `json:"known_severity"`
		FallbackText        map[string]string `json:"fallback_text"`
		AcceptedMaxSeverity int               `json:"accepted_max_severity"`
		MaxPDFBytes         int               `json:"max_pdf_bytes"`
	} `json:"tables"`
	Responses map[string]map[string]any `json:"responses"`
	Classify  map[string]map[string]any `json:"classify"`
}

type classifyCase struct {
	Name       string            `json:"name"`
	Header     *string           `json:"header"`
	Record     *string           `json:"record"`
	Codebook   map[string]string `json:"codebook"`
	Severities map[string]int    `json:"severities"`
	Lang       *string           `json:"lang"`
}

func loadGolden(t *testing.T) goldenDoc {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(respGoldenDir, "expected.json"))
	if err != nil {
		t.Fatal(err)
	}
	var doc goldenDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	return doc
}

// toAny round-trips a Go value through JSON so it compares like the oracle.
func toAny(t *testing.T, v any) any {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(b, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

func responseSnapshot(t *testing.T, data []byte) map[string]any {
	t.Helper()
	got := map[string]any{
		"fault":         toAny(t, ParseFault(data)),
		"element_names": toAny(t, ResponseElementNames(data)),
	}
	if zapis, err := ParseZapisResponse(data); err != nil {
		got["zapis"] = "parse_error"
	} else {
		got["zapis"] = toAny(t, zapis)
	}
	scalar := map[string]any{}
	for _, method := range []string{"TestDostupnosti", "MaximalniDelkaSeznamu"} {
		v, err := ParseScalarResponse(data, method)
		if err != nil {
			scalar[method] = "parse_error"
		} else {
			scalar[method] = toAny(t, v)
		}
	}
	got["scalar"] = scalar
	if items, err := ParseCiselnikResponse(data); err != nil {
		got["ciselnik"] = "parse_error"
	} else {
		got["ciselnik"] = toAny(t, items)
	}
	return got
}

func TestResponsesMatchPythonOracle(t *testing.T) {
	doc := loadGolden(t)
	names := make([]string, 0, len(doc.Responses))
	for name := range doc.Responses {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		want := doc.Responses[name]
		t.Run(name, func(t *testing.T) {
			data, err := os.ReadFile(filepath.Join(respGoldenDir, name))
			if err != nil {
				t.Fatal(err)
			}
			got := responseSnapshot(t, data)
			if len(got) != len(want) {
				t.Errorf("%s: key count want %d, got %d", name, len(want), len(got))
			}
			for key, wantVal := range want {
				if !reflect.DeepEqual(got[key], wantVal) {
					t.Errorf("%s: %s want %v, got %v", name, key, wantVal, got[key])
				}
			}
		})
	}
}

func TestClassifyMatchesPythonOracle(t *testing.T) {
	doc := loadGolden(t)
	raw, err := os.ReadFile(filepath.Join(respGoldenDir, "classify_cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	var cases []classifyCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) != len(doc.Classify) {
		t.Fatalf("classify cases: want %d oracle entries, got %d", len(cases), len(doc.Classify))
	}
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			want, ok := doc.Classify[c.Name]
			if !ok {
				t.Fatalf("no oracle entry for %s", c.Name)
			}
			lang := "en"
			if c.Lang != nil && *c.Lang != "" {
				lang = *c.Lang
			}
			state, messages := Classify(c.Header, c.Record, c.Codebook, lang, c.Severities)
			got := map[string]any{
				"state":               state,
				"messages":            toAny(t, messages),
				"record_is_duplicate": RecordIsDuplicate(c.Record, c.Codebook),
			}
			for key, wantVal := range want {
				if !reflect.DeepEqual(got[key], wantVal) {
					t.Errorf("%s: %s want %v, got %v", c.Name, key, wantVal, got[key])
				}
			}
		})
	}
}
