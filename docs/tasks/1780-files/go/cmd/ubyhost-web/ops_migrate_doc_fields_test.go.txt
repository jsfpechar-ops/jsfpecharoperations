package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestMigrateDocFieldsUsage(t *testing.T) {
	var errOut bytes.Buffer
	if got := runMigrateDocFields([]string{"--bad"}, nil, nil, &errOut); got != 2 {
		t.Fatalf("exit %d", got)
	}
	if !strings.Contains(errOut.String(), "usage:") {
		t.Fatal(errOut.String())
	}
}

func TestReconcileCodesUsage(t *testing.T) {
	var errOut bytes.Buffer
	if got := runReconcileCodes([]string{"--bad"}, nil, nil, &errOut); got != 2 {
		t.Fatalf("exit %d", got)
	}
}
