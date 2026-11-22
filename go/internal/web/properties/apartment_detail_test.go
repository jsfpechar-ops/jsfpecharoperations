package properties

// Tests of GET /apartments/{id} (brief 1701). Every expected value is written
// by hand from the Python page (apartment_form.html, _property_editor.html and
// the partials it includes); there is no golden file and no Python script.

import (
	"context"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

// Host A is 130001, host B 130002, admin 130003 (seedHosts).
const (
	adOpAlpha, adOpBeta, adOpGone, adOpOther = 130101, 130102, 130103, 130104
	adLoft, adPlain, adOld, adForeign        = 130201, 130202, 130203, 130204
)

func adEnv(extra map[string]string) func(string) string {
	return func(k string) string {
		if v, ok := extra[k]; ok {
			return v
		}
		if k == "UBYHOST_PUBLIC_BASE_URL" {
			return "https://ubyhost.example"
		}
		return apartmentNewGetenv(k)
	}
}

func adMux(pool *pgxpool.Pool, extra map[string]string) *http.ServeMux {
	mux := http.NewServeMux()
	RegisterApartmentDetail(mux, noWrap, pool, adEnv(extra), testClock)
	return mux
}

func adGet(mux http.Handler, path string, user, workspace int64, lang string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, path, nil)
	apartmentNewSignIn(req, user, workspace, lang)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// adWorld seeds host A with two operators (one with a contact e-mail), a
// complete loft with two calendars, a bare property, an archived one, and host
// B with a property of its own.
func adWorld(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	seedHosts(t, pool)
	mustExec(t, pool, `INSERT INTO legal_entity (id, owner_user_id, name, seat, ico, contact_email, archived_at, created_at) VALUES
		($1, 130001, 'Alpha Co', 'Praha', '12345678', 'a@example.test', NULL, $5),
		($2, 130001, 'Beta & Sons <s.r.o.>', 'Brno', NULL, NULL, NULL, $5),
		($3, 130001, 'Gone Co', 'Brno', NULL, NULL, '2026-01-02', $5),
		($4, 130002, 'Other Co', 'Brno', NULL, NULL, NULL, $5)`, adOpAlpha, adOpBeta, adOpGone, adOpOther, stamp0)
	keys, err := secure.LoadDataKeys(adEnv(nil))
	if err != nil {
		t.Fatal(err)
	}
	password, err := keys.EncryptString("secret-pw")
	if err != nil {
		t.Fatal(err)
	}
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, legal_entity_id, permalink_token, permalink_pin, city_en,
		addr_street, addr_house_no, addr_zip, addr_obec, addr_obec_cast, addr_okres, uby_idub, uby_mark, uby_name, uby_contact, uby_ws_user,
		uby_ws_password_enc, automation_mode, submit_after_hours, default_purpose, guest_message, notes, passport_photo_policy, ocr_scan,
		permalink_window_days, permalink_reachback_days, stay_fee_rate_czk, checkin_hour, checkout_hour, created_at) VALUES
		($1, 130001, 'Loft <A>', $5, 'tok-loft', '123456', 'Praha', 'Vinohradská', '12', '12000', 'Praha', 'Vinohrady', 'Praha',
		 '123456789012', 'AAKLI', 'BYT VINOHRADSKA 12', 'a@x.test', 'UBY-WS_AAKLI', $6, 'immediate', 3, '27', 'Welcome <b>', 'Note & more',
		 'required_foreign', 1, 4, 0, 50, 14, 10, $8),
		($2, 130001, 'Plain', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
		 NULL, 'scheduled', 24, '10', NULL, NULL, 'off', 0, 2, 365, 0, NULL, NULL, $8),
		($3, 130001, 'Old archived', $5, 'tok-old', '654321', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
		 NULL, 'scheduled', 24, '10', NULL, NULL, 'off', 0, 2, 365, 0, NULL, NULL, $8),
		($4, 130002, 'Other host', $7, 'tok-other', '111111', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
		 NULL, 'scheduled', 24, '10', NULL, NULL, 'off', 0, 2, 365, 0, NULL, NULL, $8)`,
		adLoft, adPlain, adOld, adForeign, adOpAlpha, password, adOpOther, stamp0)
	mustExec(t, pool, `UPDATE apartment SET archived_at = '2026-01-03T10:00:00+00:00', active = 0 WHERE id = $1`, adOld)
	mustExec(t, pool, `INSERT INTO ical_feed (id, apartment_id, url, label, own_name, last_sync_at, last_status, last_error, active, created_at, last_checked_at) VALUES
		(1, $1, 'https://www.airbnb.com/calendar/ical/1.ics', 'Airbnb', 'Loft on Airbnb', '2026-11-12T08:00:00+00:00', 'ok', NULL, 1, $2, '2026-11-13T08:30:00+00:00'),
		(2, $1, 'https://example.test/booking-feed.ics', 'Booking.com', '', NULL, 'error', 'Feed <gone>', 1, $2, NULL),
		(3, $1, 'https://example.test/odd.ics', '', '', NULL, NULL, NULL, 0, $2, NULL)`, adLoft, stamp0)
	mustExec(t, pool, `INSERT INTO ical_feed (id, apartment_id, url, label, own_name, active, created_at) VALUES (4, $1, 'https://example.test/foreign.ics', 'Airbnb', 'Foreign feed', 1, $2)`, adForeign, stamp0)
}

// adPageBody is the page body without the shell around it (the shell forms
// get their token from csrf.js in Python and from the layout here).
func adPageBody(body string) string {
	start := strings.Index(body, `<div class="airbnb-header">`)
	end := strings.Index(body, `data-unsaved-reset>`)
	if start < 0 || end < start {
		return ""
	}
	return body[start:end]
}

// adPostFormsHaveCSRF reports every <form method="post"> block without a _csrf
// input. The sync button is the layout macro sync_calendars_button: Python's
// macro has no input either, and csrf.js adds the token in the browser.
func adPostFormsHaveCSRF(body string) []string {
	var bad []string
	for _, m := range regexp.MustCompile(`(?s)<form[^>]*method="post"[^>]*>.*?</form>`).FindAllString(body, -1) {
		if !strings.Contains(m, `name="_csrf"`) && !strings.Contains(m, `action="/sync"`) {
			bad = append(bad, m[:min(len(m), 90)])
		}
	}
	return bad
}

func adCheck(t *testing.T, name, body string, has, lacks []string) {
	t.Helper()
	for _, h := range has {
		if !strings.Contains(body, h) {
			t.Errorf("%s: missing %q", name, h)
		}
	}
	for _, l := range lacks {
		if strings.Contains(body, l) {
			t.Errorf("%s: unexpected %q", name, l)
		}
	}
}

// TestApartmentDetailAccess: the login redirect, the owner scope (a property of
// another host, an archived one, an admin previewing) and the answers that fall
// back to Python.
func TestApartmentDetailAccess(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := adMux(pool, nil)
	for _, c := range []struct {
		name            string
		path            string
		user, workspace int64
		status          int
		fallback        bool
		has, lacks      []string
	}{
		{"signed out", "/apartments/130201", 0, 0, 303, false, nil, nil},
		{"own property", "/apartments/130201", 130001, 0, 200, false, []string{`<h1 class="airbnb-title">Loft &lt;A&gt;</h1>`}, nil},
		{"another host's property", "/apartments/130204", 130001, 0, 404, false, []string{`Not found.`}, nil},
		{"host B asks for A", "/apartments/130201", 130002, 0, 404, false, []string{`Not found.`}, nil},
		{"unknown id", "/apartments/999999", 130001, 0, 404, false, []string{`Not found.`}, nil},
		{"id not a number", "/apartments/abc", 130001, 0, 404, false, []string{"Page not found"}, nil},
		{"id past int64", "/apartments/99999999999999999999", 130001, 0, 404, false, []string{"Page not found"}, nil},
		{"id with sign and underscore", "/apartments/+130_201", 130001, 0, 200, false, []string{`Loft &lt;A&gt;`}, nil},
		{"archived property", "/apartments/130203", 130001, 0, 200, false, []string{`Old archived`}, nil},
		{"admin acting in host A", "/apartments/130201", 130003, 130001, 200, false, []string{`Loft &lt;A&gt;`}, []string{`Other host`}},
		{"admin acting in host B asks for A", "/apartments/130201", 130003, 130002, 404, false, []string{`Not found.`}, nil},
		{"copy_from of another host", "/apartments/130201?copy_from=130204", 130001, 0, 404, false, []string{`Not found.`}, nil},
		{"copy_from unknown", "/apartments/130201?copy_from=999", 130001, 0, 404, false, []string{`Not found.`}, nil},
		{"copy_from not ASCII", "/apartments/130201?copy_from=%D9%A1", 130001, 0, 404, false, []string{"Page not found"}, nil},
	} {
		rec := adGet(mux, c.path, c.user, c.workspace, "en")
		if rec.Code != c.status {
			t.Errorf("%s: status %d, want %d", c.name, rec.Code, c.status)
			continue
		}
		if got := rec.Header().Get("X-Ubyhost-Not-Ported") == "1"; got != c.fallback {
			t.Errorf("%s: fallback header %v, want %v", c.name, got, c.fallback)
		}
		if c.status == 303 && rec.Header().Get("Location") == "" {
			t.Errorf("%s: no Location", c.name)
		}
		adCheck(t, c.name, rec.Body.String(), c.has, c.lacks)
	}
}

// TestApartmentDetailPage: the whole page of the complete loft in English, as
// hand-written fragments of the Python page.
func TestApartmentDetailPage(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	body := adGet(adMux(pool, nil), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "loft", body, []string{
		`<title>Loft &lt;A&gt;`,
		`<a class="airbnb-back" href="/apartments" aria-label="Back">`,
		`<h1 class="airbnb-title">Loft &lt;A&gt;</h1><span class="page-help-wrap">`,
		`<div class="sub prop-phone-sub">Vinohradská 12, Praha</div>`,
		// the strip: calendars, guest link, police, business, fee, lock
		`data-strip="calendars" data-state="bad"><i class="sd" aria-hidden="true"></i><b>Calendars</b><small class="is-problem">`,
		`<div class="sc sc-link" data-strip="guest" data-state="off">`,
		`<small class="sc-pin" data-guest-pin>PIN 123456</small>`,
		`https://ubyhost.example/l/loft-a-`,
		`data-strip="police" data-state="ok"><i class="sd" aria-hidden="true"></i><b>Foreigner police</b><small>`,
		`data-strip="business" data-state="ok"><i class="sd" aria-hidden="true"></i><b>Business details</b><small>Alpha Co</small>`,
		`data-strip="fee" data-state="ok"><i class="sd" aria-hidden="true"></i><b>Stay fee</b><small>50 Kč</small>`,
		`data-strip="door" data-state="off"><i class="sd" aria-hidden="true"></i><b>Smart lock</b><small>Off</small>`,
		// the settings form
		`<form method="post" action="/apartments/130201" enctype="multipart/form-data" class="property-settings-form" id="property-settings-form" data-property-settings-form data-unsaved-guard>`,
		`<input type="hidden" name="return_to" value="/apartments/130201?view=settings&amp;section=property" data-property-return>`,
		`<details class="prop-sec" id="sec-basics"><summary>`,
		`<input type="text" id="internal_name" name="internal_name" value="Loft &lt;A&gt;" required`,
		`<option value="130101" selected>Alpha Co</option>`, `<option value="130102">Beta &amp; Sons &lt;s.r.o.&gt;</option>`,
		`<a href="/entities?edit=130101">Business &amp; legal details </a>`,
		`<option value="">Same as operator</option>`,
		`<option value="14" selected>14:00</option>`, `<option value="10" selected>10:00</option>`,
		`id="addr_street" name="addr_street" autocomplete="off" value="Vinohradská" maxlength="48"`, `data-ruian-suggest`,
		`id="addr_zip" name="addr_zip" autocomplete="off" value="12000" maxlength="6" inputmode="numeric"`,
		`id="addr_obec_cast" name="addr_obec_cast" autocomplete="off" value="Vinohrady"`, `id="addr_okres" name="addr_okres" autocomplete="off" value="Praha"`,
		`<textarea id="notes" name="notes" aria-describedby="notes-help">Note &amp; more</textarea>`,
		`formaction="/apartments/130201/archive"`, `data-confirm-message="This item will move to Archived.">`,
		// guest link
		`<input type="text" id="permalink_pin" name="permalink_pin" value="123456" class="mono"`,
		`formaction="/apartments/130201/regenerate-pin"`, `formaction="/apartments/130201/regenerate-link"`,
		`placeholder="For example: Welcome! Please complete this form before arrival.">Welcome &lt;b&gt;</textarea>`,
		`name="permalink_window_days" min="1" max="30" aria-describedby="permalink_window_days-help"
                 value="4"`,
		`name="permalink_reachback_days" min="1" max="3650" aria-describedby="permalink_reachback_days-help"
                 value="365"`,
		`<option value="required_foreign" selected>`, `id="ocr_scan" name="ocr_scan" value="1" checked`,
		// reporting
		`<details class="prop-sec" id="sec-police"`,
		`id="uby_idub" name="uby_idub" value="123456789012" maxlength="14" aria-required="true"`,
		`id="uby_ws_user" name="uby_ws_user" value="UBY-WS_AAKLI"`, `placeholder="••••••••" aria-describedby="uby_ws_password-help uby_ws_password-hint"`,
		`id="uby_mark" name="uby_mark" value="AAKLI" maxlength="6"`, `id="uby_name" name="uby_name" value="BYT VINOHRADSKA 12" maxlength="35"`,
		`id="uby_contact" name="uby_contact" value="a@x.test" maxlength="50"`,
		`formaction="/apartments/130201/test-connection"`,
		`<option value="immediate" data-hint=`, `<option value="27" selected>Employment</option>`,
		`id="submit_after_hours" name="submit_after_hours"
                 min="0" max="48" value="3"`,
		`<form id="police-letter-form" method="post" action="/apartments/130201/police-letter"`,
		// calendars
		`<details class="prop-sec" id="sec-fee"`,
		`<details class="prop-sec" id="sec-calendars"`,
		`<td data-label="Name"><strong>Loft on Airbnb</strong></td>`, `<strong>Booking.com</strong>`, `<strong>`,
		`<span class="ui-badge ui-badge-done" data-tone="green">`, `<span class="ui-badge ui-badge-action" data-tone="red">`,
		`<div class="ui-sub">2026-11-13 09:30</div>`, `<div class="small err-text">Feed &lt;gone&gt;</div>`,
		`title="https://www.airbnb.com/calendar/ical/1.ics"`,
		`<form method="post" action="/feeds/1/delete" class="inline"`,
		`<form method="post" action="/apartments/130201/feeds" class="panel calendar-add-form" id="calendar-add">`,
		`<option value="other">`,
		`<div class="calendar-connect is-collapsed" id="calendar-connect"`,
		`<div class="savebar save-on-dirty" data-for="property-settings-form">`,
	}, []string{`Gone Co`, `Other Co`, `Other host`, `Foreign feed`, `foreign.ics`, `class="ready-card"`, `data-leon-card`})
	if bad := adPostFormsHaveCSRF(adPageBody(body)); len(bad) > 0 {
		t.Errorf("post forms without _csrf: %q", bad)
	}
	if strings.Count(adPageBody(body), `name="_csrf"`) < 4 {
		t.Errorf("_csrf inputs: %d", strings.Count(adPageBody(body), `name="_csrf"`))
	}
	// the page strings come from the catalog, never as bare keys
	if leak := regexp.MustCompile(`>(?:apartment|property_page|property_nav|setup|wizard|health|automation|police_letter|why|nav|leon_page|door_code|workflow|calendar)\.[a-z_.0-9]+<`).FindString(body); leak != "" {
		t.Errorf("untranslated key in the page: %s", leak)
	}
}

// TestApartmentDetailBare: a property with nothing filled in shows the missing
// lists, the empty calendar state, the backfilled PIN and no operator.
func TestApartmentDetailBare(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	body := adGet(adMux(pool, nil), "/apartments/130202", 130001, 0, "en").Body.String()
	var pin string
	if err := pool.QueryRow(context.Background(), `SELECT permalink_pin FROM apartment WHERE id = 130202`).Scan(&pin); err != nil || len(pin) != 6 {
		t.Fatalf("the PIN was not made: %q %v", pin, err)
	}
	adCheck(t, "bare", body, []string{
		`value="` + pin + `" class="mono"`,
		`<option value="" disabled selected>Choose operator</option>`,
		`data-strip="business" data-state="warn"><i class="sd" aria-hidden="true"></i><b>Business details</b><small class="is-problem">`,
		`<small class="is-problem">Operator missing</small>`,
		`data-strip="police" data-state="warn"`,
		`<div class="panel empty">`,
		`<div class="calendar-connect" id="calendar-connect"`,
		`<div class="prop-sec-missing" data-missing="basics" role="note">`,
		`<div class="prop-sec-missing" data-missing="calendars" role="note">`,
		`<a href="#basics" data-fix-label=`,
		`class="dot r"`,
		`<form method="post" action="/apartments/130202/feeds"`,
		`<input class="sr-only" type="text" id="overview-guest-url" readonly value="https://ubyhost.example/l/" tabindex="-1" aria-hidden="true">`,
	}, []string{`<div class="sub prop-phone-sub">`, `<select id="legal_entity_id" name="legal_entity_id" required aria-describedby`, `href="/apartments/130202?view=bookings&amp;add_calendar=1#calendar-connect"`})
	if bad := adPostFormsHaveCSRF(adPageBody(body)); len(bad) > 0 {
		t.Errorf("post forms without _csrf: %q", bad)
	}
}

// TestApartmentDetailArchived: an archived property shows its restore form
// and not the archive button.
func TestApartmentDetailArchived(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	body := adGet(adMux(pool, nil), "/apartments/130203", 130001, 0, "en").Body.String()
	adCheck(t, "archived", body, []string{`formaction="/apartments/130203/unarchive"`, `>Restore</button>`, `<p class="prop-archive-note"><strong>Archived 03.01.2026</strong>`},
		[]string{`/archive"`})
}

// TestApartmentDetailQuery: ?view, ?section, ?sec, ?err, ?msg, ?saved, ?return_to,
// ?add_calendar and ?created change what is open and shown.
func TestApartmentDetailQuery(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := adMux(pool, nil)
	for _, c := range []struct {
		name, query string
		has, lacks  []string
	}{
		{"bookings view opens calendars", "?view=bookings", []string{`<details class="prop-sec" id="sec-calendars" open>`}, nil},
		{"section reporting", "?section=reporting", []string{`<input type="hidden" name="return_to" value="/apartments/130201?view=settings&amp;section=reporting" data-property-return>`,
			`<div class="prop-layout" data-start-section="sec-fee">`}, nil},
		{"section opens its sections", "?section=guests", []string{`<details class="prop-sec" id="sec-messages" open>`}, []string{`id="sec-basics" open`}},
		{"unknown section is ignored", "?section=nope&view=nope", []string{`section=property" data-property-return`}, nil},
		{"error beside its section", "?sec=basics&err=Boom%20%3Cx%3E", []string{`<details class="prop-sec" id="sec-basics" open>`,
			`<div class="banner err section-notice" role="alert" tabindex="-1" data-section-notice><span class="grow">Boom &lt;x&gt;</span></div>`}, nil},
		{"message beside its section", "?sec=messages&msg=Done", []string{`<div class="banner ok section-notice" role="status" tabindex="-1" data-section-notice><span class="grow">Done</span></div>`}, nil},
		{"sec must be letters", "?sec=a1&msg=Done", nil, []string{`data-section-notice`}},
		{"saved banner", "?saved=1&msg=Saved%20it", []string{`<div class="banner ok section-notice save-summary" role="status" tabindex="-1" data-save-summary><span class="grow">Saved it</span></div>`}, nil},
		{"message without saved", "?msg=Saved%20it", nil, []string{`save-summary`}},
		{"fee return", "?return_to=/stay-fees/130201%3Fmonth%3D2026-10", []string{`<input type="hidden" name="fee_return_to" value="/stay-fees/130201?month=2026-10">`}, nil},
		{"fee return of another property", "?return_to=/stay-fees/130202", nil, []string{`fee_return_to`}},
		{"fee list return", "?return_to=/stay-fees", []string{`name="fee_return_to" value="/stay-fees"`}, nil},
		{"add calendar", "?view=bookings&add_calendar=1", []string{`<div class="calendar-connect" id="calendar-connect"`}, nil},
		{"created", "?created=1", []string{`<div class="calendar-connect" id="calendar-connect"`}, []string{`#add-stay-panel`}},
	} {
		rec := adGet(mux, "/apartments/130201"+c.query, 130001, 0, "en")
		if rec.Code != 200 {
			t.Errorf("%s: status %d", c.name, rec.Code)
			continue
		}
		adCheck(t, c.name, rec.Body.String(), c.has, c.lacks)
	}
}

// TestApartmentDetailLanguages: Czech and Vietnamese pages translate the
// section titles and the strip; a number in the Czech plural form follows.
func TestApartmentDetailLanguages(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := adMux(pool, nil)
	for _, c := range []struct {
		lang string
		has  []string
	}{
		{"cs", []string{`<b>Kalendáře</b>`, `<b>Cizinecká policie</b>`}},
		{"vi", []string{`<b>Lịch</b>`}},
	} {
		body := adGet(mux, "/apartments/130201", 130001, 0, c.lang).Body.String()
		adCheck(t, c.lang, body, c.has, []string{`<b>Calendars</b>`})
	}
}

// TestApartmentDetailSetup: a property in its first setup shows the continue
// card and opens the first section that is not done; a finished or hidden
// guide changes the card and the copy dialog.
func TestApartmentDetailSetup(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	ctx := context.Background()
	settings := onboarding.PoolSettings(pool)
	mux := adMux(pool, nil)
	if err := onboarding.Start(ctx, settings, adPlain); err != nil {
		t.Fatal(err)
	}
	body := adGet(mux, "/apartments/130202", 130001, 0, "en").Body.String()
	adCheck(t, "first setup", body, []string{
		`<section class="pv setup-continue-card" aria-label="Property setup">`, `<a class="ui-btn ui-btn-primary" href="/apartments/130202/setup/property">Continue</a>`,
		`<form method="post" action="/apartments/130202/setup" class="inline">`, `name="action" value="hide"`,
		`<details class="prop-sec" id="sec-basics" open>`, `<div class="prop-layout" data-start-section="sec-basics">`,
		`<a class="ui-btn ui-btn-secondary ui-btn-compact copy-settings-open" href="/apartments/130202?view=settings&amp;section=property&amp;copy=choose" data-sheet-open="copy-settings">`,
		`<form method="get" action="/apartments/130202" class="copy-property-form">`,
		`<option value="130201">Loft &lt;A&gt;</option>`,
	}, []string{`id="sec-archive"`, `id="sec-police" open`, `Old archived`, `Other host`})
	// a hidden guide
	if err := onboarding.SetHidden(ctx, settings, adPlain, true); err != nil {
		t.Fatal(err)
	}
	body = adGet(mux, "/apartments/130202", 130001, 0, "en").Body.String()
	adCheck(t, "hidden", body, []string{`<form method="post" action="/apartments/130202/setup" class="property-setup-show">`, `name="action" value="show"`},
		[]string{`setup-continue-card`})
	// a finished guide: no copy dialog, the archive row is back
	if err := onboarding.Finish(ctx, settings, adPlain); err != nil {
		t.Fatal(err)
	}
	body = adGet(mux, "/apartments/130202", 130001, 0, "en").Body.String()
	adCheck(t, "finished", body, []string{`id="sec-archive"`}, []string{`copy-settings-open`, `setup-continue-card`, `property-setup-show`})
}

// TestApartmentDetailReadyCard: the loft completes its setup (reporting tested),
// so the page finishes the guide and shows the ready card once.
func TestApartmentDetailReadyCard(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	ctx := context.Background()
	settings := onboarding.PoolSettings(pool)
	mux := adMux(pool, nil)
	if err := onboarding.Start(ctx, settings, adLoft); err != nil {
		t.Fatal(err)
	}
	if err := onboarding.MarkTested(ctx, settings, adLoft); err != nil {
		t.Fatal(err)
	}
	body := adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "ready", body, []string{`<section class="ui-section-card ready-card" id="setup-ready"`, `<img class="ready-card-qr" src="data:image/png;base64,`,
		`<code class="ready-card-link">https://ubyhost.example/l/loft-a-`, `<b class="ready-card-pin">123456</b>`},
		[]string{`setup-continue-card`})
	state, err := onboarding.Load(ctx, settings, adLoft)
	if err != nil || state == nil || !state.Finished || !state.Celebrated {
		t.Fatalf("state after the page: %+v %v", state, err)
	}
	body = adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "second view", body, nil, []string{`ready-card`})
}

// TestApartmentDetailCopy: copy_from fills the empty fields of a property in its
// first setup and shows the notice; the stored row is not changed.
func TestApartmentDetailCopy(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	ctx := context.Background()
	mustExec(t, pool, `UPDATE apartment SET data_controller_entity_id = $1, stay_fee_rate_czk = 40, stay_fee_authority_name = 'City Hall' WHERE id = $2`, adOpBeta, adLoft)
	mustExec(t, pool, `UPDATE apartment SET permalink_window_days = 0 WHERE id = $1`, adPlain)
	if err := onboarding.Start(ctx, onboarding.PoolSettings(pool), adPlain); err != nil {
		t.Fatal(err)
	}
	body := adGet(adMux(pool, nil), "/apartments/130202?copy_from=130201&copy=choose", 130001, 0, "en").Body.String()
	adCheck(t, "copy", body, []string{
		`<div class="copy-settings-bar">`, `Copied from Loft &lt;A&gt;`,
		`<option value="130101" selected>Alpha Co</option>`,                       // the operator
		`<option value="130102" selected>Beta &amp; Sons &lt;s.r.o.&gt;</option>`, // the controller
		`<option value="130201" selected>Loft &lt;A&gt;</option>`,                 // the dialog
		`<dialog id="copy-settings" class="ui-dialog copy-settings-dialog" aria-labelledby="copy-settings-title" open>`,
		`id="permalink_window_days" name="permalink_window_days" min="1" max="30" aria-describedby="permalink_window_days-help"
                 value="4"`, // an empty window is filled from the loft
		`data-strip="fee" data-state="ok"><i class="sd" aria-hidden="true"></i><b>Stay fee</b><small>40 Kč</small>`,
		`<option value="10" selected>Tourism</option>`, // a purpose that is set stays
		`<option value="scheduled" data-hint=`,
	}, []string{`<option value="27" selected>`})
	var legal *int64
	if err := pool.QueryRow(ctx, `SELECT legal_entity_id FROM apartment WHERE id = $1`, adPlain).Scan(&legal); err != nil || legal != nil {
		t.Errorf("the stored operator changed: %v %v", legal, err)
	}
}

// TestApartmentDetailHealth: a calendar alert, a rejected police login and an
// incomplete controller turn the strip pills.
func TestApartmentDetailHealth(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mustExec(t, pool, `UPDATE ical_feed SET last_status = 'ok', last_error = NULL WHERE id = 2`)
	mustExec(t, pool, `UPDATE apartment SET data_controller_entity_id = $1 WHERE id = $2`, adOpBeta, adLoft) // no e-mail, no IČO, no seat? it has a seat but no e-mail
	mustExec(t, pool, `INSERT INTO alert (id, level, kind, apartment_id, owner_user_id, message, created_at) VALUES
		(901, 'critical', 'ubyport_auth_failed', 130201, 130001, 'm', $1), (902, 'warning', 'feed_error', 130201, 130001, 'm', $1)`, stamp0)
	body := adGet(adMux(pool, nil), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "alerts", body, []string{`data-strip="calendars" data-state="bad"`, `data-strip="police" data-state="bad"`,
		`data-strip="business" data-state="warn"><i class="sd" aria-hidden="true"></i><b>Business details</b><small class="is-problem">Business details are missing.</small>`}, nil)
	// a resolved alert does not count
	mustExec(t, pool, `UPDATE alert SET resolved_at = $1`, stamp0)
	mustExec(t, pool, `UPDATE apartment SET data_controller_entity_id = NULL WHERE id = $1`, adLoft)
	body = adGet(adMux(pool, nil), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "resolved", body, []string{`data-strip="calendars" data-state="ok"`, `data-strip="police" data-state="ok"`, `data-strip="business" data-state="ok"`}, nil)
}

func TestDetailHelpers(t *testing.T) {
	// police_check._fold
	for in, want := range map[string]string{"BYT Č. [2] FIKTIVNÍ 1234/56": "byt c 2 fiktivni 1234 56", "  Vinohradská  ": "vinohradska", "Straße": "strasse"} {
		if got := policeFold(in); got != want {
			t.Errorf("policeFold(%q) = %q, want %q", in, got, want)
		}
	}
	// _door_code_hours_overlap
	h := func(v int64) *int64 { return &v }
	for _, c := range []struct {
		in, out *int64
		want    bool
	}{{nil, h(10), false}, {h(14), h(10), false}, {h(10), h(10), true}, {h(11), h(10), true}, {h(2), h(23), false}, {h(0), h(23), true}} {
		if got := detailHoursOverlap(c.in, c.out, 1); got != c.want {
			t.Errorf("overlap(%v,%v) = %v", c.in, c.out, got)
		}
	}
	// _lock_tz_wrong
	for in, want := range map[any]bool{nil: false, 3600000.0: false, 7200000.0: false, 0.0: true, "7200000": false, "x": false, true: false} {
		if got := detailLockTZWrong(in); got != want {
			t.Errorf("tzWrong(%v) = %v", in, got)
		}
	}
	// _property_copy_value_empty: a value fills only an empty field
	dst := &detailApt{AutomationMode: "scheduled", PermalinkWindowDays: 0, StayFeeAuthorityName: "  "}
	detailApplyCopy(dst, &detailApt{AutomationMode: "manual", PermalinkWindowDays: 5, StayFeeAuthorityName: "City", LegalEntityID: 7})
	if dst.AutomationMode != "scheduled" || dst.PermalinkWindowDays != 5 || dst.StayFeeAuthorityName != "City" || dst.LegalEntityID != 7 {
		t.Errorf("applyCopy: %+v", dst)
	}
	// _readiness: the reporting list is the validation errors of the eight fields
	r := detailReadinessOf(&detailApt{InternalName: " "}, nil, validation.ValidateApartment(map[string]string{}), false, false, true)
	if r.InviteReady || r.reportComplete() || len(r.Report) != 8 || r.Report[0].Key != "idub" || r.Report[0].Message == "" || r.Invite[0].Done {
		t.Errorf("readiness: %+v", r)
	}
}

// adLockWorld connects host A's lock account (one lock, Prague offset) and
// puts the loft on it.
func adLockWorld(t *testing.T, pool *pgxpool.Pool) map[string]string {
	t.Helper()
	mustExec(t, pool, `INSERT INTO lock_account (id, owner_user_id, provider, username, status, locks_json, locks_fetched_at, created_at, updated_at)
		VALUES (1, 130001, 'ttlock', 'uh-test', 'ok', '[{"lock_id": "7001", "alias": "Front door", "tz_offset_ms": 3600000, "battery": 85}, {"lock_id": "7002", "alias": "Cellar <x>", "tz_offset_ms": 0, "battery": null}]', $1, $1, $1)`, stamp0)
	mustExec(t, pool, `UPDATE apartment SET lock_provider = 'ttlock', lock_id = '7001' WHERE id = $1`, adLoft)
	mustExec(t, pool, `UPDATE apartment SET lock_provider = 'ttlock', lock_id = '7002' WHERE id = $1`, adPlain)
	return map[string]string{"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": "id", "UBYHOST_TTLOCK_CLIENT_SECRET": "secret"}
}

// TestApartmentDetailDoor: the door-code state of the strip and the window of
// the arrival and departure times.
func TestApartmentDetailDoor(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	env := adLockWorld(t, pool)
	mux := adMux(pool, env)
	body := adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "on", body, []string{`data-strip="door" data-state="ok">`, `<small>Enabled</small>`,
		`<div data-door-code-window data-buffer="1"`, `data-checkin="14" data-checkout="10"`,
		`<dd data-window-start>13:00 · arrival day</dd>`, `<dd data-window-end>11:00 · departure day</dd>`,
		`<dl class="ui-facts" data-window-values>`, `<p data-window-missing hidden>`,
		// the Door lock section
		`<details class="prop-sec" id="sec-lock"`, `<div class="lock-state" id="lock-connected-off" data-state="on" role="status">`, `<b>Automatic door codes: On</b>`, `<small>Lock online</small>`,
		`<form method="post" action="/apartments/130201/door-codes" class="lock-state-form">`, `<input type="hidden" name="mode" value="off">`, `>Turn off</button>`,
		`<input type="hidden" name="return_to" value="/apartments/130201?view=settings&amp;section=lock#sec-lock">`,
		`<section class="panel property-section ui-section" id="door-code">`, `<select form="property-settings-form" id="lock_checkin_hour" name="lock_checkin_hour" data-hour-twin="checkin_hour" required>`,
		`<option value="14" selected>14:00</option>`,
		`<option value="7001" selected>Front door (ID 7001)</option>`,
		`<option value="7002" disabled>Cellar &lt;x&gt; (ID 7002) · in use by Plain</option>`,
		`<input form="property-settings-form" type="hidden" name="door_code_section" value="1">`,
		// the lock list
		`<section class="panel property-section ui-section" id="smart-locks">`, `<details class="ui-section" id="smart-locks-add-more">`, `<code id="ttlock-receiver-more">uh-test</code>`,
		`<section class="ui-section" id="smart-locks-list">`, `<p><strong>Front door</strong> · ID 7001`, `· battery 85 %</p>`, `<p><strong>Cellar &lt;x&gt;</strong> · ID 7002`,
		`<p class="ui-sub">Plain</p>`, `<p class="ui-sub">Loft &lt;A&gt;</p>`, `<p class="ui-sub"><strong>Time zone is not Prague. Fix it in the TTLock app.</strong></p>`,
		`<form method="post" action="/smart-locks/refresh" class="inline"><input type="hidden" name="_csrf"`, `<form method="post" action="/smart-locks/remove" class="inline"`,
	}, []string{`id="lock-unavailable"`, `data-test-mode`})
	if bad := adPostFormsHaveCSRF(adPageBody(body)); len(bad) > 0 {
		t.Errorf("post forms without _csrf: %q", bad)
	}
	// a lock that the account no longer lists is offline; missing hours are "times"
	mustExec(t, pool, `UPDATE lock_account SET status = 'reauth'`)
	body = adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "offline", body, []string{`data-strip="door" data-state="bad">`, `<div class="prop-sec-missing" data-missing="lock" role="note"><p>Lock offline.`,
		`<small>TTLock no longer accepts this connection.`, `data-state="offline" role="status">`}, nil)
	mustExec(t, pool, `UPDATE apartment SET checkout_hour = NULL WHERE id = $1`, adLoft)
	body = adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "times", body, []string{`data-strip="door" data-state="bad">`, `<dl class="ui-facts" data-window-values hidden>`, `<p data-window-missing>`, `data-checkout=""`}, nil)
	// near midnight the window wraps to the previous and the next day
	mustExec(t, pool, `UPDATE apartment SET checkin_hour = 0, checkout_hour = 23 WHERE id = $1`, adLoft)
	body = adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "wrap", body, []string{`<dd data-window-start>23:00 · day before arrival</dd>`, `<dd data-window-end>00:00 · day after departure</dd>`}, nil)
	// door codes off, or not in the owner's plan: no door state, no window
	for name, extra := range map[string]map[string]string{"switched off": nil, "billing without the add-on": {"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": "id",
		"UBYHOST_TTLOCK_CLIENT_SECRET": "s", "UBYHOST_BILLING_ENABLED": "1"}} {
		if name != "switched off" {
			mustExec(t, pool, `INSERT INTO billing_account (owner_user_id, status, plan, addon_ttlock, updated_at) VALUES (130001, 'active', 'standard', 0, $1)`, stamp0)
		}
		body = adGet(adMux(pool, extra), "/apartments/130201", 130001, 0, "en").Body.String()
		adCheck(t, name, body, []string{`data-strip="door" data-state="off">`, `<div class="lock-state" id="lock-unavailable" data-state="off" role="status">`,
			`<small>Door codes are not enabled on this deployment.</small>`}, []string{`data-door-code-window`, `door_code_section`, `id="smart-locks"`})
	}
}

// TestApartmentDetailLeon: the Leon card follows the feature switch, the plan
// and the state of the property.
func TestApartmentDetailLeon(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	on := map[string]string{"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k"}
	body := adGet(adMux(pool, nil), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "off by the switch", body, nil, []string{`data-leon-card`})
	body = adGet(adMux(pool, on), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "off", body, []string{`<a class="r" href="/apartments/130201/leon/setup" data-leon-card="off">`}, nil)
	mustExec(t, pool, `UPDATE apartment SET leon_enabled = 1, leon_terms_version = 'old' WHERE id = $1`, adLoft)
	body = adGet(adMux(pool, on), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "terms", body, []string{`data-leon-card="terms"`}, nil)
	test := map[string]string{"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k", "UBYHOST_AI_TEST_EMAILS": "someone@example.test"}
	body = adGet(adMux(pool, test), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "not on the test list", body, nil, []string{`data-leon-card`})
}

// TestApartmentDetailPoliceFindings: the warnings under the police boxes.
func TestApartmentDetailPoliceFindings(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := adMux(pool, nil)
	mustExec(t, pool, `UPDATE apartment SET uby_ws_user = 'portal-login', uby_mark = 'LOGIN', uby_name = 'FLAT WITHOUT ADDRESS' WHERE id = $1`, adLoft)
	body := adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "findings", body, []string{
		`<p class="police-letter-note" role="note" data-police-check-code="login_prefix">The login does not start with UBY-WS.`,
		`<p class="police-letter-note" role="note" data-police-check-code="name_address">The facility name has no street and house number.`,
		`<p class="police-letter-note" data-police-check data-police-check-code="first_filing" role="note">No report accepted yet.`,
	}, []string{`mark_is_login_suffix`})
	// the mark that only repeats the end of the login is flagged while nothing was accepted
	mustExec(t, pool, `UPDATE apartment SET uby_ws_user = 'UBY-WS_ZZTOP', uby_mark = 'zztop', uby_name = 'BYT VINOHRADSKA 12' WHERE id = $1`, adLoft)
	body = adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "mark", body, []string{`data-police-check-code="mark_is_login_suffix">The short name is the end of the login (ZZTOP).`}, []string{`login_prefix`, `name_address`})
	// once a report was accepted, only the facts about the saved values remain
	mustExec(t, pool, `INSERT INTO submission (id, apartment_id, created_at, state) VALUES (1, $1, $2, 'ok_duplicate')`, adLoft, stamp0)
	body = adGet(mux, "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "accepted", body, nil, []string{`data-police-check-code`})
}
