package mailnotify

import (
	_ "embed"
	"encoding/json"
)

// completion_i18n_strings.json is written by App/scripts/go_mailnotify_completion_i18n.py.
// It is a third dump next to i18n_strings.json and doorcode_i18n_strings.json, which stay as
// they are. It holds the guest keys build_completion reads: its own copy, the stay panel,
// the fee block, the door-code block and the guest footer.
//
//go:embed completion_i18n_strings.json
var completionI18nJSON []byte

type completionCatalogueFile struct {
	Guest map[string]map[string]string `json:"guest"`
}

var completionCatalogue = loadCompletionCatalogue()

func loadCompletionCatalogue() completionCatalogueFile {
	var c completionCatalogueFile
	if err := json.Unmarshal(completionI18nJSON, &c); err != nil {
		panic("mailnotify: completion_i18n_strings.json: " + err.Error())
	}
	return c
}

// completionGuestText is i18n.translator(lang)(key, **args) for the completion keys. The
// language set and the default come from the same catalogue as GuestText.
func completionGuestText(lang, key string, args Args) string {
	table := completionCatalogue.Guest[GuestLanguage(lang)]
	return lookup(table, completionCatalogue.Guest[catalogue.GuestDefaultLanguage], key, args)
}
