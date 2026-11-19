package ubyport

import (
	"context"
	"reflect"
	"strings"
	"testing"
)

// Pins codeAndTexts / StoreCodelist for country rows (App/app/codelists.py).
func TestStoreCountryCodelist(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	rows := []map[string]string{
		{"Kod3": "CZE", "TextKratkyCZ": "Česko", "TextKratkyENG": "Czechia", "Kod2": "CZ"},
		{"Kod2": "XX", "TextCZ": "Dlouhý", "TextENG": "Long"},
		{"Kod3": "", "Kod2": "SKIP", "TextCZ": "ignored"},
		{"Kod3": "   ", "TextCZ": "blank code"},
	}
	now := "2026-11-19T12:00:00+00:00"
	n, err := StoreCodelist(ctx, pool, CodelistCountries, rows, now)
	if err != nil || n != 2 {
		t.Fatalf("StoreCodelist: %d %v, want 2", n, err)
	}
	got, err := pool.Query(ctx, `SELECT code, text_cs, text_en, extra FROM codelist WHERE kind = $1 ORDER BY code`, CodelistCountries)
	if err != nil {
		t.Fatal(err)
	}
	defer got.Close()
	var lines []string
	for got.Next() {
		var code, cs, en, extra string
		if err := got.Scan(&code, &cs, &en, &extra); err != nil {
			t.Fatal(err)
		}
		lines = append(lines, strings.Join([]string{code, cs, en, extra}, "|"))
	}
	want := []string{
		"CZE|Česko|Czechia|CZ",
		"XX|Dlouhý|Long|XX",
	}
	if !reflect.DeepEqual(lines, want) {
		t.Errorf("rows:\n got %q\nwant %q", lines, want)
	}
}
