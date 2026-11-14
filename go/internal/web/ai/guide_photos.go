package ai

// The photo routes of App/app/routes/guest_guide.py that Go serves (brief
// 1442): show one stored photo and delete one. Adding a photo
// (POST .../photos) stays on Python; see brief 1447.

import (
	"net/http"
	"os"
	"path/filepath"
	"strconv"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

func init() {
	guideAdd("GET", "/apartments/{id}/guide/{item}/photos/{photo}", (*guideServer).photoFile)
	guideAdd("POST", "/apartments/{id}/guide/{item}/photos/{photo}/delete", (*guideServer).photoDelete)
}

// photoFile is GET /apartments/{id}/guide/{item}/photos/{photo} (guide_photo_file, 424-434).
func (s *guideServer) photoFile(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	photo, err := s.photo(r.Context(), a.ID, q.item, q.arg)
	if err != nil {
		guideFail(w, err)
		return
	}
	if photo == nil {
		guideNotFound(w)
		return
	}
	f, err := os.Open(filepath.Join(s.photosDir(), filepath.Base(photo.FileName)))
	if err != nil {
		guideNotFound(w)
		return
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil || !info.Mode().IsRegular() {
		guideNotFound(w)
		return
	}
	w.Header().Set("Content-Type", "image/jpeg")
	w.Header().Set("Cache-Control", "private, max-age=3600")
	http.ServeContent(w, r, photo.FileName, info.ModTime(), f)
}

// photoDelete is POST /apartments/{id}/guide/{item}/photos/{photo}/delete
// (guide_photo_delete, 437-445).
func (s *guideServer) photoDelete(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enter(w, r)
	if !ok {
		return
	}
	a, ok := s.home(w, q)
	if !ok {
		return
	}
	done, err := s.deletePhoto(r.Context(), a.ID, q.item, q.arg)
	if err != nil {
		guideFail(w, err)
		return
	}
	if !done {
		guideNotFound(w)
		return
	}
	q.back(w, q.base()+"/"+strconv.FormatInt(q.item, 10), q.flash("flash.guest_guide.photo_deleted", nil), hostweb.Flash{})
}
