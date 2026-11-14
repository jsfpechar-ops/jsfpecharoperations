package onboarding

// Unit tests of the wizard helpers that the golden cannot pin (brief 1599):
// the slug the wizard creates (Python's code is random), the lock switch
// under billing, the operator's first name, the date filters, the 501 of a
// page that is not ported yet and the template keys.

import (
	"context"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"
)

func TestWizardSlugIsCreatedOnce(t *testing.T) {
	pool := testPool(t)
	seedAccounts(t, pool)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, created_at)
 VALUES (41, 2, 'Žluťoučký kůň & spol.', 'tok41', '2026-01-01T00:00:00+00:00'), (42, 2, 'Pin', 'tok42', '2026-01-01T00:00:00+00:00'),
        (43, 2, 'No token', NULL, '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	s := &wizardServer{pool: pool, getenv: func(string) string { return "" }, now: time.Now}
	slugRE := regexp.MustCompile(`^zlutoucky-kun-spol-[abcdefghijkmnopqrstuvwxyz23456789]{6}$`)
	for _, c := range []struct {
		id   int64
		want *regexp.Regexp
	}{{41, slugRE}, {42, regexp.MustCompile(`^stay-[a-z2-9]{6}$`)}} {
		a, err := s.wizardLoadApt(ctx, 2, c.id)
		if err != nil || a == nil {
			t.Fatalf("load %d: %v", c.id, err)
		}
		first, err := s.wizardLinkKey(ctx, a, testNow)
		if err != nil || !c.want.MatchString(first) {
			t.Fatalf("apartment %d: link key %q (%v)", c.id, first, err)
		}
		again, err := s.wizardLinkKey(ctx, a, testNow)
		if err != nil || again != first {
			t.Fatalf("apartment %d: second key %q, want %q", c.id, again, first)
		}
		var n int
		if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM apartment_slug WHERE apartment_id = $1 AND is_current = 1`, c.id).Scan(&n); err != nil || n != 1 {
			t.Fatalf("apartment %d: %d current slugs (%v)", c.id, n, err)
		}
	}
	a, err := s.wizardLoadApt(ctx, 2, 43)
	if err != nil || a == nil {
		t.Fatal(err)
	}
	if key, err := s.wizardLinkKey(ctx, a, testNow); err != nil || key != "" {
		t.Fatalf("no token: key %q (%v)", key, err)
	}
	if a, _ := s.wizardLoadApt(ctx, 3, 41); a != nil {
		t.Fatal("another workspace read the apartment")
	}
}

func TestWizardLockAllowed(t *testing.T) {
	pool := testPool(t)
	seedAccounts(t, pool)
	ctx := context.Background()
	for _, row := range []string{
		`(2, 'active', 'max', 0)`, `(3, 'active', 'standard', 1)`,
	} {
		if _, err := pool.Exec(ctx, `INSERT INTO billing_account (owner_user_id, status, plan, addon_ttlock, updated_at) VALUES `+row[:len(row)-1]+`, '2026-01-01')`); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := pool.Exec(ctx, `INSERT INTO billing_account (owner_user_id, status, plan, addon_ttlock, updated_at) VALUES (1, 'paused', 'max', 1, '2026-01-01')`); err != nil {
		t.Fatal(err)
	}
	on := map[string]string{"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": "i", "UBYHOST_TTLOCK_CLIENT_SECRET": "s"}
	check := func(env map[string]string, owner *int64, want bool) {
		t.Helper()
		s := &wizardServer{pool: pool, getenv: func(k string) string { return env[k] }}
		got, err := s.wizardLockAllowed(ctx, owner)
		if err != nil || got != want {
			t.Fatalf("env %v owner %v: %v (%v), want %v", env, owner, got, err, want)
		}
	}
	id := func(n int64) *int64 { return &n }
	check(on, id(2), true) // billing off: UNBILLED
	check(on, nil, false)
	check(map[string]string{"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": " "}, id(2), false)
	check(map[string]string{"UBYHOST_DOOR_CODES": "True", "UBYHOST_TTLOCK_CLIENT_ID": "i", "UBYHOST_TTLOCK_CLIENT_SECRET": "s"}, id(2), false)
	billed := map[string]string{"UBYHOST_BILLING_ENABLED": "YES"}
	for k, v := range on {
		billed[k] = v
	}
	check(billed, id(2), true)  // max
	check(billed, id(3), true)  // standard with the TTLock add-on
	check(billed, id(1), false) // paused
	check(billed, id(99), true) // no billing row: UNBILLED
	if _, err := pool.Exec(ctx, `UPDATE billing_account SET addon_ttlock = 0 WHERE owner_user_id = 3`); err != nil {
		t.Fatal(err)
	}
	check(billed, id(3), false)
	if _, err := pool.Exec(ctx, `UPDATE billing_account SET status = 'trialing' WHERE owner_user_id = 3`); err != nil {
		t.Fatal(err)
	}
	check(billed, id(3), true)
}

func TestWizardOperatorFirstName(t *testing.T) {
	id := func(n int64) *int64 { return &n }
	entities := []wizardEntity{{ID: 1, Name: "  Jana   Nováková "}, {ID: 2, Name: "Beta s.r.o.", SignatureName: "Petr Svoboda"},
		{ID: 3, Name: "Gama S.R.O."}, {ID: 4, Name: "Acme, Inc."}, {ID: 5, Name: "Delta, a. s."}, {ID: 6, Name: "Ltd Pavel"}}
	for _, c := range []struct {
		entity *int64
		want   string
	}{{id(1), "Jana"}, {id(2), "Petr"}, {id(3), "[Your name]"}, {id(4), "[Your name]"}, {id(5), "Delta,"}, {id(6), "[Your name]"}, {nil, "[Your name]"}, {id(9), "[Your name]"}} {
		got := wizardOperatorFirstName("en", &wizardApt{LegalEntityID: c.entity}, entities)
		if c.want == "[Your name]" {
			c.want = wizardText.T("en", "wizard.guest_link.operator_placeholder", nil)
		}
		if got != c.want {
			t.Errorf("entity %v: %q, want %q", c.entity, got, c.want)
		}
	}
}

func TestWizardDateFilters(t *testing.T) {
	at := time.Date(2026, 12, 31, 23, 30, 0, 0, time.UTC)
	for in, want := range map[string]string{"2026-05-09": "9. 5.", "2027-01-02": "2. 1. 2027", "bad": "bad", "": ""} {
		if got := wizardDateShort(in, at); got != want {
			t.Errorf("date_short(%q) = %q, want %q", in, got, want)
		}
	}
	for in, want := range map[string]string{"2026-05-09": "09.05.2026", "x": "x"} {
		if got := wizardDateCZ(in); got != want {
			t.Errorf("date_cz(%q) = %q, want %q", in, got, want)
		}
	}
	// Prague is an hour ahead of UTC in winter: 23:30 UTC on 31 December is 1 January there.
	if got := wizardISO(wizardPragueToday(at)); got != "2027-01-01" {
		t.Errorf("prague today %s", got)
	}
}

func TestWizardStepWithoutPageIs501(t *testing.T) {
	s := &wizardServer{getenv: func(string) string { return "" }}
	rec := httptest.NewRecorder()
	s.wizardRender(rec, httptest.NewRequest(http.MethodGet, "/apartments/1/setup/x", nil), nil, testNow, 0,
		&wizardView{Step: "not-a-page", Apt: &wizardApt{}})
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("status %d", rec.Code)
	}
}

// TestWizardTemplatesUseKnownKeys: every literal t "key" of the wizard
// templates is in the wizard catalog (common.* may come from the layout's).
func TestWizardTemplatesUseKnownKeys(t *testing.T) {
	keyRE := regexp.MustCompile(`\bt "([a-z0-9_.]+)"`)
	names, err := fs.Glob(wizardFiles, "wizardtemplates/*.tmpl")
	if err != nil || len(names) == 0 {
		t.Fatal("no templates")
	}
	for _, name := range names {
		raw, err := fs.ReadFile(wizardFiles, name)
		if err != nil {
			t.Fatal(err)
		}
		for _, m := range keyRE.FindAllStringSubmatch(string(raw), -1) {
			// host_i18n falls back to English, as Catalog.T does.
			if _, ok := wizardText["en"][m[1]]; !ok && !strings.HasPrefix(m[1], "common.") {
				t.Errorf("%s: %s missing", name, m[1])
			}
		}
	}
	for _, step := range Steps {
		for _, prefix := range []string{"wizard.step.", "wizard.question."} {
			if _, ok := wizardText["en"][prefix+step]; !ok {
				t.Errorf("%s%s missing", prefix, step)
			}
		}
	}
}
