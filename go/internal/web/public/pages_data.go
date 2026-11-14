package public

// The marketing pages (/jak-to-funguje, /cenik, /pruvodce/{slug}), ported
// from App/app/routes/legal.py and the product.html, pricing.html and
// public_guide.html templates (briefs 1620 to 1622). Copy, guides and rates
// come from catalog_pages.json, written by App/scripts/public_pages_golden.py;
// never edit it by hand. As for the legal pages, templates are rendered with
// text/template and print only through the escaping methods below.

import (
	"embed"
	"encoding/json"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

//go:embed catalog_pages.json
var pagesJSON []byte

//go:embed templates/pages/*.tmpl
var pagesFS embed.FS

type guideSection struct {
	Heading    string   `json:"heading"`
	Paragraphs []string `json:"paragraphs"`
}

type guideData struct {
	Title       string         `json:"title"`
	Updated     string         `json:"updated"`
	Description string         `json:"description"`
	Eyebrow     string         `json:"eyebrow"`
	Lede        string         `json:"lede"`
	OfficialURL string         `json:"official_url"`
	Sections    []guideSection `json:"sections"`
	Checklist   []string       `json:"checklist"`
}

type guideSet struct {
	Order []string             `json:"order"`
	Items map[string]guideData `json:"items"`
}

type pagesCatalog struct {
	Strings hostweb.Catalog     `json:"strings"`
	Guides  map[string]guideSet `json:"guides"`
	Rates   map[string]any      `json:"rates"`
	Icons   map[string]string   `json:"icons"`
}

var pcat = loadPagesCatalog(pagesJSON)

func loadPagesCatalog(data []byte) pagesCatalog {
	var c pagesCatalog
	if err := json.Unmarshal(data, &c); err != nil {
		panic("public: bad catalog_pages.json: " + err.Error())
	}
	return c
}

// link is one <link rel="alternate">; both fields are already escaped.
type link struct{ Code, Href string }

// pg is the data of one marketing page render.
type pg struct {
	Lang, Path, Active, SwitchPath string
	Alternates                     []link
	Guide                          guideData
	Guides                         []guideEntry // the other guides, in dictionary order
	Slug                           string
	SignupHref                     string // "" while sign-up is off
	Start                          startValues
	PostHog                        bool
	PHKeyJS, PHHostJS, PHAssetsJS  string
	cfg                            config
	canonical                      string
}

type guideEntry struct {
	Slug  string
	Title string
}

// startValues is the "start" dict of legal.pricing (brief 1622).
type startValues struct {
	StdMonth, MaxMonth, StdYear, MaxYear, TTLockMonth string
	Bands                                             [3]string
}

func newPG(path, lang string, cfg config) *pg {
	p := &pg{Lang: lang, Path: path, cfg: cfg, PostHog: cfg.posthogOn()}
	if p.PostHog {
		p.PHKeyJS, p.PHHostJS, p.PHAssetsJS = pyJSON(cfg.PHKey), pyJSON(httpsOrigin(cfg.PHHost)), pyJSON(httpsOrigin(cfg.PHAssets))
	}
	return p
}

// params turns "name", value pairs into a translate mapping (public.params).
func (p *pg) tr(key string, kv ...string) string {
	return pcat.Strings.T(p.Lang, key, params(kv))
}

// T is {{ t(key, name=value, ...) }}: the translated text, escaped.
func (p *pg) T(key string, kv ...string) string { return esc(p.tr(key, kv...)) }

// TP is {{ tp(base, n) }}: host_i18n.translate_plural, escaped.
func (p *pg) TP(base string, n int) string {
	form := base
	switch {
	case n == 1:
		form = base + ".one"
	case n >= 2 && n <= 4:
		form = base + ".few"
	}
	return esc(pcat.Strings.T(p.Lang, form, map[string]any{"count": n, "n": n}))
}

// E is {{ value }}: a plain value, escaped.
func (p *pg) E(v string) string { return esc(v) }

// Icon is {{ icon(name, 14) }}: the SVG text from the catalog (no outside text).
func (p *pg) Icon(name string) string { return pcat.Icons[name] }

// Canonical is canonical_url, escaped.
func (p *pg) Canonical() string { return esc(p.canonical) }

// PublicBase is public_base_url, escaped.
func (p *pg) PublicBase() string { return esc(p.cfg.PublicBase) }

// URL is seo.page_url(path, lang), escaped.
func (p *pg) URL(path, lang string) string {
	if lang == "" {
		return esc(p.cfg.PublicBase + path)
	}
	return esc(p.cfg.PublicBase + path + "?lang=" + lang)
}

// LangIf prints v when the page language is lang, else "" (Jinja: 'x' if lang == 'cs').
func (p *pg) LangIf(lang, v string) string {
	if p.Lang == lang {
		return v
	}
	return ""
}

// OGLocale is 'cs_CZ' if lang == 'cs' else 'en_US'.
func (p *pg) OGLocale() string {
	if p.Lang == "cs" {
		return "cs_CZ"
	}
	return "en_US"
}

// OfficialLink is product.html's ipc.gov.cz link for the page language.
func (p *pg) OfficialLink() string {
	if p.Lang == "en" {
		return "https://ipc.gov.cz/en/accommodation-providers/general-information-for-accommodation-providers/"
	}
	return "https://ipc.gov.cz/pro-ubytovatele/obecne-informace-pro-ubytovatele/"
}

// FAQJSON is the FAQPage block of product.html as |tojson prints it.
func (p *pg) FAQJSON() string {
	var items []any
	for _, n := range []string{"1", "2", "3", "4"} {
		items = append(items, map[string]any{
			"@type": "Question", "name": p.tr("landing.faq." + n + ".q"),
			"acceptedAnswer": map[string]any{"@type": "Answer", "text": p.tr("landing.faq." + n + ".a")},
		})
	}
	return pyJSON(map[string]any{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items})
}

// ArticleJSON is the Article block of public_guide.html as |tojson prints it.
func (p *pg) ArticleJSON() string {
	org := map[string]any{"@type": "Organization", "name": "UbyHost", "url": p.cfg.PublicBase + "/"}
	return pyJSON(map[string]any{
		"@context": "https://schema.org", "@type": "Article",
		"headline": p.Guide.Title, "description": p.Guide.Description, "inLanguage": p.Lang,
		"datePublished": p.Guide.Updated, "dateModified": p.Guide.Updated,
		"mainEntityOfPage": p.canonical, "author": org, "publisher": org,
	})
}

// pyJSON is Jinja's |tojson (htmlsafe_json_dumps over json.dumps with
// sort_keys, the default separators and ensure_ascii) for maps, slices,
// strings, numbers, booleans and nil.
func pyJSON(v any) string {
	var b strings.Builder
	writeJSON(&b, v)
	s := b.String()
	for _, r := range [][2]string{{"<", u + "003c"}, {">", u + "003e"}, {"&", u + "0026"}, {"'", u + "0027"}} {
		s = strings.ReplaceAll(s, r[0], r[1])
	}
	return s
}

// u starts a JSON unicode escape (a backslash and "u").
const u = "\\u"

func writeJSON(b *strings.Builder, v any) {
	switch v := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		b.WriteString(strconv.FormatBool(v))
	case string:
		writeJSONString(b, v)
	case int:
		b.WriteString(strconv.Itoa(v))
	case float64:
		b.WriteString(strconv.FormatFloat(v, 'f', -1, 64))
	case []any:
		b.WriteByte('[')
		for i, e := range v {
			if i > 0 {
				b.WriteString(", ")
			}
			writeJSON(b, e)
		}
		b.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(v))
		for k := range v {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteString(", ")
			}
			writeJSONString(b, k)
			b.WriteString(": ")
			writeJSON(b, v[k])
		}
		b.WriteByte('}')
	default:
		panic("public: pyJSON: unsupported type")
	}
}

func writeJSONString(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '"':
			b.WriteString(`\"`)
		case r == '\\':
			b.WriteString(`\\`)
		case r == '\n':
			b.WriteString(`\n`)
		case r == '\r':
			b.WriteString(`\r`)
		case r == '\t':
			b.WriteString(`\t`)
		case r == '\b':
			b.WriteString(`\b`)
		case r == '\f':
			b.WriteString(`\f`)
		case r >= 0x20 && r <= 0x7e:
			b.WriteRune(r)
		case r > 0xffff:
			hi, lo := utf16.EncodeRune(r)
			b.WriteString(`\u` + hex4(int(hi)) + `\u` + hex4(int(lo)))
		default:
			b.WriteString(`\u` + hex4(int(r)))
		}
	}
	b.WriteByte('"')
}

func hex4(n int) string {
	s := strconv.FormatInt(int64(n), 16)
	return strings.Repeat("0", 4-len(s)) + s
}

// routeLang is host_i18n.resolve_language(request, default=PUBLIC_DEFAULT_LANGUAGE)
// as the three routes call it: ?lang=, then the cookie, each through
// supported_language (en, cs or vi), else Czech; never the signed-in default.
func routeLang(r *http.Request) string {
	for _, v := range []string{r.URL.Query().Get("lang"), hostweb.Cookie(r, langCookieName)} {
		if l := supportedLanguage(v); l != "" {
			return l
		}
	}
	return publicDefault
}
