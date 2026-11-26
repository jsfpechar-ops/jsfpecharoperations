package validation

import "strings"

// MarkMismatchMessage is the English validation error returned when a host
// enters a UBY-WS_<suffix> login and a facility abbreviation (zkratka) that
// does not match the suffix after the underscore.
const MarkMismatchMessage = "The abbreviation must match the part after UBY-WS_ in your login."

// WSUserUnderscoreMark returns the expected facility abbreviation when a
// production login uses the UBY-WS_<suffix> form (5 or 6 alphanumeric
// characters after the underscore). Returns "" for all other logins.
func WSUserUnderscoreMark(user string) string {
	login := pyStrip(user)
	if !wsUserRE.MatchString(login) {
		return ""
	}
	if !strings.HasPrefix(strings.ToLower(login), "uby-ws_") {
		return ""
	}
	return strings.ToUpper(string([]rune(login)[7:]))
}

// MarkFromWSUser is validation.mark_from_ws_user: the facility abbreviation
// from a production web-service login. UBY-WS_MLJNO yields MLJNO (the
// characters after UBY-WS_); a login with no underscore, UBY-WSab12cd, yields
// the six characters after UBY-WS. Test logins (uby-tws...) never do. It
// uses wsUserRE, the pattern ValidateApartment already checks the login with.
func MarkFromWSUser(user string) string {
	login := pyStrip(user)
	if !wsUserRE.MatchString(login) {
		return ""
	}
	lowered := strings.ToLower(login)
	runes := []rune(login)
	switch {
	case strings.HasPrefix(lowered, "uby-tws"):
		return ""
	case strings.HasPrefix(lowered, "uby-ws_"):
		return strings.ToUpper(string(runes[7:]))
	case strings.HasPrefix(lowered, "uby-ws"):
		return strings.ToUpper(string(runes[6:]))
	}
	return ""
}
