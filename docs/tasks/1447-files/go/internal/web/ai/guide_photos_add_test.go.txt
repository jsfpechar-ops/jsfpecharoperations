package ai

import (
	"bytes"
	"image"
	"image/color"
	"image/jpeg"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// guidePhotoUpload posts a multipart form: the CSRF field, and the file field
// "photo" unless file is nil.
func guidePhotoUpload(t *testing.T, w *guideCardWorld, uid int64, target, ctype string, file []byte) *httptest.ResponseRecorder {
	t.Helper()
	var body bytes.Buffer
	mw := multipart.NewWriter(&body)
	_ = mw.WriteField("_csrf", guideTestCSRF(t))
	if file != nil {
		h := make(map[string][]string)
		h["Content-Disposition"] = []string{`form-data; name="photo"; filename="p.jpg"`}
		h["Content-Type"] = []string{ctype}
		part, err := mw.CreatePart(h)
		if err != nil {
			t.Fatal(err)
		}
		_, _ = part.Write(file)
	}
	_ = mw.Close()
	req := httptest.NewRequest(http.MethodPost, target, &body)
	req.Header.Set("Content-Type", mw.FormDataContentType())
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: guideTestCSRFCookie})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	if uid != 0 {
		token := session.Sign(guideTestSecret, map[string]any{"uid": uid, "sv": int64(1), "iat": guideTestNow.Unix()}, guideTestNow)
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: token})
	}
	rec := httptest.NewRecorder()
	w.mux.ServeHTTP(rec, req)
	return rec
}

func guideTestJPEG(t *testing.T, w, h int) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			img.SetRGBA(x, y, color.RGBA{uint8(x), uint8(y), 90, 255})
		}
	}
	var b bytes.Buffer
	if err := jpeg.Encode(&b, img, nil); err != nil {
		t.Fatal(err)
	}
	return b.Bytes()
}

func TestGuidePhotoAdd(t *testing.T) {
	w := newGuideCardWorld(t)
	dir := filepath.Join(w.dataDir, "guide_photos")
	target := w.path("/", intString(w.checkin), "/photos")
	card := w.path("/", intString(w.checkin))
	pic := guideTestJPEG(t, 2000, 1000)

	// a good photo: row, file, redirect with the message, size 1600 x 800
	rec := guidePhotoUpload(t, w, w.host, target, "image/jpeg", pic)
	if rec.Code != 303 || !strings.HasPrefix(location(rec), card+"?msg=") {
		t.Fatalf("add: %d %q", rec.Code, location(rec))
	}
	photos, _ := w.s.photos(t.Context(), w.apt, w.checkin)
	if len(photos) != 1 || photos[0].SortOrder != 1 || !strings.HasSuffix(photos[0].FileName, ".jpg") || len(photos[0].FileName) != 36 {
		t.Fatalf("rows: %+v", photos)
	}
	raw, err := os.ReadFile(filepath.Join(dir, photos[0].FileName))
	if err != nil {
		t.Fatal(err)
	}
	img, err := jpeg.Decode(bytes.NewReader(raw))
	if err != nil || img.Bounds().Dx() != 1600 || img.Bounds().Dy() != 800 {
		t.Fatalf("stored file: %v %v", err, img)
	}
	if entries, _ := os.ReadDir(dir); len(entries) != 1 {
		t.Errorf("a temporary file is left: %v", entries)
	}

	// the type comes from the upload header; parameters and case are ignored
	if rec := guidePhotoUpload(t, w, w.host, target, "IMAGE/JPEG; charset=x", pic); rec.Code != 303 || !strings.Contains(location(rec), "msg=") {
		t.Errorf("type with parameters: %d %q", rec.Code, location(rec))
	}
	photos, _ = w.s.photos(t.Context(), w.apt, w.checkin)
	if len(photos) != 2 || photos[1].SortOrder != 2 {
		t.Errorf("second photo: %+v", photos)
	}

	refused := func(name, ctype string, file []byte) {
		t.Helper()
		before := guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_photo`)
		rec := guidePhotoUpload(t, w, w.host, target, ctype, file)
		if rec.Code != 303 || !strings.HasPrefix(location(rec), card+"?err=") {
			t.Errorf("%s: %d %q", name, rec.Code, location(rec))
		}
		if guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_photo`) != before {
			t.Errorf("%s: a row was added", name)
		}
	}
	refused("no file field", "", nil)
	refused("a gif type", "image/gif", pic)
	refused("under 64 bytes", "image/jpeg", pic[:63])
	refused("not a picture", "image/png", bytes.Repeat([]byte("not a picture "), 20))
	refused("over 10 MiB", "image/jpeg", append(append([]byte{}, pic...), make([]byte, 10*1024*1024)...))

	// at most six photos on a card
	for i := 0; i < 4; i++ {
		if rec := guidePhotoUpload(t, w, w.host, target, "image/jpeg", pic); !strings.Contains(location(rec), "msg=") {
			t.Fatalf("photo %d: %q", i+3, location(rec))
		}
	}
	refused("seventh photo", "image/jpeg", pic)

	// another account and a missing card are 404, a signed-out visitor is sent to log in
	if rec := guidePhotoUpload(t, w, w.stranger, target, "image/jpeg", pic); rec.Code != 404 {
		t.Errorf("another account: %d", rec.Code)
	}
	if rec := guidePhotoUpload(t, w, w.host, w.path("/99999/photos"), "image/jpeg", pic); rec.Code != 404 {
		t.Errorf("no such card: %d", rec.Code)
	}
	if rec := guidePhotoUpload(t, w, 0, target, "image/jpeg", pic); rec.Code != 303 || !strings.HasPrefix(location(rec), "/login") {
		t.Errorf("signed out: %d %q", rec.Code, location(rec))
	}
	if n := guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_photo`); n != 6 {
		t.Errorf("rows after the refusals: %d", n)
	}
}
