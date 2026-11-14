package public

// GET /cenik, legal.pricing and pricing.html (brief 1622).

import (
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
)

func init() { PricingHandler = pricingHandler }

// nowFunc is the clock of the click value signup_href mints; tests replace it.
var nowFunc = time.Now

// rateList is PUBLIC_RATES[plan][interval] as ints.
func rateList(plan, interval string) []int {
	raw, _ := pcat.Rates[plan].(map[string]any)[interval].([]any)
	out := make([]int, len(raw))
	for i, v := range raw {
		out[i] = int(v.(float64))
	}
	return out
}

// graduated is legal._graduated: each band prices only the apartments in it.
func graduated(count int, rates []int) int {
	sum := 0
	for i := 1; i <= count; i++ {
		switch {
		case i <= 4:
			sum += rates[0]
		case i <= 9:
			sum += rates[1]
		default:
			sum += rates[2]
		}
	}
	return sum
}

// perMonth is legal._per_month: a yearly total per month, rounded half up.
func perMonth(yearTotal int) int { return (yearTotal*2 + 12) / 24 }

// kc is legal._kc: "1 190" with a no-break space in Czech, "1,190" otherwise.
func kc(amount int, lang string) string {
	s := strconv.Itoa(amount)
	for i := len(s) - 3; i > 0; i -= 3 {
		sep := ","
		if lang == "cs" {
			sep = "\u00a0"
		}
		s = s[:i] + sep + s[i:]
	}
	return s
}

func startFor(lang string) startValues {
	stdYear := graduated(1, rateList("base", "year"))
	maxYear := stdYear + graduated(1, rateList("max", "year"))
	ttlock, _ := pcat.Rates["ttlock"].(map[string]any)["year"].(float64)
	v := startValues{
		StdMonth: kc(perMonth(stdYear), lang), MaxMonth: kc(perMonth(maxYear), lang),
		StdYear: kc(stdYear, lang), MaxYear: kc(maxYear, lang), TTLockMonth: kc(perMonth(int(ttlock)), lang),
	}
	for i, rate := range rateList("base", "year") {
		v.Bands[i] = kc(perMonth(rate), lang)
	}
	return v
}

// signupHref is signup.signup_href(lang, request.query_params):
// "/signup?" and urlencode of lang, the attribution labels and click value,
// then the bounded plan choices, in that order.
func signupHref(secret, lang string, q url.Values, now time.Time) string {
	pairs := [][2]string{{"lang", lang}}
	attr := signup.Attribution(secret, q, true, now.UnixMilli())
	for _, k := range append(append([]string{}, signup.UTMKeys...), "click") {
		if v := attr[k]; v != "" {
			pairs = append(pairs, [2]string{k, v})
		}
	}
	sel := signup.CleanSelection(q)
	for _, k := range []string{"plan", "interval", "ttlock", "apartments"} {
		if v := sel[k]; v != "" {
			pairs = append(pairs, [2]string{k, v})
		}
	}
	var b strings.Builder
	for i, kv := range pairs {
		if i > 0 {
			b.WriteByte('&')
		}
		b.WriteString(url.QueryEscape(kv[0]) + "=" + url.QueryEscape(kv[1]))
	}
	return "/signup?" + b.String()
}

// CTA is cta_href(plan): the sign-up link with the plan, or /login.
func (p *pg) CTA(plan string) string {
	if p.SignupHref == "" {
		return "/login?lang=" + p.Lang
	}
	return esc(p.SignupHref) + "&plan=" + plan + "&interval=year&apts=1"
}

// Band is start.bands[i].
func (p *pg) Band(i int) string { return p.Start.Bands[i] }

// RatesJSON is {{ rates | tojson }}.
func (p *pg) RatesJSON() string { return pyJSON(pcat.Rates) }

// WebPageJSON is the WebPage block of pricing.html as |tojson prints it.
func (p *pg) WebPageJSON() string {
	return pyJSON(map[string]any{
		"@context": "https://schema.org", "@type": "WebPage",
		"name": p.tr("pricing.page_title"), "description": p.tr("pricing.meta_description"),
		"url": p.canonical, "inLanguage": p.Lang,
		"isPartOf": map[string]any{"@type": "WebSite", "name": "UbyHost", "url": p.cfg.PublicBase + "/"},
	})
}

// PricingFAQJSON is the FAQPage block of pricing.html as |tojson prints it.
func (p *pg) PricingFAQJSON() string {
	var items []any
	for n := 1; n <= 9; n++ {
		id := strconv.Itoa(n)
		items = append(items, map[string]any{
			"@type": "Question", "name": p.tr("pricing.faq." + id + ".q"),
			"acceptedAnswer": map[string]any{"@type": "Answer", "text": p.tr("pricing.faq." + id + ".a")},
		})
	}
	return pyJSON(map[string]any{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items})
}

// pricingHandler is legal.pricing (GET /cenik). The start prices and the
// sign-up link use the route language (public default Czech, never the
// signed-in default), the page text the render language.
func pricingHandler(d Deps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		cfg := loadConfig(d.Getenv)
		routeL := routeLang(r)
		p := newPG("/cenik", resolveLang(r, d.SignedIn), cfg)
		p.Active, p.SwitchPath = "pricing", "/cenik"
		p.headLinks(r)
		p.Start = startFor(routeL)
		if cfg.SignupEnabled {
			secret, err := secure.LoadSecret(d.Getenv)
			if err != nil {
				http.Error(w, "Internal Server Error", http.StatusInternalServerError)
				return
			}
			p.SignupHref = signupHref(secret, routeL, r.URL.Query(), nowFunc())
		}
		renderPage(w, r, cfg, "pricing", p)
	}
}
