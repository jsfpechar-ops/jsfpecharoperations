package guideimport

import "testing"

func TestFilterTrimmed(t *testing.T) {
	in := Trimmed{
		{Key: "title", Value: "Welcome"},
		{Key: "text", Value: "Door code 4827."},
		{Key: "source", Value: "url"},
	}
	out, n := FilterTrimmed(in)
	if n != 1 {
		t.Fatalf("count got %d want 1", n)
	}
	if got, _ := out.Get("text").(string); got != "Door code [left out]." {
		t.Fatalf("text %q", got)
	}
	if got, _ := out.Get("title").(string); got != "Welcome" {
		t.Fatalf("title %q", got)
	}
	if got, _ := out.Get("source").(string); got != "url" {
		t.Fatalf("source %q", got)
	}
}

func TestFilterTrimmedSkipsNonStrings(t *testing.T) {
	in := Trimmed{
		{Key: "tags", Value: []string{"Door code 1234", "plain"}},
		{Key: "n", Value: 42},
	}
	out, n := FilterTrimmed(in)
	if n != 0 {
		t.Fatalf("count %d", n)
	}
	if tags, _ := out.Get("tags").([]string); len(tags) != 2 || tags[0] != "Door code 1234" {
		t.Fatalf("tags unchanged %+v", tags)
	}
}

func TestTrimmedHasText(t *testing.T) {
	if !trimmedHasText(Trimmed{{Key: "text", Value: " hello "}}) {
		t.Fatal("string field")
	}
	if trimmedHasText(Trimmed{{Key: "source", Value: "only meta"}}) {
		t.Fatal("source alone is not content")
	}
	if !trimmedHasText(Trimmed{{Key: "steps", Value: []string{"", "wifi name"}}}) {
		t.Fatal("list item")
	}
	if trimmedHasText(Trimmed{{Key: "title", Value: "   "}}) {
		t.Fatal("blank string")
	}
}

func TestNullIfZero(t *testing.T) {
	if nullIfZero(0) != nil {
		t.Fatal("zero is nil")
	}
	if v, ok := nullIfZero(3).(int); !ok || v != 3 {
		t.Fatalf("nonzero %v", nullIfZero(3))
	}
}
