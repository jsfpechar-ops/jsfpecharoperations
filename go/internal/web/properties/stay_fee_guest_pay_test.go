package properties

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"strings"
	"testing"
)

func guestPayForm(values url.Values) *http.Request {
	r := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(values.Encode()))
	r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	_ = r.ParseForm()
	return r
}

func TestGuestPayValuesRails(t *testing.T) {
	cases := []struct {
		name string
		form url.Values
		want map[string]string
	}{
		{
			name: "iban cash default cash",
			form: url.Values{
				"stay_fee_guest_rails":        []string{"iban", "cash"},
				"stay_fee_collect":            []string{"1"},
				"stay_fee_guest_default_rail": []string{"cash"},
			},
			want: map[string]string{
				"stay_fee_guest_rails": "cash,iban", "stay_fee_guest_default_rail": "cash", "stay_fee_collect": "1",
			},
		},
		{
			name: "qr normalised revolut link adds rail",
			form: url.Values{
				"stay_fee_guest_rails":        []string{"qr"},
				"stay_fee_guest_revolut_link": []string{"https://revolut.me/x"},
				"stay_fee_guest_default_rail": []string{"qr"},
				"stay_fee_guest_cash_note":    []string{"  note  "},
			},
			want: map[string]string{
				"stay_fee_guest_rails": "iban,revolut", "stay_fee_guest_default_rail": "iban",
			},
		},
		{
			name: "default falls back to first rail",
			form: url.Values{"stay_fee_guest_rails": []string{"revolut"}},
			want: map[string]string{"stay_fee_guest_rails": "revolut", "stay_fee_guest_default_rail": "revolut"},
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := guestPayValues(guestPayForm(tc.form))
			for k, want := range tc.want {
				var have string
				switch v := got[k].(type) {
				case string:
					have = v
				case int:
					have = strconv.Itoa(v)
				}
				if have != want {
					t.Errorf("%s = %q, want %q", k, have, want)
				}
			}
		})
	}
}

func TestRevolutLinkOK(t *testing.T) {
	for raw, ok := range map[string]bool{
		"https://revolut.me/user": true, "https://x.revolut.com/pay": true,
		"http://revolut.me/x": false, "https://evil.example/x": false, "": false,
	} {
		if revolutLinkOK(raw) != ok {
			t.Errorf("revolutLinkOK(%q) = %v, want %v", raw, !ok, ok)
		}
	}
}

func TestGuestPayRailsNeedAccount(t *testing.T) {
	if !guestPayRailsNeedAccount("iban,cash") || !guestPayRailsNeedAccount("qr") {
		t.Error("iban/qr need account")
	}
	if guestPayRailsNeedAccount("revolut,cash") {
		t.Error("revolut/cash alone should not need account")
	}
}

func TestStayFeeGuestPaySwitchOff(t *testing.T) {
	cols := []column{{"internal_name", "X"}}
	r := guestPayForm(url.Values{"stay_fee_guest_form": []string{"1"}, "stay_fee_collect": []string{"1"}})
	off := func(string) string { return "" }
	if got := mergeGuestPayForm(cols, r, off); len(got) != len(cols) {
		t.Errorf("switch off: %d cols, want %d unchanged", len(got), len(cols))
	}
}
