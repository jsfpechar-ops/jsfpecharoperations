package mailnotify

import (
	_ "embed"
	"encoding/json"
)

// doorcode_i18n_strings.json is written by App/scripts/go_mailnotify_doorcode_i18n.py.
// It is a second dump next to i18n_strings.json (which stays as it is). It holds the
// door-code keys: the guest copy of build_door_code and _fee_block, and the host
// notice keys (mail.door_code_notice.* and mail.door_code_reason.*).
//
//go:embed doorcode_i18n_strings.json
var doorI18nJSON []byte

type doorCatalogueFile struct {
	Guest map[string]map[string]string `json:"guest"`
	Host  map[string]map[string]string `json:"host"`
}

var doorCatalogue = loadDoorCatalogue()

func loadDoorCatalogue() doorCatalogueFile {
	var c doorCatalogueFile
	if err := json.Unmarshal(doorI18nJSON, &c); err != nil {
		panic("mailnotify: doorcode_i18n_strings.json: " + err.Error())
	}
	return c
}

// doorGuestText is i18n.translator(lang)(key, **args) for the door-code keys. The
// language set and the default come from the same catalogue as GuestText.
func doorGuestText(lang, key string, args Args) string {
	table := doorCatalogue.Guest[GuestLanguage(lang)]
	return lookup(table, doorCatalogue.Guest[catalogue.GuestDefaultLanguage], key, args)
}

// doorHostText is host_i18n.translate(lang, key, **args) for the door-code keys.
func doorHostText(lang, key string, args Args) string {
	table := doorCatalogue.Host[HostLanguage(lang)]
	return lookup(table, doorCatalogue.Host[catalogue.HostDefaultLanguage], key, args)
}
