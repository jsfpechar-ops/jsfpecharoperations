package properties

// Brief 2031: redirect-only wizard step saves on POST /apartments/{id}.

import (
	"context"
	"fmt"
	"net/http"
	"reflect"
	"strings"
	"testing"
)

func TestApartmentUpdateWizardSteps(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)
	ctx := context.Background()
	base := g.Cases[3].Form

	post := func(extra map[string]string) (int, string, string) {
		t.Helper()
		form := map[string]string{}
		for k, v := range base {
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
		}
		rec := apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, form)
		return rec.Code, rec.Header().Get("Location"), rec.Body.String()
	}

	// calendar unresolved (no feed): 200 notice, same flash as Python incomplete police.
	before := apartmentUpdateRead(t, ctx, pool, g, 201)
	code, _, body := post(map[string]string{"setup_step": "calendar", "return_to": "/apartments/201/setup/guest_link"})
	if code != http.StatusOK {
		t.Errorf("calendar unresolved: %d, want 200", code)
	}
	if !strings.Contains(body, "Calendar") || !strings.Contains(body, `role="alert"`) {
		t.Errorf("calendar unresolved: missing notice")
	}
	if after := apartmentUpdateRead(t, ctx, pool, g, 201); !reflect.DeepEqual(after, before) {
		t.Errorf("calendar unresolved: row changed")
	}

	// guest_link unresolved: 200, teaching step label in notice.
	code, _, body = post(map[string]string{"setup_step": "guest_link", "return_to": "/apartments/201/setup/guest_link"})
	if code != http.StatusOK {
		t.Errorf("guest_link unresolved: %d, want 200", code)
	}
	if !strings.Contains(body, "Guest link") {
		t.Errorf("guest_link unresolved: missing step label")
	}

	// wizard return_to without setup_step: settings save + after-save back (not interim err).
	code, loc, _ := post(map[string]string{"return_to": "/apartments/201/setup/police", "internal_name": "Loft Return"})
	if code != http.StatusSeeOther || !strings.Contains(loc, "/apartments/201/setup/police") {
		t.Errorf("wizard return_to: %d %q", code, loc)
	}
	if strings.Contains(loc, "err=") {
		t.Errorf("wizard return_to: interim err flash")
	}

	// retired stay_fee still not-ported (re-render port pending).
	before = apartmentUpdateRead(t, ctx, pool, g, 201)
	code, loc, _ = post(map[string]string{"setup_step": "stay_fee", "stay_fee_rate_czk": "50"})
	if code != http.StatusSeeOther || !strings.Contains(loc, "err=") {
		t.Errorf("stay_fee interim: %d %q", code, loc)
	}
	if after := apartmentUpdateRead(t, ctx, pool, g, 201); !reflect.DeepEqual(after, before) {
		t.Errorf("stay_fee interim: written")
	}

	// calendar_sync is not a step: ignored, normal save (no err flash).
	code, loc, _ = post(map[string]string{"setup_step": "calendar_sync", "internal_name": "Loft Sync"})
	if code != http.StatusSeeOther || strings.Contains(loc, "err=") {
		t.Errorf("calendar_sync: %d %q", code, loc)
	}
}

func TestWizardStepPayloadTable(t *testing.T) {
	t.Parallel()
	cases := []struct {
		step string
		want []string
	}{
		{"calendar", nil},
		{"guest_link", nil},
		{"door_lock", nil},
		{"automation", []string{"automation_mode", "submit_after_hours"}},
	}
	for _, c := range cases {
		c := c
		t.Run(c.step, func(t *testing.T) {
			t.Parallel()
			r := mustParseForm(t, map[string]string{
				"automation_mode": "scheduled", "submit_after_hours": "12",
			})
			cols, _ := wizardStepPayload(r, c.step, apartmentPayload{})
			var names []string
			for _, col := range cols {
				names = append(names, col.name)
			}
			if !reflect.DeepEqual(names, c.want) {
				t.Errorf("got %v want %v", names, c.want)
			}
		})
	}
}

func mustParseForm(t *testing.T, vals map[string]string) *http.Request {
	t.Helper()
	r, err := http.NewRequest(http.MethodPost, "/", strings.NewReader(formEncode(vals)))
	if err != nil {
		t.Fatal(err)
	}
	r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if err := r.ParseForm(); err != nil {
		t.Fatal(err)
	}
	r.PostForm = r.Form
	return r
}

func formEncode(vals map[string]string) string {
	var b strings.Builder
	first := true
	for k, v := range vals {
		if !first {
			b.WriteByte('&')
		}
		first = false
		b.WriteString(fmt.Sprintf("%s=%s", k, v))
	}
	return b.String()
}
