package main

import (
	"context"
	"strings"
	"testing"
)

// The kind is registered with its 5-minute interval, and the factory builds with a nil pool.
func TestDoorCodesJobIsRegistered(t *testing.T) {
	if goIntervals["door_codes"] != 5 {
		t.Fatalf("interval %d", goIntervals["door_codes"])
	}
	if _, ok := goHandlers(nil)["door_codes"]; !ok {
		t.Fatal("door_codes is not registered")
	}
	if _, err := parseGoKinds("door_codes"); err != nil {
		t.Fatalf("parseGoKinds: %v", err)
	}
}

// Off by default: the handler returns zero without touching the pool (nil here).
func TestDoorCodesJobOffDoesNothing(t *testing.T) {
	t.Setenv("UBYHOST_DOOR_CODES", "")
	n, err := doorCodesHandler(nil)(context.Background())
	if n != 0 || err != nil {
		t.Fatalf("off: n=%d err=%v", n, err)
	}
}

// On with a nil pool: the wiring refuses, and the error says why. Nothing panics.
func TestDoorCodesJobOnWithoutPoolFails(t *testing.T) {
	t.Setenv("UBYHOST_DOOR_CODES", "1")
	_, err := doorCodesHandler(nil)(context.Background())
	if err == nil || !strings.Contains(err.Error(), "no database pool") {
		t.Fatalf("on without pool: %v", err)
	}
}

// The job builds nothing without a pool: the error says why, and nothing panics.
func TestDoorCodesWiringNeedsPool(t *testing.T) {
	job, err := newDoorCodesJob(nil)
	if job != nil || err == nil || !strings.Contains(err.Error(), "no database pool") {
		t.Fatalf("wiring without a pool: %v %v", job, err)
	}
}

func TestDoorCodesOnSwitch(t *testing.T) {
	for _, v := range []string{"1", "true", "yes"} {
		if !doorCodesOn(v) {
			t.Fatalf("%q must be on", v)
		}
	}
	for _, v := range []string{"", "0", "TRUE", "on"} {
		if doorCodesOn(v) {
			t.Fatalf("%q must be off", v)
		}
	}
}
