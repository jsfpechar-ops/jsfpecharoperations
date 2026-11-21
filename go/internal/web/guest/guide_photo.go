package guest

import (
	"net/http"
	"os"
	"path/filepath"
	"strconv"
)

// serveGuidePhoto returns true when a JPEG was written.
func (h *GuideHandlers) serveGuidePhoto(w http.ResponseWriter, r *http.Request, aptID int64, level string, itemID, photoID int64) bool {
	items, err := h.store.GuestCards(r.Context(), aptID)
	if err != nil {
		return false
	}
	allowed := false
	for _, c := range items {
		if c.ID == itemID {
			allowed = true
			break
		}
	}
	if !allowed {
		return false
	}
	photo, err := h.lookupPhoto(r, aptID, itemID, photoID)
	if err != nil || photo == "" {
		return false
	}
	if st, err := os.Stat(photo); err != nil || st.IsDir() {
		return false
	}
	hdr := w.Header()
	hdr.Set("Content-Type", "image/jpeg")
	for k, v := range photoHeaders {
		hdr.Set(k, v)
	}
	http.ServeFile(w, r, photo)
	return true
}

func (h *GuideHandlers) lookupPhoto(r *http.Request, aptID, itemID, photoID int64) (string, error) {
	dir := h.getenv("UBYHOST_GUIDE_PHOTOS_DIR")
	if dir == "" {
		dir = "guide_photos"
	}
	base := filepath.Join(dir, strconv.FormatInt(aptID, 10), strconv.FormatInt(itemID, 10))
	return filepath.Join(base, strconv.FormatInt(photoID, 10)+".jpg"), nil
}
