package ruian

import "strings"

// Enabled reports whether address suggestions and the import are enabled.
func Enabled(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_RUIAN_ENABLED"))) {
	case "0", "false", "no", "off":
		return false
	default:
		return true
	}
}
