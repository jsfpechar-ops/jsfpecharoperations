// Package countries holds the ISO 3166-1 table (countries.json) shared by
// validation and ubyport, so neither has to import the other.
package countries

import (
	_ "embed"
	"encoding/json"
	"strings"
	"sync"
)

//go:embed countries.json
var countriesJSON []byte

var (
	countriesOnce   sync.Once
	countriesByCode map[string]map[string]string
)

// Name mirrors validation.country_name: the name in lang (cs, de, es,
// fr, uk) when present, else English, else the code as given. An unknown
// code comes back unchanged.
func Name(code, lang string) string {
	countriesOnce.Do(func() {
		var list []map[string]string
		if err := json.Unmarshal(countriesJSON, &list); err != nil {
			panic("countries: countries.json: " + err.Error())
		}
		countriesByCode = make(map[string]map[string]string, len(list))
		for _, c := range list {
			countriesByCode[c["code"]] = c
		}
	})
	entry, ok := countriesByCode[pyUpper(code)]
	if !ok {
		return code
	}
	switch lang {
	case "cs", "de", "es", "fr", "uk":
		if v := entry[lang]; v != "" {
			return v
		}
	}
	if v, ok := entry["en"]; ok {
		return v
	}
	return code
}

// pyUpper is the same rule as ubyport's pyUpper (Python str.upper()).
func pyUpper(s string) string {
	return strings.ToUpper(strings.ReplaceAll(s, "ß", "SS"))
}
