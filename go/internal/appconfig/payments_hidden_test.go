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

func getenvRetired(k string) string {
	if k == "UBYHOST_PAYMENTS_RETIRED" {
		return "1"
	}
	return ""
}

func TestPaymentsRetired(t *testing.T) {
	for _, v := range []string{"1", "true", "YES", " yes "} {
		getenv := func(k string) string {
			if k == "UBYHOST_PAYMENTS_RETIRED" {
				return v
			}
			return ""
		}
		if !PaymentsRetired(getenv) {
			t.Fatalf("PaymentsRetired(%q) false", v)
		}
		if !PaymentsHidden(getenv) {
			t.Fatal("retired should imply hidden")
		}
	}
	if PaymentsRetired(getenvOff) {
		t.Fatal("PaymentsRetired off should be false")
	}
}

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

func TestPaymentsHostPathBlockedRetired(t *testing.T) {
	blocked := []string{
		"/payments", "/booking-sites",
		"/p/slug/book", "/p/slug/checkout", "/p/slug/thanks",
		"/p/slug/b/9/tok", "/p/slug/b/9/tok/calendar.ics",
		"/pay/9/abc.png",
	}
	for _, path := range blocked {
		if !PaymentsHostPathBlocked(path, getenvRetired) {
			t.Fatalf("%s should be blocked when retired", path)
		}
	}
	open := []string{
		"/p/x", "/p/x/feed.ics", "/guide", "/terms/booking", "/webhooks/stripe",
		"/apartments/12/page",
	}
	for _, path := range open {
		if PaymentsHostPathBlocked(path, getenvRetired) {
			t.Fatalf("%s should stay open when retired", path)
		}
	}
}
