package properties

// Tests of POST /apartments/{id} with setup_step (brief 1702e2). The golden
// script records no wizard case, so every expected value is written by hand
// from admin._save_apartment_form, _wizard_step_payload,
// _wizard_police_format_errors, refuse_setup_save and the wizard templates
// (setup_wizard/property.html, police.html, _layout.html), on the seed of
// testdata/apartment_update_golden.json.

import (
	"context"
	"fmt"
	"net/http"
	"reflect"
	"strings"
	"testing"
)

// apartmentWizardForms are the property and police step forms as the wizard
// pages post them, without return_to (a return_to inside the wizard is 1702e3).
var apartmentWizardForms = map[string]map[string]string{
	"property": {"setup_step": "property", "internal_name": "Loft Karlín", "city_en": "Prague", "legal_entity_id": "21",
		"default_purpose": "10", "checkin_hour": "15", "checkout_hour": "10", "addr_okres": "", "addr_obec": "Praha 8",
		"addr_obec_cast": "", "addr_street": "Sokolovská", "addr_house_no": "10", "addr_orient_no": "", "addr_zip": "18600"},
	"police": {"setup_step": "police", "internal_name": "Loft Karlín", "legal_entity_id": "21", "city_en": "Prague",
		"default_purpose": "10", "step": "police", "letter_fields": "", "uby_idub": "ABC123456789", "uby_mark": "AAKLI",
		"uby_name": "Penzion Karlín", "uby_contact": "me@example.test", "uby_ws_user": "UBY-WS_OLD", "uby_ws_password": ""},
}

func TestApartmentUpdateWizard(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)
	ctx := context.Background()
	_, lastAudit := apartmentUpdateAudit(t, ctx, pool, 0)
	// post sends the step form with extra over it; an extra value "-" drops the field.
	post := func(id int64, step, lang string, extra map[string]string) (int, string, string) {
		t.Helper()
		form := map[string]string{}
		for k, v := range apartmentWizardForms[step] {
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
			if v == "-" {
				delete(form, k)
			}
		}
		rec := apartmentFormPost(t, mux, fmt.Sprintf("/apartments/%d", id), g.CSRFNonce, 2, 0, lang, true, form)
		return rec.Code, rec.Header().Get("Location"), rec.Body.String()
	}
	// refused: 400, the lines of the step page, nothing written, no audit row.
	refused := func(name string, id int64, step, lang string, extra map[string]string, want, lacks []string) {
		t.Helper()
		before := apartmentUpdateRead(t, ctx, pool, g, id)
		code, _, body := post(id, step, lang, extra)
		if code != http.StatusBadRequest {
			t.Errorf("%s: %d, want 400", name, code)
		}
		adCheck(t, name, body, want, lacks)
		if after := apartmentUpdateRead(t, ctx, pool, g, id); !reflect.DeepEqual(after, before) {
			t.Errorf("%s: the property was written", name)
		}
		if rows, last := apartmentUpdateAudit(t, ctx, pool, lastAudit); len(rows) > 0 {
			t.Errorf("%s: audit rows %v", name, rows)
			lastAudit = last
		}
	}

	// 0884: a retired step saves nothing and goes to the done page, before any other check.
	before := apartmentUpdateRead(t, ctx, pool, g, 201)
	for _, step := range []string{"automation", "stay_fee", "door_lock", "try_it"} {
		code, loc, _ := post(201, "property", "en", map[string]string{"setup_step": step, "checkin_hour": "x",
			"stay_fee_guest_form": "1", "return_to": "/apartments/201/setup/" + step})
		if code != http.StatusSeeOther || loc != "/apartments/201/setup/done" {
			t.Errorf("retired %s: %d %q", step, code, loc)
		}
	}
	if after := apartmentUpdateRead(t, ctx, pool, g, 201); !reflect.DeepEqual(after, before) {
		t.Errorf("retired step: the property was written")
	}
	// Another host's property, even with a retired step: no such property.
	for _, step := range []string{"property", "police", "door_lock"} {
		code, loc, _ := post(301, "property", "en", map[string]string{"setup_step": step})
		if code != http.StatusSeeOther || !strings.HasPrefix(loc, "/apartments?err=") {
			t.Errorf("foreign %s: %d %q", step, code, loc)
		}
	}

	// Property step refusals.
	refused("blank hour", 201, "property", "en", map[string]string{"checkout_hour": "", "internal_name": `<b>"Loft"</b>`}, []string{
		`<p class="err-text" role="alert">Choose the check-in and check-out time. UbyHost needs them for door codes and cleaning.</p>`,
		`value="&lt;b&gt;&#34;Loft&#34;&lt;/b&gt;" required`,
	}, []string{`<b>"Loft"`})
	refused("hour 24", 201, "property", "en", map[string]string{"checkin_hour": "24", "checkout_hour": ""}, []string{
		`<p class="err-text" role="alert">Choose the check-in and check-out hour.</p>`,
	}, []string{`UbyHost needs them for door codes`})
	if _, err := pool.Exec(ctx, `UPDATE apartment SET checkout_hour = NULL WHERE id = 204`); err != nil {
		t.Fatal(err)
	}
	refused("door codes need both times", 204, "property", "en", map[string]string{"checkout_hour": "-"}, []string{
		`<p class="err-text" role="alert">Choose the check-in and check-out hour.</p>`,
	}, nil)
	refused("operator refresh", 201, "property", "en", map[string]string{"operator_refresh": "1", "internal_name": "Typed name"}, []string{
		`value="Typed name" required`,
		`<select id="legal_entity_id" name="legal_entity_id" required>`,
	}, []string{`class="err-text" role="alert"`, `-error" role="alert"`, `id="operator-message"`})
	refused("no operator", 201, "property", "en", map[string]string{"legal_entity_id": "", "internal_name": "Typed name"}, []string{
		`value="Typed name" required`,
		`<select id="legal_entity_id" name="legal_entity_id" required aria-describedby="operator-message" aria-invalid="true">`,
		`<p class="err-text" id="operator-message" role="alert">Choose the operator for this property.</p>`,
		`<option value="21" selected>`, // refuse_setup_save: a blank operator keeps the stored one
	}, []string{`class="err-text" role="alert"`})
	refused("another host's controller", 201, "property", "en", map[string]string{"data_controller_entity_id": "31"}, []string{
		`<select id="legal_entity_id" name="legal_entity_id" required>`,
	}, []string{`id="operator-message"`, `role="alert">That data controller`})
	refused("broken address", 201, "property", "en", map[string]string{"addr_zip": "123", "addr_street": " "}, []string{
		`<p class="err-text" id="addr_zip-error" role="alert">Postcode must be exactly 5 digits.</p>`,
		`<p class="err-text" id="addr_street-error" role="alert">Street is required.</p>`,
		`name="addr_zip" autocomplete="off" value="123"`,
	}, []string{`id="addr_obec-error"`})

	// Police step refusals.
	refused("another host's operator", 201, "police", "en", map[string]string{"legal_entity_id": "31", "uby_idub": "TYPED1234567"}, []string{
		`<p class="err-text" role="alert">Choose the operator for this property.</p>`,
		`name="uby_idub" value="TYPED1234567"`,
	}, []string{`-error" role="alert"`})
	refused("police: another host's controller", 201, "police", "en", map[string]string{"data_controller_entity_id": "22"}, []string{
		`<p class="err-text" role="alert">That data controller no longer exists.</p>`,
	}, nil)
	refused("timing hours", 201, "police", "en", map[string]string{"automation_mode": "scheduled", "submit_after_hours": "49"}, []string{
		`<p class="err-text" role="alert">Enter the delay in whole hours, from 1 to 24. Nothing was saved.</p>`,
	}, nil)
	refused("format errors", 201, "police", "cs", map[string]string{"uby_idub": "AB", "uby_mark": "x1", "uby_name": ""}, []string{
		`<p class="err-text" id="uby_idub-error" role="alert">IDUB má 12–14 písmen nebo číslic.</p>`,
		`<p class="err-text" id="uby_mark-error" role="alert">Zkratka má 5 nebo 6 písmen či číslic přidělených policií, např. AAKLI.</p>`,
		`name="uby_mark" value="x1"`,
	}, []string{`id="uby_name-error"`})

	// Police step saved: the abbreviation upper-cased, the password encrypted,
	// the refused-login alert resolved, the automation choice kept; no
	// connection test for a wizard save, and the guest link keeps its slug.
	code, loc, _ := post(201, "police", "en", map[string]string{"uby_mark": "mljno", "uby_ws_user": "UBY-WS_MLJNO",
		"uby_ws_password": " typed-pass ", "automation_mode": "scheduled", "submit_after_hours": "12", "letter_fields": "uby_idub"})
	if code != http.StatusSeeOther || !strings.HasPrefix(loc, "/apartments/201?saved=1&msg=") || strings.Contains(loc, "ubyport") {
		t.Errorf("police saved: %d %q", code, loc)
	}
	after := apartmentUpdateRead(t, ctx, pool, g, 201)
	for col, want := range map[string]string{"uby_mark": "MLJNO", "uby_ws_user": "UBY-WS_MLJNO", "automation_mode": "scheduled",
		"submit_after_hours": "12", "internal_name": "Loft Karlín", "checkin_hour": "15"} {
		if got := after.Row[col]; got == nil || *got != want {
			t.Errorf("police saved: %s = %v, want %q", col, got, want)
		}
	}
	if after.Password == nil || *after.Password != "typed-pass" || len(after.Alerts) != 0 || after.Slug == nil || *after.Slug != "loft-karlin-abc234" {
		t.Errorf("police saved: password %v alerts %v slug %v", after.Password, after.Alerts, after.Slug)
	}
	rows, last := apartmentUpdateAudit(t, ctx, pool, lastAudit)
	if len(rows) != 1 || rows[0]["action"] != "apartment_updated" || rows[0]["detail"] != "id=201" {
		t.Errorf("police saved: audit %v", rows)
	}
	lastAudit = last

	// Property step saved: only the step's columns and the hours; the
	// controller equal to the operator is cleared; the guest link follows the name.
	code, loc, _ = post(201, "property", "en", map[string]string{"internal_name": " Loft Two ", "addr_zip": "186 00",
		"checkin_hour": "14", "checkout_hour": "11", "data_controller_entity_id": "21", "default_purpose": "zz",
		"uby_idub": "NOT-SAVED", "notes": "not saved", "uby_ws_password": "not-saved"})
	if code != http.StatusSeeOther || !strings.HasPrefix(loc, "/apartments/201?saved=1&msg=") {
		t.Errorf("property saved: %d %q", code, loc)
	}
	after = apartmentUpdateRead(t, ctx, pool, g, 201)
	for col, want := range map[string]string{"internal_name": "Loft Two", "addr_zip": "18600", "city_en": "Prague",
		"checkin_hour": "14", "checkout_hour": "11", "default_purpose": "10", "uby_idub": "ABC123456789", "uby_mark": "MLJNO", "legal_entity_id": "21"} {
		if got := after.Row[col]; got == nil || *got != want {
			t.Errorf("property saved: %s = %v, want %q", col, got, want)
		}
	}
	if after.Row["data_controller_entity_id"] != nil || after.Password == nil || *after.Password != "typed-pass" ||
		after.Slug == nil || !strings.HasPrefix(*after.Slug, "loft-two-") {
		t.Errorf("property saved: controller %v password %v slug %v", after.Row["data_controller_entity_id"], after.Password, after.Slug)
	}
	if rows, _ := apartmentUpdateAudit(t, ctx, pool, lastAudit); len(rows) != 1 || rows[0]["action"] != "apartment_updated" {
		t.Errorf("property saved: audit %v", rows)
	}
}
