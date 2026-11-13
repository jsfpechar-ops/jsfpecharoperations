package main

import (
	"bytes"
	"reflect"
	"strings"
	"testing"
)

func TestMigrateArgs(t *testing.T) {
	cases := []struct {
		argv []string
		want []string
		ok   bool
	}{
		{[]string{"ubyhost-web"}, nil, false},
		{[]string{"ubyhost-web", "-test.v"}, nil, false},
		{[]string{"ubyhost-web", "serve", "migrate"}, nil, false},
		{[]string{"ubyhost-web", "migrate"}, []string{}, true},
		{[]string{"ubyhost-web", "migrate", "apply", "--expect-database", "ubyhost"}, []string{"apply", "--expect-database", "ubyhost"}, true},
	}
	for _, c := range cases {
		got, ok := migrateArgs(c.argv)
		if ok != c.ok || !reflect.DeepEqual(got, c.want) {
			t.Errorf("migrateArgs(%q) = %q, %v; want %q, %v", c.argv, got, ok, c.want, c.ok)
		}
	}
}

func TestRunMigrateUsage(t *testing.T) {
	env := func(string) string { return "" }
	for _, args := range [][]string{
		{},
		{"drop", "--expect-database", "ubyhost"},
		{"apply"},
		{"apply", "--expect-database"},
		{"apply", "--expect-database", ""},
		{"apply", "--expect-database", "ubyhost", "extra"},
		{"apply", "--bogus"},
		{"apply", "-expect-database", "ubyhost"},
		{"apply", "check", "--expect-database", "ubyhost"},
		{"--expect-database", "--expect-database", "ubyhost"},
		{"--expect-database", "ubyhost"},
	} {
		var out, errOut bytes.Buffer
		if code := runMigrate(args, env, &out, &errOut); code != 2 {
			t.Errorf("runMigrate(%q) = %d, want 2", args, code)
		}
		if !strings.Contains(errOut.String(), "usage: ubyhost-web migrate") {
			t.Errorf("runMigrate(%q) printed %q", args, errOut.String())
		}
	}
}

func TestRunMigrateFailsWithoutURL(t *testing.T) {
	var out, errOut bytes.Buffer
	code := runMigrate([]string{"check", "--expect-database", "ubyhost"}, func(string) string { return "" }, &out, &errOut)
	if code != 1 || !strings.Contains(errOut.String(), "PostgreSQL schema check failed: Set UBYHOST_DATABASE_URL") {
		t.Fatalf("code %d, stderr %q", code, errOut.String())
	}
}

func TestRunMigrateRedactsURL(t *testing.T) {
	url := "postgresql://u:secret@db.example.com/x"
	env := map[string]string{"UBYHOST_DATABASE_URL": url, "UBYHOST_DATA_DIR": t.TempDir(),
		"UBYHOST_MIGRATIONS_DIR": "../../../App/migrations_pg"}
	var out, errOut bytes.Buffer
	code := runMigrate([]string{"plan", "--expect-database=x"}, func(k string) string { return env[k] }, &out, &errOut)
	if code != 1 || strings.Contains(errOut.String(), "secret") || !strings.Contains(errOut.String(), "sslmode") {
		t.Fatalf("code %d, stderr %q", code, errOut.String())
	}
}

func TestParseMigrateArgsAnyOrder(t *testing.T) {
	for _, args := range [][]string{
		{"apply", "--expect-database", "ubyhost"},
		{"--expect-database", "ubyhost", "apply"},
		{"--expect-database=ubyhost", "apply"},
		{"apply", "--expect-database=ubyhost"},
		{"apply", "--expect-database", "other", "--expect-database", "ubyhost"},
	} {
		action, expect, ok := parseMigrateArgs(args)
		if !ok || action != "apply" || expect != "ubyhost" {
			t.Errorf("parseMigrateArgs(%q) = %q, %q, %v", args, action, expect, ok)
		}
	}
}
