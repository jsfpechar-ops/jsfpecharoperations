package ai

// Tests of leon_facts.go: the pure state functions against the real Python
// (testdata/leon_golden.json, written by App/scripts/leon_golden.py) and the SQL
// reads on PostgreSQL.

import (
	"context"
	"encoding/json"
	"os"
	"reflect"
	"testing"
	"time"
)

type leonGolden struct {
	HostState []struct {
		Enabled int     `json:"enabled"`
		Version *string `json:"version"`
		Live    bool    `json:"live"`
		Out     string  `json:"out"`
	} `json:"host_state"`
	SetupStep []struct {
		Enabled       int     `json:"enabled"`
		Version       *string `json:"version"`
		Live          bool    `json:"live"`
		Checking      int     `json:"checking"`
		ImportStarted bool    `json:"import_started"`
		ImportOn      bool    `json:"import_on"`
		Out           string  `json:"out"`
	} `json:"setup_step"`
	Progress []struct {
		Name string `json:"name"`
		Rows []struct {
			ID         int64  `json:"id"`
			Kind       string `json:"kind"`
			State      string `json:"state"`
			Topic      string `json:"topic"`
			Title      string `json:"title"`
			SortOrder  int64  `json:"sort_order"`
			Visibility string `json:"visibility"`
		} `json:"rows"`
		Order    []int64 `json:"order"`
		Progress struct {
			Done, Total, Answered, Cards, Check int
			MustHaveDone                        int  `json:"must_have_done"`
			MustHaveTotal                       int  `json:"must_have_total"`
			Live                                bool `json:"live"`
		} `json:"progress"`
		OpenCards []int64 `json:"open_cards"`
	} `json:"progress"`
	Constants map[string]any               `json:"constants"`
	I18n      map[string]map[string]string `json:"i18n"`
	Param     string                       `json:"i18n_param"`
}

func leonLoadGolden(t *testing.T) leonGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/leon_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g leonGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func leonApt(enabled int, version *string) LeonApartment {
	a := LeonApartment{ID: 1, Enabled: enabled != 0}
	if version != nil {
		a.TermsVersion = *version
	}
	return a
}

func TestLeonStateMatchesPython(t *testing.T) {
	g := leonLoadGolden(t)
	if len(g.HostState) != 16 || len(g.SetupStep) != 48 {
		t.Fatalf("golden has %d and %d cases", len(g.HostState), len(g.SetupStep))
	}
	for _, c := range g.HostState {
		if got := LeonHostState(leonApt(c.Enabled, c.Version), c.Live); got != c.Out {
			t.Errorf("host_state(%d, %v, %v) = %q, Python %q", c.Enabled, c.Version, c.Live, got, c.Out)
		}
	}
	for _, c := range g.SetupStep {
		if got := LeonSetupStep(leonApt(c.Enabled, c.Version), c.Live, c.Checking, c.ImportStarted, c.ImportOn); got != c.Out {
			t.Errorf("setup_step(%+v) = %q, Python %q", c, got, c.Out)
		}
	}
	if LeonTermsVersion() != g.Constants["terms_version"] || !reflect.DeepEqual(LeonSetupSteps(), []string{"switch_on", "import", "cards", "try"}) ||
		float64(leonTryMax) != g.Constants["try_max"] || float64(leonTryWindow) != g.Constants["try_window"] {
		t.Error("constants differ from Python")
	}
	for lang, keys := range g.I18n {
		for k, want := range keys {
			if got := leonStrings.T(lang, k, nil); got != want {
				t.Errorf("i18n %s %s = %q, Python %q", lang, k, got, want)
			}
		}
	}
	if got := leonStrings.T("en", "leon_setup.title", map[string]any{"name": "Flat A"}); got != g.Param {
		t.Errorf("title %q, Python %q", got, g.Param)
	}
}

func TestLeonProgressMatchesPython(t *testing.T) {
	for _, c := range leonLoadGolden(t).Progress {
		var items []LeonItem
		for _, r := range c.Rows {
			items = append(items, LeonItem{ID: r.ID, Kind: r.Kind, State: r.State, Topic: r.Topic, Title: r.Title, SortOrder: r.SortOrder, Visibility: r.Visibility})
		}
		items = LeonOrder(items)
		var order []int64
		for _, it := range items {
			order = append(order, it.ID)
		}
		if len(order) == 0 {
			order = nil
		}
		want := c.Order
		if len(want) == 0 {
			want = nil
		}
		if !reflect.DeepEqual(order, want) {
			t.Errorf("%s: order %v, Python %v", c.Name, order, want)
		}
		p, w := LeonProgressOf(items), c.Progress
		if p.Done != w.Done || p.Total != w.Total || p.Answered != w.Answered || p.Cards != w.Cards || p.Check != w.Check ||
			p.MustHaveDone != w.MustHaveDone || p.MustHaveTotal != w.MustHaveTotal || p.Live != w.Live {
			t.Errorf("%s: progress %+v, Python %+v", c.Name, p, w)
		}
		var open []int64
		for _, it := range LeonOpenCards(items) {
			open = append(open, it.ID)
		}
		wantOpen := c.OpenCards
		if len(open) == 0 {
			open = nil
		}
		if len(wantOpen) == 0 {
			wantOpen = nil
		}
		if !reflect.DeepEqual(open, wantOpen) {
			t.Errorf("%s: open cards %v, Python %v", c.Name, open, wantOpen)
		}
	}
}

func TestLeonReadsOnPostgres(t *testing.T) {
	pool := havelTestPool(t)
	ctx := context.Background()
	env := havelMapEnv(map[string]string{"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k", "UBYHOST_BILLING_ENABLED": "1", "UBYHOST_APIFY_TOKEN": " tok "})
	store := LeonStore{HavelStore{Pool: pool, Env: env}}
	havelExec(t, pool,
		`INSERT INTO user_account (id, username, password_hash, role, created_at, email) VALUES (1, 'a', 'x', 'host', '2026-01-01', 'a@example.test'), (2, 'b', 'x', 'host', '2026-01-01', 'b@example.test')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, active, leon_enabled, leon_terms_version, legal_entity_id, created_at) VALUES
		 (11, 1, 'Flat A', 1, 1, '2026-10-25', NULL, '2026-01-01'), (12, 1, 'Archived', 1, 0, NULL, NULL, '2026-01-01'), (13, 2, 'Other', 1, 0, NULL, NULL, '2026-01-01')`,
		`UPDATE apartment SET archived_at = '2026-02-01' WHERE id = 12`)
	if a, err := store.Apartment(ctx, 1, 11); err != nil || a == nil || a.Name != "Flat A" || !a.Enabled || a.TermsVersion != "2026-10-25" || a.OwnerID != 1 {
		t.Fatalf("apartment: %+v %v", a, err)
	}
	for _, c := range [][2]int64{{1, 12}, {1, 13}, {2, 11}, {1, 99}} {
		if a, err := store.Apartment(ctx, c[0], c[1]); err != nil || a != nil {
			t.Errorf("apartment %v must not be found: %+v %v", c, a, err)
		}
	}
	apt, _ := store.Apartment(ctx, 1, 11)
	if ok, err := store.Offered(ctx, *apt); err != nil || !ok {
		t.Errorf("offered: %v %v", ok, err)
	}
	havelExec(t, pool, `INSERT INTO billing_account (owner_user_id, status, plan, updated_at) VALUES (1, 'paused', 'standard', '2026-01-01')`)
	if ok, _ := store.Offered(ctx, *apt); ok {
		t.Error("a paused plan does not get Leon")
	}
	havelExec(t, pool, `UPDATE billing_account SET status = 'active'`)
	if ok, _ := store.Offered(ctx, *apt); !ok {
		t.Error("an active plan gets Leon")
	}
	off := LeonStore{HavelStore{Pool: pool, Env: havelMapEnv(map[string]string{"UBYHOST_AI_FEATURES": "havel", "UBYHOST_ANTHROPIC_API_KEY": "k"})}}
	if ok, _ := off.Offered(ctx, *apt); ok {
		t.Error("the leon feature must be listed")
	}
	listed := LeonStore{HavelStore{Pool: pool, Env: havelMapEnv(map[string]string{"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k", "UBYHOST_AI_TEST_EMAILS": "b@example.test"})}}
	if ok, _ := listed.Offered(ctx, *apt); ok {
		t.Error("the owner must be on the test list")
	}

	// Cards, in guest order, with photo counts; progress and open cards.
	havelExec(t, pool,
		`INSERT INTO guide_item (id, apartment_id, topic, kind, title, state, visibility, source, sort_order, created_at, updated_at) VALUES
		 (1, 11, 'arrival', 'checkin', '', 'done', 'everyone', 'host', 0, 'x', 'x'),
		 (2, 11, 'wifi', 'wifi', '', 'check', 'everyone', 'booking', 0, 'x', 'x'),
		 (3, 11, 'area', 'custom', 'Pool', 'missing', 'booked', 'host', 5, 'x', 'x'),
		 (4, 11, 'heating', 'heating', '', 'missing', 'everyone', 'host', 0, 'x', 'x'),
		 (5, 13, 'wifi', 'wifi', '', 'done', 'everyone', 'host', 0, 'x', 'x')`)
	f, err := store.Facts(ctx, 11)
	if err != nil {
		t.Fatal(err)
	}
	var ids []int64
	for _, c := range f.OpenCards {
		ids = append(ids, c.ID)
	}
	if f.Live || f.Checking != 1 || !f.ImportOn || !reflect.DeepEqual(ids, []int64{2, 4}) || f.Drafts != 1 || f.Progress.Cards != 4 {
		t.Errorf("facts: %+v open %v", f, ids)
	}
	// Imports: the newest ten, a failed one does not use a source up.
	havelExec(t, pool,
		`INSERT INTO guide_import (apartment_id, source, url, status, error, created_at) VALUES
		 (11, 'booking', 'https://b.example/x', 'failed', 'merge boom', '2026-11-01T10:00:00+00:00'),
		 (11, 'airbnb', 'https://a.example/x', 'running', NULL, '2026-11-02T10:00:00+00:00')`)
	f, _ = store.Facts(ctx, 11)
	if !f.ImportBusy || !f.ImportStarted || !reflect.DeepEqual(f.Sources, []string{"booking"}) || len(f.Imports) != 2 || f.Imports[0].Source != "airbnb" || !f.Imports[1].MergeFailed() || f.Imports[0].CreatedDay() != "2026-11-02" {
		t.Errorf("imports: %+v", f)
	}
	havelExec(t, pool, `UPDATE guide_import SET status = 'done' WHERE source = 'airbnb'`, `UPDATE guide_import SET status = 'done' WHERE source = 'booking'`)
	f, _ = store.Facts(ctx, 11)
	if f.ImportBusy || len(f.Sources) != 0 {
		t.Errorf("both sources used: %+v", f)
	}
	if LeonImportOn(havelMapEnv(map[string]string{"UBYHOST_APIFY_TOKEN": "  "})) || LeonImportOn(havelMapEnv(nil)) {
		t.Error("no token, no import")
	}

	// The test-message allowance is per property and day.
	now := time.Date(2026, 11, 13, 12, 0, 0, 0, time.UTC)
	for i := 0; i < 3; i++ {
		_ = store.Record(ctx, "leon_try", "11", now)
	}
	_ = store.Record(ctx, "leon_try", "11", now.Add(-25*time.Hour))
	if left, err := store.TryLeft(ctx, 11, now); err != nil || left != 2 {
		t.Errorf("try left %d %v, want 2", left, err)
	}
}
