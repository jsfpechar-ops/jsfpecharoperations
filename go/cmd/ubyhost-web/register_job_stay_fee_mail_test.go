package main

import (
	"context"
	"errors"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeemail"
)

// Without a renderer the registered handler fails at once. The pool is nil,
// so any read or write would panic: nothing is touched.
func TestStayFeeMailNeedsRenderer(t *testing.T) {
	if goIntervals["stay_fee_mail"] != 24*60 {
		t.Fatalf("interval %d", goIntervals["stay_fee_mail"])
	}
	h, ok := goHandlers(nil)["stay_fee_mail"]
	if !ok {
		t.Fatal("stay_fee_mail is not registered")
	}
	n, err := h(context.Background())
	if n != 0 || !errors.Is(err, stayfeemail.ErrNoRenderer) {
		t.Fatalf("got %d, %v", n, err)
	}
	if _, err := parseGoKinds("stay_fee_mail"); err != nil {
		t.Fatalf("parseGoKinds: %v", err)
	}
}
