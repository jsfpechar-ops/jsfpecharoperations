package validation

import "strings"

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
