package auth

import (
	"bytes"
	"encoding/base64"
	"image/png"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// Values from pyotp 2.x: pyotp.TOTP("JBSWY3DPEHPK3PXP").at(t).
func TestAcctTOTPAtMatchesPyotp(t *testing.T) {
	for _, c := range []struct {
		unix int64
		want string
	}{{59, "996554"}, {1111111109, "071271"}, {2000000000, "890699"}} {
		got, err := acctTOTPAt("JBSWY3DPEHPK3PXP", c.unix/30)
		if err != nil || got != c.want {
			t.Errorf("at(%d) = %q, %v; want %q", c.unix, got, err, c.want)
		}
	}
}

func TestAcctTOTPVerifyWindow(t *testing.T) {
	now := time.Unix(1111111109, 0)
	for _, c := range []struct {
		code string
		ok   bool
	}{
		{"071271", true},
		{"０７１２７１", true}, // full-width digits: NFKC, as utils.strings_equal
		{"07127", false},
		{"", false},
		{"0712710", false},
	} {
		if got := acctTOTPVerify("JBSWY3DPEHPK3PXP", c.code, now); got != c.ok {
			t.Errorf("verify(%q) = %v, want %v", c.code, got, c.ok)
		}
	}
	prev, _ := acctTOTPAt("JBSWY3DPEHPK3PXP", now.Unix()/30-1)
	next, _ := acctTOTPAt("JBSWY3DPEHPK3PXP", now.Unix()/30+1)
	far, _ := acctTOTPAt("JBSWY3DPEHPK3PXP", now.Unix()/30+2)
	if !acctTOTPVerify("JBSWY3DPEHPK3PXP", prev, now) || !acctTOTPVerify("JBSWY3DPEHPK3PXP", next, now) {
		t.Error("valid_window=1 must accept the step before and after")
	}
	if far != prev && far != next && acctTOTPVerify("JBSWY3DPEHPK3PXP", far, now) {
		t.Error("two steps ahead must be refused")
	}
}

// qrcode.make(uri) for this URI is version 5 (37 modules): 450 px with a
// four-module border at 10 px per module. go-qrcode must draw the same size.
func TestAcctQRDataSize(t *testing.T) {
	data, err := acctQRData(session.TOTPURI("JBSWY3DPEHPK3PXP", "staged"))
	if err != nil {
		t.Fatal(err)
	}
	const prefix = "data:image/png;base64,"
	if !strings.HasPrefix(data, prefix) {
		t.Fatalf("not a PNG data URI: %.40q", data)
	}
	raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(data, prefix))
	if err != nil {
		t.Fatal(err)
	}
	img, err := png.Decode(bytes.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}
	if b := img.Bounds(); b.Dx() != 450 || b.Dy() != 450 {
		t.Errorf("QR is %dx%d, want 450x450", b.Dx(), b.Dy())
	}
}

func TestAcctGroup(t *testing.T) {
	for in, want := range map[string]string{"": "", "ABC": "ABC", "JBSWY3DPEHPK3PXP": "JBSW Y3DP EHPK 3PXP", "ABCDE": "ABCD E"} {
		if got := acctGroup(in); got != want {
			t.Errorf("acctGroup(%q) = %q, want %q", in, got, want)
		}
	}
}

// markupsafe.escape: & < > " ' and nothing else.
func TestAcctEscapeIsMarkupsafe(t *testing.T) {
	v := &acctView{}
	if got, want := v.E(`<a href="x">'&+`), "&lt;a href=&#34;x&#34;&gt;&#39;&amp;+"; got != want {
		t.Errorf("E = %q, want %q", got, want)
	}
}

func TestAcctRoutesListed(t *testing.T) {
	want := map[string]bool{"GET /account/accept": false, "POST /account/accept": false,
		"GET /account/2fa/setup": false, "POST /account/2fa/setup": false}
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		if _, ok := want[r.Pattern]; ok {
			want[r.Pattern] = true
			if r.Path != strings.SplitN(r.Pattern, " ", 2)[1] {
				t.Errorf("%s: metrics label %q", r.Pattern, r.Path)
			}
		}
	}
	for p, seen := range want {
		if !seen {
			t.Errorf("Routes has no %s", p)
		}
	}
}

// Every page template parses and names its title key in the catalog.
func TestAcctCatalogHasPageKeys(t *testing.T) {
	for _, key := range []string{"account.accept.title", "account.2fa.setup_title", "account.2fa.recovery_title",
		"auth.error.accept_required", "auth.error.setup_code_invalid", "flash.accounts.twofa_enabled", "auth.error.recent_login"} {
		for _, lang := range []string{"en", "cs"} {
			if _, ok := acctCatalog[lang][key]; !ok {
				t.Errorf("acct_i18n.json has no %s text for %s", lang, key)
			}
		}
	}
	for _, name := range []string{"account_accept", "two_factor_setup", "two_factor_recovery", "acct.head", "acct.foot"} {
		if acctTemplates.Lookup(name) == nil {
			t.Errorf("no template %s", name)
		}
	}
}
