// Package signup is App/app/signup.py in Go (brief 1281): self sign-up, the
// verification link, activation and the ad-click consent records. It is a
// library only: no route is registered here. Turnstile, the pages and the
// retention purge stay with their own briefs.
package signup

import (
	"net/url"
	"regexp"
	"strconv"
	"strings"
)

// Limits and lifetimes, as signup.py names them.
const (
	VerifyMaxAge      = 24 * 60 * 60
	UnverifiedTTLDays = 7
	WorkspaceMax      = 120
	SignupIPMax       = 10
	SignupEmailMax    = 3
	hour              = 60 * 60

	Google = "google"
	Meta   = "meta"

	GooglePrivacyURL = "https://business.safety.google/privacy/"
	MetaPrivacyURL   = "https://www.facebook.com/privacy/policy/"
	GoogleExportDays = 85
	ClickMaxAgeDays  = 90
	UserAgentMax     = 512
	ConsentGranted   = "Granted"
	ConsentDenied    = "Denied"

	clickFutureSlackMS = 5 * 60 * 1000
	clickSalt          = "ubyhost-signup-click"
	verifySalt         = "ubyhost-signup-verify"
)

// Platforms is PLATFORMS, in display order.
var Platforms = []string{Google, Meta}

// UTMKeys is UTM_KEYS.
var UTMKeys = []string{"utm_source", "utm_medium", "utm_campaign"}

// clickParam is one CLICK_PARAMS entry. clickParams keeps the dict order.
type clickParam struct {
	name     string
	platform string
	re       *regexp.Regexp
}

var (
	shortID     = regexp.MustCompile(`^[A-Za-z0-9_-]{1,200}$`)
	clickParams = []clickParam{
		{"gclid", Google, shortID},
		{"gbraid", Google, shortID},
		{"wbraid", Google, shortID},
		{"fbclid", Meta, regexp.MustCompile(`^[A-Za-z0-9_-]{1,500}$`)},
	}
	utmRE = regexp.MustCompile(`^[A-Za-z0-9._+ -]{1,100}$`)
)

// IDColumns is ID_COLUMNS: the ad_click columns blanked together.
var IDColumns = map[string][]string{
	Google: {"gclid", "gbraid", "wbraid"},
	Meta:   {"fbc", "client_user_agent"},
}

// ConsentFields is CONSENT_FIELDS: the checkbox name per platform.
var ConsentFields = map[string]string{Google: "ads_consent", Meta: "meta_consent"}

// ConsentVersions is CONSENT_VERSIONS; the language is appended.
var ConsentVersions = map[string]string{Google: "ads-google-v1", Meta: "ads-meta-v2"}

// IDRetentionDays is ID_RETENTION_DAYS: (after the click, after upload or send).
var IDRetentionDays = map[string][2]int{Google: {90, 30}, Meta: {90, 7}}

// CSVHeader is CSV_HEADER of the Google Ads offline conversion file.
var CSVHeader = []string{"Google Click ID", "Conversion Name", "Conversion Time", "Ad User Data", "Ad Personalization"}

func platformOf(param string) (clickParam, bool) {
	for _, p := range clickParams {
		if p.name == param {
			return p, true
		}
	}
	return clickParam{}, false
}

// envFlag is os.environ.get(name, "0").lower() in ("1", "true", "yes").
func envFlag(getenv func(string) string, name string) bool {
	switch strings.ToLower(getenv(name)) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// envOr is os.environ.get(name, def): an unset or empty variable gives def.
func envOr(getenv func(string) string, name, def string) string {
	if v := getenv(name); v != "" {
		return v
	}
	return def
}

// Enabled is signup.enabled (config.SIGNUP_ENABLED).
func Enabled(getenv func(string) string) bool { return envFlag(getenv, "UBYHOST_SIGNUP_ENABLED") }

// publicBase is config.PUBLIC_BASE_URL.
func publicBase(getenv func(string) string) string {
	return strings.TrimRight(envOr(getenv, "UBYHOST_PUBLIC_BASE_URL", "http://127.0.0.1:8080"), "/")
}

// appBase is config.app_base_url().
func appBase(getenv func(string) string) string {
	if v := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/"); v != "" {
		return v
	}
	return publicBase(getenv)
}

// operatorEmail is config.OPERATOR_EMAIL.
func operatorEmail(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL")); v != "" {
		return v
	}
	return "support@ubyhost.com"
}

// notifyEmail is config.SIGNUP_NOTIFY_EMAIL.
func notifyEmail(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_SIGNUP_NOTIFY_EMAIL")); v != "" {
		return v
	}
	return operatorEmail(getenv)
}

// conversionName is config.ADS_CONVERSION_NAME.
func conversionName(getenv func(string) string) string {
	return strings.TrimSpace(envOr(getenv, "UBYHOST_ADS_CONVERSION_NAME", "UbyHost sign-up"))
}

// metaEnabled is config.meta_capi_enabled().
func metaEnabled(getenv func(string) string) bool {
	return strings.TrimSpace(getenv("UBYHOST_META_DATASET_ID")) != "" &&
		strings.TrimSpace(getenv("UBYHOST_META_ACCESS_TOKEN")) != ""
}

// CleanClickID is clean_click_id: the trimmed value if it fits the parameter's
// pattern, else "".
func CleanClickID(param, value string) string {
	p, ok := platformOf(param)
	text := pyStrip(value)
	if ok && p.re.MatchString(text) {
		return text
	}
	return ""
}

// CleanGclid is clean_gclid.
func CleanGclid(value string) string { return CleanClickID("gclid", value) }

// CleanUTM is clean_utm.
func CleanUTM(value string) string {
	text := pyStrip(value)
	if utmRE.MatchString(text) {
		return text
	}
	return ""
}

// last is Starlette's QueryParams/FormData .get: the last value of a key.
func last(params url.Values, key string) (string, bool) {
	vs, ok := params[key]
	if !ok || len(vs) == 0 {
		return "", false
	}
	return vs[len(vs)-1], true
}

// ClickIDs is click_ids: the valid ad click identifiers in a query string.
func ClickIDs(params url.Values) map[string]string {
	found := map[string]string{}
	for _, p := range clickParams {
		v, _ := last(params, p.name)
		if c := CleanClickID(p.name, v); c != "" {
			found[p.name] = c
		}
	}
	return found
}

// PlatformActive is platform_active: Meta only once the Conversions API is set up.
func PlatformActive(getenv func(string) string, platform string) bool {
	if platform == Meta {
		return metaEnabled(getenv)
	}
	return true
}

// ClickPlatforms is click_platforms: the active platforms a click has ids for.
func ClickPlatforms(getenv func(string) string, click *Click) []string {
	if click == nil {
		return nil
	}
	present := map[string]bool{}
	for param := range click.IDs {
		if p, ok := platformOf(param); ok {
			present[p.platform] = true
		}
	}
	var out []string
	for _, p := range Platforms {
		if present[p] && PlatformActive(getenv, p) {
			out = append(out, p)
		}
	}
	return out
}

// Attribution is attribution(params, mint=mint): the clean utm_* labels and
// the signed click value. With mint, raw identifiers in params are signed
// with seenMS (the page view); a form post only keeps a valid signed value.
func Attribution(secret string, params url.Values, mint bool, nowMS int64) map[string]string {
	found := map[string]string{}
	for _, k := range UTMKeys {
		v, _ := last(params, k)
		if c := CleanUTM(v); c != "" {
			found[k] = c
		}
	}
	token, _ := last(params, "click")
	click := ReadClick(secret, token, nowMS)
	if click == nil {
		token = ""
	}
	if mint {
		raw := ClickIDs(params)
		if len(raw) > 0 && (click == nil || !sameIDs(click.IDs, raw)) {
			if minted, err := IssueClick(secret, raw, nowMS); err == nil {
				token = minted
			}
		}
	}
	if token != "" {
		found["click"] = token
	}
	return found
}

func sameIDs(a, b map[string]string) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if w, ok := b[k]; !ok || w != v {
			return false
		}
	}
	return true
}

// CleanSelection is signup_selection.clean: only the bounded plan choices.
func CleanSelection(params url.Values) map[string]string {
	result := map[string]string{}
	for _, f := range []struct {
		field   string
		choices []string
	}{{"plan", []string{"standard", "max"}}, {"interval", []string{"month", "year"}}, {"ttlock", []string{"0", "1"}}} {
		if v, ok := last(params, f.field); ok {
			for _, c := range f.choices {
				if v == c {
					result[f.field] = v
				}
			}
		}
	}
	count, ok := last(params, "apartments")
	if !ok {
		count, ok = last(params, "apts")
	}
	if ok && apartmentsRE.MatchString(count) {
		if n, _ := strconv.Atoi(count); n <= 50 {
			result["apartments"] = strconv.Itoa(n)
		}
	}
	return result
}

var apartmentsRE = regexp.MustCompile(`^[1-9][0-9]?$`)

// SignupSource is signup_source: google, meta or none for the admin funnel.
func SignupSource(stored []string, attr map[string]string) string {
	for _, p := range Platforms {
		for _, s := range stored {
			if s == p {
				return p
			}
		}
	}
	label := strings.ToLower(pyStrip(attr["utm_source"]))
	for _, p := range []struct {
		platform string
		names    []string
	}{{Google, []string{"google", "adwords", "googleads", "google_ads"}}, {Meta, []string{"facebook", "fb", "instagram", "ig", "meta"}}} {
		for _, n := range p.names {
			if label == n {
				return p.platform
			}
		}
	}
	return "none"
}

// CleanUserAgent is clean_user_agent: printable ASCII only, trimmed, at most
// 512 characters; "" stands for None.
func CleanUserAgent(value string) string {
	var b strings.Builder
	for _, r := range value {
		if r >= ' ' && r <= '~' {
			b.WriteRune(r)
		}
	}
	text := strings.Trim(b.String(), " ")
	if len(text) > UserAgentMax {
		text = text[:UserAgentMax]
	}
	return text
}
