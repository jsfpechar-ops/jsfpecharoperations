package stayfeepdf

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"math"
	"os"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

type goldenCase struct {
	Name   string             `json:"name"`
	Report stayfee.Hlaseni    `json:"report"`
	Sample bool               `json:"sample"`
	Error  string             `json:"error"`
	Pages  [][]map[string]any `json:"pages"`
}

func loadGolden(t *testing.T) []goldenCase {
	t.Helper()
	raw, err := os.ReadFile("testdata/hlaseni_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []goldenCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	return cases
}

func same(a, b any) bool {
	switch x := a.(type) {
	case float64:
		y, ok := b.(float64)
		return ok && math.Abs(x-y) <= 0.01
	case []any:
		y, ok := b.([]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for i := range x {
			if !same(x[i], y[i]) {
				return false
			}
		}
		return true
	default:
		return a == b
	}
}

// The draw operations (text and its order, fonts, sizes, colours, positions,
// rules, cards, images, page breaks) equal what the Python renderer draws.
func TestLayoutMatchesPythonOps(t *testing.T) {
	cases := loadGolden(t)
	if len(cases) < 7 {
		t.Fatalf("golden has %d cases", len(cases))
	}
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			docs, err := Layout(c.Report, c.Sample)
			if c.Error != "" {
				if err == nil || err.Error() != c.Error {
					t.Fatalf("err %v, Python %q", err, c.Error)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if len(docs) != len(c.Pages) {
				t.Fatalf("%d pages, Python %d", len(docs), len(c.Pages))
			}
			for pi, d := range docs {
				ops := d.Ops()
				if len(ops) != len(c.Pages[pi]) {
					t.Fatalf("page %d: %d ops, Python %d", pi+1, len(ops), len(c.Pages[pi]))
				}
				for i, op := range ops {
					raw, _ := json.Marshal(op.Map())
					var got map[string]any
					_ = json.Unmarshal(raw, &got)
					want := c.Pages[pi][i]
					for k, w := range want {
						if f, ok := w.(string); ok && k == "font" {
							w = strings.Replace(f, "UHRemit", "UHSans", 1) // same DejaVu fonts, Go names
						}
						if !same(w, got[k]) {
							t.Fatalf("page %d op %d key %q: Go %v, Python %v (op %v)", pi+1, i, k, got[k], w, want)
						}
					}
					if len(got) != len(want) {
						t.Fatalf("page %d op %d keys differ: Go %v, Python %v", pi+1, i, got, want)
					}
				}
			}
		})
	}
}

func TestRenderIsPDFAndDeterministic(t *testing.T) {
	for _, c := range loadGolden(t) {
		if c.Error != "" {
			continue
		}
		a, err := Renderer{Sample: c.Sample}.Render(c.Report)
		if err != nil {
			t.Fatalf("%s: %v", c.Name, err)
		}
		b, _ := Renderer{Sample: c.Sample}.Render(c.Report)
		if sha256.Sum256(a) != sha256.Sum256(b) {
			t.Fatalf("%s: two renders differ", c.Name)
		}
		if !bytes.HasPrefix(a, []byte("%PDF-")) || !bytes.Contains(a, []byte("%%EOF")) || !bytes.Contains(a, []byte("/FontFile2")) {
			t.Fatalf("%s: not a PDF with embedded font", c.Name)
		}
	}
}

func TestMultiPageHasTwoPages(t *testing.T) {
	for _, c := range loadGolden(t) {
		if c.Name != "many_rows_two_pages_sample" {
			continue
		}
		if len(c.Pages) < 2 {
			t.Fatal("golden should break the page")
		}
		b, err := Renderer{Sample: true}.Render(c.Report)
		if err != nil {
			t.Fatal(err)
		}
		if n := strings.Count(string(b), "/Type /Page") - strings.Count(string(b), "/Type /Pages"); n != len(c.Pages) {
			t.Fatalf("PDF has %d pages, want %d", n, len(c.Pages))
		}
	}
}

func TestAmountAndNights(t *testing.T) {
	if amount(1234567) != "1 234 567 Kč" || amount(0) != "0 Kč" || amount(999) != "999 Kč" || amount(-1050) != "-1 050 Kč" {
		t.Fatal("amount")
	}
	if nights(1) != "1 lůžkoden" || nights(3) != "3 lůžkodny" || nights(0) != "0 lůžkodnů" || nights(5) != "5 lůžkodnů" {
		t.Fatal("nights")
	}
}
