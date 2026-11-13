package ai

// The QR routes of App/app/routes/guest_guide.py (brief 1443): the page, the
// print-size PNG and "make a new link". The token rules are in guide_data.go
// (App/app/guide_token.py). The PNG comes from github.com/skip2/go-qrcode,
// already a dependency (go/internal/payments uses it).

import (
	"encoding/base64"
	"html/template"
	"net/http"

	"github.com/skip2/go-qrcode"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func init() {
	guideAdd("GET", "/apartments/{id}/guide/qr", (*guideServer).qrPage)
	guideAdd("GET", "/apartments/{id}/guide/qr.png", (*guideServer).qrPNG)
	guideAdd("POST", "/apartments/{id}/guide/qr/rotate", (*guideServer).qrRotate)
}

// guideQRPNG is a Medium-correction QR code with a four-module border and
// pixels pixels per module (qrcode box_size, border=4, ERROR_CORRECT_M).
func guideQRPNG(payload string, pixels int) ([]byte, error) {
	code, err := qrcode.New(payload, qrcode.Medium)
	if err != nil {
		return nil, err
	}
	return code.PNG(-pixels)
}

// guestURL is _guest_url: PUBLIC_BASE_URL/g/<token>, the token created on first use.
func (s *guideServer) guestURL(q *guideReq) (string, error) {
	token, err := s.ensureToken(q.r.Context(), q.apt)
	if err != nil {
		return "", err
	}
	return hostweb.PublicBase(s.getenv) + "/g/" + token, nil
}

// guideQRData is the context of guide_qr.tmpl.
type guideQRData struct {
	Apartment *guideApartment
	Base      string
	GuestURL  string
	QR        template.URL
	Progress  guideProgress
}

// qrPage is GET /apartments/{id}/guide/qr (guide_qr, 202-212).
func (s *guideServer) qrPage(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	url, err := s.guestURL(q)
	if err != nil {
		guideFail(w, err)
		return
	}
	png, err := guideQRPNG(url, 6) // payments.qr_data_uri: box_size=6
	if err != nil {
		guideFail(w, err)
		return
	}
	progress, err := s.progress(r.Context(), a.ID)
	if err != nil {
		guideFail(w, err)
		return
	}
	data := guideQRData{Apartment: a, Base: q.base(), GuestURL: url, Progress: progress,
		QR: template.URL("data:image/png;base64," + base64.StdEncoding.EncodeToString(png))}
	page := layout.Page{
		Title:    guideCatalog.T(q.lang, "guest_guide.qr.title", nil) + " · " + a.InternalName + " · UbyHost",
		BodyKind: "form", V2: true, BackURL: q.base(),
	}
	s.render(w, q, "guide_qr", page, http.StatusOK, data)
}

// qrPNG is GET /apartments/{id}/guide/qr.png (guide_qr_png, 215-225): about 6 cm at 300 dpi.
func (s *guideServer) qrPNG(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	if _, ok := s.home(w, q); !ok {
		return
	}
	url, err := s.guestURL(q)
	if err != nil {
		guideFail(w, err)
		return
	}
	png, err := guideQRPNG(url, 20) // guide_token.qr_png: box_size=20
	if err != nil {
		guideFail(w, err)
		return
	}
	w.Header().Set("Content-Type", "image/png")
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Disposition", `attachment; filename="guest-guide-qr.png"`)
	_, _ = w.Write(png)
}

// qrRotate is POST /apartments/{id}/guide/qr/rotate (guide_qr_rotate, 228-235).
func (s *guideServer) qrRotate(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	if _, ok := s.home(w, q); !ok {
		return
	}
	if err := s.rotateToken(r.Context(), q.apt); err != nil {
		guideFail(w, err)
		return
	}
	q.back(w, q.base()+"/qr", q.flash("flash.guest_guide.qr_rotated", nil), hostweb.Flash{})
}
