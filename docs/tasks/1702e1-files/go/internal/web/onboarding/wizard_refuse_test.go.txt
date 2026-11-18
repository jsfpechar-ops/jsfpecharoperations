package onboarding

// Tests of RenderSetupPage (brief 1702e1): the wizard step drawn again with a
// save's notice, errors and draft. The expected lines are hand-written from
// App/app/templates/setup_wizard/{_layout,police,property}.html and
// _property_address_fields.html. Seed: testdata/wizard_golden_post.json
// (user 1 owns apartment 11 and operators 31 and 32; user 2 owns apartment 21).

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"
)

// wizardRefuseCall draws step of apartment apt for user 1 through
// RenderSetupPage (a test-only POST on the step's path, so the layout's
// return_to links match), or through GET /apartments/{id}/setup/{step} when get is true.
func wizardRefuseCall(t *testing.T, apt int, step string, p SetupPage, get bool) *httptest.ResponseRecorder {
	t.Helper()
	g := wizardLoadGolden(t, "testdata/wizard_golden_post.json")
	pool := testPool(t)
	wizardGoldenSeed(t, pool, g)
	env := wizardGoldenEnv(g)
	now := func() time.Time { return wizardGoldenNow }
	mux := http.NewServeMux()
	RegisterWizard(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, env, now)
	mux.HandleFunc("POST /apartments/{id}/setup/{step}", func(w http.ResponseWriter, r *http.Request) {
		s := &wizardServer{pool: pool, getenv: env, now: now}
		h, ok := s.wizardLogin(w, r, now())
		if !ok {
			return
		}
		id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
		RenderSetupPage(w, r, pool, env, now, h, id, r.PathValue("step"), p)
	})
	user := int64(1)
	c := wizardGoldenCase{Name: step, Method: http.MethodPost, Path: fmt.Sprintf("/apartments/%d/setup/%s", apt, step), User: &user, CSRF: true}
	if get {
		c.Method, c.CSRF = http.MethodGet, false
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, wizardGoldenRequest(t, g, c))
	return rec
}

// wizardWantInOrder checks that each line is in body, each after the one before.
func wizardWantInOrder(t *testing.T, body string, lines ...string) {
	t.Helper()
	at := 0
	for _, line := range lines {
		i := strings.Index(body[at:], line)
		if i < 0 {
			t.Errorf("missing (or out of order): %s", line)
			continue
		}
		at += i + len(line)
	}
}

func TestWizardRefusePolice(t *testing.T) {
	rec := wizardRefuseCall(t, 11, "police", SetupPage{
		Status: http.StatusBadRequest,
		Notice: "Pozor <b>",
		PoliceErrors: []FieldError{
			{Field: "uby_mark", Message: "Bad mark"},
			{Field: "uby_idub", Message: "Bad IDUB"},
		},
		Draft: map[string]string{"uby_idub": `12<x"`, "uby_name": "", "submit_after_hours": "6"},
	}, false)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status %d, location %q", rec.Code, rec.Header().Get("Location"))
	}
	body := rec.Body.String()
	wizardWantInOrder(t, body,
		`<p class="err-text" role="alert">Pozor &lt;b&gt;</p>`,
		`<p class="err-text" id="uby_mark-error" role="alert">Bad mark</p>`,
		`<p class="err-text" id="uby_idub-error" role="alert">Bad IDUB</p>`,
		`<form method="post" action="/apartments/11" class="setup-wizard-form" id="police-form">`,
		`name="uby_idub" value="12&lt;x&#34;"`,
		`name="uby_mark" value="AAKLI"`,
		`name="uby_name" value=""`,
	)
	if strings.Contains(body, "<b>") {
		t.Error("the notice is not escaped")
	}
}

func TestWizardRefuseProperty(t *testing.T) {
	rec := wizardRefuseCall(t, 11, "property", SetupPage{
		Status:        http.StatusBadRequest,
		AddressErrors: map[string]string{"addr_zip": "Bad zip", "addr_obec": "Bad town"},
		Draft:         map[string]string{"addr_zip": "1", "legal_entity_id": "32", "checkin_hour": "7", "internal_name": "Nový"},
	}, false)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status %d, location %q", rec.Code, rec.Header().Get("Location"))
	}
	body := rec.Body.String()
	wizardWantInOrder(t, body,
		`name="internal_name" value="Nový"`,
		`<option value="7" selected>07:00</option>`,
		`<option value="32" selected>`,
		`aria-describedby="addr_street-help" data-ruian-suggest`,
		`id="addr_zip" name="addr_zip" autocomplete="off" value="1" maxlength="6" inputmode="numeric" placeholder="12000" required aria-required="true" aria-describedby="addr_zip-help addr_zip-error" aria-invalid="true">`,
		`<p class="err-text" id="addr_zip-error" role="alert">Bad zip</p>`,
		`placeholder="Praha" required aria-required="true" aria-describedby="addr_obec-error" aria-invalid="true">`,
		`<p class="err-text" id="addr_obec-error" role="alert">Bad town</p>`,
	)
	if strings.Count(body, `aria-invalid="true"`) != 2 || strings.Contains(body, `class="err-text" role="alert"`) {
		t.Error("only the two refused fields carry an error, and there is no notice")
	}
}

// TestWizardRefuseEmptyIsTheStepPage: no extra context draws exactly what GET does.
func TestWizardRefuseEmptyIsTheStepPage(t *testing.T) {
	// Apartment 12 has no details yet (GET shows its property step); 11 is complete.
	for step, apt := range map[string]int{"property": 12, "police": 11} {
		got := wizardRefuseCall(t, apt, step, SetupPage{}, false)
		want := wizardRefuseCall(t, apt, step, SetupPage{}, true)
		if got.Code != http.StatusOK || want.Code != http.StatusOK {
			t.Fatalf("%s: status %d and %d", step, got.Code, want.Code)
		}
		if g, w := wizardCSRFRE.ReplaceAllString(got.Body.String(), ""), wizardCSRFRE.ReplaceAllString(want.Body.String(), ""); g != w {
			t.Errorf("%s: %s", step, wizardTextDiff(g, w))
		}
	}
}

// TestWizardRefuseForeign: another host's apartment is _wizard_context's redirect.
func TestWizardRefuseForeign(t *testing.T) {
	rec := wizardRefuseCall(t, 21, "police", SetupPage{Status: http.StatusBadRequest, Notice: "x"}, false)
	if loc := rec.Header().Get("Location"); rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, "/apartments?err=") {
		t.Fatalf("status %d, location %q", rec.Code, loc)
	}
}

func TestWizardSetupPageDraft(t *testing.T) {
	id := int64(31)
	v := &wizardView{Apt: &wizardApt{ID: 9, LegalEntityID: &id}}
	v.Values = v.Apt.values()
	v.applySetupPage(SetupPage{Draft: map[string]string{"legal_entity_id": "x", "notes": "ignored", "uby_mark": "ab"}})
	if v.Apt.LegalEntityID != nil || v.Values.LegalEntityID != "None" || v.Values.UbyMark != "ab" {
		t.Errorf("draft %+v %+v", v.Apt.LegalEntityID, v.Values)
	}
	if id != 31 {
		t.Error("the draft changed the loaded apartment")
	}
	v.applySetupPage(SetupPage{Draft: map[string]string{"legal_entity_id": " 32 "}})
	if v.Apt.LegalEntityID == nil || *v.Apt.LegalEntityID != 32 || v.Values.LegalEntityID != "32" {
		t.Errorf("draft 32: %+v", v.Values.LegalEntityID)
	}
	v.OperatorError = "keep"
	v.applySetupPage(SetupPage{})
	if v.OperatorError != "keep" {
		t.Error("an empty operator_error cleared the view's")
	}
	in := wizardAddressInput{Name: "addr_zip", Help: "h"}
	if in.Described() != "addr_zip-help" {
		t.Error(in.Described())
	}
	in.Error, in.Help = "e", ""
	if in.Described() != "addr_zip-error" {
		t.Error(in.Described())
	}
}
