package booking

// Host property page review (brief 1710a): payments.property_page_review,
// property_page_save, property_page_photo_move, property_page_photo_delete.
// Python: App/app/routes/payments.py 412-518 and property_page.py helpers.

import (
	"context"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed property_page_host_i18n.json
var propertyPageHostI18nJSON []byte

//go:embed templates/property_page_review.tmpl
var propertyPageReviewFS embed.FS

var (
	propertyPageCatalog = hostweb.Load(propertyPageHostI18nJSON)
	propertyPageReview  = layout.MustParseFuncs(propertyPageCatalog, nil, propertyPageReviewFS, "templates/property_page_review.tmpl")
)

type pageHostServer struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

type reviewPageRow struct {
	Description    *string
	AmenitiesJSON  *string
	HouseRules     *string
	PhotosJSON     *string
	Published      int
	HideFromSearch int
}

type reviewPageData struct {
	ApartmentID    int64
	ApartmentName  string
	Description    string
	AmenitiesText  string
	HouseRules     string
	Photos         []string
	Slug           string
	Published      bool
	HideFromSearch bool
}

// RegisterPropertyPageHost registers the four host routes (dormant until UBYHOST_GO_PATHS).
func RegisterPropertyPageHost(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	s := &pageHostServer{pool: pool, getenv: getenv, now: now}
	mux.Handle("GET /apartments/{apartment_id}/page", wrap("/apartments/{apartment_id}/page", s.review()))
	mux.Handle("POST /apartments/{apartment_id}/page", wrap("/apartments/{apartment_id}/page", s.save()))
	mux.Handle("POST /apartments/{apartment_id}/page/photo-move", wrap("/apartments/{apartment_id}/page/photo-move", s.photoMove()))
	mux.Handle("POST /apartments/{apartment_id}/page/photo-delete", wrap("/apartments/{apartment_id}/page/photo-delete", s.photoDelete()))
}

func (s *pageHostServer) flash(lang, key string) hostweb.Flash {
	text := propertyPageCatalog.T(lang, key, nil)
	if text == key {
		text = hostweb.HostStrings.T(lang, key, nil)
	}
	return hostweb.Flash{Text: text, Key: key}
}

func parseApartmentID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("apartment_id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return 0, false
	}
	return id, true
}

func (s *pageHostServer) login(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, bool) {
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		hostPageError(w, err)
		return nil, false
	}
	return h, h != nil
}

func hostPageError(w http.ResponseWriter, err error) {
	log.Printf("booking property_page_host: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

func (s *pageHostServer) ownApartment(ctx context.Context, ownerID, apartmentID int64) (string, bool, error) {
	var name string
	err := s.pool.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1 AND owner_user_id = $2`,
		apartmentID, ownerID).Scan(&name)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	return name, err == nil, err
}

func ensurePageRow(ctx context.Context, db DB, apartmentID int64, now time.Time) error {
	stamp := StampAt(now)
	_, err := db.Exec(ctx, `INSERT INTO property_page (apartment_id, created_at, updated_at) VALUES ($1, $2, $2)
		ON CONFLICT (apartment_id) DO NOTHING`, apartmentID, stamp)
	return err
}

func loadReviewPage(ctx context.Context, db DB, apartmentID int64, now time.Time) (*reviewPageRow, error) {
	if err := ensurePageRow(ctx, db, apartmentID, now); err != nil {
		return nil, err
	}
	var row reviewPageRow
	err := db.QueryRow(ctx, `SELECT description, amenities_json, house_rules, photos_json, published, hide_from_search
		FROM property_page WHERE apartment_id = $1`, apartmentID).
		Scan(&row.Description, &row.AmenitiesJSON, &row.HouseRules, &row.PhotosJSON, &row.Published, &row.HideFromSearch)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return &row, err
}

func strOrEmpty(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func amenitiesText(raw *string) string {
	if raw == nil || strings.TrimSpace(*raw) == "" {
		return ""
	}
	var items []string
	if err := json.Unmarshal([]byte(*raw), &items); err != nil {
		return ""
	}
	return strings.Join(items, "\n")
}

func parseAmenities(text string) []string {
	var out []string
	for _, ln := range strings.Split(text, "\n") {
		if s := strings.TrimSpace(ln); s != "" {
			out = append(out, s)
		}
	}
	return out
}

func photosFromJSON(raw *string) []string {
	if raw == nil || strings.TrimSpace(*raw) == "" {
		return nil
	}
	var photos []string
	if err := json.Unmarshal([]byte(*raw), &photos); err != nil {
		return nil
	}
	return photos
}

func (s *pageHostServer) buildReview(ctx context.Context, apartmentID int64, name string, at time.Time) (*reviewPageData, error) {
	row, err := loadReviewPage(ctx, s.pool, apartmentID, at)
	if err != nil || row == nil {
		return nil, err
	}
	slug, err := EnsureSlug(ctx, s.pool, apartmentID, at)
	if err != nil {
		return nil, err
	}
	return &reviewPageData{
		ApartmentID:    apartmentID,
		ApartmentName:  name,
		Description:    strOrEmpty(row.Description),
		AmenitiesText:  amenitiesText(row.AmenitiesJSON),
		HouseRules:     strOrEmpty(row.HouseRules),
		Photos:         photosFromJSON(row.PhotosJSON),
		Slug:           slug,
		Published:      row.Published != 0,
		HideFromSearch: row.HideFromSearch != 0,
	}, nil
}

func (s *pageHostServer) review() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		aptID, ok := parseApartmentID(w, r)
		if !ok {
			return
		}
		name, found, err := s.ownApartment(r.Context(), h.Workspace.ID, aptID)
		if err != nil {
			hostPageError(w, err)
			return
		}
		if !found {
			http.NotFound(w, r)
			return
		}
		data, err := s.buildReview(r.Context(), aptID, name, at)
		if err != nil {
			hostPageError(w, err)
			return
		}
		title := propertyPageCatalog.T(hostweb.Lang(r), "payments.page.title", nil) + " · " + name
		env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: at}
		p := layout.Page{Title: title, Nav: "properties", BodyKind: "form", V2: true}
		w.Header().Set("Cache-Control", "no-store, private")
		if err := layout.Render(w, r, env, h, p, propertyPageReview, "property_page_review", data); err != nil {
			hostPageError(w, err)
		}
	}
}

func (s *pageHostServer) enterPost(w http.ResponseWriter, r *http.Request) (*session.Host, int64, bool) {
	at := s.now()
	if !hostweb.CSRF(w, r, s.getenv, at) {
		return nil, 0, false
	}
	h, ok := s.login(w, r, at)
	if !ok {
		return nil, 0, false
	}
	aptID, ok := parseApartmentID(w, r)
	if !ok {
		return nil, 0, false
	}
	if err := r.ParseForm(); err != nil {
		hostPageError(w, err)
		return nil, 0, false
	}
	name, found, err := s.ownApartment(r.Context(), h.Workspace.ID, aptID)
	if err != nil {
		hostPageError(w, err)
		return nil, 0, false
	}
	if !found {
		http.NotFound(w, r)
		return nil, 0, false
	}
	_ = name
	return h, aptID, true
}

func pageBack(w http.ResponseWriter, r *http.Request, apartmentID int64, msg hostweb.Flash) {
	hostweb.Back(w, r, fmt.Sprintf("/apartments/%d/page", apartmentID), msg, hostweb.Flash{})
}

func (s *pageHostServer) save() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, aptID, ok := s.enterPost(w, r)
		if !ok {
			return
		}
		lang := hostweb.Lang(r)
		ctx := r.Context()
		at := s.now()
		form := r.PostForm
		path := fmt.Sprintf("/apartments/%d/page", aptID)
		switch {
		case form.Get("search_save") != "":
			hide := 0
			if len(form["hide_from_search"]) > 0 {
				hide = 1
			}
			_, err := s.pool.Exec(ctx, `UPDATE property_page SET hide_from_search = $1, updated_at = $2 WHERE apartment_id = $3`,
				hide, StampAt(at), aptID)
			if err != nil {
				hostPageError(w, err)
				return
			}
			pageBack(w, r, aptID, s.flash(lang, "payments.page.saved"))
			return
		case form.Get("publish") != "" || form.Get("unpublish") != "":
			pub := form.Get("publish") != ""
			if err := PublishPage(ctx, s.pool, aptID, pub, at); err != nil {
				hostPageError(w, err)
				return
			}
			key := "payments.page.unpublished"
			if pub {
				key = "payments.page.published"
			}
			pageBack(w, r, aptID, s.flash(lang, key))
			return
		}
		rules := strings.TrimSpace(form.Get("house_rules"))
		if utf8.RuneCountInString(rules) > 4000 {
			rules = string([]rune(rules)[:4000])
		}
		amen := parseAmenities(form.Get("amenities"))
		var amenJSON any
		if len(amen) > 0 {
			b, _ := json.Marshal(amen)
			amenJSON = string(b)
		}
		desc := strings.TrimSpace(form.Get("description"))
		if err := ensurePageRow(ctx, s.pool, aptID, at); err != nil {
			hostPageError(w, err)
			return
		}
		_, err := s.pool.Exec(ctx, `UPDATE property_page SET description = $1, amenities_json = $2, house_rules = $3, updated_at = $4 WHERE apartment_id = $5`,
			nullIfEmpty(desc), amenJSON, nullIfEmpty(rules), StampAt(at), aptID)
		if err != nil {
			hostPageError(w, err)
			return
		}
		_ = h
		_ = path
		pageBack(w, r, aptID, s.flash(lang, "payments.page.saved"))
	}
}

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func moveHostPhoto(ctx context.Context, db DB, apartmentID int64, path, direction string, now time.Time) error {
	row, err := loadReviewPage(ctx, db, apartmentID, now)
	if err != nil || row == nil || direction != "up" && direction != "down" {
		return err
	}
	photos := photosFromJSON(row.PhotosJSON)
	if path == "" || !photosContains(photos, path) {
		return nil
	}
	i := indexOf(photos, path)
	j := i - 1
	if direction == "down" {
		j = i + 1
	}
	if j < 0 || j >= len(photos) {
		return nil
	}
	photos[i], photos[j] = photos[j], photos[i]
	b, _ := json.Marshal(photos)
	_, err = db.Exec(ctx, `UPDATE property_page SET photos_json = $1, updated_at = $2 WHERE apartment_id = $3`,
		string(b), StampAt(now), apartmentID)
	return err
}

func deleteHostPhoto(ctx context.Context, db DB, getenv func(string) string, apartmentID int64, path string, now time.Time) error {
	row, err := loadReviewPage(ctx, db, apartmentID, now)
	if err != nil || row == nil {
		return err
	}
	photos := photosFromJSON(row.PhotosJSON)
	if path == "" || !photosContains(photos, path) {
		return nil
	}
	photos = remove(photos, path)
	var raw any
	if len(photos) > 0 {
		b, _ := json.Marshal(photos)
		raw = string(b)
	}
	_, err = db.Exec(ctx, `UPDATE property_page SET photos_json = $1, updated_at = $2 WHERE apartment_id = $3`,
		raw, StampAt(now), apartmentID)
	if err != nil {
		return err
	}
	name := path[strings.LastIndex(path, "/")+1:]
	target := filepath.Join(PhotosDir(getenv), name)
	_ = os.Remove(target)
	return nil
}

func photosContains(ss []string, want string) bool {
	for _, s := range ss {
		if s == want {
			return true
		}
	}
	return false
}

func indexOf(ss []string, want string) int {
	for i, s := range ss {
		if s == want {
			return i
		}
	}
	return -1
}

func remove(ss []string, drop string) []string {
	out := make([]string, 0, len(ss))
	for _, s := range ss {
		if s != drop {
			out = append(out, s)
		}
	}
	return out
}

func (s *pageHostServer) photoMove() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		_, aptID, ok := s.enterPost(w, r)
		if !ok {
			return
		}
		if err := moveHostPhoto(r.Context(), s.pool, aptID, r.PostForm.Get("path"), r.PostForm.Get("dir"), s.now()); err != nil {
			hostPageError(w, err)
			return
		}
		pageBack(w, r, aptID, hostweb.Flash{})
	}
}

func (s *pageHostServer) photoDelete() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		_, aptID, ok := s.enterPost(w, r)
		if !ok {
			return
		}
		lang := hostweb.Lang(r)
		if err := deleteHostPhoto(r.Context(), s.pool, s.getenv, aptID, r.PostForm.Get("path"), s.now()); err != nil {
			hostPageError(w, err)
			return
		}
		pageBack(w, r, aptID, s.flash(lang, "payments.page.saved"))
	}
}
