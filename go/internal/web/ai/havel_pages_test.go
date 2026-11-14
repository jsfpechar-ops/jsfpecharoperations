package ai

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"
)

// The pure helpers of havel_pages.go against the real Python (testdata/havel_golden.json).
func TestHavelPageHelpersMatchPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/havel_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g struct {
		Blocks []struct {
			In  string `json:"in"`
			Out []struct {
				Kind  string   `json:"kind"`
				Text  string   `json:"text"`
				Items []string `json:"items"`
			} `json:"out"`
		} `json:"blocks"`
		CleanID  []struct{ In, Out string } `json:"clean_id"`
		SafePath []struct{ In, Out string } `json:"safe_path"`
	}
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Blocks) == 0 || len(g.CleanID) == 0 || len(g.SafePath) < 25 {
		t.Fatal("golden cases missing: run App/scripts/havel_golden.py")
	}
	for _, c := range g.Blocks {
		got := havelBlocks(c.In)
		if len(got) != len(c.Out) {
			t.Errorf("blocks(%q): %d blocks, Python %d", c.In, len(got), len(c.Out))
			continue
		}
		for i, b := range got {
			w := c.Out[i]
			if b.Kind != w.Kind || b.Text != w.Text || (w.Kind == "ol" && !reflect.DeepEqual(b.Items, w.Items)) {
				t.Errorf("blocks(%q)[%d] = %+v, Python %+v", c.In, i, b, w)
			}
		}
	}
	for _, c := range g.CleanID {
		if got := havelCleanID(c.In); got != c.Out {
			t.Errorf("clean_id(%q) = %q, Python %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.SafePath {
		if got := HavelSafeLocalPath(c.In, "/havel"); got != c.Out {
			t.Errorf("safe_local_path(%q) = %q, Python %q", c.In, got, c.Out)
		}
	}
}

func TestHavelSplitLines(t *testing.T) {
	got := havelSplitLines("a\r\nb\rc d\x0be\n\nf\n")
	want := []string{"a", "b", "c", "d", "e", "", "f"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("splitlines %q, want %q (str.splitlines)", got, want)
	}
}

func TestHavelCardDateLabels(t *testing.T) {
	c := &HavelCard{DateFrom: "2026-12-01", DateTo: "2026-12-04"}
	if c.DateFromLabel() != "Tue 01.12.2026" || c.DateToLabel() != "Fri 04.12.2026" {
		t.Errorf("labels %q %q", c.DateFromLabel(), c.DateToLabel())
	}
}
