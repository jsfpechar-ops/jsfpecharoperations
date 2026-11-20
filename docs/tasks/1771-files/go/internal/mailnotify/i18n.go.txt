package mailnotify

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
)

// i18n_strings.json is written by App/scripts/go_mailnotify_i18n.py. It holds only
// the keys the reminder and shell builders read, per language.
//
//go:embed i18n_strings.json
var i18nJSON []byte

type catalogueFile struct {
	Guest                 map[string]map[string]string `json:"guest"`
	Host                  map[string]map[string]string `json:"host"`
	GuestLanguages        []string                     `json:"guest_languages"`
	HostLanguages         []string                     `json:"host_languages"`
	GuestDefaultLanguages []string                     `json:"guest_default_languages"`
	GuestDefaultLanguage  string                       `json:"guest_default_language"`
	HostDefaultLanguage   string                       `json:"host_default_language"`
}

var catalogue = loadCatalogue()

func loadCatalogue() catalogueFile {
	var c catalogueFile
	if err := json.Unmarshal(i18nJSON, &c); err != nil {
		panic("mailnotify: i18n_strings.json: " + err.Error())
	}
	return c
}

// alwaysOnGuest mirrors i18n.ALWAYS_ON: these guest languages are on whatever the env says.
var alwaysOnGuest = map[string]bool{"en": true, "cs": true}

// guestEnabled is the set i18n.enabled_languages() returns.
var guestEnabled = enabledGuest(strings.Join(catalogue.GuestDefaultLanguages, ","))

// SetGuestLanguages applies a UBYHOST_GUEST_LANGS value (comma-separated codes),
// as i18n.enabled_languages() reads it. Call once at startup.
func SetGuestLanguages(raw string) {
	guestEnabled = enabledGuest(raw)
}

func enabledGuest(raw string) map[string]bool {
	wanted := map[string]bool{}
	for _, code := range strings.Split(raw, ",") {
		if c := strings.ToLower(strings.TrimSpace(code)); c != "" {
			wanted[c] = true
		}
	}
	out := map[string]bool{}
	for _, code := range catalogue.GuestLanguages {
		if alwaysOnGuest[code] || wanted[code] {
			out[code] = true
		}
	}
	return out
}

// GuestLanguage is i18n.normalise_language: the enabled guest language for value,
// English otherwise. Accepts "sk" as Czech and region tags such as "cs-CZ".
func GuestLanguage(value string) string {
	code := strings.ToLower(strings.TrimSpace(value))
	code = strings.ReplaceAll(code, "_", "-")
	if i := strings.Index(code, "-"); i >= 0 {
		code = code[:i]
	}
	if code == "sk" {
		code = "cs"
	}
	if guestEnabled[code] {
		return code
	}
	return catalogue.GuestDefaultLanguage
}

// HostLanguage is host_i18n.normalise_language: the first two characters of the
// lower-cased value when they name a host language, English otherwise.
func HostLanguage(value string) string {
	runes := []rune(strings.ToLower(value))
	if len(runes) > 2 {
		runes = runes[:2]
	}
	code := string(runes)
	for _, l := range catalogue.HostLanguages {
		if l == code {
			return code
		}
	}
	return catalogue.HostDefaultLanguage
}

// Args are the %-format values of a catalogue string, keyed by name. A value is a
// string, an int, or nil (Python None).
type Args map[string]any

// GuestText is i18n.translator(lang)(key, **args): guest copy.
func GuestText(lang, key string, args Args) string {
	table := catalogue.Guest[GuestLanguage(lang)]
	return lookup(table, catalogue.Guest[catalogue.GuestDefaultLanguage], key, args)
}

// HostText is host_i18n.translate(lang, key, **args): host copy.
func HostText(lang, key string, args Args) string {
	table := catalogue.Host[HostLanguage(lang)]
	return lookup(table, catalogue.Host[catalogue.HostDefaultLanguage], key, args)
}

// lookup is host_i18n.lookup: a missing key falls back, then renders the key
// itself; with arguments, a format failure returns the raw text.
func lookup(table, fallback map[string]string, key string, args Args) string {
	text, ok := table[key]
	if !ok {
		text, ok = fallback[key]
		if !ok {
			text = key
		}
	}
	if len(args) == 0 {
		return text
	}
	if out, ok := pyFormat(text, args); ok {
		return out
	}
	return text
}

// pyFormat implements the subset of Python's "text % mapping" the catalogues use:
// %(name)s, %(name)d and %%. Anything else (a bare %, an unknown name, %d on a
// non-int) fails, and the caller returns the raw text, as Python's ValueError,
// KeyError and TypeError do in lookup.
func pyFormat(s string, args Args) (string, bool) {
	var b strings.Builder
	for i := 0; i < len(s); {
		if s[i] != '%' {
			b.WriteByte(s[i])
			i++
			continue
		}
		if i+1 < len(s) && s[i+1] == '%' {
			b.WriteByte('%')
			i += 2
			continue
		}
		if i+1 >= len(s) || s[i+1] != '(' {
			return "", false
		}
		end := strings.IndexByte(s[i+2:], ')')
		if end < 0 {
			return "", false
		}
		name := s[i+2 : i+2+end]
		conv := i + 2 + end + 1
		if conv >= len(s) {
			return "", false
		}
		v, ok := args[name]
		if !ok {
			return "", false
		}
		switch s[conv] {
		case 's':
			b.WriteString(pyStr(v))
		case 'd':
			n, isInt := v.(int)
			if !isInt {
				return "", false
			}
			b.WriteString(strconv.Itoa(n))
		default:
			return "", false
		}
		i = conv + 1
	}
	return b.String(), true
}

func pyStr(v any) string {
	switch t := v.(type) {
	case nil:
		return "None"
	case string:
		return t
	case int:
		return strconv.Itoa(t)
	}
	return fmt.Sprint(v)
}

// optInt turns an optional int into an Args value (nil for Python None).
func optInt(p *int) any {
	if p == nil {
		return nil
	}
	return *p
}
