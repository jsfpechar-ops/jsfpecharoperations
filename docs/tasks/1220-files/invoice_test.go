package pdf

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"math"
	"os"
	"testing"
)

type goldenCase struct {
	Name    string           `json:"name"`
	Lang    string           `json:"lang"`
	Preview bool             `json:"preview"`
	Invoice Invoice          `json:"invoice"`
	Items   []Item           `json:"items"`
	TooLong bool             `json:"too_long"`
	Ops     []map[string]any `json:"ops"`
}

func loadGolden(t *testing.T) []goldenCase {
	t.Helper()
	raw, err := os.ReadFile("testdata/invoice_pdf_golden.json")
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

func asJSON(t *testing.T, m map[string]any) map[string]any {
	raw, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

func TestLayoutMatchesPythonOps(t *testing.T) {
	for _, c := range loadGolden(t) {
		t.Run(c.Name, func(t *testing.T) {
			long, err := TooLong(c.Invoice, c.Items, c.Lang)
			if err != nil {
				t.Fatal(err)
			}
			if long != c.TooLong {
				t.Fatalf("too_long = %v, Python %v", long, c.TooLong)
			}
			if c.TooLong {
				if _, err := Render(c.Invoice, c.Items, c.Lang, false, true); err != ErrTooLong {
					t.Fatalf("strict render err = %v", err)
				}
				return
			}
			d, err := Layout(c.Invoice, c.Items, c.Lang, c.Preview, false)
			if err != nil {
				t.Fatal(err)
			}
			ops := d.Ops()
			if len(ops) != len(c.Ops) {
				t.Fatalf("%d ops, Python %d", len(ops), len(c.Ops))
			}
			for i, op := range ops {
				got := asJSON(t, op.Map())
				for k, want := range c.Ops[i] {
					if !same(want, got[k]) {
						t.Fatalf("op %d key %q: Go %v, Python %v (op %v)", i, k, got[k], want, c.Ops[i])
					}
				}
				if len(got) != len(c.Ops[i]) {
					t.Fatalf("op %d keys differ: Go %v, Python %v", i, got, c.Ops[i])
				}
			}
		})
	}
}

func TestRenderParsesAndIsDeterministic(t *testing.T) {
	for _, c := range loadGolden(t) {
		if c.TooLong {
			continue
		}
		a, err := Render(c.Invoice, c.Items, c.Lang, c.Preview, true)
		if err != nil {
			t.Fatalf("%s: %v", c.Name, err)
		}
		b, _ := Render(c.Invoice, c.Items, c.Lang, c.Preview, true)
		if sha256.Sum256(a) != sha256.Sum256(b) {
			t.Fatalf("%s: two renders differ", c.Name)
		}
		if !bytes.HasPrefix(a, []byte("%PDF-")) || !bytes.Contains(a, []byte("%%EOF")) {
			t.Fatalf("%s: not a PDF", c.Name)
		}
		if !bytes.Contains(a, []byte("/FontFile2")) || !bytes.Contains(a, []byte("UHSans")) {
			t.Fatalf("%s: font not embedded", c.Name)
		}
		if len(a) > 400_000 {
			t.Fatalf("%s: %d bytes is too big", c.Name, len(a))
		}
	}
}

func TestMoneyAndWidths(t *testing.T) {
	if got := Money(-123456789); got != "−1 234 567,89 Kč" {
		t.Fatalf("money %q", got)
	}
	if got := Money(5); got != "0,05 Kč" {
		t.Fatalf("money %q", got)
	}
	if floorDiv(-7, 2) != -4 || floorDiv(7, 2) != 3 {
		t.Fatal("floorDiv")
	}
}

func TestPreviewWatermarkIsTransparent(t *testing.T) {
	d := NewDoc()
	d.Watermark("X", Bold, 34, Coral, 0.12, 35, W/2, H/2)
	b, err := d.Bytes()
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(b, []byte("/ca 0.12")) {
		t.Fatal("watermark has no 0.12 fill alpha")
	}
}
