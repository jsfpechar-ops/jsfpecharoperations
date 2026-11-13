package public

import (
	"encoding/json"
	"net/http"
	"strings"
	"unicode"
	"unicode/utf8"
)

// operator is operator.details().
type operator struct{ Name, ICO, DIC, Address, Email, Registry string }

// page is the data of one render. Templates print only through the escaping
// methods (T, TL, E, L, Effective, URL, Canonical) or the fields named in
// TestEveryActionEscapes.
type page struct {
	Lang, Path, WrapClass string
	Op                    operator
	Controller            operator // privacy.html "controller": name, ico, address with placeholders
	Sections              []string // the TOC and section ids of terms, privacy or dpa
	Prefix                string   // "terms", "privacy" or "dpa"
	SubprocessorIDs       []string
	RecipientIDs          []string
	Cookies               []cookieRow
	Cookieless            []service
	SignupAdsNotice       bool
	SignupMetaNotice      bool
	PostHog               bool
	PHKeyJS, PHHostJS     string // tojson of the tag values
	PHAssetsJS            string
	PublicBase            string
	cfg                   config
	asked                 string // ?lang= when it is en or cs
}

func newPage(r *http.Request, path, lang string, cfg config) *page {
	p := &page{
		Lang: lang, Path: path, WrapClass: "narrow", cfg: cfg, PublicBase: cfg.PublicBase,
		Op:      operator{cfg.OpName, cfg.OpICO, cfg.OpDIC, cfg.OpAddress, cfg.OpEmail, cfg.OpRegistry},
		PostHog: cfg.posthogOn(),
	}
	if asked := supportedLanguage(r.URL.Query().Get("lang")); asked == "en" || asked == "cs" {
		p.asked = asked
	}
	if p.PostHog {
		p.PHKeyJS, p.PHHostJS, p.PHAssetsJS = tojson(cfg.PHKey), tojson(httpsOrigin(cfg.PHHost)), tojson(httpsOrigin(cfg.PHAssets))
	}
	switch path {
	case "/legal":
		p.Prefix = "legal"
	case "/terms":
		p.Sections, p.Prefix = cat.TermsSections, "terms"
	case "/privacy":
		p.Sections, p.Prefix = cat.PrivacySections, "privacy"
		p.Cookies, p.Cookieless = cat.CookieInventory, cat.CookielessServices
		placeholders := cfg.Deployment != "production"
		pick := func(v, key string) string {
			if v != "" {
				return v
			}
			if placeholders {
				return cat.Strings.T(lang, key, nil)
			}
			return ""
		}
		p.Controller = operator{
			Name:    pick(cfg.OpName, "privacy.placeholder_name"),
			ICO:     pick(cfg.OpICO, "privacy.placeholder_ico"),
			Address: pick(cfg.OpAddress, "privacy.placeholder_address"),
		}
		p.SignupAdsNotice = cfg.SignupEnabled
		p.SignupMetaNotice = cfg.SignupEnabled && cfg.metaOn()
	case "/dpa":
		p.Sections, p.Prefix = cat.DPASections, "dpa"
	case "/subprocessors":
		p.SubprocessorIDs = cat.SubprocessorIDs
		p.RecipientIDs = recipientIDs(cfg)
		p.SignupMetaNotice = cfg.SignupEnabled && cfg.metaOn()
	}
	return p
}

// recipientIDs is legal.recipient_ids().
func recipientIDs(cfg config) []string {
	hidden := map[string]bool{}
	if !cfg.WebPush {
		hidden["push"] = true
	}
	if !cfg.SignupEnabled {
		hidden["google_ads"], hidden["meta_ads"] = true, true
	} else if !cfg.metaOn() {
		hidden["meta_ads"] = true
	}
	var out []string
	for _, id := range cat.RecipientIDs {
		if !hidden[id] {
			out = append(out, id)
		}
	}
	return out
}

// params turns "name", value pairs into a translate mapping.
func params(kv []string) map[string]any {
	if len(kv) == 0 {
		return nil
	}
	m := map[string]any{}
	for i := 0; i+1 < len(kv); i += 2 {
		m[kv[i]] = kv[i+1]
	}
	return m
}

// T is {{ t(key, name=value, ...) }}: the translated text, escaped.
func (p *page) T(key string, kv ...string) string { return esc(cat.Strings.T(p.Lang, key, params(kv))) }

// TL is {{ t(key, ...) | legal_links }}.
func (p *page) TL(key string, kv ...string) string {
	return legalLinks(esc(cat.Strings.T(p.Lang, key, params(kv))))
}

// E is {{ value }}: a plain value, escaped.
func (p *page) E(v string) string { return esc(v) }

// L picks a localized cookie-table text, as row.purpose[lang] or row.purpose['en'].
func (p *page) L(v localized) string {
	if s := v[p.Lang]; s != "" {
		return esc(s)
	}
	return esc(v["en"])
}

// Effective is {{ legal_effective(doc) }}.
func (p *page) Effective(doc string) string {
	version := map[string]string{"terms": p.cfg.TermsVersion, "privacy": p.cfg.PrivacyVersion, "dpa": p.cfg.DPAVersion}[doc]
	return esc(cat.Strings.T(p.Lang, doc+".effective", map[string]any{
		"date": effectiveDateText(p.cfg.EffectiveDate, p.Lang), "version": version,
	}))
}

// URL is seo.page_url(path, lang) for the head links, escaped.
func (p *page) URL(lang string) string {
	if lang == "" {
		return esc(p.PublicBase + p.Path)
	}
	return esc(p.PublicBase + p.Path + "?lang=" + lang)
}

// Canonical is seo.head_links' canonical_url: ?lang= only when the query
// asks for a public language.
func (p *page) Canonical() string { return p.URL(p.asked) }

// tojson is Jinja's |tojson (htmlsafe_json_dumps) for an ASCII string.
func tojson(s string) string {
	b, _ := json.Marshal(s)
	return strings.ReplaceAll(string(b), "'", `'`)
}

// legalPaths are templating._LEGAL_PATHS, in the regex's alternation order.
var legalPaths = []string{"/dpa", "/legal", "/privacy", "/subprocessors", "/terms"}

// legalLinks is templating._legal_links on already escaped text: a legal
// path at the start or after whitespace or "(", and followed by the end,
// whitespace or one of . , ; : ), becomes <a href="/x">/x</a>. Go regexp has
// no lookbehind, so this scans by hand; \s is Unicode whitespace as in Python.
func legalLinks(s string) string {
	var b strings.Builder
	prev := rune(-1) // -1: start of the string
	for i := 0; i < len(s); {
		if prev == -1 || prev == '(' || unicode.IsSpace(prev) {
			if path := legalPathAt(s[i:]); path != "" {
				b.WriteString(`<a href="` + path + `">` + path + `</a>`)
				i += len(path)
				prev = '/' // the last rune of a path is a letter; never a boundary
				continue
			}
		}
		r, size := utf8.DecodeRuneInString(s[i:])
		b.WriteString(s[i : i+size])
		prev = r
		i += size
	}
	return b.String()
}

func legalPathAt(s string) string {
	for _, path := range legalPaths {
		if !strings.HasPrefix(s, path) {
			continue
		}
		rest := s[len(path):]
		if rest == "" {
			return path
		}
		next, _ := utf8.DecodeRuneInString(rest)
		if unicode.IsSpace(next) || strings.ContainsRune(".,;:)", next) {
			return path
		}
	}
	return ""
}
