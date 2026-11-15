package authpage

import "strings"

// DeviceKind picks the passkey button wording from the User-Agent: "apple",
// "android", "windows" or "other". The header is read per request; it is never
// stored or logged (privacy rule 2).
func DeviceKind(userAgent string) string {
	switch {
	case strings.Contains(userAgent, "iPhone"), strings.Contains(userAgent, "iPad"),
		strings.Contains(userAgent, "iPod"), strings.Contains(userAgent, "Macintosh"):
		return "apple"
	case strings.Contains(userAgent, "Android"):
		return "android"
	case strings.Contains(userAgent, "Windows"):
		return "windows"
	default:
		return "other"
	}
}
