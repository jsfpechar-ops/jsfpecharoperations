package palette

import (
	"context"
	"regexp"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

// base seeds two users and two apartments: id 7 (owner 1, no slug) and id 8 (owner 2, no slug).
func base(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	stmts := []string{
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'owner@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (2, 'admin@example.test', 'x', 'admin', '2026-01-01')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at) VALUES (7, 1, 'Byt Dole', 'Brno', 'UBY', 'tok7', '2026-01-01')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at) VALUES (8, 2, 'Other', 'Praha', 'OTH', 'tok8', '2026-01-01')`,
	}
	for _, s := range stmts {
		if _, err := pool.Exec(context.Background(), s); err != nil {
			t.Fatal(err)
		}
	}
}

func count(t *testing.T, pool *pgxpool.Pool, query string) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), query).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func fieldValues(items []object, key string) []string {
	var out []string
	for _, it := range items {
		for _, f := range it {
			if f.k == key {
				out = append(out, f.v.(string))
			}
		}
	}
	return out
}

func contains(list []string, want string) bool {
	for _, v := range list {
		if v == want {
			return true
		}
	}
	return false
}

// TestReadableTable: expected values are the output of
// guest_slug._generated_readable in App/app (run with .venv/bin/python).
func TestReadableTable(t *testing.T) {
	cases := []struct{ name, want string }{
		{"Chata Žluťoučký kůň", "chata-zlutoucky-kun"},
		{"Vinohrady – Studio Žižkov", "vinohrady-studio-zizkov"},
		{"Ostrava-Poruba  (Byt č. 3)", "ostrava-poruba-byt-c-3"},
		{"Ærø Øl & Ørn Hus", "aero-ol-orn-hus"},
		{"Ššťčž Řeka", "sstcz-reka"},
		{"!!! ???", "stay"},
	}
	for _, c := range cases {
		if got := generatedReadable(c.name); got != c.want {
			t.Errorf("%q: got %q want %q", c.name, got, c.want)
		}
	}
}

func TestReadableCutsLongWord(t *testing.T) {
	// Python: readable_part('x' * 45 + ' yy') keeps 40 characters.
	if got := readablePart(strings.Repeat("x", 45) + " yy"); got != strings.Repeat("x", 40) {
		t.Fatalf("got %q", got)
	}
}

func TestEnsureCreatesSlugOnceAndPaletteReusesIt(t *testing.T) {
	pool := testPool(t)
	base(t, pool)
	ctx := context.Background()
	items, err := Items(ctx, pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	copies := fieldValues(items, "copy")
	re := regexp.MustCompile(`^http://127\.0\.0\.1:8080/l/byt-dole-[a-km-z2-9]{6}$`)
	if len(copies) != 1 || !re.MatchString(copies[0]) {
		t.Fatalf("copy links %v", copies)
	}
	if n := count(t, pool, `SELECT count(*) FROM apartment_slug WHERE apartment_id = 7`); n != 1 {
		t.Fatalf("slug rows after first request: %d", n)
	}
	items2, err := Items(ctx, pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	if again := fieldValues(items2, "copy"); len(again) != 1 || again[0] != copies[0] {
		t.Fatalf("second request %v, first %v", again, copies)
	}
	if n := count(t, pool, `SELECT count(*) FROM apartment_slug WHERE apartment_id = 7`); n != 1 {
		t.Fatalf("slug rows after second request: %d", n)
	}
}

func TestExistingSlugUsedAsIs(t *testing.T) {
	pool := testPool(t)
	base(t, pool)
	if _, err := pool.Exec(context.Background(),
		`INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at) VALUES ('byt-dole-abc234', 7, 1, '2026-01-01')`); err != nil {
		t.Fatal(err)
	}
	items, err := Items(context.Background(), pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	if copies := fieldValues(items, "copy"); len(copies) != 1 || copies[0] != "http://127.0.0.1:8080/l/byt-dole-abc234" {
		t.Fatalf("copy links %v", copies)
	}
	if n := count(t, pool, `SELECT count(*) FROM apartment_slug`); n != 1 {
		t.Fatalf("slug rows: %d", n)
	}
}

func TestTwoPropertiesOpenSummaries(t *testing.T) {
	pool := testPool(t)
	base(t, pool)
	if _, err := pool.Exec(context.Background(),
		`INSERT INTO apartment (id, owner_user_id, internal_name, city_en, uby_name, permalink_token, created_at) VALUES (9, 1, 'Byt Brno', 'Brno', 'UBY2', 'tok9', '2026-01-01')`); err != nil {
		t.Fatal(err)
	}
	items, err := Items(context.Background(), pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	urls := fieldValues(items, "url")
	if n := strings.Count(strings.Join(urls, "\n"), "/apartments#property-summaries"); n != 2 {
		t.Fatalf("summary urls: %d in %v", n, urls)
	}
	for _, u := range urls {
		if strings.HasPrefix(u, "/apartments/7?view=settings") {
			t.Fatalf("one-property hub leaked into a two-property account: %s", u)
		}
	}
}

func TestAdminRoleAddsTwoItems(t *testing.T) {
	pool := testPool(t)
	base(t, pool)
	ctx := context.Background()
	admin, err := Items(ctx, pool, host(2, "admin"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	urls := fieldValues(admin, "url")
	if !contains(urls, "/admin/customers") || !contains(urls, "/admin/incidents") {
		t.Fatalf("admin items missing: %v", urls)
	}
	plain, err := Items(ctx, pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	if contains(fieldValues(plain, "url"), "/admin/customers") {
		t.Fatal("host sees admin items")
	}
}

func TestStayCapEightyAndExclusions(t *testing.T) {
	pool := testPool(t)
	base(t, pool)
	ctx := context.Background()
	stmts := []string{
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, created_at, updated_at)
		 SELECT g, 7, 'u' || g, to_char(date '2026-01-01' + g, 'YYYY-MM-DD'), to_char(date '2026-01-02' + g, 'YYYY-MM-DD'), '', '2026-01-01', '2026-01-01'
		   FROM generate_series(1, 81) g`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, created_at, updated_at, archived_at)
		 VALUES (500, 7, 'arch', '2026-12-01', '2026-12-02', '', '2026-01-01', '2026-01-01', '2026-02-01')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, summary, created_at, updated_at)
		 VALUES (501, 8, 'other', '2026-12-03', '2026-12-04', '', '2026-01-01', '2026-01-01')`,
	}
	for _, s := range stmts {
		if _, err := pool.Exec(ctx, s); err != nil {
			t.Fatal(err)
		}
	}
	items, err := Items(ctx, pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	var stays []string
	for _, u := range fieldValues(items, "url") {
		if strings.HasPrefix(u, "/reservations/") {
			stays = append(stays, u)
		}
	}
	if len(stays) != 80 {
		t.Fatalf("stay items: %d", len(stays))
	}
	for _, gone := range []string{"/reservations/1", "/reservations/500", "/reservations/501"} {
		if contains(stays, gone) {
			t.Fatalf("%s should be left out", gone)
		}
	}
	if !contains(stays, "/reservations/2") || !contains(stays, "/reservations/81") {
		t.Fatalf("newest 80 stays missing: %v", stays)
	}
}

func TestSubmissionCapForty(t *testing.T) {
	pool := testPool(t)
	base(t, pool)
	ctx := context.Background()
	if _, err := pool.Exec(ctx,
		`INSERT INTO submission (id, apartment_id, created_at, state)
		 SELECT g, 7, '2026-05-02', 'done' FROM generate_series(1, 41) g`); err != nil {
		t.Fatal(err)
	}
	items, err := Items(ctx, pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	var subs []string
	for _, u := range fieldValues(items, "url") {
		if strings.HasPrefix(u, "/submissions/") {
			subs = append(subs, u)
		}
	}
	if len(subs) != 40 {
		t.Fatalf("submission items: %d", len(subs))
	}
	if contains(subs, "/submissions/1") || !contains(subs, "/submissions/41") {
		t.Fatalf("wrong window: %v", subs)
	}
}

// TestExactBytesNoProperties pins the exact response body for one signed-in
// host with no properties, stays or submissions.
func TestExactBytesNoProperties(t *testing.T) {
	pool := testPool(t)
	if _, err := pool.Exec(context.Background(),
		`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'owner@example.test', 'x', 'host', '2026-01-01')`); err != nil {
		t.Fatal(err)
	}
	items, err := Items(context.Background(), pool, host(1, "host"), "en", noEnv)
	if err != nil {
		t.Fatal(err)
	}
	got, err := marshalNoHTML(struct {
		Items []object `json:"items"`
	}{Items: items})
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != goldenNoProperties {
		t.Fatalf("got:\n%s", got)
	}
}

const goldenNoProperties = `{"items":[{"label":"Dashboard","group":"Pages","url":"/","keywords":"dashboard"},{"label":"Stays","group":"Pages","url":"/reservations","keywords":"bookings calendar"},{"label":"Police reports","group":"Pages","url":"/submissions","keywords":"ubyport dorucenka"},{"label":"Guest register","group":"Pages","url":"/housebook","keywords":"export csv"},{"label":"Invoices","group":"Pages","url":"/invoices","keywords":"faktura invoice doklad"},{"label":"Stay fees","group":"Pages","url":"/stay-fees","keywords":"poplatek z pobytu hlaseni city tax"},{"label":"Settings","group":"Pages","url":"/settings","keywords":"environment account"},{"label":"Update calendars","group":"Actions","url":"/sync","method":"post","keywords":"ical refresh"},{"label":"Add stay","group":"Actions","url":"/reservations?new=1","keywords":"booking reservation"},{"label":"Properties","group":"Pages","url":"/apartments","keywords":"property apartment ubytovani"},{"label":"Business & legal details","group":"Pages","url":"/entities","keywords":"business operator company billing firma"},{"label":"Guest links","group":"Pages","url":"/apartments#property-summaries","keywords":"invitation guest link pin"},{"label":"Automation & UbyPort","group":"Pages","url":"/apartments#property-summaries","keywords":"automatic reporting timing police"},{"label":"Invoice settings","group":"Pages","url":"/entities","keywords":"invoice settings faktura"},{"label":"Security","group":"Pages","url":"/settings#settings-group-security","keywords":"passkey 2fa authenticator login password"},{"label":"Data & archive","group":"Pages","url":"/settings#settings-group-data","keywords":"retention backup delete expired export"},{"label":"Archive","group":"Pages","url":"/settings/archived","keywords":"restore archived records"},{"label":"Data requests","group":"Pages","url":"/privacy-requests","keywords":"privacy gdpr"},{"label":"Help","group":"Pages","url":"/guide","keywords":"help guide support"}]}`
