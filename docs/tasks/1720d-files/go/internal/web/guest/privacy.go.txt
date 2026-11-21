package guest

import (
	"encoding/json"
	"html/template"
	"io"
	"log"
	"net/http"
	"strings"
)

type cookieRow struct {
	Name     string            `json:"name"`
	Party    string            `json:"party"`
	Purpose  map[string]string `json:"purpose"`
	Lifetime map[string]string `json:"lifetime"`
}

var guestCookieInventory = loadGuestCookies()

func loadGuestCookies() []cookieRow {
	var rows []cookieRow
	if err := json.Unmarshal(guestCookieJSON, &rows); err != nil {
		panic("guest: bad guest_cookie_inventory.json: " + err.Error())
	}
	return rows
}

// PrivacyView is guest/privacy.html context.
type PrivacyView struct {
	Page
	Controller          EntityContact
	BackURL             string
	PassportPhotoPolicy string
	DoorCodes           bool
	MailEnabled         bool
	NoticeVersion       string
	CookieInventory     []cookieRow
	SoftwareOperator    SoftwareOperator
	HostMessageURL      string
	ShowPassportPhoto   bool
}

func (p PrivacyView) T(key string, kv ...any) string { return p.Page.T(key, kv...) }

func cookiePartyLabel(p PrivacyView, party string) string {
	if party == "first" {
		return p.T("cookies.party.first")
	}
	return party
}

func cookieText(lang string, m map[string]string) string {
	if v := strings.TrimSpace(m[lang]); v != "" {
		return v
	}
	return strings.TrimSpace(m["en"])
}

var privacySet = func() *template.Template {
	funcs := template.FuncMap{}
	for k, v := range tplFuncs {
		funcs[k] = v
	}
	funcs["cookiePartyLabel"] = cookiePartyLabel
	funcs["cookieText"] = cookieText
	t := template.Must(template.New("guest.base").Funcs(funcs).ParseFS(templateFS,
		"templates/base.tmpl", "templates/host_fragment.tmpl", "templates/privacy.tmpl", "templates/cookie_table.tmpl"))
	return t
}()

func (d shellDeps) privacyNotice(w http.ResponseWriter, r *http.Request) {
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
	back := safeReturnTo(r.URL.Query().Get("return_to"), link, lang)
	page := sharedPage(r, link, lang, apt, d.getenv, d.pool)
	csrf, err := mintGuestPageCSRF(w, r, d.getenv, now)
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	page.CSRFToken = csrf
	ctrl := controller(ctx, d.pool, apt)
	policy := "off"
	lock := ""
	if apt != nil {
		policy = strings.TrimSpace(apt.PassportPhotoPolicy)
		if policy == "" {
			policy = "off"
		}
		lock = apt.LockProvider
	}
	view := PrivacyView{
		Page:                page,
		Controller:          ctrl,
		BackURL:             back,
		PassportPhotoPolicy: policy,
		DoorCodes:           lock == "ttlock",
		MailEnabled:         mailEnabled(d.getenv),
		NoticeVersion:       noticeVersion(d.getenv),
		CookieInventory:     guestCookieInventory,
		SoftwareOperator:    softwareOperator(d.getenv),
		ShowPassportPhoto:   policy == "required_foreign",
	}
	if apt != nil {
		view.HostMessageURL = hostMessageURL(apt, hostContact(ctx, d.pool, apt))
	}
	var buf strings.Builder
	if err := privacySet.ExecuteTemplate(&buf, "guest.base", view); err != nil {
		log.Printf("guest privacy: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	WithLang(w, d.getenv, GuestLanguage(lang))
	h := w.Header()
	h.Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	if r.Method != http.MethodHead {
		_, _ = io.WriteString(w, buf.String())
	}
}
