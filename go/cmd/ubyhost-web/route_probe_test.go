package main

// Route probe for scripts/go_parity_check.py. It builds the real mux and, for
// each {method, path} in the file named by GO_PROBE_IN, writes the mux pattern
// that would serve it to GO_PROBE_OUT. Only the "/" catch-all means "no Go
// handler". It skips when GO_PROBE_IN is unset, so a normal `go test` ignores it.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"testing"
)

type probeIn struct {
	Method string `json:"method"`
	Path   string `json:"path"`
}

type probeOut struct {
	Method  string `json:"method"`
	Path    string `json:"path"`
	Pattern string `json:"pattern"`
	Handled bool   `json:"handled"`
}

var probeParam = regexp.MustCompile(`\{[^/}]*\}`)

func TestRouteProbe(t *testing.T) {
	in := os.Getenv("GO_PROBE_IN")
	if in == "" {
		t.Skip("GO_PROBE_IN not set")
	}
	raw, err := os.ReadFile(in)
	if err != nil {
		t.Fatal(err)
	}
	var items []probeIn
	if err := json.Unmarshal(raw, &items); err != nil {
		t.Fatal(err)
	}
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	out := make([]probeOut, 0, len(items))
	for _, it := range items {
		p := probeParam.ReplaceAllString(it.Path, "1")
		req := httptest.NewRequest(it.Method, p, nil)
		_, pat := mux.Handler(req)
		out = append(out, probeOut{it.Method, it.Path, pat, pat != "" && pat != "/"})
	}
	b, _ := json.Marshal(out)
	if err := os.WriteFile(os.Getenv("GO_PROBE_OUT"), b, 0o644); err != nil {
		t.Fatal(err)
	}
	_ = http.MethodGet
}

// TestJobProbe writes the Go job kinds and their intervals (minutes) to
// GO_PROBE_JOBS_OUT for scripts/go_jobs_parity.py.
func TestJobProbe(t *testing.T) {
	out := os.Getenv("GO_PROBE_JOBS_OUT")
	if out == "" {
		t.Skip("GO_PROBE_JOBS_OUT not set")
	}
	b, _ := json.Marshal(goIntervals)
	if err := os.WriteFile(out, b, 0o644); err != nil {
		t.Fatal(err)
	}
}
