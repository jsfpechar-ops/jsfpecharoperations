package ai

import (
	"context"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

func init() {
	guideAdd("POST", "/apartments/{id}/guide/external", (*guideServer).externalSave)
}

const guideExternalURLErr = "flash.error.guide_external_url"

// guideExternalURL validates an optional https URL with a domain host (no port, no userinfo).
func guideExternalURL(raw string) (clean, host string, ok bool) {
	text := guidePyStrip(raw)
	if text == "" {
		return "", "", true
	}
	if !guideASCII(text) || utf8Len(text) > guideMaxURLLength {
		return "", "", false
	}
	if strings.IndexFunc(text, func(r rune) bool {
		return guideIsPySpace(r) || r < 0x20 || r == 0x7f
	}) >= 0 {
		return "", "", false
	}
	u, err := url.Parse(text)
	if err != nil {
		return "", "", false
	}
	if strings.ToLower(u.Scheme) != "https" || u.User != nil || u.Port() != "" {
		return "", "", false
	}
	hostname := u.Hostname()
	if hostname == "" {
		return "", "", false
	}
	if net.ParseIP(hostname) != nil {
		return "", "", false
	}
	if !strings.Contains(hostname, ".") {
		return "", "", false
	}
	return u.String(), strings.ToLower(hostname), true
}

// externalSave is POST /apartments/{id}/guide/external.
func (s *guideServer) externalSave(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	if _, ok := s.home(w, q); !ok {
		return
	}
	ctx := r.Context()
	idText := strconv.FormatInt(q.apt, 10)
	page := q.base() + "#external"
	action, _ := guideFormValue(r, "action")
	raw, _ := guideFormValue(r, "guide_external_url")
	if action == "clear" || guidePyStrip(raw) == "" {
		if _, err := s.pool.Exec(ctx, `UPDATE apartment SET guide_external_url = NULL WHERE id = $1`, q.apt); err != nil {
			guideFail(w, err)
			return
		}
		if err := s.audit(ctx, q, "guide_external_url_cleared", "apartment="+idText); err != nil {
			guideFail(w, err)
			return
		}
		q.back(w, page, q.flash("flash.guest_guide.external_cleared", nil), hostweb.Flash{})
		return
	}
	clean, host, good := guideExternalURL(raw)
	if !good {
		q.back(w, page, hostweb.Flash{}, q.flash(guideExternalURLErr, nil))
		return
	}
	if _, err := s.pool.Exec(ctx, `UPDATE apartment SET guide_external_url = $1 WHERE id = $2`, clean, q.apt); err != nil {
		guideFail(w, err)
		return
	}
	if err := s.audit(ctx, q, "guide_external_url_set", "apartment="+idText+" host="+host); err != nil {
		guideFail(w, err)
		return
	}
	q.back(w, page, q.flash("flash.guest_guide.external_saved", nil), hostweb.Flash{})
}