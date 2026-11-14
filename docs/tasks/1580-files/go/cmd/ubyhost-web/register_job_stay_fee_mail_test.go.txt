package main

import (
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeepdf"
)

// The registered job has the hlášení renderer (brief 1580). The handler is
// not run here: with a nil pool it would touch the database.
func TestStayFeeMailHasRenderer(t *testing.T) {
	if goIntervals["stay_fee_mail"] != 24*60 {
		t.Fatalf("interval %d", goIntervals["stay_fee_mail"])
	}
	if _, ok := goHandlers(nil)["stay_fee_mail"]; !ok {
		t.Fatal("stay_fee_mail is not registered")
	}
	if _, ok := stayFeeRenderer.(stayfeepdf.Renderer); !ok {
		t.Fatalf("stayFeeRenderer is %T", stayFeeRenderer)
	}
	if _, err := parseGoKinds("stay_fee_mail"); err != nil {
		t.Fatalf("parseGoKinds: %v", err)
	}
}
