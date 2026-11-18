package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestPropertySettingsAllRoutesRegistered lists every route of the property
// settings thread (briefs 1300-1302, 1520-1524, 1700-1704) and the wizard POST
// that shares apartment paths. Each must reach its own Go pattern on newMux; a
// missing or shadowed route falls through and fails the test.
func TestPropertySettingsAllRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	const id = "130201"
	const entityID = "42"
	const alertID = "9"
	const feedID = "3"
	cases := []struct{ method, path, want string }{
		// 1301 pages
		{http.MethodGet, "/guide", "GET /guide"},
		{http.MethodGet, "/guest-links", "GET /guest-links"},
		// 1302 lists
		{http.MethodGet, "/entities", "GET /entities"},
		{http.MethodGet, "/apartments", "GET /apartments"},
		// 1520 misc
		{http.MethodPost, "/alerts/" + alertID + "/dismiss", "POST /alerts/{id}/dismiss"},
		{http.MethodGet, "/smart-locks", "GET /smart-locks"},
		{http.MethodGet, "/menu", "GET /menu"},
		// 1521 sync
		{http.MethodPost, "/sync", "POST /sync"},
		// 1522 entities
		{http.MethodPost, "/entities", "POST /entities"},
		{http.MethodPost, "/entities/" + entityID, "POST /entities/{id}"},
		// 1524 invoice details
		{http.MethodPost, "/entities/" + entityID + "/invoice", "POST /entities/{id}/invoice"},
		// entity and apartment archive posts (1300 Register)
		{http.MethodPost, "/entities/" + entityID + "/archive", "POST /entities/{id}/archive"},
		{http.MethodPost, "/entities/" + entityID + "/unarchive", "POST /entities/{id}/unarchive"},
		{http.MethodPost, "/entities/" + entityID + "/delete", "POST /entities/{id}/delete"},
		{http.MethodPost, "/apartments/" + id + "/archive", "POST /apartments/{id}/archive"},
		{http.MethodPost, "/apartments/" + id + "/unarchive", "POST /apartments/{id}/unarchive"},
		{http.MethodPost, "/apartments/" + id + "/regenerate-pin", "POST /apartments/{id}/regenerate-pin"},
		{http.MethodPost, "/apartments/" + id + "/regenerate-link", "POST /apartments/{id}/regenerate-link"},
		{http.MethodPost, "/feeds/" + feedID + "/delete", "POST /feeds/{id}/delete"},
		// 1700 apartment new, create, ruian
		{http.MethodGet, "/apartments/new", "GET /apartments/new"},
		{http.MethodPost, "/apartments", "POST /apartments"},
		{http.MethodGet, "/apartments/ruian-suggest", "GET /apartments/ruian-suggest"},
		// 1701 detail
		{http.MethodGet, "/apartments/" + id, "GET /apartments/{id}"},
		// 1702 door-codes; 1702c update; 1703 small posts
		{http.MethodPost, "/apartments/" + id + "/door-codes", "POST /apartments/{id}/door-codes"},
		{http.MethodPost, "/apartments/" + id, "POST /apartments/{id}"},
		{http.MethodPost, "/apartments/" + id + "/automation-timing", "POST /apartments/{id}/automation-timing"},
		{http.MethodPost, "/apartments/" + id + "/feeds", "POST /apartments/{id}/feeds"},
		{http.MethodPost, "/apartments/" + id + "/test-connection", "POST /apartments/{id}/test-connection"},
		{http.MethodPost, "/apartments/" + id + "/police-letter", "POST /apartments/{id}/police-letter"},
		{http.MethodPost, "/apartments/" + id + "/refresh-codelists", "POST /apartments/{id}/refresh-codelists"},
		// 1704a housebook
		{http.MethodGet, "/housebook", "GET /housebook"},
		// 1704b settings pages (forms still post elsewhere; these GETs are in scope)
		{http.MethodGet, "/settings", "GET /settings"},
		{http.MethodGet, "/settings/account", "GET /settings/account"},
		{http.MethodGet, "/settings/data", "GET /settings/data"},
		{http.MethodGet, "/settings/technical", "GET /settings/technical"},
		{http.MethodGet, "/settings/help", "GET /settings/help"},
		{http.MethodGet, "/settings/archived", "GET /settings/archived"},
		{http.MethodPost, "/settings/purge-expired", "POST /settings/purge-expired"},
		{http.MethodPost, "/settings/privacy/ad-consent", "POST /settings/privacy/ad-consent"},
		// 1704c security and phone
		{http.MethodGet, "/settings/security", "GET /settings/security"},
		{http.MethodGet, "/settings/phone", "GET /settings/phone"},
		// onboarding wizard POST (1602); GET steps stay wave 7
		{http.MethodPost, "/apartments/" + id + "/setup", "POST /apartments/{id}/setup"},
	}
	if len(cases) != 42 {
		t.Fatalf("%d cases, want 42 property-settings routes", len(cases))
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.want {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.want)
		}
	}
}
