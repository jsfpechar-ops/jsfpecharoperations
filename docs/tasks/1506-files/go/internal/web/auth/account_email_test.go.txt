package auth

import (
	"strings"
	"testing"
	"time"
)

func TestAccountEmailGoldenDatabase(t *testing.T) {
	runAccountGolden(t, "testdata/account_email.json")
}

func TestAcctEmailRoutesListed(t *testing.T) {
	want := map[string]bool{"POST /account/email": false, "GET /account/email/confirm": false,
		"POST /account/email/confirm": false}
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
	if acctTemplates.Lookup("account_email_confirm") == nil {
		t.Error("no template account_email_confirm")
	}
}
