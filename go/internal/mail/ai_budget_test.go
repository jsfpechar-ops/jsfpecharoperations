package mail

import (
	"strings"
	"testing"
)

func TestAIBudgetMailGolden(t *testing.T) {
	got := BuildAIBudget("https://public.example", "https://app.example", "operator@example.test", "guide_import", "2026-01", 8, 10)
	wantSubject := "AI budget 80% spent: guide_import"
	wantText := "guide_import has spent $8.00 of its $10.00 budget for 2026-01. At 100% it switches off until the 1st.\n\nOpen Operations: https://app.example/admin/operations\n\n--\nUbyHost\nQuestions: operator@example.test"
	if got.Subject != wantSubject || got.Text != wantText {
		t.Fatalf("copy mismatch subject=%q text=%q", got.Subject, got.Text)
	}
	for _, fragment := range []string{`<html lang="en">`, `<title>` + wantSubject + `</title>`, "guide_import has spent $8.00", `href="https://app.example/admin/operations"`, "Questions: operator@example.test"} {
		if !strings.Contains(got.HTML, fragment) {
			t.Fatalf("HTML missing %q", fragment)
		}
	}
	zeroCap := BuildAIBudget("https://public.example", "https://app.example", "operator@example.test", "feature", "2026-01", 1, 0)
	if !strings.HasPrefix(zeroCap.Subject, "AI budget 100%") {
		t.Fatalf("zero cap subject=%q", zeroCap.Subject)
	}
}
