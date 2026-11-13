package ai

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guideimport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// The catalog constants equal the ones go/internal/guideimport pins against
// the Python golden (guest_guide.TOPICS, KINDS, LIMITS).
func TestGuideCatalogMatchesGuideImport(t *testing.T) {
	if strings.Join(guideTopics, ",") != strings.Join(guideimport.Topics, ",") {
		t.Errorf("topics differ: %v vs %v", guideTopics, guideimport.Topics)
	}
	if len(guideKinds) != len(guideimport.Kinds) {
		t.Fatalf("kinds: %d vs %d", len(guideKinds), len(guideimport.Kinds))
	}
	for i, k := range guideimport.Kinds {
		if guideKinds[i].Kind != k.Kind || guideKinds[i].Topic != k.Topic {
			t.Errorf("kind %d: %v vs %v", i, guideKinds[i], k)
		}
	}
	for name, n := range guideimport.Limits {
		if guideLimits[name] != n {
			t.Errorf("limit %s: %d vs %d", name, guideLimits[name], n)
		}
	}
	for _, kind := range append(append([]string{}, guideDefaultKinds...), guideMustHave...) {
		if _, ok := guideKindTopicOf(kind); !ok {
			t.Errorf("default or must-have kind %q is not a built-in kind", kind)
		}
	}
}

func TestGuideClean(t *testing.T) {
	long := strings.Repeat("x", 121)
	cases := []struct {
		name   string
		fields map[string]string
		want   map[string]string
		key    string
	}{
		{"trim and crlf", map[string]string{"steps": "  a\r\nb \x1f"}, map[string]string{"steps": "a\nb"}, ""},
		{"only sent fields", map[string]string{"location": "hall"}, map[string]string{"location": "hall"}, ""},
		{"title too long", map[string]string{"title": long}, nil, "flash.error.guide_too_long"},
		{"limit counts code points", map[string]string{"title": strings.Repeat("ž", 120)}, map[string]string{"title": strings.Repeat("ž", 120)}, ""},
		{"video must be https", map[string]string{"video_url": "http://x.example/v"}, nil, "flash.error.guide_video_url"},
		{"video https ok", map[string]string{"video_url": "https://x.example/v"}, map[string]string{"video_url": "https://x.example/v"}, ""},
		{"empty video ok", map[string]string{"video_url": "  "}, map[string]string{"video_url": ""}, ""},
		{"bad visibility", map[string]string{"visibility": "all"}, nil, "flash.error.guide_visibility"},
		{"good visibility", map[string]string{"visibility": "host"}, map[string]string{"visibility": "host"}, ""},
		{"first error wins", map[string]string{"title": long, "video_url": "ftp://x"}, nil, "flash.error.guide_too_long"},
	}
	for _, c := range cases {
		got, err := guideClean(c.fields)
		if guideErrKey(err) != c.key {
			t.Errorf("%s: error key %q, want %q", c.name, guideErrKey(err), c.key)
			continue
		}
		if c.key == "" {
			if len(got) != len(c.want) {
				t.Errorf("%s: got %v, want %v", c.name, got, c.want)
			}
			for k, v := range c.want {
				if got[k] != v {
					t.Errorf("%s: %s = %q, want %q", c.name, k, got[k], v)
				}
			}
		}
	}
}

func TestGuideNextOpenAndProgress(t *testing.T) {
	rows := []guideItem{
		{ID: 1, Kind: "checkin", State: "done"},
		{ID: 2, Kind: "keys", State: "missing"},
		{ID: 3, Kind: "wifi", State: "skipped"},
		{ID: 4, Kind: "heating", State: "check"},
		{ID: 5, Kind: "checkout", State: "done"},
		{ID: 6, Kind: "emergency", State: "done"},
	}
	for after, want := range map[int64]int64{0: 2, 2: 4, 4: 2, 6: 2, 99: 2} {
		if got := guideNextOpen(rows, after); got != want {
			t.Errorf("guideNextOpen(after %d) = %d, want %d", after, got, want)
		}
	}
	if got := guideNextOpen(rows[:1], 1); got != 0 {
		t.Errorf("a list with nothing open = %d, want 0", got)
	}
	p := guideProgressOf(rows)
	// skipped counts as answered but not in total; wifi is skipped so the five must-haves are all dealt with except heating (check).
	want := guideProgress{Done: 3, Total: 5, Answered: 4, Cards: 6, Check: 1, MustHaveDone: 4, MustHaveTotal: 5, Live: false}
	if p != want {
		t.Errorf("progress = %+v, want %+v", p, want)
	}
	rows[3].State = "done"
	if p := guideProgressOf(rows); !p.Live || p.MustHaveDone != 5 {
		t.Errorf("progress with everything done = %+v", p)
	}
}

func TestGuidePyStripAndTruncate(t *testing.T) {
	if got := guidePyStrip("\x1c  a b　\n"); got != "a b" {
		t.Errorf("guidePyStrip = %q", got)
	}
	if got := guideTruncate("žluťoučký", 4); got != "žluť" {
		t.Errorf("guideTruncate = %q", got)
	}
}

func TestGuideDataLayer(t *testing.T) {
	pool := guideTestPool(t)
	ctx := context.Background()
	s := guideTestServer(pool, nil)
	owner := guideSeedUser(t, pool, "host1", "host")
	apt := guideSeedApartment(t, pool, owner, "Flat 1")
	now := guideStamp(guideTestNow)

	a := &guideApartment{ID: apt, CheckinInfo: "  Ring the bell  ", CheckoutInfo: ""}
	for i := 0; i < 2; i++ { // twice: the second run adds nothing
		if err := s.ensureDefaults(ctx, a, now); err != nil {
			t.Fatal(err)
		}
	}
	rows, err := s.items(ctx, apt)
	if err != nil || len(rows) != len(guideDefaultKinds) {
		t.Fatalf("items = %d rows, err %v; want %d", len(rows), err, len(guideDefaultKinds))
	}
	if rows[0].Kind != "checkin" || rows[0].State != "check" || rows[0].Source != "legacy" || rows[0].Steps != "Ring the bell" {
		t.Errorf("legacy check-in text is not a draft: %+v", rows[0])
	}
	if rows[1].Kind != "keys" || rows[1].State != "missing" {
		t.Errorf("second card = %+v", rows[1])
	}
	if p, _ := s.progress(ctx, apt); p.Live || p.Cards != len(guideDefaultKinds) || p.Check != 1 {
		t.Errorf("progress = %+v", p)
	}

	// save: text makes it done and the host its source; no text makes it missing.
	checkin := rows[0]
	saved, err := s.save(ctx, apt, checkin.ID, map[string]string{"location": "Door 3", "visibility": "booked"}, now)
	if err != nil || saved.State != "done" || saved.Source != "host" || saved.Location != "Door 3" || saved.Visibility != "booked" {
		t.Fatalf("save = %+v, %v", saved, err)
	}
	saved, err = s.save(ctx, apt, checkin.ID, map[string]string{"location": "", "steps": ""}, now)
	if err != nil || saved.State != "missing" {
		t.Fatalf("save of empty text = %+v, %v", saved, err)
	}
	if _, err := s.save(ctx, apt, checkin.ID, map[string]string{"video_url": "http://x"}, now); guideErrKey(err) != "flash.error.guide_video_url" {
		t.Errorf("save with http video: %v", err)
	}
	if _, err := s.save(ctx, apt, 999999, nil, now); guideErrKey(err) != "flash.error.guide_no_such_item" {
		t.Errorf("save of a missing item: %v", err)
	}

	// custom cards
	if _, err := s.addCustom(ctx, apt, "nope", "x", now); guideErrKey(err) != "flash.error.guide_unknown_card" {
		t.Errorf("addCustom topic: %v", err)
	}
	if _, err := s.addCustom(ctx, apt, "area", "   ", now); guideErrKey(err) != "flash.error.guide_title_required" {
		t.Errorf("addCustom title: %v", err)
	}
	if _, err := s.addCustom(ctx, apt, "area", strings.Repeat("x", 121), now); guideErrKey(err) != "flash.error.guide_too_long" {
		t.Errorf("addCustom long: %v", err)
	}
	custom, err := s.addCustom(ctx, apt, "area", "  Bakery  ", now)
	if err != nil {
		t.Fatal(err)
	}
	item, _ := s.getItem(ctx, apt, custom)
	if item == nil || item.Kind != "custom" || item.Title != "Bakery" || item.SortOrder != int64(len(guideKinds)+1) || item.State != "missing" {
		t.Fatalf("custom card = %+v", item)
	}
	if _, err := s.save(ctx, apt, custom, map[string]string{"title": " "}, now); guideErrKey(err) != "flash.error.guide_title_required" {
		t.Errorf("custom card without a title: %v", err)
	}
	// skip and bring back: text the host never saved goes to check, saved text to done.
	if err := s.skip(ctx, apt, custom, true, now); err != nil {
		t.Fatal(err)
	}
	if item, _ = s.getItem(ctx, apt, custom); item.State != "skipped" {
		t.Errorf("skipped state = %q", item.State)
	}
	if err := s.skip(ctx, apt, custom, false, now); err != nil {
		t.Fatal(err)
	}
	if item, _ = s.getItem(ctx, apt, custom); item.State != "missing" {
		t.Errorf("unskipped empty card = %q", item.State)
	}
	guideTestExec(t, pool, `UPDATE guide_item SET steps = 'Open the gate', source = 'booking', state = 'skipped' WHERE id = $1`, custom)
	if err := s.skip(ctx, apt, custom, false, now); err != nil {
		t.Fatal(err)
	}
	if item, _ = s.getItem(ctx, apt, custom); item.State != "check" {
		t.Errorf("unskipped imported text = %q, want check", item.State)
	}
	// discard: only a draft
	if ok, err := s.discardDraft(ctx, apt, custom, now); err != nil || !ok {
		t.Fatalf("discardDraft = %v, %v", ok, err)
	}
	if item, _ = s.getItem(ctx, apt, custom); item.State != "missing" || item.Steps != "" || item.Source != "host" {
		t.Errorf("discarded card = %+v", item)
	}
	if ok, _ := s.discardDraft(ctx, apt, custom, now); ok {
		t.Error("discardDraft of a card that is not a draft returned true")
	}
	// only custom cards are deleted
	if ok, _ := s.deleteCustom(ctx, apt, checkin.ID); ok {
		t.Error("deleteCustom removed a built-in card")
	}
	if ok, err := s.deleteCustom(ctx, apt, custom); err != nil || !ok {
		t.Errorf("deleteCustom = %v, %v", ok, err)
	}

	// another property's id never reads or changes this card
	other := guideSeedApartment(t, pool, owner, "Flat 2")
	if it, _ := s.getItem(ctx, other, checkin.ID); it != nil {
		t.Error("getItem returned a card of another property")
	}
	if _, err := s.save(ctx, other, checkin.ID, map[string]string{"steps": "x"}, now); guideErrKey(err) != "flash.error.guide_no_such_item" {
		t.Errorf("save across properties: %v", err)
	}

	// QR token: created once, rotated on request
	t1, err := s.ensureToken(ctx, apt)
	if err != nil || len(t1) != 32 {
		t.Fatalf("ensureToken = %q, %v", t1, err)
	}
	if t2, _ := s.ensureToken(ctx, apt); t2 != t1 {
		t.Errorf("ensureToken replaced a token: %q vs %q", t2, t1)
	}
	if err := s.rotateToken(ctx, apt); err != nil {
		t.Fatal(err)
	}
	if t3, _ := s.currentToken(ctx, apt); t3 == t1 || len(t3) != 32 {
		t.Errorf("rotateToken left %q", t3)
	}

	// photos: listed per card of the property only
	guideTestExec(t, pool, `INSERT INTO guide_photo (item_id, file_name, sort_order, created_at) VALUES ($1, 'a.jpg', 2, $2), ($1, 'b.jpg', 1, $2)`, checkin.ID, now)
	ph, err := s.photos(ctx, apt, checkin.ID)
	if err != nil || len(ph) != 2 || ph[0].FileName != "b.jpg" {
		t.Fatalf("photos = %+v, %v", ph, err)
	}
	if ph, _ := s.photos(ctx, other, checkin.ID); len(ph) != 0 {
		t.Error("photos of a card of another property")
	}
	if p, _ := s.photo(ctx, other, checkin.ID, ph0ID(t, s, apt, checkin.ID)); p != nil {
		t.Error("photo across properties")
	}

	// quick answers: the next step is the first not seen
	if step, _ := s.nextStep(ctx, apt); step != "times" {
		t.Errorf("nextStep = %q", step)
	}
	guideTestExec(t, pool, `INSERT INTO guide_fact (apartment_id, fact, value, updated_at) VALUES ($1, 'step.times', 'seen', $2)`, apt, now)
	if step, _ := s.nextStep(ctx, apt); step != "rules" {
		t.Errorf("nextStep after times = %q", step)
	}
}

func ph0ID(t *testing.T, s *guideServer, apt, item int64) int64 {
	t.Helper()
	ph, err := s.photos(context.Background(), apt, item)
	if err != nil || len(ph) == 0 {
		t.Fatalf("photos: %v", err)
	}
	return ph[0].ID
}

// home: the owner's property is found; another workspace's, a missing and an
// archived one are a 404 JSON body.
func TestGuideHomeOwnership(t *testing.T) {
	pool := guideTestPool(t)
	s := guideTestServer(pool, nil)
	alice := guideSeedUser(t, pool, "alice", "host")
	bob := guideSeedUser(t, pool, "bob", "host")
	mine := guideSeedApartment(t, pool, alice, "Mine")
	archived := guideSeedApartment(t, pool, alice, "Old")
	guideTestExec(t, pool, `UPDATE apartment SET archived_at = '2026-02-01T00:00:00+00:00' WHERE id = $1`, archived)
	try := func(workspace, apt int64) (*guideApartment, int) {
		r := httptest.NewRequest(http.MethodGet, "/", nil)
		w := httptest.NewRecorder()
		q := &guideReq{host: &session.Host{Workspace: session.Account{ID: workspace}}, apt: apt, r: r}
		a, ok := s.home(w, q)
		if ok {
			return a, 200
		}
		return nil, w.Code
	}
	if a, code := try(alice, mine); code != 200 || a.InternalName != "Mine" {
		t.Errorf("own property: %v %d", a, code)
	}
	for name, c := range map[string][2]int64{"foreign": {bob, mine}, "archived": {alice, archived}, "missing": {alice, 424242}} {
		if _, code := try(c[0], c[1]); code != 404 {
			t.Errorf("%s property: status %d, want 404", name, code)
		}
	}
}
