package booking

import (
	"context"
	"encoding/json"
	"os"
	"testing"
	"time"
)

// testdata/slug_golden.json: App/app/property_page.py slug_for(id, name) for
// 16 names (Python 3.12), including accents, full-width and ligature letters,
// a name with no ASCII letter, an empty name and a 60-character name.
func TestSlugForMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/slug_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		ID         int64
		Name, Slug string
	}
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) != 16 {
		t.Fatalf("%d cases, want 16", len(cases))
	}
	for _, c := range cases {
		if got := SlugFor(c.ID, c.Name); got != c.Slug {
			t.Errorf("SlugFor(%d, %q) = %q, Python says %q", c.ID, c.Name, got, c.Slug)
		}
	}
}

func TestPublishPage(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	exec := func(sql string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, sql, args...); err != nil {
			t.Fatal(err)
		}
	}
	exec(`INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (1, 'host1', 'x', 'host', '2026-01-01T00:00:00+00:00')`)
	exec(`INSERT INTO apartment (id, owner_user_id, internal_name, created_at) VALUES (7, 1, 'Karlín Loft (demo)', '2026-01-01T00:00:00+00:00'), (8, 1, 'No Page', '2026-01-01T00:00:00+00:00')`)
	exec(`INSERT INTO property_page (apartment_id, created_at, updated_at) VALUES (7, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')`)
	now := time.Date(2026, 11, 14, 10, 0, 0, 0, time.UTC)
	stamp := "2026-11-14T10:00:00+00:00"
	read := func(sql string, args ...any) (published int64, at *string) {
		t.Helper()
		if err := pool.QueryRow(ctx, sql, args...).Scan(&published, &at); err != nil {
			t.Fatal(err)
		}
		return
	}

	if err := PublishPage(ctx, pool, 7, true, now); err != nil {
		t.Fatal(err)
	}
	for _, sql := range []string{`SELECT published, published_at FROM property_page WHERE apartment_id = 7`, `SELECT published, published_at FROM property_slug WHERE apartment_id = 7`} {
		if p, at := read(sql); p != 1 || at == nil || *at != stamp {
			t.Errorf("%s: %d %v", sql, p, at)
		}
	}
	var slug string
	if err := pool.QueryRow(ctx, `SELECT slug FROM property_slug WHERE apartment_id = 7`).Scan(&slug); err != nil || slug != SlugFor(7, "Karlín Loft (demo)") {
		t.Errorf("slug %q (%v)", slug, err)
	}

	// unpublish: flags off, published_at NULL
	if err := PublishPage(ctx, pool, 7, false, now.Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if p, at := read(`SELECT published, published_at FROM property_slug WHERE apartment_id = 7`); p != 0 || at != nil {
		t.Errorf("unpublished slug: %d %v", p, at)
	}

	// a rename moves the old slug to history, once
	exec(`UPDATE apartment SET internal_name = 'Karlin Loft Renamed' WHERE id = 7`)
	if err := PublishPage(ctx, pool, 7, true, now); err != nil {
		t.Fatal(err)
	}
	var history int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM property_slug_history WHERE apartment_id = 7 AND old_slug = $1`, slug).Scan(&history); err != nil || history != 1 {
		t.Errorf("history rows %d (%v)", history, err)
	}
	if err := PublishPage(ctx, pool, 7, true, now); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM property_slug_history`).Scan(&history); err != nil || history != 1 {
		t.Errorf("a second publish added history: %d (%v)", history, err)
	}

	// a property without a property_page row still gets a published slug (Python's UPDATE touches no row)
	if err := PublishPage(ctx, pool, 8, true, now); err != nil {
		t.Fatal(err)
	}
	if p, _ := read(`SELECT published, published_at FROM property_slug WHERE apartment_id = 8`); p != 1 {
		t.Error("slug of a property without a page not published")
	}
	var pages int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM property_page WHERE apartment_id = 8`).Scan(&pages); err != nil || pages != 0 {
		t.Errorf("a property_page row was created: %d (%v)", pages, err)
	}

	// an unknown apartment is an error and writes nothing
	if err := PublishPage(ctx, pool, 999, true, now); err == nil {
		t.Error("unknown apartment: no error")
	}
}
