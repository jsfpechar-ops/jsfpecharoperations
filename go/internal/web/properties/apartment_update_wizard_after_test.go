package properties

// Tests of a wizard save that goes back into the wizard (_setup_after_save,
// brief 1702e3). The golden script records no wizard case, so every expected
// value is written by hand from admin._setup_after_save (2655-2737),
// property_setup (mark, current, wizard_unresolved, step_status, finish),
// admin_helpers.back and setup_wizard/_layout.html, on the seed of
// testdata/apartment_update_golden.json: property 201 is complete except the
// police password, has no feed, no stay and no stored guide.

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"reflect"
	"testing"
)

func TestApartmentUpdateWizardAfter(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)
	ctx := context.Background()
	// post sends the step form with extra over it; an extra value "-" drops the field.
	post := func(id int64, step string, extra map[string]string) (int, string, string) {
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
		rec := apartmentFormPost(t, mux, fmt.Sprintf("/apartments/%d", id), g.CSRFNonce, 2, 0, "en", true, form)
		return rec.Code, rec.Header().Get("Location"), rec.Body.String()
	}
	// guide is the stored property_setup:<id> setting.
	type guideState struct {
		Steps    map[string]string `json:"steps"`
		Finished bool              `json:"finished"`
		Hidden   bool              `json:"hidden"`
		Legacy   bool              `json:"legacy"`
	}
	guide := func(id int64) guideState {
		t.Helper()
		var raw string
		if err := pool.QueryRow(ctx, `SELECT COALESCE((SELECT value FROM settings WHERE key = $1), '')`, fmt.Sprintf("property_setup:%d", id)).Scan(&raw); err != nil {
			t.Fatalf("guide %d: %v", id, err)
		}
		var s guideState
		if raw == "" {
			return s // nothing stored
		}
		if err := json.Unmarshal([]byte(raw), &s); err != nil {
			t.Fatalf("guide %d: %q", id, raw)
		}
		return s
	}
	check := func(name string, got, want guideState) {
		t.Helper()
		if !reflect.DeepEqual(got, want) {
			t.Errorf("%s: guide %+v, want %+v", name, got, want)
		}
	}
	const (
		savedPassword = "msg=Saved.%20Still%20missing%20for%20police%20reporting%3A%20Password.&toast_kind=warning&toast_sticky=1"
		savedReady    = "msg=Saved.%20This%20property%20is%20ready%20to%20report.&toast_kind=success"
	)

	// Property saved and complete: the step is marked done (a legacy guide,
	// none was stored) and the host goes to return_to with the saved message.
	code, loc, _ := post(201, "property", map[string]string{"return_to": "/apartments/201/setup/calendar", "internal_name": "Loft Wizard"})
	if code != http.StatusSeeOther || loc != "/apartments/201/setup/calendar?"+savedPassword {
		t.Errorf("property saved: %d %q", code, loc)
	}
	if after := apartmentUpdateRead(t, ctx, pool, g, 201); after.Row["internal_name"] == nil || *after.Row["internal_name"] != "Loft Wizard" {
		t.Errorf("property saved: not written")
	}
	check("property saved", guide(201), guideState{Steps: map[string]string{"property": "done"}, Legacy: true})

	// Police saved without a password: the save is written, the step stays
	// open, and the police page is drawn again (200) with the notice naming
	// what is missing.
	code, _, body := post(201, "police", map[string]string{"return_to": "/apartments/201/setup/police", "uby_name": "Penzion <Nový>"})
	if code != http.StatusOK {
		t.Errorf("police incomplete: %d, want 200", code)
	}
	adCheck(t, "police incomplete", body, []string{
		`<p class="err-text" role="alert">Saved. Still missing for police reporting: Password.</p>`,
		`name="uby_name" value="Penzion &lt;Nový&gt;"`,
	}, []string{`Penzion <Nový>`})
	if after := apartmentUpdateRead(t, ctx, pool, g, 201); after.Row["uby_name"] == nil || *after.Row["uby_name"] != "Penzion <Nový>" {
		t.Errorf("police incomplete: not written")
	}
	check("police incomplete", guide(201), guideState{Steps: map[string]string{"property": "done"}, Legacy: true})

	// A return to /done while a step is open: the current guide step, no message.
	code, loc, _ = post(201, "property", map[string]string{"return_to": "/apartments/201/setup/done"})
	if code != http.StatusSeeOther || loc != "/apartments/201/setup/calendar" {
		t.Errorf("done, unresolved: %d %q", code, loc)
	}

	// Police complete with the automation choice: automation and police are
	// marked done, back to return_to with "ready to report".
	code, loc, _ = post(201, "police", map[string]string{"return_to": "/apartments/201/setup/police", "uby_ws_password": "typed-pass",
		"automation_mode": "immediate", "submit_after_hours": "2"})
	if code != http.StatusSeeOther || loc != "/apartments/201/setup/police?"+savedReady {
		t.Errorf("police complete: %d %q", code, loc)
	}
	check("police complete", guide(201), guideState{Steps: map[string]string{"property": "done", "police": "done", "automation": "done"}, Legacy: true})

	// A return to /done/ (trailing slash) with every step answered: the guide
	// is finished and the host lands on the finish page with "Setup complete."
	if _, err := pool.Exec(ctx, `UPDATE settings SET value = $1 WHERE key = 'property_setup:201'`,
		`{"celebrated": false, "finished": false, "hidden": false, "legacy": true, "steps": {"automation": "done", "calendar": "skipped", "guest_link": "done", "police": "done", "property": "done"}, "tested": false}`); err != nil {
		t.Fatal(err)
	}
	code, loc, _ = post(201, "property", map[string]string{"return_to": "/apartments/201/setup/done/"})
	if code != http.StatusSeeOther || loc != "/apartments/201/setup/done?msg=Setup%20complete.&toast_kind=success" {
		t.Errorf("done, resolved: %d %q", code, loc)
	}
	finished := guideState{Steps: map[string]string{"automation": "done", "calendar": "skipped", "guest_link": "done", "police": "done", "property": "done"},
		Finished: true, Legacy: true}
	check("done, resolved", guide(201), finished)

	// A finished guide: plain back to return_to with the saved message, even
	// for a step that is not resolved any more; the guide is unchanged.
	code, loc, _ = post(201, "police", map[string]string{"return_to": "/apartments/201/setup/police", "uby_idub": ""})
	want := "/apartments/201/setup/police?msg=Saved.%20Still%20missing%20for%20police%20reporting%3A%20Police%20accommodation%20number%20%28IDUB%29.&toast_kind=warning&toast_sticky=1"
	if code != http.StatusSeeOther || loc != want {
		t.Errorf("finished: %d %q", code, loc)
	}
	check("finished", guide(201), finished)

	// Every police field ready but the property step open (no name): the
	// notice names the step. Property 203 gets its password through a police
	// save that goes back to the settings page (no wizard return_to).
	code, loc, _ = post(203, "police", map[string]string{"internal_name": "-", "legal_entity_id": "-", "uby_ws_password": "typed-pass"})
	if code != http.StatusSeeOther || loc != "/apartments/203?saved=1&"+savedReady {
		t.Errorf("203 police: %d %q", code, loc)
	}
	code, _, body = post(203, "property", map[string]string{"return_to": "/apartments/203/setup/calendar", "internal_name": ""})
	if code != http.StatusOK {
		t.Errorf("property incomplete: %d, want 200", code)
	}
	adCheck(t, "property incomplete", body, []string{
		`<p class="err-text" role="alert">Saved. Still missing for police reporting: Property details.</p>`,
	}, nil)
	check("property incomplete", guide(203), guideState{})
}
