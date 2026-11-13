package signup

import "strings"

// consentStrings are the host_i18n keys of the consent boxes (en, cs, vi),
// copied from App/app/host_i18n.py; the golden test checks every text.
var consentStrings = map[string]map[string]string{
	"en": {
		"signup.ads_consent":       "Optional: I agree that UbyHost may record that I came from a Google ad and share that click identifier with Google (an independent controller) to measure our ad campaigns. No personalised ads. You can withdraw anytime in Settings.",
		"signup.ads_consent_link":  "How Google uses data",
		"signup.meta_consent":      "Optional: I agree that UbyHost may record that I came from Facebook or Instagram and send that click identifier and my browser type string, with the fact and time of my sign-up, to Meta Platforms Ireland Ltd. to measure our campaigns. Meta receives it as a joint controller and then uses it as its own controller. You can withdraw anytime in Settings.",
		"signup.meta_consent_link": "How Meta uses data",
	},
	"cs": {
		"signup.ads_consent":       "Nepovinné: Souhlasím, aby UbyHost zaznamenal, že jsem přišel z reklamy Google, a předal tento identifikátor kliknutí společnosti Google (samostatnému správci) k měření úspěšnosti našich reklam. Bez personalizované reklamy. Souhlas můžete kdykoli odvolat v Nastavení.",
		"signup.ads_consent_link":  "Jak Google používá data",
		"signup.meta_consent":      "Nepovinné: Souhlasím, aby UbyHost zaznamenal, že jsem přišel z Facebooku nebo Instagramu, a předal tento identifikátor kliknutí a údaj o typu mého prohlížeče spolu s informací o mé registraci a jejím čase společnosti Meta Platforms Ireland Ltd. k měření úspěšnosti našich kampaní. Meta je při předání společným správcem a dále údaje zpracovává jako samostatný správce. Souhlas můžete kdykoli odvolat v Nastavení.",
		"signup.meta_consent_link": "Jak Meta používá data",
	},
	"vi": {
		"signup.ads_consent":       "Optional: I agree that UbyHost may record that I came from a Google ad and share that click identifier with Google (an independent controller) to measure our ad campaigns. No personalised ads. You can withdraw anytime in Settings.",
		"signup.ads_consent_link":  "Cách Google sử dụng dữ liệu",
		"signup.meta_consent":      "Optional: I agree that UbyHost may record that I came from Facebook or Instagram and send that click identifier and my browser type string, with the fact and time of my sign-up, to Meta Platforms Ireland Ltd. to measure our campaigns. Meta receives it as a joint controller and then uses it as its own controller. You can withdraw anytime in Settings.",
		"signup.meta_consent_link": "Cách Meta sử dụng dữ liệu",
	},
}

// consentLanguage is host_i18n.normalise_language.
func consentLanguage(lang string) string {
	code := []rune(strings.ToLower(lang))
	if len(code) > 2 {
		code = code[:2]
	}
	if _, ok := consentStrings[string(code)]; ok {
		return string(code)
	}
	return "en"
}
