package passportphotos

import (
	"bytes"
	"encoding/base64"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

func testKeys(t *testing.T) *secure.MultiFernet {
	t.Helper()
	key := base64.URLEncoding.EncodeToString(bytes.Repeat([]byte("p"), 32))
	m, err := secure.NewMultiFernet([]byte(key))
	if err != nil {
		t.Fatal(err)
	}
	return m
}

func TestSaveDemoPassportRoundTrip(t *testing.T) {
	dir := t.TempDir()
	keys := testKeys(t)
	png, err := DemoPassportPNG()
	if err != nil {
		t.Fatal(err)
	}
	const guestID = 20311
	if err := Save(dir, keys, guestID, png, "image/png"); err != nil {
		t.Fatal(err)
	}
	enc := filepath.Join(PhotosDir(dir), "20311.jpg.enc")
	if _, err := os.Stat(enc); err != nil {
		t.Fatalf("expected encrypted file: %v", err)
	}
	raw, _ := os.ReadFile(enc)
	if bytes.HasPrefix(raw, []byte{0xFF, 0xD8, 0xFF}) {
		t.Fatal("on-disk file must be Fernet, not plaintext JPEG")
	}
	plain, media, ok := Read(dir, keys, guestID)
	if !ok || media != "image/jpeg" {
		t.Fatalf("read back: ok=%v media=%q", ok, media)
	}
	if !bytes.HasPrefix(plain, []byte{0xFF, 0xD8, 0xFF}) {
		t.Fatal("decrypted content must be JPEG")
	}
	w, h, ok := JPEGConfig(plain)
	if !ok || w != 8 || h != 8 {
		t.Fatalf("JPEG size: %dx%d ok=%v", w, h, ok)
	}
	img, err := jpeg.Decode(bytes.NewReader(plain))
	if err != nil {
		t.Fatal(err)
	}
	r, g, b, _ := img.At(4, 4).RGBA()
	if r>>8 < 180 || g>>8 < 180 || b>>8 < 180 {
		t.Fatalf("grey pixel got (%d,%d,%d)", r>>8, g>>8, b>>8)
	}
}

func TestSaveReplacesPriorFile(t *testing.T) {
	dir := t.TempDir()
	keys := testKeys(t)
	id := int64(99)
	red := image.NewRGBA(image.Rect(0, 0, 4, 4))
	var buf bytes.Buffer
	if err := png.Encode(&buf, red); err != nil {
		t.Fatal(err)
	}
	if err := Save(dir, keys, id, buf.Bytes(), "image/png"); err != nil {
		t.Fatal(err)
	}
	green := image.NewRGBA(image.Rect(0, 0, 6, 6))
	for y := 0; y < 6; y++ {
		for x := 0; x < 6; x++ {
			green.SetRGBA(x, y, color.RGBA{R: 0, G: 255, B: 0, A: 255})
		}
	}
	buf.Reset()
	if err := png.Encode(&buf, green); err != nil {
		t.Fatal(err)
	}
	if err := Save(dir, keys, id, buf.Bytes(), "image/png"); err != nil {
		t.Fatal(err)
	}
	files, err := os.ReadDir(PhotosDir(dir))
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 1 || files[0].Name() != "99.jpg.enc" {
		t.Fatalf("want one .jpg.enc, got %v", files)
	}
	plain, _, ok := Read(dir, keys, id)
	if !ok {
		t.Fatal("read failed")
	}
	w, h, _ := JPEGConfig(plain)
	if w != 6 || h != 6 {
		t.Fatalf("replaced file should be 6x6, got %dx%d", w, h)
	}
}

func TestDeletePhotoClearsFiles(t *testing.T) {
	dir := t.TempDir()
	keys := testKeys(t)
	pdf := bytes.Repeat([]byte("%PDF-1.4 demo passport attachment padding\n"), 4)
	if err := Save(dir, keys, 1, pdf, "application/pdf"); err != nil {
		t.Fatal(err)
	}
	if err := DeletePhoto(dir, 1); err != nil {
		t.Fatal(err)
	}
	entries, _ := os.ReadDir(PhotosDir(dir))
	if len(entries) != 0 {
		t.Fatalf("expected empty dir, got %d files", len(entries))
	}
}
