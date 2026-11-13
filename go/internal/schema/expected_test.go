package schema

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadExpected(t *testing.T) {
	e, err := LoadExpected()
	if err != nil {
		t.Fatal(err)
	}
	if e.ExpectedVersion < 45 || len(e.Tables["schema_migrations"]) != 3 || len(e.Triggers) != 6 || len(e.Indexes) == 0 {
		t.Fatalf("unexpected snapshot: version %d, %d tables, %d indexes, %d triggers",
			e.ExpectedVersion, len(e.Tables), len(e.Indexes), len(e.Triggers))
	}
}

func fakeExpected() Expected {
	return Expected{
		ExpectedVersion: 3,
		Tables: map[string][]Column{
			"a": {{Name: "id", Type: "bigint", NotNull: true}, {Name: "note", Type: "text"}},
			"b": {{Name: "id", Type: "bigint", NotNull: true}},
		},
		Indexes:  []string{"a_note"},
		Triggers: []string{"t1"},
	}
}

func fakeActual() Actual {
	return Actual{
		Version: 3,
		Tables: map[string][]Column{
			"a":     {{Name: "id", Type: "bigint", NotNull: true}, {Name: "note", Type: "text"}},
			"b":     {{Name: "id", Type: "bigint", NotNull: true}},
			"extra": {{Name: "x", Type: "text"}},
		},
		Indexes:  map[string]bool{"a_note": true, "a_pkey": true},
		Triggers: map[string]bool{"t1": true},
	}
}

func TestCompareCurrent(t *testing.T) {
	s := Compare(fakeExpected(), fakeActual())
	if !s.Current || s.ExtraTables != 1 || s.ActualTables != 3 || s.ExpectedTables != 2 {
		t.Fatalf("want current with one extra table, got %+v", s)
	}
}

func TestCompareFailures(t *testing.T) {
	cases := map[string]func(*Expected, *Actual){
		"version":         func(e *Expected, a *Actual) { a.Version = 2 },
		"missing table":   func(e *Expected, a *Actual) { delete(a.Tables, "b") },
		"missing column":  func(e *Expected, a *Actual) { a.Tables["a"] = a.Tables["a"][:1] },
		"column order":    func(e *Expected, a *Actual) { a.Tables["a"] = []Column{a.Tables["a"][1], a.Tables["a"][0]} },
		"column type":     func(e *Expected, a *Actual) { a.Tables["b"] = []Column{{Name: "id", Type: "integer", NotNull: true}} },
		"nullable":        func(e *Expected, a *Actual) { a.Tables["b"] = []Column{{Name: "id", Type: "bigint"}} },
		"not null":        func(e *Expected, a *Actual) { a.Tables["a"][1].NotNull = true },
		"unmapped type":   func(e *Expected, a *Actual) { e.Tables["b"] = []Column{{Name: "id", Type: "", NotNull: true}} },
		"missing index":   func(e *Expected, a *Actual) { delete(a.Indexes, "a_note") },
		"missing trigger": func(e *Expected, a *Actual) { delete(a.Triggers, "t1") },
		"extra trigger":   func(e *Expected, a *Actual) { a.Triggers["t2"] = true },
	}
	for name, mutate := range cases {
		e, a := fakeExpected(), fakeActual()
		a.Tables["a"] = append([]Column(nil), a.Tables["a"]...)
		mutate(&e, &a)
		if s := Compare(e, a); s.Current {
			t.Errorf("%s: want not current, got %+v", name, s)
		}
	}
}

func TestCheckAuthority(t *testing.T) {
	url := "postgresql:///ubyhost?host=/var/run/postgresql"
	fp, err := Fingerprint(url)
	if err != nil {
		t.Fatal(err)
	}
	good := `{"backend":"postgresql","database":"ubyhost","format_version":1,"schema":"public","target_fingerprint":"` + fp + `"}`
	cases := []struct {
		name, marker, database, want string
	}{
		{"no marker", "", "ubyhost", ""},
		{"good", good, "ubyhost", ""},
		{"other database", good, "other", "does not match the durable authority marker"},
		{"unreadable", "{", "ubyhost", "unreadable"},
		{"bad format", strings.Replace(good, `"format_version":1`, `"format_version":2`, 1), "ubyhost", "invalid"},
		{"bad backend", strings.Replace(good, `"backend":"postgresql"`, `"backend":"sqlite"`, 1), "ubyhost", "invalid"},
		{"bad schema", strings.Replace(good, `"schema":"public"`, `"schema":"x"`, 1), "ubyhost", "does not match"},
		{"bad fingerprint", strings.Replace(good, fp, strings.Repeat("0", 64), 1), "ubyhost", "UBYHOST_DATABASE_URL does not match"},
	}
	for _, c := range cases {
		dir := t.TempDir()
		if c.marker != "" {
			if err := os.WriteFile(filepath.Join(dir, AuthorityFile), []byte(c.marker), 0o600); err != nil {
				t.Fatal(err)
			}
		}
		err := CheckAuthority(dir, url, c.database)
		if c.want == "" && err != nil {
			t.Errorf("%s: unexpected %v", c.name, err)
		}
		if c.want != "" && (err == nil || !strings.Contains(err.Error(), c.want)) {
			t.Errorf("%s: want %q, got %v", c.name, c.want, err)
		}
	}
}

func TestRunRefusesBeforeConnecting(t *testing.T) {
	base := Config{Action: "check", ExpectDatabase: "ubyhost", DatabaseURL: "postgresql:///ubyhost?host=/nonexistent",
		DataDir: t.TempDir(), MigrationsDir: filepath.Join("..", "..", "..", "App", "migrations_pg")}
	cases := map[string]func(*Config){
		"unknown action": func(c *Config) { c.Action = "drop" },
		"no expect":      func(c *Config) { c.ExpectDatabase = "" },
		"no url":         func(c *Config) { c.DatabaseURL = "" },
		"no data dir":    func(c *Config) { c.DataDir = "" },
		"bad url":        func(c *Config) { c.DatabaseURL = "postgresql://db.example.com/x" },
		"no goose files": func(c *Config) { c.MigrationsDir = t.TempDir() },
	}
	for name, mutate := range cases {
		c := base
		mutate(&c)
		if err := Run(t.Context(), c, os.Stdout); err == nil {
			t.Errorf("%s: want an error", name)
		}
	}
}
