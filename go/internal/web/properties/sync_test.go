package properties

import (
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
)

func TestPluralFlashKey(t *testing.T) {
	for _, c := range []struct {
		n    int
		lang string
		want string
	}{
		{1, "en", "k.one"}, {2, "en", "k.few"}, {4, "cs", "k.few"}, {5, "cs", "k"}, {0, "en", "k"},
		{21, "uk", "k.one"}, {11, "uk", "k"}, {23, "uk", "k.few"}, {12, "uk", "k"}, {25, "uk", "k"},
	} {
		if got := pluralFlashKey("k", c.n, c.lang); got != c.want {
			t.Errorf("%d %s: %s want %s", c.n, c.lang, got, c.want)
		}
	}
}

// sync_now (admin.py ~3415): only the signed-in workspace's active calendars are fetched.
func TestSyncNow(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	var mu sync.Mutex
	hits := map[string]int{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		hits[r.URL.Path]++
		mu.Unlock()
		if r.URL.Path == "/bad.ics" {
			http.Error(w, "no", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "text/calendar")
		_, _ = w.Write([]byte("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:" + r.URL.Path + "-1\r\nDTSTART;VALUE=DATE:20261210\r\nDTEND;VALUE=DATE:20261212\r\nSUMMARY:Reserved\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"))
	}))
	defer srv.Close()
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, active, created_at) VALUES
		(130201, 130001, 'A live', 1, $1), (130202, 130001, 'A off', 0, $1), (130203, 130002, 'B live', 1, $1)`, stamp0)
	feed := func(id, apt int64, path string, active int) {
		mustExec(t, pool, `INSERT INTO ical_feed (id, apartment_id, url, active, created_at) VALUES ($1, $2, $3, $4, $5)`, id, apt, srv.URL+path, active, stamp0)
	}
	feed(130701, 130201, "/a.ics", 1)
	feed(130702, 130202, "/off.ics", 1) // apartment switched off
	feed(130703, 130203, "/b.ics", 1)   // another host
	feed(130704, 130201, "/stopped.ics", 0)

	mux := http.NewServeMux()
	RegisterSync(mux, noWrap, pool, testEnv, testClock, &ical.FetchOptions{Resolver: net.DefaultResolver, AllowPrivate: true})

	rec := postWithHost(t, mux, "/sync", 130001, "h.example", nil)
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d", rec.Code)
	}
	want := "/?msg=Synced%201%20calendar%3A%201%20new%2C%200%20updated%2C%200%20cancelled."
	if got := rec.Header().Get("Location"); got != want {
		t.Errorf("Location %q want %q", got, want)
	}
	mu.Lock()
	if hits["/a.ics"] != 1 || hits["/off.ics"] != 0 || hits["/b.ics"] != 0 || hits["/stopped.ics"] != 0 {
		t.Errorf("fetched: %v", hits)
	}
	mu.Unlock()
	if n := oneInt(t, pool, `SELECT COUNT(*) FROM reservation WHERE apartment_id = 130201`); n != 1 {
		t.Errorf("reservations for the synced flat: %d", n)
	}
	if n := oneInt(t, pool, `SELECT COUNT(*) FROM reservation WHERE apartment_id = 130203`); n != 0 {
		t.Errorf("another host's calendar was imported")
	}
	if n := oneInt(t, pool, `SELECT COUNT(*) FROM settings WHERE key = 'last_ical_sync'`); n != 1 {
		t.Error("last_ical_sync not written")
	}

	// A failing calendar: counted as read, reported with the error flash; return_to is honoured.
	feed(130705, 130201, "/bad.ics", 1)
	form := url.Values{"return_to": {"/apartments/130201?view=bookings#calendars"}}
	rec = post(t, mux, "/sync", 130001, 0, "en", form)
	loc := rec.Header().Get("Location")
	if !strings.HasPrefix(loc, "/apartments/130201?view=bookings&msg=") || !strings.Contains(loc, "&err=") || strings.Contains(loc, "#") { // the fragment is dropped: keep_fragment is off
		t.Errorf("Location %q", loc)
	}
	if !strings.Contains(loc, "Synced%202%20calendars%3A%200%20new") {
		t.Errorf("counts in %q", loc)
	}

	// Signed out: login page, and nothing fetched.
	before := hits["/a.ics"]
	if rec = postWithHost(t, mux, "/sync", 0, "h.example", nil); rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if hits["/a.ics"] != before {
		t.Error("a signed-out request fetched a calendar")
	}
}
