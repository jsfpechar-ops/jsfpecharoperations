package billingweb

// The ARES lookup of the order form (App/app/ares.py lookup and _map_payload,
// brief 1557). It sends only the IC to the Czech business register, exactly as
// Python does. Tests never reach the network: they give the client a stub transport.

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
)

const (
	aresURL          = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/" // ares._API_URL
	aresTimeout      = 4 * time.Second                                                          // ares._TIMEOUT_SECONDS
	aresUserAgent    = "UbyHost"                                                                // ares._USER_AGENT
	aresCacheTTL     = 24 * time.Hour                                                           // ares._CACHE_TTL_SECONDS
	aresCacheMax     = 1000
	aresRateScope    = "ares" // ares._RATE_SCOPE
	aresRateLimit    = 20     // ares._RATE_LIMIT
	aresRateWindow   = 60 * 60
	aresMaxBodyBytes = 1 << 20
)

// AresData is the part of ares._map_payload the order form reads.
type AresData struct {
	Name, Street, City, Zip string
	DIC                     string // "" is Python's None
}

type aresEntry struct {
	at   time.Time
	data *AresData
}

// AresClient is ares.lookup with its 24 hour in-process cache.
type AresClient struct {
	HTTP *http.Client // nil: a client with the 4 second timeout
	URL  string       // "" is the register's address
	mu   sync.Mutex
	seen map[string]aresEntry
}

func (a *AresClient) client() *http.Client {
	if a.HTTP != nil {
		return a.HTTP
	}
	return &http.Client{Timeout: aresTimeout}
}

// Lookup is ares.lookup (lines 126-151): the mapped data, or nil on any
// failure, a bad IC included. It returns at most one outbound GET per IC a day.
func (a *AresClient) Lookup(ico string, now time.Time) *AresData {
	text := pyStrip(ico)
	if !billing.ICOOK(text) {
		return nil
	}
	a.mu.Lock()
	if e, ok := a.seen[text]; ok && now.Sub(e.at) < aresCacheTTL {
		a.mu.Unlock()
		return e.data
	}
	a.mu.Unlock()
	base := a.URL
	if base == "" {
		base = aresURL
	}
	req, err := http.NewRequest(http.MethodGet, base+text, nil)
	if err != nil {
		return nil
	}
	req.Header.Set("User-Agent", aresUserAgent)
	resp, err := a.client().Do(req)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		a.store(text, now, nil)
		return nil
	}
	if resp.StatusCode >= 400 {
		return nil
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, aresMaxBodyBytes))
	if err != nil {
		return nil
	}
	data := mapAresPayload(body)
	if data == nil || data.Name == "" {
		return nil
	}
	a.store(text, now, data)
	return data
}

func (a *AresClient) store(text string, now time.Time, data *AresData) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.seen == nil || len(a.seen) > aresCacheMax {
		a.seen = map[string]aresEntry{}
	}
	a.seen[text] = aresEntry{now, data}
}

// jsonStr is `(value or "").strip()`: ok is false where Python would raise
// (a value that is not text), which the caller's except turns into "no data".
func jsonStr(v any) (string, bool) {
	switch x := v.(type) {
	case nil:
		return "", true
	case string:
		return pyStrip(x), true
	case bool:
		if !x {
			return "", true
		}
	case json.Number:
		if x.String() == "0" {
			return "", true
		}
	}
	return "", false
}

// pyText is str(value) for a JSON scalar.
func pyText(v any) string {
	switch x := v.(type) {
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
	return fmt.Sprint(v)
}

// mapAresPayload is _map_payload for the fields the form reads; nil when the
// payload is not the object Python would map (its exception becomes "no data").
func mapAresPayload(body []byte) *AresData {
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	var payload map[string]any
	if dec.Decode(&payload) != nil || payload == nil {
		return nil
	}
	sidlo := map[string]any{}
	if v, ok := payload["sidlo"]; ok && v != nil {
		m, isMap := v.(map[string]any)
		if !isMap {
			if s, isStr := v.(string); !isStr || s != "" {
				return nil
			}
		} else {
			sidlo = m
		}
	}
	var ok bool
	var out AresData
	if out.Name, ok = jsonStr(payload["obchodniJmeno"]); !ok {
		return nil
	}
	if out.City, ok = jsonStr(sidlo["nazevObce"]); !ok {
		return nil
	}
	if out.DIC, ok = jsonStr(payload["dic"]); !ok {
		return nil
	}
	if out.Street, ok = aresStreet(sidlo); !ok {
		return nil
	}
	if psc, has := sidlo["psc"]; has && psc != nil {
		out.Zip = pyStrip(pyText(psc))
		if out.Zip != "" && len([]rune(out.Zip)) < 5 && isAllDigits(out.Zip) {
			out.Zip = strings.Repeat("0", 5-len([]rune(out.Zip))) + out.Zip
		}
	}
	return &out
}

func isAllDigits(s string) bool {
	for _, r := range s {
		if !unicode.IsDigit(r) {
			return false
		}
	}
	return s != ""
}

// aresStreet is ares._street (lines 73-85).
func aresStreet(sidlo map[string]any) (string, bool) {
	name, ok := jsonStr(sidlo["nazevUlice"])
	if !ok || name == "" {
		return "", ok
	}
	parts := []string{name}
	cd, co := sidlo["cisloDomovni"], sidlo["cisloOrientacni"]
	letter, ok := jsonStr(sidlo["cisloOrientacniPismeno"])
	if !ok {
		return "", false
	}
	switch {
	case cd != nil && co != nil:
		parts = append(parts, pyText(cd)+"/"+pyText(co)+letter)
	case cd != nil:
		parts = append(parts, pyText(cd))
	}
	return strings.Join(parts, " "), true
}
