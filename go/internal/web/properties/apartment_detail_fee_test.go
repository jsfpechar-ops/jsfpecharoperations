package properties

// Tests of the Stay fee section of GET /apartments/{id} (brief 1701b). Every
// expected value is written by hand from _property_editor.html,
// _stay_fee_fields.html and _fee_signature_fields.html; there is no golden file
// and no Python script. The world is adWorld (apartment_detail_test.go).

import (
	"regexp"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const adGuestPayOn = "UBYHOST_STAY_FEE_GUEST_PAY"

// adFeeWorld gives the loft a complete stay fee, an operator with an account and
// a signature, and the plain property a fee of its own (the loft's copy peer).
// The foreign property and the archived one have a fee too: neither may show.
func adFeeWorld(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	adWorld(t, pool)
	keys, err := secure.LoadDataKeys(adEnv(nil))
	if err != nil {
		t.Fatal(err)
	}
	sig, err := keys.EncryptString("data:image/png;base64,AAAA")
	if err != nil {
		t.Fatal(err)
	}
	mustExec(t, pool, `UPDATE legal_entity SET bank_account = '19-2000145399/0800', signature_name = 'J. Novak', signature_png_enc = $2 WHERE id = $1`, adOpAlpha, sig)
	mustExec(t, pool, `UPDATE apartment SET stay_fee_cadence = 'quarterly', stay_fee_vs = '5566', stay_fee_council_account = '19-2000145399/0800',
		stay_fee_authority_name = 'Office <Praha 2>', stay_fee_authority_address = 'Namesti Miru 1', stay_fee_collect = 1,
		stay_fee_guest_rails = 'qr,revolut', stay_fee_guest_default_rail = 'qr', stay_fee_guest_revolut_link = 'https://revolut.me/loft',
		stay_fee_guest_cash_note = 'Cash <box>' WHERE id = $1`, adLoft)
	mustExec(t, pool, `UPDATE apartment SET stay_fee_rate_czk = 30, stay_fee_cadence = 'monthly', stay_fee_vs = '77', stay_fee_council_account = '123/0300',
		stay_fee_authority_name = 'Brno office', stay_fee_authority_address = 'Street 2', stay_fee_authority_contact = 'brno@example.test',
		stay_fee_payee = 'Payee & Co', stay_fee_instruction = 'Pay by 15th' WHERE id = $1`, adPlain)
	mustExec(t, pool, `UPDATE apartment SET stay_fee_rate_czk = 20 WHERE id IN ($1, $2)`, adForeign, adOld)
}

// adBlock is the part of body from the first marker to the next closing marker.
func adBlock(t *testing.T, body, from, to string) string {
	t.Helper()
	i := strings.Index(body, from)
	if i < 0 {
		t.Fatalf("no %q in the page", from)
	}
	j := strings.Index(body[i:], to)
	if j < 0 {
		t.Fatalf("no %q after %q", to, from)
	}
	return body[i : i+j]
}

// TestApartmentDetailFee: the section of a property with a fee, guest pay on.
func TestApartmentDetailFee(t *testing.T) {
	pool := testPool(t)
	adFeeWorld(t, pool)
	body := adGet(adMux(pool, map[string]string{adGuestPayOn: "on"}), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "loft fee", body, []string{
		`<details class="prop-sec" id="sec-fee"><summary><span class="dot g" aria-hidden="true"></span><div><b>Stay fee</b></div><small class="sec-state">50 Kč</small></summary>`,
		`<section class="panel property-section ui-section" id="stay-fee-settings">`,
		`<h3 class="property-subsection-title">1. Calculation</h3>`,
		`<h3 class="property-subsection-title">2. Pay the council</h3>`,
		`<h3 class="property-subsection-title">3. Council and delivery</h3>`,
		`<h3 class="property-subsection-title">4. Collect from guests</h3>`,
		`<input type="hidden" name="_stay_fee_account_existing" value="19-2000145399/0800">`,
		`<input type="number" id="stay_fee_rate_czk" name="stay_fee_rate_czk" aria-describedby="stay_fee_rate_czk-help" min="0" max="50" step="1"
             value="50">`,
		`<option value="monthly" >Monthly</option>`, `<option value="quarterly" selected>Quarterly</option>`,
		`<input type="date" id="stay_fee_rate_from" name="stay_fee_rate_from" aria-describedby="stay_fee_rate_from-help" min="2026-11-13" value="2026-11-13">`,
		`id="stay_fee_vs" name="stay_fee_vs" aria-describedby="stay_fee_vs-help" inputmode="numeric" maxlength="10" aria-required="true" value="5566">`,
		`id="stay_fee_council_account" name="stay_fee_council_account" autocomplete="off" spellcheck="false" maxlength="42" aria-required="true"`,
		`value="19-2000145399/0800">`,
		`id="stay_fee_authority_name" name="stay_fee_authority_name" aria-describedby="stay_fee_authority_name-help" maxlength="200" aria-required="true" value="Office &lt;Praha 2&gt;">`,
		`<details class="fee-more ui-details-box" open>`,
		`id="stay_fee_authority_address" name="stay_fee_authority_address" aria-describedby="stay_fee_authority_address-help" maxlength="200" value="Namesti Miru 1">`,
		`id="stay_fee_authority_contact" name="stay_fee_authority_contact" aria-describedby="stay_fee_authority_contact-help" maxlength="200" value="">`,
		`<span class="req-star" aria-hidden="true">*</span>`,
		// the guest pay block
		`<div class="fee-setup-section" id="stay-fee-guest-pay">`,
		`<input type="hidden" name="stay_fee_guest_form" value="1">`,
		`id="stay_fee_collect" name="stay_fee_collect" value="1" checked aria-describedby="stay_fee_collect-help">`,
		`data-rate-warning hidden>`,
		`<input type="checkbox" name="stay_fee_guest_rails" value="iban" checked> <span>Bank transfer (IBAN)</span>`,
		`<input type="checkbox" name="stay_fee_guest_rails" value="revolut" checked> <span>Revolut</span>`,
		`<input type="checkbox" name="stay_fee_guest_rails" value="cash"> <span>Cash</span>`,
		`data-guest-pay-operator data-preview-url="/stay-fees/130201/guest-pay-preview">`,
		`id="stay_fee_guest_operator_account" name="stay_fee_guest_operator_account" autocomplete="off" spellcheck="false" maxlength="42"
                     aria-describedby="stay_fee_guest_operator_account-help stay-fee-guest-preview-status"
                     value="19-2000145399/0800">`,
		`<div class="gp-preview" id="stay-fee-guest-preview" data-preview-box>`,
		`<img src="data:image/png;base64,`, `width="176" height="176"`,
		`<p class="gp-account-number" data-preview-account>CZ65 0800 0000 1920 0014 5399</p>`,
		`value="https://revolut.me/loft"`, `rows="2">Cash &lt;box&gt;</textarea>`,
		`<option value="iban" data-rail="iban" selected>Bank transfer (IBAN)</option>`,
		`<option value="revolut" data-rail="revolut">Revolut</option>`,
		`<option value="cash" data-rail="cash" disabled hidden>Cash</option>`,
		// the signature
		`<input type="hidden" name="fee_signature_section" value="1">`,
		`<fieldset class="signature-block" data-host-signature>`,
		`<img class="signature-locked-img" data-signature-preview alt="Saved signature" src="data:image/png;base64,AAAA">`,
		`data-signature-open hidden>Edit signature</button>`,
		`<input type="hidden" id="fee_signature" name="signature_drawn" value="data:image/png;base64,AAAA">`,
		`id="fee_signature_name" name="signature_name" maxlength="80" autocomplete="name" autocapitalize="words" value="J. Novak" data-signature-typed>`,
		`name="signature_remove" value="1">`,
		`<script src="/static/stay-fee-guest-pay.js?v=20261105-gp4" defer data-turbo-track="reload"></script>`,
		// complete fee: no warning; the overview link
		`<a href="/stay-fees/130201">Open this property&#39;s stay fee </a>`,
	}, []string{`Add the variable symbol, the council account and the office name`, `fee-return-note`})
	// the copy dropdown: this workspace's other properties with a fee, nothing else
	peers := adBlock(t, body, `id="fee-copy-source"`, `</select>`)
	adCheck(t, "peers", peers, []string{`<option value="130202"`, `data-rate="30"`, `data-cadence="monthly"`, `data-vs="77"`,
		`data-account="123/0300"`, `data-authority-name="Brno office"`, `data-authority-address="Street 2"`,
		`data-authority-contact="brno@example.test"`, `data-payee="Payee &amp; Co"`, `data-instruction="Pay by 15th"`, `>Plain</option>`},
		[]string{`Other host`, `Old archived`, `Loft`, `130204`, `130203`})
	if n := strings.Count(peers, `<option `); n != 1 {
		t.Errorf("peers: %d options, want 1", n)
	}
	// every post form (the settings form holds the fee fields) carries _csrf
	if bad := adPostFormsHaveCSRF(adPageBody(body)); len(bad) > 0 {
		t.Errorf("post forms without _csrf: %q", bad)
	}
	// the fee fields sit inside the settings form, before its closing tag
	form := adBlock(t, body, `id="property-settings-form"`, `</form>`)
	for _, id := range []string{`id="sec-fee"`, `id="stay_fee_rate_czk"`, `name="signature_drawn"`} {
		if !strings.Contains(form, id) {
			t.Errorf("%s is not inside the settings form", id)
		}
	}
}

// TestApartmentDetailFeeBare: a property without a fee, guest pay off (the
// default), no operator.
func TestApartmentDetailFeeBare(t *testing.T) {
	pool := testPool(t)
	adFeeWorld(t, pool)
	mustExec(t, pool, `UPDATE apartment SET stay_fee_rate_czk = 0, stay_fee_cadence = 'monthly', stay_fee_vs = NULL, stay_fee_council_account = NULL,
		stay_fee_authority_name = NULL, stay_fee_authority_address = NULL, stay_fee_authority_contact = NULL WHERE id = $1`, adPlain)
	body := adGet(adMux(pool, nil), "/apartments/130202?return_to=/stay-fees/130202", 130001, 0, "en").Body.String()
	adCheck(t, "bare fee", body, []string{
		`<span class="dot n" aria-hidden="true"></span><div><b>Stay fee</b></div><small class="sec-state">not used</small>`,
		`<p class="small fee-return-note"><a href="/stay-fees/130202"> Back to stay fees</a></p>`,
		`<option value="130201"`, `data-rate="50"`, `data-cadence="quarterly"`, `data-vs="5566"`,
		`stay_fee_rate_czk" aria-describedby="stay_fee_rate_czk-help" min="0" max="50" step="1"
             value="0">`,
		`id="stay_fee_vs" name="stay_fee_vs" aria-describedby="stay_fee_vs-help" inputmode="numeric" maxlength="10" aria-required="false" value="">`,
		`<details class="fee-more ui-details-box">`,
		`<option value="monthly" selected>Monthly</option>`,
	}, []string{`id="stay_fee_rate_from"`, `id="stay-fee-guest-pay"`, `stay_fee_guest_form`, `fee_signature_section`, `data-signature-dialog`,
		`stay-fee-guest-preview`, `Open this property`, `Add the variable symbol`})
	// a rate with a missing symbol shows the warning
	mustExec(t, pool, `UPDATE apartment SET stay_fee_rate_czk = 25, stay_fee_vs = '  ' WHERE id = $1`, adPlain)
	body = adGet(adMux(pool, nil), "/apartments/130202", 130001, 0, "en").Body.String()
	adCheck(t, "missing symbol", body, []string{
		`<p class="small warn-text">Add the variable symbol, the council account and the office name to create the report and the payment QR.</p>`,
		`<a href="/stay-fees/130202">Open this property&#39;s stay fee </a>`,
		`<input type="date" id="stay_fee_rate_from"`,
	}, []string{`fee-return-note`})
	// a return_to that is not the fee list or this property's report is dropped
	body = adGet(adMux(pool, nil), "/apartments/130202?return_to=/stay-fees/130201", 130001, 0, "en").Body.String()
	adCheck(t, "return_to of another property", body, nil, []string{`fee-return-note`, `/stay-fees/130201"`})
}

// TestApartmentDetailFeeScope: another host's business never reaches the page,
// an archived business gives no sample QR, the signature is read through the
// workspace, and the Czech labels come from the catalog.
func TestApartmentDetailFeeScope(t *testing.T) {
	pool := testPool(t)
	adFeeWorld(t, pool)
	on := map[string]string{adGuestPayOn: "on"}
	// the loft is pointed at host B's business with an account and a signature
	mustExec(t, pool, `UPDATE legal_entity SET bank_account = '555/0600', signature_name = 'Stranger' WHERE id = $1`, adOpOther)
	mustExec(t, pool, `UPDATE apartment SET legal_entity_id = $2 WHERE id = $1`, adLoft, adOpOther)
	body := adGet(adMux(pool, on), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "foreign business", body, []string{`id="stay-fee-guest-pay"`, `data-preview-box hidden>`, `data-preview-account></p>`},
		[]string{`Stranger`, `fee_signature_section`, `555/0600`, `data-signature-dialog`})
	// an archived business of this host: its signature shows (access.entity), its account does not (access.entities)
	mustExec(t, pool, `UPDATE legal_entity SET bank_account = '19-2000145399/0800', signature_name = 'Gone Signer' WHERE id = $1`, adOpGone)
	mustExec(t, pool, `UPDATE apartment SET legal_entity_id = $2 WHERE id = $1`, adLoft, adOpGone)
	body = adGet(adMux(pool, on), "/apartments/130201", 130001, 0, "en").Body.String()
	adCheck(t, "archived business", body, []string{`value="Gone Signer" data-signature-typed>`, `data-preview-box hidden>`,
		`<img class="signature-locked-img" data-signature-preview alt="Saved signature" hidden>`, `data-signature-open hidden>Add signature</button>`},
		[]string{`CZ65 0800`, `name="signature_remove"`})
	// the Czech page
	body = adGet(adMux(pool, nil), "/apartments/130201", 130001, 0, "cs").Body.String()
	adCheck(t, "cs", body, []string{`<b>Poplatek z pobytu</b>`, `1. Výpočet</h3>`, `2. Platba obci</h3>`, `3. Úřad a doručení</h3>`,
		`Otevřít poplatek tohoto ubytování`}, []string{`1. Calculation`})
	if !regexp.MustCompile(`value="Gone Signer"`).MatchString(body) {
		t.Errorf("cs: the typed signature is missing")
	}
}

// TestDetailFeeRails: the {% set %} lines of _stay_fee_fields.html.
func TestDetailFeeRails(t *testing.T) {
	for _, c := range []struct {
		name, stored, def string
		on                string // the rails that are on, in order
		selected          string
	}{
		{"none", "", "", "", ""},
		{"old qr name", "qr,cash", "qr", "iban,cash", "iban"},
		{"default not stored", "cash", "iban", "cash", "cash"},
		{"default off", "iban,revolut", "cash", "iban,revolut", "iban"},
		{"default revolut", "iban,revolut", "revolut", "iban,revolut", "revolut"},
		{"unknown name", "x,revolut", "x", "revolut", "revolut"},
	} {
		var on, selected []string
		for _, r := range detailFeeRails(c.stored, c.def) {
			if r.On {
				on = append(on, r.Code)
			}
			if r.IsDefault {
				selected = append(selected, r.Code)
			}
		}
		if strings.Join(on, ",") != c.on || strings.Join(selected, ",") != c.selected {
			t.Errorf("%s: on %v selected %v, want %q %q", c.name, on, selected, c.on, c.selected)
		}
	}
}
