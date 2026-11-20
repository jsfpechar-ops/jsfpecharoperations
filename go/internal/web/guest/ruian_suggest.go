package guest

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ruian"
)

const (
	ruianGuestScope = "ruian_guest"
	ruianGuestMax   = 120
	ruianGuestWin   = 15 * 60
	ruianOwnerScope = "ruian"
	ruianOwnerMax   = 60
	ruianOwnerWin   = 60 * 60
)

func writeGuestJSON(w http.ResponseWriter, status int, v any) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(bytes.TrimRight(buf.Bytes(), "\n"))
}

func (d shellDeps) ruianSuggest(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	lang := Language(r)
	key := r.PathValue("token")
	now := d.now()
	apt, link, early := OpenLink(r, d.pool, key, lang)
	if early != nil {
		early.ServeHTTP(w, r)
		return
	}
	if requirePin(w, r, d, link, lang, apt) {
		return
	}
	if !ruian.Enabled(d.getenv) {
		writeGuestJSON(w, http.StatusNotFound, map[string]string{"error": "not_found"})
		return
	}
	q := r.URL.Query().Get("q")
	if ruian.UsableQuery(q) == "" {
		writeGuestJSON(w, http.StatusOK, []any{})
		return
	}
	lockToken := link
	if apt != nil && apt.PermalinkToken != "" {
		lockToken = apt.PermalinkToken
	}
	ipKey := clientip.Key(r, d.getenv, fmt.Sprintf("%s:%s", ruianGuestScope, lockToken))
	guestLimited, err := rateBlocked(ctx, d.pool, ruianGuestScope, ipKey, ruianGuestMax, ruianGuestWin, now)
	if err != nil {
		writeGuestJSON(w, http.StatusOK, []any{})
		return
	}
	ownerID := int64(0)
	if apt != nil {
		ownerID = apt.OwnerUserID
	}
	ownerKey := fmt.Sprintf("%d", ownerID)
	ownerLimited, err := rateBlocked(ctx, d.pool, ruianOwnerScope, ownerKey, ruianOwnerMax, ruianOwnerWin, now)
	if err != nil {
		writeGuestJSON(w, http.StatusOK, []any{})
		return
	}
	if guestLimited || ownerLimited {
		writeGuestJSON(w, http.StatusTooManyRequests, map[string]string{"error": "rate_limited"})
		return
	}
	_ = rateRecord(ctx, d.pool, ruianGuestScope, ipKey, now)
	if ownerID > 0 {
		_ = rateRecord(ctx, d.pool, ruianOwnerScope, ownerKey, now)
	}
	items := ruian.SuggestLive(d.getenv, q)
	if items == nil {
		items = []ruian.SuggestItem{}
	}
	writeGuestJSON(w, http.StatusOK, items)
}
