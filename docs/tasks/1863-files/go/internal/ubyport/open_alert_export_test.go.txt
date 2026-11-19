package ubyport

import (
	"context"
	"testing"
)

func TestOpenAlertWrapsUnexported(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	key := "open_alert_export:1"
	check := func(step string, wantOpen bool) {
		got, gerr := OpenAlert(ctx, pool, key)
		want, werr := openAlert(ctx, pool, key)
		if gerr != nil || werr != nil || got != want || got != wantOpen {
			t.Fatalf("%s: wrapper %v %v, unexported %v %v", step, got, gerr, want, werr)
		}
	}
	check("none", false)
	if err := RaiseAlert(ctx, pool, "warning", "open_alert_export", "message", "", key, nil, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	check("raised", true)
	if err := ResolveAlert(ctx, pool, key); err != nil {
		t.Fatal(err)
	}
	check("resolved", false)
}
