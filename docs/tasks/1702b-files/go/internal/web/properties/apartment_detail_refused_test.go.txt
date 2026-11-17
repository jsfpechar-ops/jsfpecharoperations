package properties

// Tests of the error lines of a refused property save (brief 1702b): the view
// fields that _refuse_apartment_save and refuse_fee_save hand to
// _property_editor.html, _property_operator.html, _property_address_fields.html
// and _stay_fee_fields.html. Every expected line is written by hand from those
// Python templates; the POST that fills the fields is brief 1702c.

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

// adRefused draws the property page of host A's property id with view, as the
// refused POST will.
func adRefused(t *testing.T, s *Pages, id int64, path, lang string, view *detailView) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	apartmentNewSignIn(req, 130001, 0, lang)
	rec := httptest.NewRecorder()
	host, err := hostweb.Login(rec, req, s.pool, s.getenv, testNow)
	if err != nil || host == nil {
		t.Fatalf("login: %v %v", host, err)
	}
	a, err := s.detailLoad(req.Context(), host.Workspace.ID, id)
	if err != nil || a == nil {
		t.Fatalf("load: %v %v", a, err)
	}
	view.Base = path[:len("/apartments/130201")]
	s.detailRender(rec, req, host, a, view, onboarding.PoolSettings(s.pool), testNow)
	return rec
}

func TestApartmentDetailRefusedBasics(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	s := &Pages{pool: pool, getenv: adEnv(nil), now: testClock}
	view := &detailView{Status: http.StatusBadRequest,
		SaveErrors:    []detailSaveError{{"basics", "addr_zip"}, {"basics", "legal_entity_id"}, {"basics", "checkin_hour"}},
		AddressErrors: map[string]string{"addr_zip": "Zip <bad>."}, OperatorError: "apartment.form.operator.required",
		SharedTimeError: "flash.error.door_code_hours"}
	rec := adRefused(t, s, adLoft, "/apartments/130201?view=settings&section=property", "en", view)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status %d", rec.Code)
	}
	body := rec.Body.String()
	adCheck(t, "basics", body, []string{
		`data-property-settings-form data-unsaved-guard data-dirty-start="1">`,
		`<details class="prop-sec" id="sec-basics" open>`,
		`<select id="legal_entity_id" name="legal_entity_id" required aria-describedby="operator-message" aria-invalid="true">`,
		`<p class="err-text" id="operator-message" role="alert">Choose the operator for this property.</p>`,
		`<select id="data_controller_entity_id" name="data_controller_entity_id">`,
		`<p class="err-text" role="alert" data-field-error>Choose the check-in and check-out hour.</p>`,
		`aria-describedby="addr_zip-help addr_zip-error" aria-invalid="true">`,
		`<p class="err-text" id="addr_zip-error" role="alert">Zip &lt;bad&gt;.</p>`,
		`<div class="banner err section-notice save-summary" role="alert" tabindex="-1" data-save-summary data-first-error="addr_zip"><span class="grow">Not saved: fix 3 fields. Nothing was changed.</span> <a href="#addr_zip">Go to the first one</a></div>`,
	}, []string{`id="controller-message"`, `addr_street-error`, `stay-fee-account-error`, `data-save-summary data-first-error="legal`})
	// One error in Czech: the .one form.
	view = &detailView{Status: http.StatusBadRequest, SaveErrors: []detailSaveError{{"basics", "data_controller_entity_id"}},
		OperatorError: "flash.error.no_such_controller"}
	body = adRefused(t, s, adLoft, "/apartments/130201?view=settings&section=property", "cs", view).Body.String()
	adCheck(t, "controller cs", body, []string{
		`data-unsaved-guard data-dirty-start="1">`,
		`<select id="legal_entity_id" name="legal_entity_id" required>`,
		`<select id="data_controller_entity_id" name="data_controller_entity_id" aria-describedby="controller-message" aria-invalid="true">`,
		`<p class="err-text" id="controller-message" role="alert" data-field-error>Tento správce údajů už neexistuje.</p>`,
		`data-first-error="data_controller_entity_id"><span class="grow">Neuloženo: opravte 1 pole. Nic se nezměnilo.</span> <a href="#data_controller_entity_id">Přejít na první</a></div>`,
	}, []string{`id="operator-message" role="alert"`, `data-field-error>Vyberte hodinu`})
	// A plain GET of the same page shows none of it.
	body = adGet(adMux(pool, nil), "/apartments/130201?view=settings&section=property", 130001, 0, "en").Body.String()
	adCheck(t, "get", body, []string{`data-property-settings-form data-unsaved-guard>`,
		`<select id="legal_entity_id" name="legal_entity_id" required>`},
		[]string{`data-save-summary data-first-error`, `aria-invalid="true"`, `data-field-error`, `data-dirty-start`})
}

func TestApartmentDetailRefusedFeeAndLock(t *testing.T) {
	pool := testPool(t)
	adFeeWorld(t, pool)
	env := adLockWorld(t, pool)
	env[adGuestPayOn] = "on"
	s := &Pages{pool: pool, getenv: adEnv(env), now: testClock}
	view := &detailView{Status: http.StatusBadRequest,
		SaveErrors:   []detailSaveError{{"fee", "stay_fee_guest_operator_account"}, {"fee", "stay_fee_guest_revolut_link"}, {"fee", "stay_fee_collect"}},
		FeeLinkError: true, FeeRateError: true, FeeOperatorAccountError: true}
	body := adRefused(t, s, adLoft, "/apartments/130201?view=settings&section=reporting", "en", view).Body.String()
	adCheck(t, "fee", body, []string{
		`<details class="prop-sec" id="sec-fee" open>`,
		`id="stay-fee-rate-warning" role="alert" data-rate-warning data-field-error>`,
		`<p class="err-text small" id="stay-fee-guest-operator-error" role="alert" data-field-error>Enter your business bank account for guest QR code and bank transfer.</p>`,
		`aria-describedby="stay_fee_guest_operator_account-help stay-fee-guest-preview-status stay-fee-guest-operator-error"
                     value="19-2000145399/0800" aria-invalid="true">`,
		`aria-describedby="stay_fee_guest_revolut_link-help stay-fee-link-error"`,
		`value="https://revolut.me/loft" aria-invalid="true">
              <p class="err-text small" id="stay-fee-link-error" role="alert" data-field-error>Use an https link on revolut.me or revolut.com.</p>`,
		`data-first-error="stay_fee_guest_operator_account"><span class="grow">Not saved: fix 3 fields. Nothing was changed.</span>`,
	}, []string{`stay-fee-account-error`, `data-rate-warning hidden>`, `<details class="prop-sec" id="sec-basics" open>`})
	view = &detailView{Status: http.StatusBadRequest, SaveErrors: []detailSaveError{{"fee", "stay_fee_council_account"}}, FeeAccountError: true}
	body = adRefused(t, s, adLoft, "/apartments/130201?view=settings&section=reporting", "en", view).Body.String()
	adCheck(t, "fee account", body, []string{
		`aria-describedby="stay_fee_council_account-help stay-fee-account-error"
           value="19-2000145399/0800" aria-invalid="true">
    <p class="err-text small" id="stay-fee-account-error" role="alert" data-field-error>This account number does not add up.`,
		`data-first-error="stay_fee_council_account"><span class="grow">Not saved: fix 1 field. Nothing was changed.</span>`,
	}, []string{`stay-fee-link-error`, `stay-fee-guest-operator-error`})
	view = &detailView{Status: http.StatusBadRequest, SaveErrors: []detailSaveError{{"lock", "lock_checkin_hour"}}, LockTimesError: true}
	body = adRefused(t, s, adLoft, "/apartments/130201?view=settings&section=lock", "en", view).Body.String()
	adCheck(t, "lock", body, []string{
		`<details class="prop-sec" id="sec-lock" open>`,
		`<p class="err-text" id="door-code-times-error" role="alert" data-field-error>Check-in and check-out times are missing, so door codes cannot work yet. Set them first.</p>`,
		`id="lock_checkin_hour" name="lock_checkin_hour" data-hour-twin="checkin_hour" required aria-invalid="true" aria-describedby="door-code-times-error">`,
		`id="lock_checkout_hour" name="lock_checkout_hour" data-hour-twin="checkout_hour" required aria-invalid="true" aria-describedby="door-code-times-error">`,
		`data-first-error="lock_checkin_hour">`,
	}, []string{`id="lock-times-required"`})
}
