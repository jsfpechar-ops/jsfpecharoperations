// Package appconfig mirrors App/app/config.py flags the Go stack reads from the environment.
package appconfig

import (
	"strings"
)

// PaymentsHidden is config.PAYMENTS_HIDDEN: UBYHOST_PAYMENTS_HIDDEN in 1, true, yes (default off).
func PaymentsHidden(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_PAYMENTS_HIDDEN"))) {
	case "1", "true", "yes":
		return true
	default:
		return false
	}
}

// PaymentsHostPathBlocked is config.payments_host_path_blocked. While hidden, host
// payments and booking-site URLs answer 404. Guest pay links, webhooks, guest
// booking /p/*, and payment QR PNGs stay reachable on Go.
func PaymentsHostPathBlocked(path string, getenv func(string) string) bool {
	if !PaymentsHidden(getenv) {
		return false
	}
	if path == "/booking-sites" {
		return true
	}
	if strings.HasPrefix(path, "/pay/") {
		return false
	}
	if strings.HasPrefix(path, "/payments/qr/") && strings.HasSuffix(path, ".png") {
		return false
	}
	if strings.HasPrefix(path, "/payments") {
		return true
	}
	if strings.HasPrefix(path, "/apartments/") && strings.Contains(path, "/booking-site") {
		return true
	}
	return false
}