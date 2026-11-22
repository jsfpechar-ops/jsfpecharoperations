package properties

// Tests of GET /apartments/new (brief 1700a). Every expected value is written
// by hand from the Python page (apartment_form.html create branch); there is
// no golden file and no Python script.

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const apartmentNewSecret = "apartment-new-test-secret-key-0123456789"

// Host A is 130001, host B 130002, admin 130003 (seedHosts).
const (
	anOpAlpha, anOpBeta, anOpGone, anOpOther = 130101, 130102, 130103, 130104
	anLoft, anPlain, anOld, anForeign        = 130201, 130202, 130203, 130204
)

func apartmentNewGetenv(k string) string {
	return map[string]string{"UBYHOST_SECRET_KEY": apartmentNewSecret, "UBYHOST_TERMS_VERSION": "t1",
		"UBYHOST_PRIVACY_VERSION": "p1", "UBYHOST_DPA_VERSION": "d1"}[k]
}

func apartmentNewMux(pool *pgxpool.Pool) *http.ServeMux {
	mux := http.NewServeMux()
	RegisterApartmentNew(mux, noWrap, pool, apartmentNewGetenv, testClock)
	return mux
}

// apartmentNewSignIn adds the language and session cookies of user (0: signed
// out), previewing workspace when it is not 0.
func apartmentNewSignIn(req *http.Request, user, workspace int64, lang string) {
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	if user != 0 {
		payload := map[string]any{"uid": user, "sv": 1}
		if workspace != 0 {
			payload["as"] = workspace
			payload["ast"] = testNow.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(apartmentNewSecret, payload, testNow)})
	}
}

// apartmentNewWorld seeds two hosts and an admin: host A has two live
// operators, an archived one, a loft with copyable settings, a plain
// property (blank stay fee text) and an archived property; host B has one
// operator and one property.
func apartmentNewWorld(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	seedHosts(t, pool)
	mustExec(t, pool, `INSERT INTO legal_entity (id, owner_user_id, name, seat, archived_at, created_at) VALUES
		($1, 130001, 'Alpha Co', 'Praha', NULL, $5), ($2, 130001, 'Beta & Sons <s.r.o.>', 'Brno', NULL, $5),
		($3, 130001, 'Gone Co', 'Brno', '2026-01-02', $5), ($4, 130002, 'Other Co', 'Brno', NULL, $5)`,
		anOpAlpha, anOpBeta, anOpGone, anOpOther, stamp0)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, legal_entity_id, data_controller_entity_id, automation_mode,
		submit_after_hours, default_purpose, permalink_window_days, permalink_reachback_days, stay_fee_rate_czk, stay_fee_cadence,
		stay_fee_payee, archived_at, created_at) VALUES
		($1, 130001, 'Loft <A>', $5, $6, 'manual', 12, '20', 5, 30, 50, 'quarterly', 'City Hall', NULL, $8),
		($2, 130001, 'Plain', $6, NULL, 'scheduled', 0, '10', 0, 0, 0, 'monthly', '  ', NULL, $8),
		($3, 130001, 'Old archived', $5, NULL, 'scheduled', 0, '10', 0, 0, 0, 'monthly', NULL, '2026-01-03', $8),
		($4, 130002, 'Other host', $7, NULL, 'scheduled', 0, '10', 0, 0, 0, 'monthly', NULL, NULL, $8)`,
		anLoft, anPlain, anOld, anForeign, anOpAlpha, anOpBeta, anOpOther, stamp0)
}

func apartmentNewGet(mux http.Handler, query string, user, workspace int64, lang string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, "/apartments/new"+query, nil)
	req.Header.Set("Accept", "text/html")
	apartmentNewSignIn(req, user, workspace, lang)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// TestApartmentNewPage: status, redirect, owner scoping, the selected
// operator, the hidden copy fields and the CSRF field, all as hand-written
// fragments of the page.
func TestApartmentNewPage(t *testing.T) {
	pool := testPool(t)
	apartmentNewWorld(t, pool)
	mux := apartmentNewMux(pool)
	const createForm = `<form method="post" action="/apartments" class="property-create-form" id="property-create-form">`
	chooseSelected := `<option value="" disabled selected>Choose operator</option>`
	for _, c := range []struct {
		name            string
		user, workspace int64
		lang, query     string
		status          int
		has, lacks      []string
	}{
		{"signed out", 0, 0, "en", "", 303, nil, nil},
		{"host A default", 130001, 0, "en", "", 200, []string{
			`<title>Add property</title>`, createForm, chooseSelected,
			`<option value="130101">Alpha Co</option>`, `<option value="130102">Beta &amp; Sons &lt;s.r.o.&gt;</option>`,
			`<dialog id="copy-settings" class="ui-dialog copy-settings-dialog" aria-labelledby="copy-settings-title">`,
			`<h2 id="copy-settings-title">Copy settings from another property</h2>`,
			`<form method="get" action="/apartments/new" class="copy-property-form">`,
			`<option value="130201">Loft &lt;A&gt;</option>`, `<option value="130202">Plain</option>`,
			`<input type="hidden" name="default_purpose" value="10">`,
			`<a class="property-create-manage" href="/entities">`,
			`<script src="/static/ruian_suggest.js?v=20261111-1103b" defer data-turbo-track="reload"></script>`,
			`id="addr_street" name="addr_street"`, `data-ruian-suggest`, `maxlength="48"`, `placeholder="Vinohradsk`,
		}, []string{`Gone Co`, `Other Co`, `Old archived`, `Other host`, `name="copy_from" value=`, `class="panel property-create-copied"`, `id="alternate-controller"`,
			`copy-settings-dialog" aria-labelledby="copy-settings-title" open>`}},
		{"operator chosen", 130001, 0, "en", "?legal_entity_id=130102", 200,
			[]string{`<option value="130102" selected>Beta &amp; Sons &lt;s.r.o.&gt;</option>`}, []string{chooseSelected}},
		{"operator padded and signed", 130001, 0, "vi", "?legal_entity_id=%20%2B130102%20", 200,
			[]string{`<option value="130102" selected>Beta &amp; Sons &lt;s.r.o.&gt;</option>`}, []string{`value="" disabled selected>Choose`}},
		{"operator of another host", 130001, 0, "en", "?legal_entity_id=130104", 200,
			[]string{chooseSelected}, []string{`Other Co`, `130104`}},
		{"archived operator", 130001, 0, "en", "?legal_entity_id=130103", 200, []string{chooseSelected}, []string{`Gone Co`}},
		{"operator not a number", 130001, 0, "en", "?legal_entity_id=abc", 200, []string{chooseSelected}, nil},
		{"copy dialog open", 130001, 0, "cs", "?copy=choose", 200,
			[]string{`<dialog id="copy-settings" class="ui-dialog copy-settings-dialog" aria-labelledby="copy-settings-title" open>`}, nil},
		{"copy with stay fee", 130001, 0, "en", "?copy_from=130201", 200, []string{
			`<option value="130201" selected>Loft &lt;A&gt;</option>`,
			`<p class="panel property-create-copied" role="status">Copied from Loft &lt;A&gt;. Check and save.`,
			`<a href="/apartments/new">Start without copying</a>`,
			`<input type="hidden" name="copy_from" value="130201">`,
			`<input type="hidden" name="automation_mode" value="manual">`,
			`<input type="hidden" name="submit_after_hours" value="12">`,
			`<input type="hidden" name="default_purpose" value="20">`,
			`<input type="hidden" name="permalink_window_days" value="5">`,
			`<input type="hidden" name="permalink_reachback_days" value="30">`,
			`<input type="hidden" name="stay_fee_rate_czk" value="50">`,
			`<input type="hidden" name="stay_fee_cadence" value="quarterly">`,
			`<input type="hidden" name="stay_fee_payee" value="City Hall">`,
			`<option value="130101" selected>Alpha Co</option>`, `<option value="130102" selected>Beta &amp; Sons &lt;s.r.o.&gt;</option>`,
			`<option value="">Same as operator</option>`, `id="alternate-controller"`,
		}, []string{chooseSelected, `name="default_purpose" value="10"`, `name="stay_fee_authority_name"`}},
		{"copy with underscore id", 130001, 0, "cs", "?copy_from=130_201", 200,
			[]string{`<input type="hidden" name="copy_from" value="130201">`}, nil},
		{"copy plain drops blank values", 130001, 0, "en", "?copy_from=130202", 200, []string{
			`<input type="hidden" name="copy_from" value="130202">`, `<input type="hidden" name="automation_mode" value="scheduled">`,
			`<input type="hidden" name="default_purpose" value="10">`, `<option value="130102" selected>Beta`,
		}, []string{`name="stay_fee_payee"`, `name="stay_fee_rate_czk"`, `name="submit_after_hours"`, `name="permalink_window_days"`}},
		{"copy from an archived property", 130001, 0, "en", "?copy_from=130203", 200,
			[]string{`<input type="hidden" name="copy_from" value="130203">`, `Copied from Old archived.`}, nil},
		{"copy with operator override", 130001, 0, "en", "?copy_from=130201&legal_entity_id=130102", 200,
			[]string{`<option value="130102" selected>Beta &amp; Sons &lt;s.r.o.&gt;</option>`}, []string{`<option value="130101" selected>`}},
		{"copy from another host", 130001, 0, "en", "?copy_from=130204", 404, []string{`<h1 class="big">Page not found</h1>`, `href="/"`}, []string{`Other host`}},
		{"copy from a missing id", 130001, 0, "en", "?copy_from=999999", 404, []string{`<h1 class="big">Page not found</h1>`, `href="/"`}, nil},
		{"copy id not a number", 130001, 0, "en", "?copy_from=abc", 200, nil, []string{`name="copy_from" value=`}},
		{"copy id zero", 130001, 0, "en", "?copy_from=0", 200, nil, []string{`name="copy_from" value=`}},
		{"copy id past 64 bits", 130001, 0, "en", "?copy_from=99999999999999999999", 404, []string{"Page not found"}, nil},
		{"admin previews host A", 130003, 130001, "en", "?copy_from=130201", 200,
			[]string{`<input type="hidden" name="copy_from" value="130201">`, `<option value="130101" selected>Alpha Co</option>`}, nil},
		{"admin previews host B", 130003, 130002, "en", "?copy_from=130201", 404, []string{`<h1 class="big">Page not found</h1>`, `href="/"`}, nil},
		{"admin previews host B list", 130003, 130002, "en", "", 200,
			[]string{`<option value="130104" selected>Other Co</option>`, `<option value="130204">Other host</option>`}, []string{`Alpha Co`, `Loft`}},
		{"host B sees only its own", 130002, 0, "en", "", 200,
			[]string{`<option value="130104" selected>Other Co</option>`}, []string{`Alpha Co`, `Loft`, `Plain`}},
	} {
		rec := apartmentNewGet(mux, c.query, c.user, c.workspace, c.lang)
		body := rec.Body.String()
		if rec.Code != c.status {
			t.Errorf("%s: status %d, want %d", c.name, rec.Code, c.status)
			continue
		}
		for _, want := range c.has {
			if !strings.Contains(body, want) {
				t.Errorf("%s: page lacks %q", c.name, want)
			}
		}
		for _, bad := range c.lacks {
			if strings.Contains(body, bad) {
				t.Errorf("%s: page has %q", c.name, bad)
			}
		}
		switch c.status {
		case 303:
			if got := rec.Header().Get("Location"); !strings.HasPrefix(got, "/login") {
				t.Errorf("%s: Location %q", c.name, got)
			}
		case 200:
			// the create form carries its own _csrf input right after the form tag
			i := strings.Index(body, createForm)
			if i < 0 || !strings.Contains(body[i:min(len(body), i+400)], `<input type="hidden" name="_csrf" value="`) {
				t.Errorf("%s: the create form has no _csrf hidden field", c.name)
			}
		}
	}
	for lang, title := range map[string]string{"en": "Add property", "cs": "Přidat ubytování", "vi": "Thêm chỗ ở"} {
		if body := apartmentNewGet(mux, "", 130001, 0, lang).Body.String(); !strings.Contains(body, "<title>"+title+"</title>") {
			t.Errorf("%s: no title %q", lang, title)
		}
	}
}

// TestApartmentNewChoices: loadApartmentNewChoices (also used by 1700b) is
// scoped to the workspace and leaves out archived rows.
func TestApartmentNewChoices(t *testing.T) {
	pool := testPool(t)
	apartmentNewWorld(t, pool)
	names := func(o []ApartmentNewOption) string {
		var out []string
		for _, x := range o {
			out = append(out, x.Name)
		}
		return strings.Join(out, "|")
	}
	for _, c := range []struct {
		workspace            int64
		entities, apartments string
	}{
		{130001, "Alpha Co|Beta & Sons <s.r.o.>", "Loft <A>|Plain"},
		{130002, "Other Co", "Other host"},
		{999999, "", ""},
	} {
		e, a, err := loadApartmentNewChoices(context.Background(), pool, c.workspace)
		if err != nil {
			t.Fatal(err)
		}
		if names(e) != c.entities || names(a) != c.apartments {
			t.Errorf("workspace %d: entities %q, apartments %q", c.workspace, names(e), names(a))
		}
	}
}

// TestApartmentNewRenderRefusal draws the form the way brief 1700b does for a
// refused create: typed values, errors, copy fields and status 400.
func TestApartmentNewRenderRefusal(t *testing.T) {
	pool := testPool(t)
	apartmentNewWorld(t, pool)
	render := func(form ApartmentNewForm) *httptest.ResponseRecorder {
		h := func(w http.ResponseWriter, r *http.Request) {
			host, err := hostweb.Login(w, r, pool, apartmentNewGetenv, testNow)
			if err != nil || host == nil {
				t.Errorf("login: %v", err)
				return
			}
			form.Entities, form.Peers, err = loadApartmentNewChoices(r.Context(), pool, host.Workspace.ID)
			if err != nil {
				t.Error(err)
				return
			}
			if err := RenderApartmentNew(w, r, layout.Env{Pool: pool, Getenv: apartmentNewGetenv, Now: testNow}, host, form); err != nil {
				t.Error(err)
			}
		}
		req := httptest.NewRequest(http.MethodPost, "/apartments", nil)
		apartmentNewSignIn(req, 130001, 0, "en")
		rec := httptest.NewRecorder()
		h(rec, req)
		return rec
	}
	rec := render(ApartmentNewForm{
		Status: http.StatusBadRequest, NameError: true,
		Draft:         map[string]string{"internal_name": "Typed <x>", "city_en": "Praha", "addr_zip": "1200"},
		DraftEntityID: anOpBeta, DraftControllerID: anOpAlpha,
		OperatorError: "flash.error.no_such_controller",
		AddressErrors: map[string]string{"addr_zip": "Enter 5 digits."},
	})
	body := rec.Body.String()
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status %d, want 400", rec.Code)
	}
	for _, want := range []string{
		`value="Typed &lt;x&gt;"`, `aria-invalid="true" autofocus`, `id="internal_name-error"`, `id="city_en" name="city_en" value="Praha"`,
		`id="addr_zip-error" role="alert">Enter 5 digits.</p>`, `aria-describedby="addr_zip-help addr_zip-error"`,
		`<option value="130102" selected>`, `id="controller-message"`, `<option value="130101" selected>`, `name="_csrf"`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("refusal page lacks %q", want)
		}
	}
	if strings.Contains(body, `name="copy_from" value=`) {
		t.Error("a refusal without a copy source carries copy_from")
	}
	rec = render(ApartmentNewForm{
		Status: http.StatusBadRequest, CopyFromID: anLoft, CopiedFromName: "Loft <A>",
		Prefill:       map[string]string{"automation_mode": "", "stay_fee_rate_czk": "0", "stay_fee_payee": "Me"},
		OperatorError: "apartment.form.operator.choose",
	})
	body = rec.Body.String()
	for _, want := range []string{`name="copy_from" value="130201"`, `name="automation_mode" value=""`, `name="stay_fee_payee" value="Me"`,
		`name="default_purpose" value="10"`, `aria-describedby="operator-message" aria-invalid="true"`, `id="operator-message" role="alert">`} {
		if !strings.Contains(body, want) {
			t.Errorf("copy refusal page lacks %q", want)
		}
	}
}

func TestApartmentNewQueryInt(t *testing.T) {
	for _, c := range []struct {
		query string
		n     int64
		ok    bool
	}{
		{"", 0, true}, {"?x=1", 0, true}, {"?k=41", 41, true}, {"?k=%20%2B4_1%20", 41, true}, {"?k=-5", -5, true},
		{"?k=abc", 0, true}, {"?k=1.5", 0, true}, {"?k=1__0", 0, true}, {"?k=%2B", 0, true}, {"?k=1&k=2", 2, true},
		{"?k=%D9%A3", 0, false}, {"?k=99999999999999999999", 0, false},
	} {
		n, ok := apartmentNewQueryInt(httptest.NewRequest(http.MethodGet, "/apartments/new"+c.query, nil), "k")
		if n != c.n || ok != c.ok {
			t.Errorf("%q: got %d %v, want %d %v", c.query, n, ok, c.n, c.ok)
		}
	}
}

// TestApartmentNewTemplateKeys: every key the template or the field table
// reads is in the page catalog in all three languages.
func TestApartmentNewTemplateKeys(t *testing.T) {
	raw, err := os.ReadFile("apartmentnew/apartment_new.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	keys := map[string]bool{}
	for _, m := range regexp.MustCompile(`[({]t "([a-z_.]+)"`).FindAllStringSubmatch(string(raw), -1) {
		keys[m[1]] = true
	}
	v := ApartmentNewForm{}.view("Add property")
	for _, a := range append(append([]apartmentNewAddr{}, v.AddrRow1...), v.AddrRow2...) {
		keys[a.LabelKey] = true
		if a.HintKey != "" {
			keys[a.HintKey] = true
		}
	}
	if len(keys) < 40 {
		t.Fatalf("only %d keys found", len(keys))
	}
	for key := range keys {
		for _, lang := range []string{"en", "cs", "vi"} {
			if _, ok := apartmentNewStrings[lang][key]; !ok {
				t.Errorf("catalog %s lacks %q", lang, key)
			}
		}
	}
}

// TestApartmentNewRegisterDoesNotTouchThePool: building the route needs no
// database, and a POST is not answered by the GET pattern.
func TestApartmentNewRegisterDoesNotTouchThePool(t *testing.T) {
	mux := apartmentNewMux(nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, "/apartments/new", nil))
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("POST /apartments/new: code %d, want 405", rec.Code)
	}
}
