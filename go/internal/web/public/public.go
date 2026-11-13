// Package public serves the public legal pages (/legal, /terms, /privacy,
// /dpa, /subprocessors), ported from App/app/routes/legal.py and the
// public_legal_base.html templates (brief 1270). The copy comes from
// catalog.json, written by App/scripts/public_legal_golden.py; never edit it
// by hand. Pages are rendered with text/template and every printed value goes
// through html.EscapeString (markupsafe's escape), because html/template
// escapes "+" and rewrites URLs, which would break byte parity with Jinja.
// TestEveryActionEscapes guards that rule.
package public

import (
	_ "embed"
	"encoding/json"
	"html"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

//go:embed catalog.json
var catalogJSON []byte

// localized is a {"en": ..., "cs": ...} text from cookie_inventory.py.
type localized map[string]string

type cookieRow struct {
	Name     string    `json:"name"`
	Party    string    `json:"party"`
	Purpose  localized `json:"purpose"`
	Lifetime localized `json:"lifetime"`
}

type service struct {
	Name  string    `json:"name"`
	Party string    `json:"party"`
	Note  localized `json:"note"`
}

type catalogFile struct {
	Strings            hostweb.Catalog `json:"strings"`
	TermsSections      []string        `json:"terms_sections"`
	PrivacySections    []string        `json:"privacy_sections"`
	DPASections        []string        `json:"dpa_sections"`
	SubprocessorIDs    []string        `json:"subprocessor_ids"`
	RecipientIDs       []string        `json:"recipient_ids"`
	CookieInventory    []cookieRow     `json:"cookie_inventory"`
	CookielessServices []service       `json:"cookieless_services"`
}

var cat = loadCatalog(catalogJSON)

func loadCatalog(data []byte) catalogFile {
	var c catalogFile
	if err := json.Unmarshal(data, &c); err != nil {
		panic("public: bad catalog.json: " + err.Error())
	}
	return c
}

const (
	langCookieName = "ubyhost_lang" // host_i18n.LANG_COOKIE
	publicDefault  = "cs"           // host_i18n.PUBLIC_DEFAULT_LANGUAGE
	appDefault     = "en"           // host_i18n.DEFAULT_LANGUAGE
)

// resolveLang is templating.render's language for a public page:
// host_i18n.resolve_language (?lang=, then the cookie, each through
// supported_language), else PUBLIC_DEFAULT_LANGUAGE for a visitor and
// DEFAULT_LANGUAGE for a signed-in host; a language the public pages do not
// have (vi) becomes "en".
func resolveLang(r *http.Request, signedIn func(*http.Request) bool) string {
	lang := ""
	for _, v := range []string{r.URL.Query().Get("lang"), hostweb.Cookie(r, langCookieName)} {
		if lang = supportedLanguage(v); lang != "" {
			break
		}
	}
	if lang == "" {
		lang = publicDefault
		if signedIn != nil && signedIn(r) {
			lang = appDefault
		}
	}
	if lang != "en" && lang != "cs" {
		lang = "en"
	}
	return lang
}

// supportedLanguage is host_i18n.supported_language: the first two letters,
// lower-cased and trimmed, when the app speaks them (en, cs, vi), else "".
func supportedLanguage(v string) string {
	r := []rune(strings.ToLower(strings.TrimSpace(v)))
	if len(r) > 2 {
		r = r[:2]
	}
	switch s := string(r); s {
	case "en", "cs", "vi":
		return s
	}
	return ""
}

// config is what config.py reads for these pages; the golden script's
// config_values() is the Python side of the same table.
type config struct {
	Deployment, PublicBase                                  string
	WebPush, SignupEnabled                                  bool
	OpName, OpICO, OpDIC, OpAddress, OpEmail, OpRegistry    string
	PHKey, PHHost, PHAssets, MetaDataset, MetaToken         string
	TermsVersion, PrivacyVersion, DPAVersion, EffectiveDate string
}

func loadConfig(getenv func(string) string) config {
	or := func(key, def string) string {
		if v := getenv(key); v != "" {
			return v
		}
		return def
	}
	trim := func(key string) string { return strings.TrimSpace(getenv(key)) }
	email := trim("UBYHOST_OPERATOR_EMAIL")
	if email == "" {
		email = "support@ubyhost.com"
	}
	return config{
		Deployment:     strings.ToLower(or("UBYHOST_DEPLOYMENT", "local")),
		PublicBase:     strings.TrimRight(or("UBYHOST_PUBLIC_BASE_URL", "http://127.0.0.1:8080"), "/"),
		WebPush:        !inSet(strings.ToLower(strings.TrimSpace(or("UBYHOST_WEB_PUSH", "1"))), "0", "false", "no"),
		SignupEnabled:  inSet(strings.ToLower(getenv("UBYHOST_SIGNUP_ENABLED")), "1", "true", "yes"),
		OpName:         trim("UBYHOST_OPERATOR_NAME"),
		OpICO:          trim("UBYHOST_OPERATOR_ICO"),
		OpDIC:          trim("UBYHOST_OPERATOR_DIC"),
		OpAddress:      trim("UBYHOST_OPERATOR_ADDRESS"),
		OpEmail:        email,
		OpRegistry:     trim("UBYHOST_OPERATOR_REGISTRY_URL"),
		PHKey:          trim("POSTHOG_PROJECT_API_KEY"),
		PHHost:         strings.TrimRight(strings.TrimSpace(or("POSTHOG_HOST", "https://eu.i.posthog.com")), "/"),
		PHAssets:       strings.TrimRight(strings.TrimSpace(or("POSTHOG_ASSETS_HOST", "https://eu-assets.i.posthog.com")), "/"),
		MetaDataset:    trim("UBYHOST_META_DATASET_ID"),
		MetaToken:      trim("UBYHOST_META_ACCESS_TOKEN"),
		TermsVersion:   or("UBYHOST_TERMS_VERSION", "1.7"),
		PrivacyVersion: or("UBYHOST_PRIVACY_VERSION", "1.8"),
		DPAVersion:     or("UBYHOST_DPA_VERSION", "1.8"),
		EffectiveDate:  or("UBYHOST_LEGAL_EFFECTIVE_DATE", "2026-10-05"),
	}
}

func inSet(v string, set ...string) bool {
	for _, s := range set {
		if v == s {
			return true
		}
	}
	return false
}

// metaOn is config.meta_capi_enabled().
func (c config) metaOn() bool { return c.MetaDataset != "" && c.MetaToken != "" }

// httpsOrigin is analytics._https_origin: "https://host[:port]" or "".
func httpsOrigin(raw string) string {
	u, err := url.Parse(raw)
	if err != nil || u.Scheme != "https" || u.Hostname() == "" {
		return ""
	}
	host := strings.ToLower(u.Hostname())
	if p := u.Port(); p != "" {
		host += ":" + p
	}
	return "https://" + host
}

// hostAllowed is analytics._host_allowed: an https origin outside PostHog US.
func hostAllowed(raw string) bool {
	o := httpsOrigin(raw)
	return o != "" && !strings.Contains(o, "us.i.posthog.com") && !strings.Contains(o, "us-assets.i.posthog.com")
}

// posthogOn is analytics.enabled(); tag() then always has both origins.
func (c config) posthogOn() bool {
	return c.PHKey != "" && hostAllowed(c.PHHost) && hostAllowed(c.PHAssets)
}

// publicCSP is main._public_csp() while analytics is on.
func publicCSP(c config) string {
	return "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; " +
		"form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; " +
		"script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com " + httpsOrigin(c.PHAssets) + "; " +
		"frame-src https://challenges.cloudflare.com; " +
		"connect-src 'self' https://challenges.cloudflare.com " + httpsOrigin(c.PHHost) + " " + httpsOrigin(c.PHAssets)
}

var enMonths = []string{"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December"}

// csMonths are genitive, as in "4. října 2026" (acceptance._CS_MONTHS).
var csMonths = []string{"ledna", "února", "března", "dubna", "května", "června",
	"července", "srpna", "září", "října", "listopadu", "prosince"}

// effectiveDateText is acceptance.effective_date_text.
func effectiveDateText(iso, lang string) string {
	day, err := time.Parse("2006-01-02", strings.TrimSpace(iso))
	if err != nil {
		day, _ = time.Parse("2006-01-02", "2026-10-05")
	}
	d, y := strconv.Itoa(day.Day()), strconv.Itoa(day.Year())
	if lang == "cs" {
		return d + ". " + csMonths[day.Month()-1] + " " + y
	}
	return d + " " + enMonths[day.Month()-1] + " " + y
}

// esc is markupsafe.escape: html.EscapeString writes the same five entities
// (&amp; &lt; &gt; &#39; &#34;).
func esc(s string) string { return html.EscapeString(s) }
