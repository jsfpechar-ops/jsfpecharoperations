package invoices

// The Czech business register (ARES) lookup behind the "fill from register"
// button: App/app/ares.py (lookup, _map_payload, the per-owner rate limit)
// and routes/invoices.py _buyer_ares_fill. Only the IČO is sent to the
// register, as before (a request Python already makes: no new outbound
// request).

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"
)

const (
	aresTimeout   = 4 * time.Second
	aresCacheTTL  = 24 * time.Hour
	aresScope     = "ares"
	aresLimit     = 20
	aresWindow    = 3600.0
	aresUserAgent = "UbyHost"
)

// aresURL and aresClient are variables so tests can point them at a local server.
var (
	aresURL    = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/%s"
	aresClient = &http.Client{Timeout: aresTimeout}
)

// icoOK is validation.ico_ok: eight digits, the last a mod-11 check digit.
func icoOK(ico string) bool {
	text := strings.TrimSpace(ico)
	if len(text) != 8 {
		return false
	}
	for _, c := range text {
		if c < '0' || c > '9' {
			return false
		}
	}
	weights := [7]int{8, 7, 6, 5, 4, 3, 2}
	total := 0
	for i, w := range weights {
		total += int(text[i]-'0') * w
	}
	rem := total % 11
	check := 11 - rem
	switch rem {
	case 0:
		check = 1
	case 1:
		check = 0
	}
	return int(text[7]-'0') == check
}

// aresData is the mapped register entry (_map_payload).
type aresData struct {
	Name, Seat, Street, City, Zip, Country, DIC, RegistryEntry string
	VATPayer                                                   bool
}

var courts = map[string]string{
	"MSPH": "Městského soudu v Praze", "KSBR": "Krajského soudu v Brně", "KSOS": "Krajského soudu v Ostravě",
	"KSPH": "Krajského soudu v Praze", "KSPL": "Krajského soudu v Plzni", "KSUL": "Krajského soudu v Ústí nad Labem",
	"KSHK": "Krajského soudu v Hradci Králové", "KSCB": "Krajského soudu v Českých Budějovicích",
}

func formatRegistryMark(raw string) string {
	text := strings.TrimSpace(raw)
	if text == "" {
		return ""
	}
	i := strings.LastIndex(text, "/")
	if i < 0 {
		return text
	}
	mark, code := strings.TrimSpace(text[:i]), strings.TrimSpace(text[i+1:])
	court, ok := courts[code]
	if !ok {
		return text
	}
	return "spisová značka " + mark + " vedená u " + court
}

func jstr(v any) string {
	switch x := v.(type) {
	case string:
		return strings.TrimSpace(x)
	case json.Number:
		return x.String()
	}
	return ""
}

// pyStr is str(value).strip() for a JSON scalar (None counts as absent).
func pyStr(v any) (string, bool) {
	switch x := v.(type) {
	case nil:
		return "", false
	case string:
		return strings.TrimSpace(x), true
	case json.Number:
		return x.String(), true
	case bool:
		if x {
			return "True", true
		}
		return "False", true
	}
	return fmt.Sprint(v), true
}

func aresStreet(sidlo map[string]any) string {
	name := jstr(sidlo["nazevUlice"])
	if name == "" {
		return ""
	}
	cd, hasCD := sidlo["cisloDomovni"]
	co, hasCO := sidlo["cisloOrientacni"]
	hasCD, hasCO = hasCD && cd != nil, hasCO && co != nil
	letter := jstr(sidlo["cisloOrientacniPismeno"])
	switch {
	case hasCD && hasCO:
		a, _ := pyStr(cd)
		b, _ := pyStr(co)
		return name + " " + a + "/" + b + letter
	case hasCD:
		a, _ := pyStr(cd)
		return name + " " + a
	}
	return name
}

func mapAresPayload(p map[string]any) aresData {
	sidlo, _ := p["sidlo"].(map[string]any)
	if sidlo == nil {
		sidlo = map[string]any{}
	}
	zip, _ := pyStr(sidlo["psc"])
	if zip != "" && len(zip) < 5 && isDigits(zip) {
		zip = strings.Repeat("0", 5-len(zip)) + zip
	}
	reg, _ := p["seznamRegistraci"].(map[string]any)
	vat := strings.ToUpper(jstr(reg["stavZdrojeDph"])) == "AKTIVNI"
	entry := ""
	if blocks, ok := p["dalsiUdaje"].([]any); ok {
		for _, b := range blocks {
			block, _ := b.(map[string]any)
			if strings.ToLower(jstr(block["datovyZdroj"])) != "vr" {
				continue
			}
			if raw, ok := block["spisovaZnacka"].(string); ok && strings.TrimSpace(raw) != "" {
				entry = formatRegistryMark(strings.TrimSpace(raw))
				break
			}
		}
	}
	return aresData{
		Name: jstr(p["obchodniJmeno"]), Seat: jstr(sidlo["textovaAdresa"]), Street: aresStreet(sidlo),
		City: jstr(sidlo["nazevObce"]), Zip: zip, Country: "CZE", DIC: jstr(p["dic"]), VATPayer: vat, RegistryEntry: entry,
	}
}

var (
	aresMu    sync.Mutex
	aresCache = map[string]aresCacheEntry{}
)

type aresCacheEntry struct {
	at   time.Time
	data *aresData
}

// aresLookup is ares.lookup: the mapped entry, or nil on any failure
// (including an invalid IČO).
func aresLookup(ctx context.Context, ico string, now time.Time) *aresData {
	text := strings.TrimSpace(ico)
	if !icoOK(text) {
		return nil
	}
	aresMu.Lock()
	cached, ok := aresCache[text]
	aresMu.Unlock()
	if ok && now.Sub(cached.at) < aresCacheTTL {
		return cached.data
	}
	store := func(d *aresData) {
		aresMu.Lock()
		defer aresMu.Unlock()
		if len(aresCache) > 1000 {
			aresCache = map[string]aresCacheEntry{}
		}
		aresCache[text] = aresCacheEntry{at: now, data: d}
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, fmt.Sprintf(aresURL, text), nil)
	if err != nil {
		return nil
	}
	req.Header.Set("User-Agent", aresUserAgent)
	resp, err := aresClient.Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		store(nil)
		return nil
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 400 {
		return nil
	}
	var payload map[string]any
	dec := json.NewDecoder(resp.Body)
	dec.UseNumber()
	if err := dec.Decode(&payload); err != nil {
		return nil
	}
	data := mapAresPayload(payload)
	if data.Name == "" {
		return nil
	}
	store(&data)
	return &data
}

// aresField is data.get(key) for the buyer map; ok false for None.
func (a aresData) field(key string) (string, bool) {
	var v string
	switch key {
	case "name":
		v = a.Name
	case "street":
		v = a.Street
	case "city":
		v = a.City
	case "zip":
		v = a.Zip
	case "country":
		v = a.Country
	case "dic":
		if a.DIC == "" {
			return "", false // dic is None when ARES has none
		}
		v = a.DIC
	}
	return v, true
}

// buyerAresMap is _BUYER_ARES_MAP in order.
var buyerAresMap = [][2]string{
	{"buyer_name", "name"}, {"buyer_street", "street"}, {"buyer_city", "city"},
	{"buyer_zip", "zip"}, {"buyer_country", "country"}, {"buyer_dic", "dic"},
}

type aresMeta struct{ Error, Note string }

// rateBlocked is rate_limit.blocked: prune the window, then count.
func rateBlocked(ctx context.Context, d deps, scope, key string, limit int64, window float64, now time.Time) (bool, error) {
	if key == "" {
		return true, nil
	}
	at := float64(now.UnixNano()) / 1e9
	if _, err := d.pool.Exec(ctx, `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`, scope, key, at-window); err != nil {
		return false, err
	}
	var n int64
	if err := d.pool.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`, scope, key).Scan(&n); err != nil {
		return false, err
	}
	return n >= limit, nil
}

// rateRecord is rate_limit.record.
func rateRecord(ctx context.Context, d deps, scope, key string, now time.Time) error {
	_, err := d.pool.Exec(ctx, `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`, scope, key, float64(now.UnixNano())/1e9)
	return err
}

// buyerAresFill is _buyer_ares_fill: fill the blank buyer fields of values
// from the register, under the per-owner limit of 20 lookups an hour.
func (c *call) buyerAresFill(values map[string]string) (aresMeta, error) {
	ctx := c.r.Context()
	ico := c.formStr("buyer_ico")
	if ico == "" {
		ico = strings.TrimSpace(values["buyer_ico"])
	}
	key := itoa(c.owner)
	blocked, err := rateBlocked(ctx, c.deps, aresScope, key, aresLimit, aresWindow, c.at)
	if err != nil {
		return aresMeta{}, err
	}
	if blocked {
		return aresMeta{Error: c.t("ares.rate_limited", nil)}, nil
	}
	if !icoOK(ico) {
		return aresMeta{Error: c.t("ares.failure", nil)}, nil
	}
	if err := rateRecord(ctx, c.deps, aresScope, key, c.at); err != nil {
		return aresMeta{}, err
	}
	data := aresLookup(ctx, ico, c.at)
	if data == nil {
		return aresMeta{Error: c.t("ares.failure", nil)}, nil
	}
	var filled []string
	for _, m := range buyerAresMap {
		if strings.TrimSpace(values[m[0]]) != "" {
			continue
		}
		v, ok := data.field(m[1])
		if !ok || strings.TrimSpace(v) == "" {
			continue
		}
		values[m[0]] = v
		filled = append(filled, m[0])
	}
	var meta aresMeta
	if len(filled) > 0 {
		labels := make([]string, len(filled))
		for i, f := range filled {
			labels[i] = c.t("ares.field."+f, nil)
		}
		meta.Note = c.t("ares.filled", map[string]any{"fields": strings.Join(labels, ", ")})
	}
	return meta, nil
}
