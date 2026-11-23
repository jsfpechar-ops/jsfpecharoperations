// Package appconfig mirrors App/app/config.py flags the Go stack reads from the environment.
package appconfig

import (
	"strings"
)

// PaymentsRetired is UBYHOST_PAYMENTS_RETIRED in 1, true, yes (default off).
func PaymentsRetired(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_PAYMENTS_RETIRED"))) {
	case "1", "true", "yes":
		return true
	default:
		return false
	}
}

// PaymentsHidden is config.PAYMENTS_HIDDEN: UBYHOST_PAYMENTS_HIDDEN in 1, true, yes (default off).
// Payments retired also counts as hidden.
func PaymentsHidden(getenv func(string) string) bool {
	if PaymentsRetired(getenv) {
		return true
	}
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_PAYMENTS_HIDDEN"))) {
	case "1", "true", "yes":
		return true
	default:
		return false
	}
}

// paymentsRetiredBookingPathBlocked is extra blocking when payments are retired (booking flows under /p/).
func paymentsRetiredBookingPathBlocked(path string) bool {
	if !strings.HasPrefix(path, "/p/") {
		return false
	}
	rest := strings.TrimPrefix(path, "/p/")
	if rest == "" {
		return false
	}
	slash := strings.Index(rest, "/")
	if slash < 0 {
		return false
	}
	suffix := rest[slash:]
	switch suffix {
	case "/book", "/checkout", "/thanks":
		return true
	}
	return strings.HasPrefix(suffix, "/b/")
}

// PaymentsHostPathBlocked is config.payments_host_path_blocked. While hidden, host
// payments and booking-site URLs answer 404. When retired, guest book/checkout/manage
// and pay links also 404; property pages and iCal feeds stay reachable.
func PaymentsHostPathBlocked(path string, getenv func(string) string) bool {
	if !PaymentsHidden(getenv) {
		return false
	}
	if path == "/booking-sites" {
		return true
	}
	if strings.HasPrefix(path, "/payments") {
		return true
	}
	if strings.HasPrefix(path, "/apartments/") && strings.Contains(path, "/booking-site") {
		return true
	}
	if PaymentsRetired(getenv) {
		if strings.HasPrefix(path, "/pay/") {
			return true
		}
		if paymentsRetiredBookingPathBlocked(path) {
			return true
		}
	}
	return false
}
