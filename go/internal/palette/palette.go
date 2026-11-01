// Package palette serves GET /api/command-palette, the Ctrl-K list of pages,
// actions, properties, stays and submissions. It ports App/app/routes/api.py
// command_palette as-is: the same items, in the same order, with the same keys.
package palette

import (
	"bytes"
	"context"
	_ "embed"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the host strings this endpoint reads (i18n_keys.txt).
var catalog = hostweb.Load(catalogJSON)

// unauthorized is the body require_login gives the palette: JSON, never a redirect.
const unauthorized = `{"items":[]}`

// field is one key of an item, in the order Python inserted it.
type field struct {
	k string
	v any
}

// object is a JSON object whose keys keep their insertion order.
type object []field

// MarshalJSON writes the keys in order, each value encoded without HTML escaping.
func (o object) MarshalJSON() ([]byte, error) {
	var b bytes.Buffer
	b.WriteByte('{')
	for i, f := range o {
		if i > 0 {
			b.WriteByte(',')
		}
		k, err := marshalNoHTML(f.k)
		if err != nil {
			return nil, err
		}
		v, err := marshalNoHTML(f.v)
		if err != nil {
			return nil, err
		}
		b.Write(k)
		b.WriteByte(':')
		b.Write(v)
	}
	b.WriteByte('}')
	return b.Bytes(), nil
}

// marshalNoHTML is json.dumps(..., ensure_ascii=False, separators=(",", ":")) for
// the values used here: compact, no HTML escaping, no trailing newline.
func marshalNoHTML(v any) ([]byte, error) {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(b.Bytes(), []byte("\n")), nil
}

// discard is the response Login writes its redirect to when the request is not
// signed in. The palette answers 401 JSON instead, so the redirect is dropped.
type discard struct{ h http.Header }

func (d *discard) Header() http.Header         { return d.h }
func (d *discard) Write(p []byte) (int, error) { return len(p), nil }
func (d *discard) WriteHeader(int)             {}

// Handler serves GET /api/command-palette.
func Handler(pool pgxPool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		at := now()
		// require_login's side effects (expired impersonation, acceptance) still
		// happen; only its response is replaced by the palette's 401.
		h, err := hostweb.Login(&discard{h: http.Header{}}, r, pool, getenv, at)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if h == nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(unauthorized))
			return
		}
		items, err := Items(r.Context(), pool, h, hostweb.Lang(r), getenv)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		body, err := marshalNoHTML(struct {
			Items []object `json:"items"`
		}{Items: items})
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(body)
	}
}

// Items builds the palette list for a signed-in host, in Python's order.
func Items(ctx context.Context, pool pgxPool, h *session.Host, lang string, getenv func(string) string) ([]object, error) {
	t := func(key string, params ...any) string {
		var p map[string]any
		if len(params) > 0 {
			p = map[string]any{}
			for i := 0; i+1 < len(params); i += 2 {
				p[params[i].(string)] = params[i+1]
			}
		}
		return catalog.T(lang, key, p)
	}
	pages := "command.group.pages"
	actions := "command.group.actions"
	items := []object{
		{{"label", t("nav.overview")}, {"group", t(pages)}, {"url", "/"}, {"keywords", "dashboard"}},
		{{"label", t("nav.stays")}, {"group", t(pages)}, {"url", "/reservations"}, {"keywords", "bookings calendar"}},
		{{"label", t("nav.reports")}, {"group", t(pages)}, {"url", "/submissions"}, {"keywords", "ubyport dorucenka"}},
		{{"label", t("nav.housebook")}, {"group", t(pages)}, {"url", "/housebook"}, {"keywords", "export csv"}},
		{{"label", t("nav.invoices")}, {"group", t(pages)}, {"url", "/invoices"}, {"keywords", "faktura invoice doklad"}},
		{{"label", t("nav.stay_fees")}, {"group", t(pages)}, {"url", "/stay-fees"}, {"keywords", "poplatek z pobytu hlaseni city tax"}},
		{{"label", t("nav.settings")}, {"group", t(pages)}, {"url", "/settings"}, {"keywords", "environment account"}},
		{{"label", t("dashboard.sync_calendars")}, {"group", t(actions)}, {"url", "/sync"}, {"method", "post"}, {"keywords", "ical refresh"}},
		{{"label", t("stays.add_stay")}, {"group", t(actions)}, {"url", "/reservations?new=1"}, {"keywords", "booking reservation"}},
	}

	owner := ownerID(h)
	apartments, err := apartmentRows(ctx, pool, owner)
	if err != nil {
		return nil, err
	}
	hubURL := func(section, anchor string) string {
		// 0078: one property opens its Settings group; several, the Properties summary.
		if len(apartments) == 1 {
			return fmt.Sprintf("/apartments/%d?view=settings&section=%s#%s", apartments[0].id, section, anchor)
		}
		return "/apartments#property-summaries"
	}
	invoiceURL, err := invoiceDetailsURL(ctx, pool, owner)
	if err != nil {
		return nil, err
	}
	type destination struct{ key, url, keywords string }
	destinations := []destination{
		{"nav.properties", "/apartments", "property apartment ubytovani"},
		{"host.business", "/entities", "business operator company billing firma"},
		{"nav.guest_links", hubURL("guests", "communication"), "invitation guest link pin"},
		{"nav.automation", hubURL("automation", "automation"), "automatic reporting timing police"},
		{"host.invoice_settings", invoiceURL, "invoice settings faktura"},
		{"settings.group.security", "/settings#settings-group-security", "passkey 2fa authenticator login password"},
		{"settings.group.data", "/settings#settings-group-data", "retention backup delete expired export"},
		{"settings.nav.archive", "/settings/archived", "restore archived records"},
		{"nav.privacy_requests", "/privacy-requests", "privacy gdpr"},
		{"nav.guide", "/guide", "help guide support"},
	}
	if ttlockEnabled(getenv) {
		has, err := lockAccountExists(ctx, pool, owner)
		if err != nil {
			return nil, err
		}
		if has {
			destinations = append(destinations, destination{"properties.shared.lock", "/smart-locks", "ttlock door lock code"})
		}
	}
	if h.Account.Role == "admin" {
		destinations = append(destinations,
			destination{"nav.users", "/admin/customers", "team accounts roles"},
			destination{"users.incidents_link", "/admin/incidents", "incidents"},
		)
	}
	for _, d := range destinations {
		items = append(items, object{{"label", t(d.key)}, {"group", t(pages)}, {"url", d.url}, {"keywords", d.keywords}})
	}

	for _, a := range apartments {
		items = append(items, object{
			{"label", a.internalName},
			{"meta", t("command.property")},
			{"group", t("nav.properties")},
			{"url", fmt.Sprintf("/apartments/%d", a.id)},
			{"tone", a.id % 10},
			{"keywords", a.ubyName + " " + a.cityEn},
		})
		if a.permalinkToken != "" {
			key, err := linkKey(ctx, pool, a)
			if err != nil {
				return nil, err
			}
			items = append(items, object{
				{"label", t("command.copy_property_link", "property", a.internalName)},
				{"group", t(actions)},
				{"copy", hostweb.PublicBase(getenv) + "/l/" + key},
				{"tone", a.id % 10},
				{"keywords", "guest permalink pin"},
			})
		}
	}

	stays, err := stayRows(ctx, pool, owner)
	if err != nil {
		return nil, err
	}
	for _, s := range stays {
		meta := t("command.stay")
		if s.summary != "" {
			meta = s.summary
		}
		items = append(items, object{
			{"label", s.internalName + " · " + s.dateFrom + " – " + s.dateTo},
			{"meta", meta},
			{"group", t("nav.stays")},
			{"url", fmt.Sprintf("/reservations/%d", s.id)},
			{"tone", s.apartmentID % 10},
			{"keywords", s.summary},
		})
	}

	subs, err := submissionRows(ctx, pool, owner)
	if err != nil {
		return nil, err
	}
	for _, s := range subs {
		items = append(items, object{
			{"label", t("reports.detail.title", "id", s.id)},
			{"meta", s.internalName + " · " + s.state},
			{"group", t("nav.reports")},
			{"url", fmt.Sprintf("/submissions/%d", s.id)},
			{"tone", s.apartmentID % 10},
			{"keywords", s.createdAt},
		})
	}

	// 0322: app.js shows this row only when nothing else matches.
	accountEmail, err := accountEmailOf(ctx, pool, h.Account.ID)
	if err != nil {
		return nil, err
	}
	if aiEnabledFor(getenv, "havel", accountEmail) {
		items = append(items, object{{"label", t("havel.launcher")}, {"group", t("havel.name")}, {"url", "/havel"}, {"havel", true}})
	}
	return items, nil
}

// pgxPool is the pool methods the palette uses, so tests can pass the real pool.
type pgxPool = *pgxpool.Pool

// ownerID is access.owner_id: the workspace account, nil when there is none.
func ownerID(h *session.Host) *int64 {
	if h == nil || h.Workspace.ID == 0 {
		return nil
	}
	id := h.Workspace.ID
	return &id
}

// ttlockEnabled is ttlock.enabled (config DOOR_CODES_ENABLED and the app's credentials).
func ttlockEnabled(getenv func(string) string) bool {
	switch getenv("UBYHOST_DOOR_CODES") {
	case "1", "true", "yes":
	default:
		return false
	}
	return strings.TrimSpace(getenv("UBYHOST_TTLOCK_CLIENT_ID")) != "" &&
		strings.TrimSpace(getenv("UBYHOST_TTLOCK_CLIENT_SECRET")) != ""
}

// aiEnabledFor is ai.enabled_for: the feature is in UBYHOST_AI_FEATURES, the
// provider's key is set, and the account is on UBYHOST_AI_TEST_EMAILS (or the list is empty).
func aiEnabledFor(getenv func(string) string, feature, email string) bool {
	if !listHas(getenv("UBYHOST_AI_FEATURES"), feature) {
		return false
	}
	key := getenv("UBYHOST_ANTHROPIC_API_KEY")
	if strings.ToLower(strings.TrimSpace(getenv("UBYHOST_AI_PROVIDER"))) == "mistral" {
		key = getenv("UBYHOST_MISTRAL_API_KEY")
	}
	if strings.TrimSpace(key) == "" {
		return false
	}
	// on_test_list: an empty UBYHOST_AI_TEST_EMAILS lets everyone use AI.
	testEmails := getenv("UBYHOST_AI_TEST_EMAILS")
	if strings.TrimSpace(testEmails) == "" {
		return true
	}
	return listHas(testEmails, email)
}

// listHas reports whether a comma-separated list holds value, case-insensitively.
func listHas(list, value string) bool {
	value = strings.ToLower(strings.TrimSpace(value))
	if value == "" {
		return false
	}
	for _, part := range strings.Split(list, ",") {
		if strings.ToLower(strings.TrimSpace(part)) == value {
			return true
		}
	}
	return false
}
