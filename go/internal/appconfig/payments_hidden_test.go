package appconfig

import (
	"testing"
)

func getenvOn(k string) string {
	if k == "UBYHOST_PAYMENTS_HIDDEN" {
		return "1"
	}
	return ""
}

func getenvOff(k string) string { return "" }

func TestPaymentsHidden(t *testing.T) {
	for _, v := range []string{"1", "true", "YES", " yes "} {
		getenv := func(k string) string {
			if k == "UBYHOST_PAYMENTS_HIDDEN" {
				return v
			}
			return ""
		}
		if !PaymentsHidden(getenv) {
			t.Fatalf("PaymentsHidden(%q) false", v)
		}
	}
	if PaymentsHidden(getenvOff) || PaymentsHidden(func(string) string { return "0" }) {
		t.Fatal("PaymentsHidden off should be false")
	}
}

func TestPaymentsHostPathBlockedHiddenOff(t *testing.T) {
	for _, path := range []string{"/payments", "/booking-sites", "/payments/new"} {
		if PaymentsHostPathBlocked(path, getenvOff) {
			t.Fatalf("%s blocked while hidden off", path)
		}
	}
}

func TestPaymentsHostPathBlockedHiddenOn(t *testing.T) {
	blocked := []string{
		"/payments", "/payments/new", "/payments/consent", "/booking-sites",
		"/payments/connect/start", "/payments/qr/42.png",
		"/apartments/12/booking-site", "/apartments/12/booking-site/edit",
	}
	for _, path := range blocked {
		if !PaymentsHostPathBlocked(path, getenvOn) {
			t.Fatalf("%s should be blocked", path)
		}
	}
	open := []string{
		"/webhooks/stripe", "/p/slug", "/p/slug/book", "/pay/9/abc.png",
		"/reservations", "/guide",
	}
	for _, path := range open {
		if PaymentsHostPathBlocked(path, getenvOn) {
			t.Fatalf("%s should stay open", path)
		}
	}
}
