package invoices

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestICOOK(t *testing.T) {
	// 27082440 is a real, valid IČO (mod-11 check digit 0); 12345678 is not.
	for ico, want := range map[string]bool{"27082440": true, "25596641": true, "12345678": false, "1234567": false, "123456789": false, "2708244a": false, "": false, " 27082440 ": true} {
		if got := icoOK(ico); got != want {
			t.Errorf("%q: %v want %v", ico, got, want)
		}
	}
}

func TestMapAresPayload(t *testing.T) {
	data := mapAresPayload(map[string]any{
		"obchodniJmeno": " Firma s.r.o. ", "dic": "CZ27082440",
		"sidlo": map[string]any{"textovaAdresa": "Ulice 12/3a, 110 00 Praha", "nazevUlice": "Ulice", "cisloDomovni": jn("12"), "cisloOrientacni": jn("3"),
			"cisloOrientacniPismeno": "a", "nazevObce": "Praha", "psc": jn("11000")},
		"seznamRegistraci": map[string]any{"stavZdrojeDph": "aktivni"},
		"dalsiUdaje":       []any{map[string]any{"datovyZdroj": "rzp", "spisovaZnacka": "X"}, map[string]any{"datovyZdroj": "VR", "spisovaZnacka": " C 12345/MSPH "}},
	})
	want := aresData{Name: "Firma s.r.o.", Seat: "Ulice 12/3a, 110 00 Praha", Street: "Ulice 12/3a", City: "Praha", Zip: "11000", Country: "CZE", DIC: "CZ27082440",
		VATPayer: true, RegistryEntry: "spisová značka C 12345 vedená u Městského soudu v Praze"}
	if data != want {
		t.Fatalf("got %+v\nwant %+v", data, want)
	}
	// a short PSČ is padded, only the house number gives "Ulice 5", no street gives ""
	data = mapAresPayload(map[string]any{"obchodniJmeno": "X", "sidlo": map[string]any{"nazevUlice": "Ulice", "cisloDomovni": jn("5"), "psc": jn("1100")}})
	if data.Zip != "01100" || data.Street != "Ulice 5" || data.DIC != "" || data.VATPayer || data.RegistryEntry != "" {
		t.Errorf("%+v", data)
	}
	if mapAresPayload(map[string]any{"obchodniJmeno": "X", "sidlo": map[string]any{"cisloDomovni": jn("5")}}).Street != "" {
		t.Error("no street name, no street")
	}
	if formatRegistryMark("C 1/ZZZZ") != "C 1/ZZZZ" || formatRegistryMark("C 1") != "C 1" || formatRegistryMark("  ") != "" {
		t.Error("registry mark")
	}
}

func jn(s string) any { return json.Number(s) }

// fakeAres serves one register entry and counts the requests.
func fakeAres(t *testing.T) (*int32, func()) {
	t.Helper()
	var hits int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&hits, 1)
		if r.Header.Get("User-Agent") != "UbyHost" {
			t.Errorf("user agent %q", r.Header.Get("User-Agent"))
		}
		switch {
		case strings.HasSuffix(r.URL.Path, "/27082440"):
			_, _ = w.Write([]byte(`{"obchodniJmeno":"Firma s.r.o.","dic":"CZ27082440","sidlo":{"textovaAdresa":"Ulice 12, Praha","nazevUlice":"Ulice","cisloDomovni":12,"nazevObce":"Praha","psc":11000}}`))
		case strings.HasSuffix(r.URL.Path, "/25596641"):
			http.NotFound(w, r)
		default:
			http.Error(w, "boom", http.StatusInternalServerError)
		}
	}))
	oldURL, oldClient := aresURL, aresClient
	aresURL, aresClient = srv.URL+"/%s", srv.Client()
	aresMu.Lock()
	aresCache = map[string]aresCacheEntry{}
	aresMu.Unlock()
	return &hits, func() { srv.Close(); aresURL, aresClient = oldURL, oldClient }
}

func TestAresLookupCachesAndFailsQuietly(t *testing.T) {
	hits, stop := fakeAres(t)
	defer stop()
	ctx := context.Background()
	now := time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)
	if d := aresLookup(ctx, "27082440", now); d == nil || d.Name != "Firma s.r.o." || d.Zip != "11000" || d.Street != "Ulice 12" {
		t.Fatalf("lookup: %+v", d)
	}
	aresLookup(ctx, "27082440", now.Add(time.Hour))
	if *hits != 1 {
		t.Errorf("a second lookup inside 24 hours is cached: %d requests", *hits)
	}
	aresLookup(ctx, "27082440", now.Add(25*time.Hour))
	if *hits != 2 {
		t.Errorf("after 24 hours it asks again: %d", *hits)
	}
	if aresLookup(ctx, "25596641", now) != nil || aresLookup(ctx, "25596641", now) != nil || *hits != 3 {
		t.Errorf("a 404 is cached as absent: %d requests", *hits)
	}
	if aresLookup(ctx, "12345678", now) != nil || *hits != 3 {
		t.Error("an invalid IČO never leaves the server")
	}
}
