package exports

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"os"
	"testing"
	"time"
)

// formGolden is one case of testdata/registration_form_golden.json, written by
// App/scripts/registration_form_golden.py from housebook.registration_form_pdf.
type formGolden struct {
	Name   string            `json:"name"`
	Now    string            `json:"now"`
	Guest  map[string]any    `json:"guest"`
	Record map[string]string `json:"record"`
	Ops    []map[string]any  `json:"ops"`
}

// sameValue compares a golden JSON value with a Go op value (numbers within 0.01 pt).
func sameValue(want, got any) bool {
	switch w := want.(type) {
	case json.Number:
		f, _ := w.Float64()
		var g float64
		switch x := got.(type) {
		case float64:
			g = x
		case int:
			g = float64(x)
		default:
			return false
		}
		return math.Abs(f-g) < 0.01
	case []any:
		g, ok := got.([]float64)
		if !ok || len(g) != len(w) {
			return false
		}
		for i := range w {
			if !sameValue(w[i], g[i]) {
				return false
			}
		}
		return true
	default:
		return fmt.Sprint(want) == fmt.Sprint(got)
	}
}

func TestRegistrationFormMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/registration_form_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []formGolden
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 9 {
		t.Fatalf("%d cases, want at least 9", len(cases))
	}
	for _, c := range cases {
		at, err := time.ParseInLocation("2006-01-02T15:04:05", c.Now, time.Local)
		if err != nil {
			t.Fatal(err)
		}
		g := row{}
		for k, v := range c.Guest {
			g[k] = value(v)
		}
		doc := drawRegistrationForm(g, sigRecord{Kind: c.Record["kind"], Text: c.Record["text"]}, at)
		ops := doc.Ops()
		if len(ops) != len(c.Ops) {
			t.Errorf("%s: %d ops, want %d", c.Name, len(ops), len(c.Ops))
			continue
		}
		for i, op := range ops {
			got := op.Map()
			want := c.Ops[i]
			if len(got) != len(want) {
				t.Errorf("%s op %d: keys %v, want %v", c.Name, i, got, want)
				continue
			}
			for k, wv := range want {
				if !sameValue(wv, got[k]) {
					t.Errorf("%s op %d (%v): %s = %v, want %v", c.Name, i, want["op"], k, got[k], wv)
				}
			}
		}
		body, err := doc.Bytes()
		if err != nil || !bytes.HasPrefix(body, []byte("%PDF-")) {
			t.Errorf("%s: no PDF (%v)", c.Name, err)
		}
	}
}

func TestSignatureRecord(t *testing.T) {
	w := newWorld(t)
	ctx := context.Background()
	d := deps{w.pool, w.getenv, func() time.Time { return w.at }}
	for _, c := range []struct {
		id   int64
		want sigRecord
	}{
		// Guest 11 signed; 12 is under 15 and 11 (an adult with a valid
		// signature) signed for them; 19 is under 15 and 20 signed on paper,
		// which does not count; 14 is a paper import.
		{11, sigRecord{"own", ""}},
		{12, sigRecord{"signed_for", "Signed by Hans Müller for Kid Müller, as None, None, wording None"}},
		{19, sigRecord{"exempt", "Under 15, no signature required (§ 103(b))"}},
		{14, sigRecord{"imported", "Signature on paper (host)"}},
		{1, sigRecord{"missing", ""}},
	} {
		rows, _, err := queryRows(ctx, w.pool, registrationFormSQL, c.id)
		if err != nil || len(rows) != 1 {
			t.Fatalf("guest %d: %v", c.id, err)
		}
		if err := hydrate(w.getenv, rows[0]); err != nil {
			t.Fatal(err)
		}
		got, err := signatureRecord(ctx, d, rows[0])
		if err != nil || got != c.want {
			t.Errorf("guest %d: %+v (%v), want %+v", c.id, got, err, c.want)
		}
	}
	w.exec(`UPDATE guest SET signed_for_role = 'parent', signed_for_at = '2026-05-01T10:05:00+00:00',
		signed_for_wording = 'v1' WHERE id = 12`)
	rows, _, _ := queryRows(ctx, w.pool, registrationFormSQL, int64(12))
	_ = hydrate(w.getenv, rows[0])
	got, _ := signatureRecord(ctx, d, rows[0])
	if want := "Signed by Hans Müller for Kid Müller, as parent or legal guardian, 2026-05-01T10:05:00+00:00, wording v1"; got.Text != want {
		t.Errorf("role text %q", got.Text)
	}
	if _, err := registrationFormPDF(ctx, d, 999, w.at); err != errNoGuest {
		t.Errorf("missing guest: %v", err)
	}
}

func TestGuestFormPDFRoute(t *testing.T) {
	w := newWorld(t)
	rec := w.do(http.MethodGet, "/guests/11/form.pdf", nil, nil, false)
	redirectsTo(t, "signed out", rec, "/login?next=/guests/11/form.pdf")
	for _, c := range []struct {
		name, path string
		s          *who
		prefix     string
	}{
		{"other owner's guest", "/guests/4/form.pdf", asOwner, "/reservations?err="},
		{"missing guest", "/guests/999/form.pdf", asOwner, "/reservations?err="},
		{"another workspace", "/guests/11/form.pdf", asOther, "/reservations?err="},
	} {
		before := w.auditMax()
		rec := w.do(http.MethodGet, c.path, c.s, nil, false)
		redirectsTo(t, c.name, rec, c.prefix)
		if w.auditMax() != before {
			t.Errorf("%s: wrote an audit row", c.name)
		}
	}
	rec = w.do(http.MethodGet, "/guests/11/form.pdf", asOwner, nil, false)
	if rec.Code != http.StatusOK || rec.Header().Get("Content-Type") != "application/pdf" ||
		rec.Header().Get("Content-Disposition") != `attachment; filename="registration-form-11.pdf"` ||
		rec.Header().Get("Cache-Control") != "no-store, private" || !bytes.HasPrefix(rec.Body.Bytes(), []byte("%PDF-")) {
		t.Fatalf("owner: %d %v", rec.Code, rec.Header())
	}
	if got := fmt.Sprint(w.lastAudit()); got != "[export_registration_pdf guest_id=11 owner@example.test 1 1 <nil>]" {
		t.Errorf("audit %s", got)
	}
	// An administrator supporting the workspace sees identity data
	// (access.identity_visible): the form, audited with the impersonator.
	if rec := w.do(http.MethodGet, "/guests/11/form.pdf", asSupport, nil, false); rec.Code != http.StatusOK {
		t.Errorf("supporting: %d", rec.Code)
	}
	if got := fmt.Sprint(w.lastAudit()); got != "[export_registration_pdf guest_id=11 admin@example.test 1 3 3]" {
		t.Errorf("supporting audit %s", got)
	}
	// A child signed for by an adult renders too (the record needs a second read).
	if rec := w.do(http.MethodGet, "/guests/12/form.pdf", asOwner, nil, false); rec.Code != http.StatusOK {
		t.Errorf("child: %d", rec.Code)
	}
	// A token no key reads: access.guest raises, a 500, no audit row.
	before := w.auditMax()
	if rec := w.do(http.MethodGet, "/guests/400/form.pdf", asBroken, nil, false); rec.Code != http.StatusInternalServerError {
		t.Errorf("corrupt token: %d", rec.Code)
	}
	if w.auditMax() != before {
		t.Error("corrupt token wrote an audit row")
	}
	if rec := w.do(http.MethodGet, "/guests/abc/form.pdf", asOwner, nil, false); rec.Code != http.StatusNotFound {
		t.Errorf("non-integer id: %d", rec.Code)
	}
	// An admin in their own (empty) workspace finds no guest.
	redirectsTo(t, "admin", w.do(http.MethodGet, "/guests/11/form.pdf", asAdmin, nil, false), "/reservations?err=")
}
