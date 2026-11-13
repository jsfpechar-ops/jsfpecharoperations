package ai

import (
	"context"
	"encoding/json"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

// guide_import_urls.json is written by App/scripts/guide_import_urls_golden.py
// from the Python normalise_url. A link Python cannot parse (ValueError) is
// refused by Go as a bad link.
func TestGuideNormaliseURLMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/guide_import_urls.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Input, Source, URL, Error string
	}
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 40 {
		t.Fatalf("only %d cases", len(cases))
	}
	for _, c := range cases {
		got, err := guideNormaliseURL(c.Input)
		want := c.Error
		if want == "ValueError" {
			want = guideLinkErr
		}
		if key := guideErrKey(err); key != want {
			t.Errorf("%q: error %q, want %q", c.Input, key, want)
			continue
		}
		if want == "" && (got.Source != c.Source || got.URL != c.URL) {
			t.Errorf("%q: %+v, want %s %s", c.Input, got, c.Source, c.URL)
		}
	}
}

func TestGuideImportRoute(t *testing.T) {
	pool := guideTestPool(t)
	owner := guideSeedUser(t, pool, "host1", "host")
	stranger := guideSeedUser(t, pool, "stranger", "host")
	apt := guideSeedApartment(t, pool, owner, "Flat")
	path := "/apartments/" + itoa64(apt) + "/guide/import"
	on := map[string]string{"UBYHOST_APIFY_TOKEN": "t", "UBYHOST_APIFY_MONTHLY_RUNS": "3"}
	mux := guideTestMux(pool, on)
	count := func() int64 {
		return guideTestCount(t, pool, `SELECT COUNT(*) FROM guide_import WHERE apartment_id = $1`, apt)
	}
	booking := "https://www.booking.com/hotel/cz/vivus-3.cs.html?x=1"
	airbnb := "https://www.airbnb.com/rooms/123"
	post := func(uid int64, form url.Values) string {
		rec := guideTestDo(t, mux, "POST", path, uid, form)
		if rec.Code != 303 && rec.Code != 404 {
			t.Fatalf("status %d", rec.Code)
		}
		return rec.Header().Get("Location")
	}

	// nothing, one bad link, two links of one source: nothing is queued
	for name, form := range map[string]url.Values{
		"empty":       {},
		"blank":       {"booking_url": {"  "}},
		"bad link":    {"booking_url": {"https://evil.example/x"}},
		"same source": {"booking_url": {booking}, "url": {"https://booking.com/hotel/de/b.html"}},
	} {
		loc := post(owner, form)
		if !strings.Contains(loc, "?err=") || count() != 0 {
			t.Errorf("%s: Location %q, %d rows", name, loc, count())
		}
	}
	// both links: two rows, back to the import section
	loc := post(owner, url.Values{"booking_url": {booking}, "airbnb_url": {airbnb}})
	if !strings.HasPrefix(loc, "/apartments/"+itoa64(apt)+"/guide?msg=") || !strings.HasSuffix(loc, "#import") {
		t.Errorf("queued Location = %q", loc)
	}
	if count() != 2 {
		t.Fatalf("%d rows queued, want 2", count())
	}
	var src, link, status, created string
	if err := pool.QueryRow(context.Background(), `SELECT source, url, status, created_at FROM guide_import WHERE source = 'booking'`).Scan(&src, &link, &status, &created); err != nil {
		t.Fatal(err)
	}
	if link != "https://www.booking.com/hotel/cz/vivus-3.cs.html" || status != "queued" || created != guideStamp(guideTestNow) {
		t.Errorf("queued row = %s %s %s %s", src, link, status, created)
	}
	// busy while queued
	if loc := post(owner, url.Values{"booking_url": {booking}}); !strings.Contains(loc, "?err=") || count() != 2 {
		t.Errorf("busy: %q %d", loc, count())
	}
	// a source already imported (not failed) is refused; a failed one may be tried again
	guideTestExec(t, pool, `UPDATE guide_import SET status = 'used'`)
	if loc := post(owner, url.Values{"airbnb_url": {airbnb}}); !strings.Contains(loc, "?err=") || count() != 2 {
		t.Errorf("limit: %q %d", loc, count())
	}
	guideTestExec(t, pool, `UPDATE guide_import SET status = 'failed' WHERE source = 'airbnb'`)
	// the monthly run budget: 3 runs, 2 counted, a third fits, a fourth would not
	guideTestExec(t, pool, `INSERT INTO lock_api_usage (month, provider, calls) VALUES ('2026-11', 'apify', 3)`)
	if loc := post(owner, url.Values{"airbnb_url": {airbnb}}); !strings.Contains(loc, "?err=") || count() != 2 {
		t.Errorf("budget: %q %d", loc, count())
	}
	guideTestExec(t, pool, `UPDATE lock_api_usage SET calls = 2`)
	if loc := post(owner, url.Values{"airbnb_url": {airbnb}, "next": {"leon"}}); !strings.HasPrefix(loc, "/apartments/"+itoa64(apt)+"/leon/setup/import?msg=") || count() != 3 {
		t.Errorf("leon target: %q %d", loc, count())
	}
	// access
	if rec := guideTestDo(t, mux, "POST", path, stranger, url.Values{"booking_url": {booking}}); rec.Code != 404 {
		t.Errorf("another account: %d", rec.Code)
	}
	// the switch: without an Apify token nothing is queued
	off := guideTestMux(pool, nil)
	rec := guideTestDo(t, off, "POST", path, owner, url.Values{"booking_url": {booking}})
	if !strings.Contains(rec.Header().Get("Location"), "?err=") || count() != 3 {
		t.Errorf("import off: %q %d", rec.Header().Get("Location"), count())
	}
}

func TestGuideRunsThisMonthIsUTC(t *testing.T) {
	pool := guideTestPool(t)
	s := guideTestServer(pool, nil)
	guideTestExec(t, pool, `INSERT INTO lock_api_usage (month, provider, calls) VALUES ('2026-10', 'apify', 7), ('2026-11', 'apify', 1)`)
	for at, want := range map[time.Time]int{
		time.Date(2026, 10, 31, 23, 59, 0, 0, time.UTC): 7,
		time.Date(2026, 11, 1, 0, 0, 0, 0, time.UTC):    1,
		time.Date(2026, 12, 1, 0, 0, 0, 0, time.UTC):    0,
	} {
		if got, err := s.runsThisMonth(context.Background(), at); err != nil || got != want {
			t.Errorf("runsThisMonth(%v) = %d, %v; want %d", at, got, err, want)
		}
	}
}
