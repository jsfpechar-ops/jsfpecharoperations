package billingweb

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"os"
	"reflect"
	"testing"
	"time"
)

// golden is testdata/billing_admin_golden.json, written by
// App/scripts/billing_admin_golden.py from the real Python.
type golden struct {
	Today string `json:"today"`
	Seed  []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Pure struct {
		MonthOrCurrent []struct{ In, Out string } `json:"month_or_current"`
		KcCSV          []struct {
			In  int64
			Out string
		} `json:"kc_csv"`
		Cz []struct {
			In  int64
			Out string
		} `json:"cz"`
		KcPage []struct {
			In  int64
			Out string
		} `json:"kc_page"`
		NextMonthStart []struct{ In, Out string } `json:"next_month_start"`
	} `json:"pure"`
	Parser []struct {
		Name     string    `json:"name"`
		InputB64 string    `json:"input_b64"`
		Rows     []Payment `json:"rows"`
		Error    string    `json:"error"`
		Reason   string    `json:"reason"`
	} `json:"parser"`
	Scenarios []struct {
		Fn     string            `json:"fn"`
		Args   map[string]string `json:"args"`
		Today  string            `json:"today"`
		Result json.RawMessage   `json:"result"`
	} `json:"scenarios"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/billing_admin_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g golden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	return g
}

func mustDay(t *testing.T, s string) time.Time {
	t.Helper()
	d, err := time.Parse("2006-01-02", s)
	if err != nil {
		t.Fatal(err)
	}
	return d
}

// sameJSON reports whether the JSON of got equals want, number for number.
func sameJSON(t *testing.T, got any, want json.RawMessage) (bool, string, string) {
	t.Helper()
	gb, err := json.Marshal(got)
	if err != nil {
		t.Fatal(err)
	}
	decode := func(b []byte) any {
		dec := json.NewDecoder(bytes.NewReader(b))
		dec.UseNumber()
		var v any
		if err := dec.Decode(&v); err != nil {
			t.Fatal(err)
		}
		return v
	}
	return reflect.DeepEqual(decode(gb), decode(want)), string(gb), string(want)
}

func clip(s string) string {
	if len(s) > 1500 {
		return s[:1500] + "..."
	}
	return s
}

func TestPureHelpersMatchPython(t *testing.T) {
	g := loadGolden(t)
	today := mustDay(t, g.Today)
	if len(g.Pure.MonthOrCurrent) < 9 || len(g.Pure.KcCSV) < 10 || len(g.Pure.KcPage) < 11 || len(g.Pure.NextMonthStart) < 4 {
		t.Fatal("golden file has too few pure cases")
	}
	for _, c := range g.Pure.MonthOrCurrent {
		if got := MonthOrCurrent(c.In, today); got != c.Out {
			t.Errorf("MonthOrCurrent(%q) = %q, Python %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Pure.KcCSV {
		if got := KcCSV(c.In); got != c.Out {
			t.Errorf("KcCSV(%d) = %q, Python %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Pure.Cz {
		if got := KcCSV(c.In); got != c.Out {
			t.Errorf("_cz(%d) = %q, Python %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Pure.KcPage {
		if got := Kc(c.In); got != c.Out {
			t.Errorf("Kc(%d) = %q, Python %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Pure.NextMonthStart {
		if got := NextMonthStart(mustDay(t, c.In)); got != c.Out {
			t.Errorf("NextMonthStart(%s) = %q, Python %q", c.In, got, c.Out)
		}
	}
}

func TestParseMatchesPython(t *testing.T) {
	g := loadGolden(t)
	if len(g.Parser) < 16 {
		t.Fatalf("golden file has %d statements, want at least 16", len(g.Parser))
	}
	rowsSeen := 0
	for _, c := range g.Parser {
		data, err := base64.StdEncoding.DecodeString(c.InputB64)
		if err != nil {
			t.Fatal(err)
		}
		rows, err := Parse(data)
		switch c.Error {
		case "":
			if err != nil {
				t.Errorf("%s: %v, Python parsed %d rows", c.Name, err, len(c.Rows))
				continue
			}
			want, _ := json.Marshal(c.Rows)
			if ok, got, _ := sameJSON(t, rows, want); !ok {
				t.Errorf("%s differs from Python\n got: %s\nwant: %s", c.Name, clip(got), clip(string(want)))
			}
			rowsSeen += len(rows)
		case "StatementError":
			var se *StatementError
			if err == nil || !IsStatementError(err) {
				t.Errorf("%s: err = %v, Python StatementError", c.Name, err)
			} else if se = err.(*StatementError); se.Reason != c.Reason {
				t.Errorf("%s: reason %q, Python %q", c.Name, se.Reason, c.Reason)
			}
		case "ValueError":
			if err == nil || IsStatementError(err) {
				t.Errorf("%s: err = %v, Python ValueError", c.Name, err)
			}
		default:
			t.Fatalf("%s: unknown golden error %q", c.Name, c.Error)
		}
	}
	if rowsSeen < 40 {
		t.Fatalf("only %d parsed rows compared", rowsSeen)
	}
}

func TestInvoiceVS(t *testing.T) {
	for vs, want := range map[string]bool{
		"20260042": true, "20991231": true, "2026004": false, "202600421": false,
		"19260042": false, "2026004a": false, "": false,
	} {
		if InvoiceVS(vs) != want {
			t.Errorf("InvoiceVS(%q) != %v", vs, want)
		}
	}
}
