package cleaning

import (
	"strings"
	"testing"
)

func TestHostCleaningMobilePropertyPicker(t *testing.T) {
	e := newHostEnv(t)

	// Host 1 has multiple active properties -> mobile picker shown, calendar wrapped in cal-tablet-up.
	rec := e.get(i64(1), "/cleaning", "")
	if rec.Code != 200 {
		t.Fatalf("status %d: %.300s", rec.Code, rec.Body.String())
	}
	body := rec.Body.String()
	mustContain(t, "picker", body,
		`<div class="cal-mobile-only">`,
		`<div class="cal-prop-index" data-cleaning-picker>`,
		`href="/cleaning?cal_property=`,
		`<svg class="mini-cal-svg"`,
		`<div class="cal-tablet-up">`,
		`/static/comfy.css`,
		`/static/comfy-responsive.css`,
	)
	mustLack(t, "picker no back", body, `cal-prop-back-link`, `cal-single-mode`)

	// Picking one property -> back-to-all link on mobile + cal-single-mode, no picker.
	rec = e.get(i64(1), "/cleaning", "cal_property=11")
	if rec.Code != 200 {
		t.Fatalf("single property status %d: %.300s", rec.Code, rec.Body.String())
	}
	body = rec.Body.String()
	mustContain(t, "single property", body,
		`<div class="cal-prop-back cal-mobile-only">`,
		`<a class="cal-prop-back-link" href="/cleaning">`,
		`class="dashboard-calendar cal-single-mode"`,
	)
	mustLack(t, "single property no picker", body, `data-cleaning-picker`, `<div class="cal-tablet-up">`)

	// Single-property host (owner 2) -> skips picker and back link, renders calendar directly in single-mode.
	rec = e.get(i64(2), "/cleaning", "")
	if rec.Code != 200 {
		t.Fatalf("owner 2 status %d: %.300s", rec.Code, rec.Body.String())
	}
	body = rec.Body.String()
	if !strings.Contains(body, `class="dashboard-calendar cal-single-mode"`) {
		t.Errorf("single-property host should render cal-single-mode calendar")
	}
	mustLack(t, "single-property host no picker", body, `data-cleaning-picker`, `cal-prop-back-link`)
}
