package guest

// Guest guide view (brief 1629). Port of App/app/routes/guest_guide_view.py.
// Depends on guest shell helpers in shell.go (brief 1720) and claim helpers in stay_claim.go (brief 1721).

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

const QRMaxViews = 120

var (
	hardenedHeaders = map[string]string{
		"Cache-Control":   "no-store",
		"X-Robots-Tag":    "noindex, nofollow",
		"Referrer-Policy": "no-referrer",
	}
	photoHeaders = map[string]string{
		"Cache-Control":   "private, max-age=3600",
		"X-Robots-Tag":    "noindex",
		"Referrer-Policy": "no-referrer",
	}
)

// RegisterGuideView adds the four public guide routes (dormant until wave G, brief 1728).
func RegisterGuideView(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	env := ai.HavelEnv(func(k string) (string, bool) { v := getenv(k); return v, v != "" })
	h := &GuideHandlers{pool: pool, getenv: getenv, now: now, store: ai.LeonStore{HavelStore: ai.HavelStore{Pool: pool, Env: env}}}
	mux.Handle("GET /g/{token}", wrap("/g/{token}", h.qrGuide))
	mux.Handle("GET /g/{token}/photos/{item_id}/{photo_id}", wrap("/g/{token}/photos/{item_id}/{photo_id}", h.qrGuidePhoto))
	mux.Handle("GET /l/{token}/{reservation_id}/guide", wrap("/l/{token}/{reservation_id}/guide", h.stayGuide))
	mux.Handle("GET /l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}", wrap("/l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}", h.stayGuidePhoto))
}

// GuideHandlers serves guest-facing guide pages.
type GuideHandlers struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
	store  ai.LeonStore
}

// BookedLevel is guest_guide_view.booked_level.
func BookedLevel(dateFrom, dateTo string, today time.Time) string {
	if dateFrom == "" || dateTo == "" {
		return "everyone"
	}
	from, err1 := time.Parse("2006-01-02", dateFrom)
	to, err2 := time.Parse("2006-01-02", dateTo)
	if err1 != nil || err2 != nil {
		return "everyone"
	}
	todayD := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC)
	fromD := time.Date(from.Year(), from.Month(), from.Day(), 0, 0, 0, 0, time.UTC)
	toD := time.Date(to.Year(), to.Month(), to.Day(), 0, 0, 0, 0, time.UTC)
	if fromD.Add(-24*time.Hour).Compare(todayD) <= 0 && todayD.Compare(toD) <= 0 {
		return "booked"
	}
	return "everyone"
}

func (h *GuideHandlers) qrGuide(w http.ResponseWriter, r *http.Request) {
	token := r.PathValue("token")
	lang := Language(r)
	key := RateClientKey(r, "guide_qr")
	if RateBlocked(r.Context(), h.pool, "guide_qr", key, QRMaxViews, h.now()) {
		WriteUnavailable(w, r, lang, "bad_link", http.StatusTooManyRequests, "", hardenedHeaders)
		return
	}
	apt, err := h.apartmentByGuideToken(r.Context(), token)
	if err != nil || apt == nil {
		WriteUnavailable(w, r, lang, "bad_link", http.StatusNotFound, "", hardenedHeaders)
		return
	}
	RateRecord(r.Context(), h.pool, "guide_qr", key, h.now())
	h.renderGuidePage(w, r, lang, apt, nil, "everyone", "qr", token, "", "")
}

func (h *GuideHandlers) qrGuidePhoto(w http.ResponseWriter, r *http.Request) {
	token := r.PathValue("token")
	itemID, ok1 := pathInt(r, "item_id")
	photoID, ok2 := pathInt(r, "photo_id")
	if !ok1 || !ok2 {
		WriteUnavailable(w, r, Language(r), "bad_link", http.StatusNotFound, "", hardenedHeaders)
		return
	}
	lang := Language(r)
	key := RateClientKey(r, "guide_qr")
	if RateBlocked(r.Context(), h.pool, "guide_qr", key, QRMaxViews, h.now()) {
		WriteUnavailable(w, r, lang, "bad_link", http.StatusTooManyRequests, "", hardenedHeaders)
		return
	}
	apt, err := h.apartmentByGuideToken(r.Context(), token)
	if err != nil || apt == nil {
		WriteUnavailable(w, r, lang, "bad_link", http.StatusNotFound, "", hardenedHeaders)
		return
	}
	if !h.serveGuidePhoto(w, r, apt.ID, "everyone", itemID, photoID) {
		WriteUnavailable(w, r, lang, "bad_link", http.StatusNotFound, "", hardenedHeaders)
	}
}

func (h *GuideHandlers) stayGuide(w http.ResponseWriter, r *http.Request) {
	token := r.PathValue("token")
	resID, ok := pathInt(r, "reservation_id")
	if !ok {
		WriteUnavailable(w, r, Language(r), "bad_link", http.StatusNotFound, token, hardenedHeaders)
		return
	}
	lang, apt, res, done := StayGate(r, w, h.pool, h.getenv, h.now, token, resID)
	if done {
		return
	}
	level := BookedLevel(res.DateFrom, res.DateTo, PragueToday(h.now))
	base := "/l/" + token + "/" + strconv.FormatInt(resID, 10)
	h.renderGuidePage(w, r, lang, apt, res, level, "stay", token, base+"?lang="+lang, base+"/guide/leon")
}

func (h *GuideHandlers) stayGuidePhoto(w http.ResponseWriter, r *http.Request) {
	token := r.PathValue("token")
	resID, ok := pathInt(r, "reservation_id")
	itemID, ok1 := pathInt(r, "item_id")
	photoID, ok2 := pathInt(r, "photo_id")
	if !ok || !ok1 || !ok2 {
		WriteUnavailable(w, r, Language(r), "bad_link", http.StatusNotFound, token, hardenedHeaders)
		return
	}
	lang, apt, res, done := StayGate(r, w, h.pool, h.getenv, h.now, token, resID)
	if done {
		return
	}
	level := BookedLevel(res.DateFrom, res.DateTo, PragueToday(h.now))
	if !h.serveGuidePhoto(w, r, apt.ID, level, itemID, photoID) {
		WriteUnavailable(w, r, lang, "bad_link", http.StatusNotFound, token, hardenedHeaders)
	}
}

func (h *GuideHandlers) apartmentByGuideToken(ctx context.Context, token string) (*GuideApartment, error) {
	if len(token) < 16 || len(token) > 64 {
		return nil, nil
	}
	var row GuideApartment
	err := h.pool.QueryRow(ctx, `SELECT id, owner_user_id, internal_name FROM apartment WHERE guide_token = $1 AND active = 1`, token).
		Scan(&row.ID, &row.OwnerUserID, &row.Name)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &row, nil
}

func pathInt(r *http.Request, name string) (int64, bool) {
	v := strings.TrimSpace(r.PathValue(name))
	n, err := strconv.ParseInt(v, 10, 64)
	return n, err == nil && n > 0
}
