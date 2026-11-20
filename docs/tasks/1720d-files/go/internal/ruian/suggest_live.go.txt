// Package ruian — live ČÚZK geocoder for guest /l/.../ruian-suggest (App/app/ruian.py).
// Outbound: address text typed by the guest is sent only to ČÚZK; nothing is stored.
package ruian

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
	"unicode/utf8"
)

const (
	liveTimeout    = 4 * time.Second
	liveUserAgent  = "UbyHost"
	liveMinScore   = 60
	liveMaxRes     = 6
	liveAddrType   = "AdresniMisto"
	liveDefaultURL = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/Vyhledavaci_sluzba_nad_daty_RUIAN/MapServer/exts/GeocodeSOE/tables/1/findAddressCandidates"
)

// SuggestFields is the JSON the guest residence form reads.
type SuggestFields struct {
	Street   string `json:"addr_street,omitempty"`
	HouseNo  string `json:"addr_house_no,omitempty"`
	OrientNo string `json:"addr_orient_no,omitempty"`
	Zip      string `json:"addr_zip,omitempty"`
	Obec     string `json:"addr_obec,omitempty"`
	ObecCast string `json:"addr_obec_cast,omitempty"`
	Okres    string `json:"addr_okres,omitempty"`
}

// SuggestItem is one suggestion in the JSON list.
type SuggestItem struct {
	Label  string        `json:"label"`
	Fields SuggestFields `json:"fields"`
}

var liveCache = map[string]struct {
	at    time.Time
	items []SuggestItem
}{}

// UsableQuery is ruian.usable_query.
func UsableQuery(q string) string {
	text := strings.Join(strings.Fields(q), " ")
	if utf8.RuneCountInString(text) < 3 {
		return ""
	}
	return text
}

// FindURL reads UBYHOST_RUIAN_URL or the default geocoder.
func FindURL(getenv func(string) string) string {
	if u := strings.TrimSpace(getenv("UBYHOST_RUIAN_URL")); u != "" {
		return u
	}
	return liveDefaultURL
}

// SuggestLive fetches suggestions from ČÚZK. Errors yield an empty slice.
func SuggestLive(getenv func(string) string, q string) []SuggestItem {
	text := UsableQuery(q)
	if text == "" || !Enabled(getenv) {
		return []SuggestItem{}
	}
	key := strings.ToLower(text)
	if c, ok := liveCache[key]; ok && time.Since(c.at) < 24*time.Hour {
		return c.items
	}
	items := suggestHTTP(FindURL(getenv), text)
	if len(liveCache) > 1000 {
		liveCache = map[string]struct {
			at    time.Time
			items []SuggestItem
		}{}
	}
	liveCache[key] = struct {
		at    time.Time
		items []SuggestItem
	}{at: time.Now(), items: items}
	return items
}

func suggestHTTP(findURL, text string) []SuggestItem {
	client := &http.Client{Timeout: liveTimeout}
	u, err := url.Parse(findURL)
	if err != nil {
		return nil
	}
	q := u.Query()
	q.Set("SingleLine", text)
	q.Set("outFields", "*")
	q.Set("maxLocations", fmt.Sprintf("%d", liveMaxRes))
	q.Set("f", "json")
	u.RawQuery = q.Encode()
	req, err := http.NewRequest(http.MethodGet, u.String(), nil)
	if err != nil {
		return nil
	}
	req.Header.Set("User-Agent", liveUserAgent)
	resp, err := client.Do(req)
	if err != nil || resp.StatusCode < 200 || resp.StatusCode >= 300 {
		if resp != nil {
			_ = resp.Body.Close()
		}
		return nil
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil
	}
	var payload struct {
		Candidates []map[string]any `json:"candidates"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil
	}
	var kept []map[string]any
	for _, c := range payload.Candidates {
		if keepCandidate(c) {
			kept = append(kept, c)
		}
		if len(kept) >= liveMaxRes {
			break
		}
	}
	out := make([]SuggestItem, 0, len(kept))
	for _, c := range kept {
		if item := resolveCandidate(c); item != nil {
			out = append(out, *item)
		}
	}
	if out == nil {
		return []SuggestItem{}
	}
	return out
}

func keepCandidate(c map[string]any) bool {
	addr, _ := c["address"].(string)
	if strings.TrimSpace(addr) == "" {
		return false
	}
	score, ok := c["score"].(float64)
	if !ok || score < liveMinScore {
		return false
	}
	attrs, _ := c["attributes"].(map[string]any)
	if attrs != nil {
		if t, ok := attrs["Type"].(string); ok && t != "" && t != liveAddrType {
			return false
		}
	}
	return true
}

func resolveCandidate(c map[string]any) *SuggestItem {
	addr, _ := c["address"].(string)
	addr = strings.TrimSpace(addr)
	if addr == "" {
		return nil
	}
	return &SuggestItem{Label: addr, Fields: SuggestFields{}}
}
