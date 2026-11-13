package retention

import (
	"testing"
	"time"
)

func env(m map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v, ok := m[k]
		return v, ok
	}
}

func TestConfigFromEnvSwitches(t *testing.T) {
	for _, c := range []struct {
		vars map[string]string
		dry  bool
	}{
		{map[string]string{}, true},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "1"}, true},
		{map[string]string{"UBYHOST_GO_RETENTION_APPLY": "1"}, true},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "1", "UBYHOST_GO_RETENTION_APPLY": "0"}, true},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "TRUE", "UBYHOST_GO_RETENTION_APPLY": "1"}, true},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "1", "UBYHOST_GO_RETENTION_APPLY": "1"}, false},
		{map[string]string{"UBYHOST_RETENTION_AUTOPURGE": "yes", "UBYHOST_GO_RETENTION_APPLY": "true"}, false},
	} {
		cfg, err := ConfigFromEnv(env(c.vars))
		if err != nil || cfg.DryRun != c.dry {
			t.Errorf("%v: DryRun %v (%v), want %v", c.vars, cfg.DryRun, err, c.dry)
		}
	}
	cfg, err := ConfigFromEnv(env(map[string]string{}))
	if err != nil || cfg.AuditDays != 1095 || cfg.AlertDays != 365 || cfg.RateLimitHours != 24 || cfg.NoticeDays != 30 {
		t.Fatalf("defaults %+v %v", cfg, err)
	}
	if _, err := ConfigFromEnv(env(map[string]string{"UBYHOST_AUDIT_RETENTION_DAYS": "x"})); err == nil {
		t.Fatal("a bad number must be an error")
	}
}

func TestStepsOrderMatchesPython(t *testing.T) {
	want := []string{"guests", "invoices", "platform_invoices", "claim_emails", "reservation_contacts",
		"submitter_ips", "empty_reservations", "stay_fee_records", "audit_rows", "alerts",
		"rate_limit_events", "havel_gap", "login_tokens", "webauthn_challenges", "door_code_pins",
		"cleaning", "push", "guide_imports", "guest_chats", "legal_acceptance", "workspaces"}
	if len(steps) != len(want) {
		t.Fatalf("%d steps, want %d", len(steps), len(want))
	}
	for i, s := range steps {
		if s.name != want[i] {
			t.Errorf("step %d is %s, want %s", i, s.name, want[i])
		}
	}
}

func TestFormats(t *testing.T) {
	at := time.Date(2026, 1, 20, 3, 0, 0, 250000999, time.UTC)
	if got := pyISO(at); got != "2026-01-20T03:00:00+00:00" {
		t.Errorf("pyISO %s", got)
	}
	if got := pyISOMicro(at); got != "2026-01-20T03:00:00.250000+00:00" {
		t.Errorf("pyISOMicro %s", got)
	}
	if got := pyISOMicro(at.Truncate(time.Second)); got != "2026-01-20T03:00:00+00:00" {
		t.Errorf("pyISOMicro whole second %s", got)
	}
	for in, want := range map[string]string{"2026-01-30": "2019-01-01", "2026-01-31": "2020-01-01", "2026-12-31": "2020-01-01"} {
		d, _ := time.Parse("2006-01-02", in)
		if got := isoDate(housebookCutoff(d)); got != want {
			t.Errorf("housebookCutoff(%s) = %s, want %s", in, got, want)
		}
	}
	if got := pyQuote("a\"b\\c\n" + string(rune(0xe9)) + string(rune(0x1F600)) + "\x7f"); got != "\"a\\\"b\\\\c\\n\\u00e9\\ud83d\\ude00\\u007f\"" {
		t.Errorf("pyQuote %s", got)
	}
	owner := int64(7)
	s := Summary{DryRun: true, OwnerUserID: &owner, Counts: []Count{{"guests", 2}, {"invoices", 0}}}
	if got := summaryJSON(s, ""); got != `{"dry_run": true, "owner_user_id": 7, "counts": {"guests": 2, "invoices": 0}}` {
		t.Errorf("summaryJSON %s", got)
	}
	if got := summaryJSON(Summary{Counts: []Count{}}, "T"); got != `{"dry_run": false, "owner_user_id": null, "counts": {}, "at": "T"}` {
		t.Errorf("summaryJSON at %s", got)
	}
}
