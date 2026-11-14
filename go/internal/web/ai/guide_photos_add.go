package ai

// POST /apartments/{id}/guide/{item}/photos (brief 1447): add a photo to a
// guide card, routed from cardAction (guide_cards.go): net/http refuses a
// pattern ".../{item}/photos" next to ".../quick/{step}". Port of guide_photo_add (App/app/routes/guest_guide.py 402-421)
// and guide_photos.add (App/app/guide_photos.py 68-95). The picture goes
// through imgproc.Clean (brief 1641), the file is written under
// $UBYHOST_DATA_DIR/guide_photos, which needs the writable volume of brief 1640.

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/imgproc"
)

const (
	guidePhotoMaxUpload  = 10 * 1024 * 1024 // guide_photos.MAX_UPLOAD_BYTES
	guidePhotoMaxPerItem = 6                // guide_photos.MAX_PER_ITEM
	guidePhotoMinBytes   = 64
)

// guidePhotoTypes is guide_photos.ALLOWED_TYPES.
var guidePhotoTypes = []string{"image/jpeg", "image/jpg", "image/png", "image/webp"}

// photoAdd is guide_photo_add. The order is Python's: CSRF, login, the
// property, the card (404), then the upload.
func (s *guideServer) photoAdd(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	item, err := s.getItem(r.Context(), a.ID, q.item)
	if err != nil {
		guideFail(w, err)
		return
	}
	if item == nil {
		guideNotFound(w)
		return
	}
	card := q.base() + "/" + strconv.FormatInt(q.item, 10)
	content, ctype, found, err := guideUpload(r)
	if err != nil {
		guideFail(w, err)
		return
	}
	if !found {
		q.back(w, card, hostweb.Flash{}, q.flash("flash.error.guide_photo_type", nil))
		return
	}
	if err := s.addPhoto(r.Context(), a.ID, q.item, content, ctype, q.at); err != nil {
		if key := guideErrKey(err); key != "" {
			q.back(w, card, hostweb.Flash{}, q.flash(key, nil))
			return
		}
		guideFail(w, err)
		return
	}
	q.back(w, card, q.flash("flash.guest_guide.photo_added", nil), hostweb.Flash{})
}

// guideUpload is `upload = form.get("photo")` and `await upload.read(MAX + 1)`:
// the last field named photo, when it is a file, read up to one byte past the
// limit. found is false when there is no such file field.
func guideUpload(r *http.Request) (content []byte, contentType string, found bool, err error) {
	if r.MultipartForm == nil {
		return nil, "", false, nil
	}
	files := r.MultipartForm.File["photo"]
	if len(files) == 0 {
		return nil, "", false, nil
	}
	h := files[len(files)-1]
	f, err := h.Open()
	if err != nil {
		return nil, "", false, err
	}
	defer f.Close()
	content, err = io.ReadAll(io.LimitReader(f, guidePhotoMaxUpload+1))
	if err != nil {
		return nil, "", false, err
	}
	return content, h.Header.Get("Content-Type"), true, nil
}

// addPhoto is guide_photos.add after the card check: the checks in Python's
// order (type and size of the upload, six photos at most, then the picture
// itself), the clean JPEG written atomically under a random name, then the row.
func (s *guideServer) addPhoto(ctx context.Context, apt, item int64, content []byte, contentType string, at time.Time) error {
	ctype := strings.ToLower(strings.TrimSpace(strings.SplitN(contentType, ";", 2)[0]))
	if !guideIn(guidePhotoTypes, ctype) || len(content) < guidePhotoMinBytes {
		return guideErr("flash.error.guide_photo_type")
	}
	if len(content) > guidePhotoMaxUpload {
		return guideErr("flash.error.guide_photo_size")
	}
	existing, err := s.photos(ctx, apt, item)
	if err != nil {
		return err
	}
	if len(existing) >= guidePhotoMaxPerItem {
		return guideErr("flash.error.guide_photo_limit")
	}
	clean, err := imgproc.Clean(content)
	if err == imgproc.ErrNotImage || err == imgproc.ErrTooManyPixels {
		return guideErr("flash.error.guide_photo_type")
	}
	if err != nil {
		return err
	}
	var raw [16]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return err
	}
	name := hex.EncodeToString(raw[:]) + ".jpg"
	dir := s.photosDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	target := filepath.Join(dir, name)
	tmp := strings.TrimSuffix(target, ".jpg") + ".tmp"
	if err := os.WriteFile(tmp, clean, 0o644); err != nil {
		return err
	}
	if err := os.Rename(tmp, target); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	order := int64(0)
	for _, p := range existing {
		order = max(order, p.SortOrder)
	}
	if _, err := s.pool.Exec(ctx, `INSERT INTO guide_photo (item_id, file_name, sort_order, created_at) VALUES ($1, $2, $3, $4)`,
		item, name, order+1, guideStamp(at)); err != nil {
		_ = os.Remove(target)
		return err
	}
	return nil
}
