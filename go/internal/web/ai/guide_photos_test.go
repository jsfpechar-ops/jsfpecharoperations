package ai

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestGuidePhotoFileAndDelete(t *testing.T) {
	w := newGuideCardWorld(t)
	dir := filepath.Join(w.dataDir, "guide_photos")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	body := "\xff\xd8\xff\xe0fake-jpeg-bytes"
	if err := os.WriteFile(filepath.Join(dir, "aa.jpg"), []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "bb.jpg"), []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	guideTestExec(t, w.s.pool, `INSERT INTO guide_photo (item_id, file_name, sort_order, created_at) VALUES ($1, 'aa.jpg', 1, 'x'), ($1, 'gone.jpg', 2, 'x')`, w.checkin)
	photos, _ := w.s.photos(t.Context(), w.apt, w.checkin)
	a, gone := photos[0].ID, photos[1].ID
	file := func(id int64) string {
		return w.path("/", intString(w.checkin), "/photos/", intString(id))
	}

	rec := guideTestDo(t, w.mux, "GET", file(a), w.host, nil)
	if rec.Code != 200 || rec.Body.String() != body {
		t.Fatalf("photo: %d %q", rec.Code, rec.Body.String())
	}
	if rec.Header().Get("Content-Type") != "image/jpeg" || rec.Header().Get("Cache-Control") != "private, max-age=3600" {
		t.Errorf("headers: %v", rec.Header())
	}
	if rec := guideTestDo(t, w.mux, "GET", file(gone), w.host, nil); rec.Code != 404 {
		t.Errorf("a row without a file: %d", rec.Code)
	}
	if rec := guideTestDo(t, w.mux, "GET", file(999), w.host, nil); rec.Code != 404 {
		t.Errorf("no such photo: %d", rec.Code)
	}
	if rec := guideTestDo(t, w.mux, "GET", file(a), 0, nil); rec.Code != 303 {
		t.Errorf("signed out: %d", rec.Code)
	}
	if rec := guideTestDo(t, w.mux, "GET", file(a), w.stranger, nil); rec.Code != 404 {
		t.Errorf("another account: %d", rec.Code)
	}
	// the photo is on the card named in the URL only
	if rec := guideTestDo(t, w.mux, "GET", w.path("/", intString(w.wifi), "/photos/", intString(a)), w.host, nil); rec.Code != 404 {
		t.Errorf("photo on another card: %d", rec.Code)
	}
	// a file name from the database never leaves the photo folder
	guideTestExec(t, w.s.pool, `UPDATE guide_photo SET file_name = '../../etc/passwd' WHERE id = $1`, gone)
	if rec := guideTestDo(t, w.mux, "GET", file(gone), w.host, nil); rec.Code != 404 {
		t.Errorf("path escape: %d", rec.Code)
	}

	// delete: another property cannot, the owner can; the row and the file go
	if rec := guideTestDo(t, w.mux, "POST", file(a)+"/delete", w.stranger, nil); rec.Code != 404 {
		t.Errorf("delete by another account: %d", rec.Code)
	}
	if n := guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_photo WHERE id = $1`, a); n != 1 {
		t.Fatal("a stranger deleted a photo")
	}
	rec = guideTestDo(t, w.mux, "POST", file(a)+"/delete", w.host, nil)
	if rec.Code != 303 || !strings.HasPrefix(location(rec), w.path("/", intString(w.checkin))+"?msg=") {
		t.Errorf("delete: %d %q", rec.Code, location(rec))
	}
	if n := guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_photo WHERE id = $1`, a); n != 0 {
		t.Error("the photo row is still there")
	}
	if _, err := os.Stat(filepath.Join(dir, "aa.jpg")); !os.IsNotExist(err) {
		t.Errorf("the file is still there: %v", err)
	}
	if _, err := os.Stat(filepath.Join(dir, "bb.jpg")); err != nil {
		t.Errorf("another file went too: %v", err)
	}
	if rec := guideTestDo(t, w.mux, "POST", file(a)+"/delete", w.host, nil); rec.Code != 404 {
		t.Errorf("second delete: %d", rec.Code)
	}
}
