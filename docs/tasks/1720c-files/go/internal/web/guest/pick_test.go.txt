package guest

import (
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

func TestPickNightsLabelEnglish(t *testing.T) {
	got := pickNightsLabel("en", "2026-06-10", "2026-06-13")
	if got != "3 nights" {
		t.Fatalf("got %q", got)
	}
	got = pickNightsLabel("en", "2026-06-10", "2026-06-11")
	if got != "1 night" {
		t.Fatalf("one night %q", got)
	}
}

func TestPickNightsLabelCzech(t *testing.T) {
	got := pickNightsLabel("cs", "2026-06-10", "2026-06-12")
	if got != "2 noci" {
		t.Fatalf("got %q", got)
	}
}

func TestGuestPinRequiredEnv(t *testing.T) {
 getenv := func(k string) string {
  if k == "UBYHOST_GUEST_PIN" {
   return "no"
  }
  return ""
 }
	if guestPinRequired(getenv) {
		t.Fatal("expected off")
	}
}

func TestPragueTodayPickStable(t *testing.T) {
	if _, ok := validation.ParseISODate("2026-06-15"); !ok {
		t.Fatal("parse")
	}
}