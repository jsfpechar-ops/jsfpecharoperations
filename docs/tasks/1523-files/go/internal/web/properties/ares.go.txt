package properties

// Brief 1523: the ARES business register lookup (App/app/ares.py) and the
// per-owner limit (rate_limit.py blocked/record). The only data sent is the
// IČO, in the URL, on the host's click ("Fill from register").

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
)

// aresURL is _API_URL; a test points it at a local server (never the real one).
var aresURL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/%s"

const (
	aresTimeout   = 4 * time.Second
	aresCacheTTL  = 24 * time.Hour
	aresRateScope = "ares"
	aresRateMax   = 20
	aresRateWin   = 60 * 60
	aresMaxBody   = 1 << 20
)

// aresData is the mapped ARES answer (_map_payload).
type aresData struct {
	Name, Seat, Street, City, Zip string
	DIC                           string // "" is None
	VATPayer                      bool
	RegistryEntry                 string
}

type aresCacheEntry struct {
	at   time.Time
	data *aresData
}

var (
	aresMu    sync.Mutex
	aresCache = map[string]aresCacheEntry{}
	aresClock = time.Now
)

var aresCourts = map[string]string{
	"MSPH": "Městského soudu v Praze", "KSBR": "Krajského soudu v Brně", "KSOS": "Krajského soudu v Ostravě",
	"KSPH": "Krajského soudu v Praze", "KSPL": "Krajského soudu v Plzni", "KSUL": "Krajského soudu v Ústí nad Labem",
	"KSHK": "Krajského soudu v Hradci Králové", "KSCB": "Krajského soudu v Českých Budějovicích",
}

func jsonText(v any) string {
	switch x := v.(type) {
	case nil:
		return ""
	case string:
		return x
	case json.Number:
		return x.String()
	case bool:
		if x {
			return "True"
		}
		return "False"
	}
	return ""
}

func jsonMap(v any) map[string]any {
	m, _ := v.(map[string]any)
	if m == nil {
		return map[string]any{}
	}
	return m
}

func formatRegistryMark(raw string) string {
	text := pyStrip(raw)
	if text == "" {
		return ""
	}
	i := strings.LastIndex(text, "/")
	if i < 0 {
		return text
	}
	mark, code := pyStrip(text[:i]), pyStrip(text[i+1:])
	court, ok := aresCourts[code]
	if !ok {
		return text
	}
	return "spisová značka " + mark + " vedená u " + court
}

func aresStreet(sidlo map[string]any) string {
	name := pyStrip(jsonText(sidlo["nazevUlice"]))
	if name == "" {
		return ""
	}
	parts := []string{name}
	cd, co := sidlo["cisloDomovni"], sidlo["cisloOrientacni"]
	letter := pyStrip(jsonText(sidlo["cisloOrientacniPismeno"]))
	switch {
	case cd != nil && co != nil:
		parts = append(parts, jsonText(cd)+"/"+jsonText(co)+letter)
	case cd != nil:
		parts = append(parts, jsonText(cd))
	}
	return strings.Join(parts, " ")
}

func aresRegistryEntry(payload map[string]any) string {
	list, _ := payload["dalsiUdaje"].([]any)
	for _, b := range list {
		block := jsonMap(b)
		if strings.ToLower(jsonText(block["datovyZdroj"])) != "vr" {
			continue
		}
		if raw, ok := block["spisovaZnacka"].(string); ok && pyStrip(raw) != "" {
			return formatRegistryMark(pyStrip(raw))
		}
	}
	return ""
}

// mapAres is ares._map_payload.
func mapAres(payload map[string]any) aresData {
	sidlo := jsonMap(payload["sidlo"])
	zip := ""
	if sidlo["psc"] != nil {
		zip = pyStrip(jsonText(sidlo["psc"]))
	}
	if zip != "" && len(zip) < 5 && isDigits(zip) {
		zip = strings.Repeat("0", 5-len(zip)) + zip
	}
	reg := jsonMap(payload["seznamRegistraci"])
	return aresData{
		Name:          pyStrip(jsonText(payload["obchodniJmeno"])),
		Seat:          pyStrip(jsonText(sidlo["textovaAdresa"])),
		Street:        aresStreet(sidlo),
		City:          pyStrip(jsonText(sidlo["nazevObce"])),
		Zip:           zip,
		DIC:           pyStrip(jsonText(payload["dic"])),
		VATPayer:      strings.ToUpper(jsonText(reg["stavZdrojeDph"])) == "AKTIVNI",
		RegistryEntry: aresRegistryEntry(payload),
	}
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if !unicode.IsDigit(c) {
			return false
		}
	}
	return true
}

// aresLookup is ares.lookup: the mapped data, or nil on any failure (an invalid
// IČO, a 404 which is cached, a non-2xx answer, a body without a name, a network error).
func aresLookup(ctx context.Context, ico string) *aresData {
	text := pyStrip(ico)
	if !billing.ICOOK(text) {
		return nil
	}
	now := aresClock()
	aresMu.Lock()
	if c, ok := aresCache[text]; ok && now.Sub(c.at) < aresCacheTTL {
		aresMu.Unlock()
		return c.data
	}
	aresMu.Unlock()
	store := func(d *aresData) {
		aresMu.Lock()
		defer aresMu.Unlock()
		if len(aresCache) > 1000 {
			aresCache = map[string]aresCacheEntry{}
		}
		aresCache[text] = aresCacheEntry{now, d}
	}
	ctx, cancel := context.WithTimeout(ctx, aresTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, strings.Replace(aresURL, "%s", text, 1), nil)
	if err != nil {
		return nil
	}
	req.Header.Set("User-Agent", "UbyHost")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		store(nil)
		return nil
	}
	if resp.StatusCode >= 400 {
		return nil
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, aresMaxBody))
	if err != nil {
		return nil
	}
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	var payload map[string]any
	if err := dec.Decode(&payload); err != nil {
		return nil
	}
	data := mapAres(payload)
	if data.Name == "" {
		return nil
	}
	store(&data)
	return &data
}

const (
	ratePruneSQL = `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`
	rateCountSQL = `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`
	rateAddSQL   = `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`
)

func epoch(t time.Time) float64 { return float64(t.UnixNano()) / 1e9 }

// rateBlocked is rate_limit.blocked: prune the window, then count.
func rateBlocked(ctx context.Context, pool *pgxpool.Pool, scope, key string, max int64, window int64, at time.Time) (bool, error) {
	if key == "" {
		return true, nil
	}
	if _, err := pool.Exec(ctx, ratePruneSQL, scope, key, epoch(at)-float64(window)); err != nil {
		return false, err
	}
	var n int64
	if err := pool.QueryRow(ctx, rateCountSQL, scope, key).Scan(&n); err != nil {
		return false, err
	}
	return n >= max, nil
}

func rateRecord(ctx context.Context, pool *pgxpool.Pool, scope, key string, at time.Time) error {
	_, err := pool.Exec(ctx, rateAddSQL, scope, key, epoch(at))
	return err
}

// registerLookup is invoices.register_lookup: one click-only ARES lookup under
// the per-owner limit (20 an hour) and the cache. It returns the data, or the
// translated error text.
func registerLookup(ctx context.Context, pool *pgxpool.Pool, owner int64, lang, ico string, at time.Time) (*aresData, string, error) {
	key := itoa64(owner)
	limited, err := rateBlocked(ctx, pool, aresRateScope, key, aresRateMax, aresRateWin, at)
	if err != nil {
		return nil, "", err
	}
	if limited {
		return nil, catalog.T(lang, "ares.rate_limited", nil), nil
	}
	if !billing.ICOOK(ico) {
		return nil, catalog.T(lang, "ares.failure", nil), nil
	}
	if err := rateRecord(ctx, pool, aresRateScope, key, at); err != nil {
		return nil, "", err
	}
	data := aresLookup(ctx, ico)
	if data == nil {
		return nil, catalog.T(lang, "ares.failure", nil), nil
	}
	return data, "", nil
}

// mergeBlank is ares.merge_blank over the named fields of values: it fills a
// blank field from data when data has a non-blank value, and returns the names it filled.
func mergeBlank(values map[string]string, data *aresData, fields ...string) []string {
	var filled []string
	for _, f := range fields {
		if pyStrip(values[f]) != "" {
			continue
		}
		var v string
		switch f {
		case "name":
			v = data.Name
		case "seat":
			v = data.Seat
		case "dic":
			v = data.DIC
		case "registry_entry":
			v = data.RegistryEntry
		}
		if pyStrip(v) == "" {
			continue
		}
		values[f] = v
		filled = append(filled, f)
	}
	return filled
}

// registerFilledNote is invoices.register_filled_note.
func registerFilledNote(lang string, filled []string) string {
	if len(filled) == 0 {
		return ""
	}
	labels := make([]string, len(filled))
	for i, f := range filled {
		labels[i] = catalog.T(lang, "ares.field."+f, nil)
	}
	return catalog.T(lang, "ares.filled", map[string]any{"fields": strings.Join(labels, ", ")})
}
