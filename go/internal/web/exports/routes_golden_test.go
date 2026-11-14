package exports

// Brief 1606: the request cases of testdata/exports_routes_golden.json
// (written by App/scripts/exports_routes_golden.py against the Python app),
// replayed on the Go routes. Each brief from 1606 to 1609 adds the test of
// its own case prefix; the replay is shared.

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"testing"
)

type routeCase struct {
	Name    string            `json:"name"`
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Session map[string]int64  `json:"session"`
	Lang    *string           `json:"lang"`
	CSRF    bool              `json:"csrf"`
	Status  int               `json:"status"`
	Headers map[string]string `json:"headers"`
	Audit   [][]any           `json:"audit"`
	Zip     [][]string        `json:"zip"`
	Body    *string           `json:"body"`
	State   map[string]any    `json:"state"`
}

type routesGolden struct {
	Extras []string    `json:"extras"`
	Photos []string    `json:"photos"`
	Cases  []routeCase `json:"cases"`
}

var (
	mainRE   = regexp.MustCompile(`(?s)<main id="main-content".*?</main>`)
	spacesRE = regexp.MustCompile(`\s+`)
)

// mainPart is the golden's main_part: the <main> element, whitespace folded.
func mainPart(s string) string {
	if m := mainRE.FindString(s); m != "" {
		s = m
	}
	return strings.ReplaceAll(spacesRE.ReplaceAllString(s, " "), "> <", "><")
}

// newRoutesWorld is newWorld plus the golden's extra rows and photo files.
func newRoutesWorld(t *testing.T) (*world, routesGolden) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "exports_routes_golden.json"))
	if err != nil {
		t.Fatal(err)
	}
	var h routesGolden
	if err := json.Unmarshal(raw, &h); err != nil {
		t.Fatal(err)
	}
	w := newWorld(t)
	for _, s := range h.Extras {
		w.exec(s)
	}
	for _, name := range h.Photos {
		if err := os.WriteFile(filepath.Join(w.dataDir, "passport_photos", name), []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	return w, h
}

func optional(p *int64) string {
	if p == nil {
		return "<nil>"
	}
	return fmt.Sprint(*p)
}

// replayRoutes runs, in golden order, the cases whose name starts with
// prefix and compares status, headers, audit rows, zip entries, page and
// state. It returns the number of cases run.
func replayRoutes(t *testing.T, prefix string) int {
	t.Helper()
	w, h := newRoutesWorld(t)
	ctx := context.Background()
	ran := 0
	for _, c := range h.Cases {
		if !strings.HasPrefix(c.Name, prefix) {
			continue
		}
		ran++
		last := w.auditMax()
		var s *who
		if c.Session != nil {
			s = &who{uid: c.Session["uid"], as: c.Session["as"], stale: c.Session["stale"] != 0}
		}
		rec := w.doLang(c.Method, c.Path, s, c.Lang, !c.CSRF)
		if rec.Code != c.Status {
			t.Errorf("%s: status %d, want %d (%.200s)", c.Name, rec.Code, c.Status, rec.Body.String())
			continue
		}
		for _, k := range comparedHeaders {
			if rec.Code == 303 && k == "content-type" {
				continue
			}
			if got, want := rec.Header().Get(k), c.Headers[k]; got != want {
				t.Errorf("%s: %s %q, want %q", c.Name, k, got, want)
			}
		}
		rows, err := w.pool.Query(ctx, `SELECT actor, action, detail, owner_user_id, actor_user_id,
			impersonator_user_id FROM audit WHERE id > $1 ORDER BY id`, last)
		if err != nil {
			t.Fatal(err)
		}
		var got, want []string
		for rows.Next() {
			var actor, action string
			var detail *string
			var o, a, i *int64
			if err := rows.Scan(&actor, &action, &detail, &o, &a, &i); err != nil {
				t.Fatal(err)
			}
			got = append(got, fmt.Sprint(actor, "|", action, "|", deref(detail), "|", optional(o), "|", optional(a), "|", optional(i)))
		}
		rows.Close()
		for _, r := range c.Audit {
			cell := func(v any) string {
				if v == nil {
					return "<nil>"
				}
				return fmt.Sprint(v)
			}
			want = append(want, cell(r[0])+"|"+cell(r[1])+"|"+cell(r[2])+"|"+cell(r[3])+"|"+cell(r[4])+"|"+cell(r[5]))
		}
		if strings.Join(got, "\n") != strings.Join(want, "\n") {
			t.Errorf("%s: audit rows\n got %q\nwant %q", c.Name, got, want)
		}
		switch {
		case c.Zip != nil:
			compareZip(t, c, rec.Body.Bytes())
		case c.Body != nil && rec.Code == 200 && strings.HasPrefix(rec.Header().Get("Content-Type"), "text/html"):
			if g := mainPart(rec.Body.String()); g != *c.Body {
				i := 0
				for i < len(g) && i < len(*c.Body) && g[i] == (*c.Body)[i] {
					i++
				}
				lo := max(0, i-150)
				t.Errorf("%s: page differs at byte %d\n go: %s\n py: %s", c.Name, i,
					g[lo:min(len(g), i+250)], (*c.Body)[lo:min(len(*c.Body), i+250)])
			}
		case c.Body != nil && *c.Body == "PDF":
			if !bytes.HasPrefix(rec.Body.Bytes(), []byte("%PDF")) {
				t.Errorf("%s: body is not a PDF", c.Name)
			}
		}
		compareState(t, w, c)
	}
	if ran == 0 {
		t.Fatalf("no golden case starts with %q", prefix)
	}
	return ran
}

// compareZip compares the entries by name: a registration form as "PDF", the
// manifest as text, anything else as base64 (exports_routes_golden's form).
func compareZip(t *testing.T, c routeCase, body []byte) {
	t.Helper()
	zr, err := zip.NewReader(bytes.NewReader(body), int64(len(body)))
	if err != nil {
		t.Errorf("%s: zip: %v", c.Name, err)
		return
	}
	var got [][]string
	for _, f := range zr.File {
		rc, err := f.Open()
		if err != nil {
			t.Fatal(err)
		}
		var b bytes.Buffer
		if _, err := b.ReadFrom(rc); err != nil {
			t.Fatal(err)
		}
		rc.Close()
		switch {
		case bytes.HasPrefix(b.Bytes(), []byte("%PDF")) && strings.HasSuffix(f.Name, ".pdf") &&
			(strings.HasPrefix(f.Name, "guests/") || !strings.Contains(f.Name, "/")):
			got = append(got, []string{f.Name, "PDF"})
		case f.Name == "manifest.json":
			got = append(got, []string{f.Name, b.String()})
		default:
			got = append(got, []string{f.Name, base64.StdEncoding.EncodeToString(b.Bytes())})
		}
	}
	want := append([][]string(nil), c.Zip...)
	if !strings.HasPrefix(c.Name, "ws_") {
		// The house-book zip keeps Python's row order; only the workspace
		// zip is compared by name (Known differences of brief 1607).
		if fmt.Sprint(names(got)) != fmt.Sprint(names(want)) {
			t.Errorf("%s: zip entries\n got %v\nwant %v", c.Name, names(got), names(want))
		}
	}
	sort.Slice(got, func(i, j int) bool { return got[i][0] < got[j][0] })
	sort.Slice(want, func(i, j int) bool { return want[i][0] < want[j][0] })
	if len(got) != len(want) {
		t.Errorf("%s: zip entries\n got %v\nwant %v", c.Name, names(got), names(want))
		return
	}
	for i := range got {
		if got[i][0] != want[i][0] || got[i][1] != want[i][1] {
			t.Errorf("%s: entry %s\n got %.600s\nwant %.600s", c.Name, want[i][0], got[i][1], want[i][1])
		}
	}
}

func names(entries [][]string) []string {
	var out []string
	for _, e := range entries {
		out = append(out, e[0])
	}
	return out
}

// compareState checks the golden's queries and the photo directory.
func compareState(t *testing.T, w *world, c routeCase) {
	t.Helper()
	for q, v := range c.State {
		if q == "photos" {
			entries, err := os.ReadDir(filepath.Join(w.dataDir, "passport_photos"))
			if err != nil {
				t.Fatal(err)
			}
			got := []string{}
			for _, e := range entries {
				got = append(got, e.Name())
			}
			sort.Strings(got)
			if fmt.Sprint(got) != fmt.Sprint(v) {
				t.Errorf("%s: photos %v, want %v", c.Name, got, v)
			}
			continue
		}
		var got any
		if err := w.pool.QueryRow(context.Background(), q).Scan(&got); err != nil {
			t.Fatalf("%s: %v", q, err)
		}
		if fmt.Sprint(got) != fmt.Sprint(v) {
			t.Errorf("%s: %s = %v, want %v", c.Name, q, got, v)
		}
	}
}

// TestFormRefusalsMatchPython replays the form_ cases (brief 1605's route).
func TestFormRefusalsMatchPython(t *testing.T) {
	if n := replayRoutes(t, "form_"); n != 11 {
		t.Errorf("ran %d form_ cases, want 11", n)
	}
}

// TestHousebookPDFsMatchPython replays the zip_ cases.
func TestHousebookPDFsMatchPython(t *testing.T) {
	if n := replayRoutes(t, "zip_"); n != 11 {
		t.Errorf("ran %d zip_ cases, want 11", n)
	}
}
