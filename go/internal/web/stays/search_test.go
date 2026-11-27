package stays

import (
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestParseParamsAndSearchSQL(t *testing.T) {
	today := time.Date(2026, 11, 26, 0, 0, 0, 0, time.UTC)
	p := ParseParams(url.Values{"q": {"  Novak_100%  "}}, today)
	if p.Query != "Novak_100%" {
		t.Fatalf("Query = %q, want Novak_100%%", p.Query)
	}
	sql, args := listSQL(7, p, "2026-11-26", nil)
	if !strings.Contains(sql, "ILIKE") || !strings.Contains(sql, `ESCAPE '\'`) {
		t.Fatalf("expected escaped ILIKE search clause, got %s", sql)
	}
	wantPat := `%Novak\_100\%%`
	found := false
	for _, a := range args {
		if s, ok := a.(string); ok && s == wantPat {
			found = true
		}
	}
	if !found {
		t.Fatalf("expected escaped pattern %q in args %#v", wantPat, args)
	}
}
