package main

import "testing"

func TestParseGoKindsPush(t *testing.T) {
	kinds, err := parseGoKinds("push")
	if err != nil || len(kinds) != 1 || kinds[0] != "push" {
		t.Fatalf("parseGoKinds(push) = %v, %v", kinds, err)
	}
	if goIntervals["push"] != 1 {
		t.Fatalf("push interval %d, want 1 minute", goIntervals["push"])
	}
}
