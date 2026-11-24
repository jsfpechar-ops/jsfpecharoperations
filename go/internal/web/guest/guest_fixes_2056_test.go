package guest

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

// The 30 guest keys added to i18n.json by brief 2056 step a, in all six guest languages.
var fixes2056Keys = strings.Fields(`leon_error leon_error_reload leon_host_answered leon_host_answered_plain leon_intro leon_label leon_name leon_needs_js leon_other_prompt leon_placeholder leon_queued leon_role leon_see_card leon_send leon_sending leon_sit_emergency_help leon_sit_other leon_tag leon_waiting leon_welcome leon_you passport_photo_bad_type passport_photo_selected passport_photo_too_large_image passport_photo_too_large_pdf remove_help remove_keep remove_title remove_yes sign_for_who`)

func loadGuestCatalogue2056(t *testing.T) map[string]map[string]string {
	t.Helper()
	raw, err := os.ReadFile("i18n.json")
	if err != nil {
		t.Fatal(err)
	}
	var cat map[string]map[string]string
	if err := json.Unmarshal(raw, &cat); err != nil {
		t.Fatal(err)
	}
	return cat
}

func TestI18nFixes2056KeysInAllLanguages(t *testing.T) {
	cat := loadGuestCatalogue2056(t)
	for _, lang := range []string{"en", "cs", "de", "es", "fr", "uk"} {
		for _, k := range fixes2056Keys {
			if cat[lang][k] == "" {
				t.Errorf("language %s: key %s missing or empty", lang, k)
			}
		}
	}
}

func TestRemovePageFixes2056ShowsFooterAndNoRawKeys(t *testing.T) {
	cat := loadGuestCatalogue2056(t)
	for _, lang := range []string{"en", "cs"} {
		v := formView{
			Page: Page{
				Lang:       lang,
				Token:      "tok2056",
				PrivacyURL: "/l/tok2056/privacy?lang=" + lang,
				CSRFToken:  "csrf",
			},
			ReservationID: 1,
			GuestID:       2,
			PersonName:    "Test Person",
			BackURL:       "/l/tok2056/1?lang=" + lang,
		}
		rec := httptest.NewRecorder()
		writeRemovePage(rec, httptest.NewRequest("GET", "/", nil), v)
		if rec.Code != 200 {
			t.Fatalf("%s: status %d", lang, rec.Code)
		}
		body := rec.Body.String()
		if strings.Contains(body, "remove_") {
			t.Errorf("%s: raw remove key visible", lang)
		}
		if want := cat[lang]["privacy_link"]; want == "" || !strings.Contains(body, want) {
			t.Errorf("%s: privacy footer link %q missing", lang, want)
		}
		if !strings.Contains(body, `href="/l/tok2056/privacy?lang=`+lang+`"`) {
			t.Errorf("%s: privacy href missing", lang)
		}
	}
}
