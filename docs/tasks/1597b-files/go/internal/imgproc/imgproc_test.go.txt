package imgproc

import (
	"bytes"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"image"
	"image/color"
	"image/gif"
	"image/jpeg"
	"image/png"
	"testing"
)

// Fixtures made with Pillow 12: 8x4 pictures, left half red, right half blue.
const (
	webpLossy    = "UklGRloAAABXRUJQVlA4IE4AAAAwAwCdASoIAAQAAMASJagCdLoB+AFGA/ACu/9wABGB3KzAAP79nr/+cyG3/7tkSYKRP+uiftsiTBSJ//Wjn/41LKEjlc3+NSyhI5feAAA="
	webpLossless = "UklGRh4AAABXRUJQVlA4TBIAAAAvB8AAAA8Q87//8x8O+hDR/wA="
	// webpClear is 8x4 and fully transparent.
	webpClear = "UklGRhoAAABXRUJQVlA4TA0AAAAvB8AAEAcQERGIiP4HAA=="
	// webpAnimated has two frames: the first is webpLossless, the second green.
	webpAnimated = "UklGRoYAAABXRUJQVlA4WAoAAAACAAAABwAAAwAAQU5JTQYAAAAAAAAAAABBTk1GKgAAAAAAAAAAAAcAAAMAAGQAAAJWUDhMEgAAAC8HwAAADxDzv//zHw76ENH/AEFOTUYoAAAAAAAAAAAABwAAAwAAZAAAAFZQOEwPAAAALwfAAAAH0P+I/gciov8BAA=="
)

func decodeJPEG(t *testing.T, b []byte) image.Image {
	t.Helper()
	img, err := jpeg.Decode(bytes.NewReader(b))
	if err != nil {
		t.Fatalf("result is not a JPEG: %v", err)
	}
	return img
}

// near reports whether the pixel is close to c (JPEG is lossy).
func near(img image.Image, x, y int, c color.RGBA) bool {
	r, g, b, _ := img.At(x, y).RGBA()
	d := func(a uint32, e uint8) bool {
		v := int(a>>8) - int(e)
		return v > -40 && v < 40
	}
	return d(r, c.R) && d(g, c.G) && d(b, c.B)
}

var (
	red   = color.RGBA{255, 0, 0, 255}
	blue  = color.RGBA{0, 0, 255, 255}
	white = color.RGBA{255, 255, 255, 255}
)

// halves is w x h, left half red and right half blue.
func halves(w, h int) *image.RGBA {
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			if x < w/2 {
				img.SetRGBA(x, y, red)
			} else {
				img.SetRGBA(x, y, blue)
			}
		}
	}
	return img
}

func encodeJPEG(t *testing.T, img image.Image) []byte {
	t.Helper()
	var b bytes.Buffer
	if err := jpeg.Encode(&b, img, &jpeg.Options{Quality: 95}); err != nil {
		t.Fatal(err)
	}
	return b.Bytes()
}

// withOrientation inserts an EXIF APP1 segment with the orientation, a GPS-like
// extra tag and a comment right after the SOI marker.
func withOrientation(jpg []byte, o uint16, bigEndian bool) []byte {
	var bo binary.AppendByteOrder = binary.LittleEndian
	head := "II"
	if bigEndian {
		bo, head = binary.BigEndian, "MM"
	}
	tiff := []byte(head)
	tiff = bo.AppendUint16(tiff, 42)
	tiff = bo.AppendUint32(tiff, 8)
	tiff = bo.AppendUint16(tiff, 2) // two entries
	tiff = bo.AppendUint16(tiff, 0x010F)
	tiff = bo.AppendUint16(tiff, 2)
	tiff = bo.AppendUint32(tiff, 4)
	tiff = append(tiff, 'C', 'a', 'm', 0)
	tiff = bo.AppendUint16(tiff, 0x0112)
	tiff = bo.AppendUint16(tiff, 3)
	tiff = bo.AppendUint32(tiff, 1)
	tiff = bo.AppendUint16(tiff, o)
	tiff = append(tiff, 0, 0)
	tiff = bo.AppendUint32(tiff, 0)
	seg := append([]byte("Exif\x00\x00"), tiff...)
	out := []byte{0xFF, 0xD8, 0xFF, 0xE1}
	out = binary.BigEndian.AppendUint16(out, uint16(len(seg)+2))
	out = append(out, seg...)
	return append(out, jpg[2:]...)
}

func TestOrientationEightValues(t *testing.T) {
	// 16x8, left red, right blue. Expected size and where red ends up.
	base := encodeJPEG(t, halves(16, 8))
	cases := []struct {
		o          uint16
		w, h       int
		redX, redY int // a point that must be red
		blueX      int
		blueY      int
	}{
		{1, 16, 8, 2, 4, 13, 4},
		{2, 16, 8, 13, 4, 2, 4}, // mirrored: red on the right
		{3, 16, 8, 13, 4, 2, 4}, // 180: red on the right
		{4, 16, 8, 2, 4, 13, 4}, // top-bottom mirror: halves stay
		{5, 8, 16, 4, 2, 4, 13}, // transpose: red on top
		{6, 8, 16, 4, 2, 4, 13}, // 90 clockwise: red on top
		{7, 8, 16, 4, 13, 4, 2}, // transverse: red at the bottom
		{8, 8, 16, 4, 13, 4, 2}, // 90 counter-clockwise: red at the bottom
	}
	for _, c := range cases {
		for _, be := range []bool{false, true} {
			out, err := Clean(withOrientation(base, c.o, be))
			if err != nil {
				t.Fatalf("orientation %d: %v", c.o, err)
			}
			img := decodeJPEG(t, out)
			if img.Bounds().Dx() != c.w || img.Bounds().Dy() != c.h {
				t.Fatalf("orientation %d: %v", c.o, img.Bounds())
			}
			if !near(img, c.redX, c.redY, red) || !near(img, c.blueX, c.blueY, blue) {
				t.Errorf("orientation %d (big endian %v): red/blue in the wrong place", c.o, be)
			}
		}
	}
}

func TestNoMetadataSurvives(t *testing.T) {
	out, err := Clean(withOrientation(encodeJPEG(t, halves(16, 8)), 6, false))
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(out, []byte("Exif")) || bytes.Contains(out, []byte("Cam")) {
		t.Error("EXIF data survived")
	}
}

func TestShrinkOnlyAndAspect(t *testing.T) {
	big := encodeJPEG(t, halves(3200, 2400))
	out, err := Clean(big)
	if err != nil {
		t.Fatal(err)
	}
	if b := decodeJPEG(t, out).Bounds(); b.Dx() != 1600 || b.Dy() != 1200 {
		t.Errorf("3200x2400 became %v", b)
	}
	tall := encodeJPEG(t, halves(1000, 2001))
	out, _ = Clean(tall)
	if b := decodeJPEG(t, out).Bounds(); b.Dx() != 800 || b.Dy() != 1600 {
		t.Errorf("1000x2001 became %v", b) // 1000*1600/2001 = 799.6 -> 800
	}
	small := encodeJPEG(t, halves(40, 30))
	out, _ = Clean(small)
	if b := decodeJPEG(t, out).Bounds(); b.Dx() != 40 || b.Dy() != 30 {
		t.Errorf("a small picture was resized: %v", b)
	}
}

func TestPNGTransparencyOnWhite(t *testing.T) {
	img := image.NewNRGBA(image.Rect(0, 0, 8, 4))
	for x := 4; x < 8; x++ {
		for y := 0; y < 4; y++ {
			img.SetNRGBA(x, y, color.NRGBA{0, 0, 255, 255})
		}
	}
	var b bytes.Buffer
	if err := png.Encode(&b, img); err != nil {
		t.Fatal(err)
	}
	out, err := Clean(b.Bytes())
	if err != nil {
		t.Fatal(err)
	}
	got := decodeJPEG(t, out)
	if !near(got, 1, 1, white) || !near(got, 6, 2, blue) {
		t.Error("transparent pixels are not white, or opaque ones changed")
	}
}

func TestWebP(t *testing.T) {
	for name, data := range map[string]string{"lossy": webpLossy, "lossless": webpLossless} {
		raw, _ := base64.StdEncoding.DecodeString(data)
		out, err := Clean(raw)
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		img := decodeJPEG(t, out)
		if img.Bounds().Dx() != 8 || img.Bounds().Dy() != 4 || !near(img, 1, 2, red) || !near(img, 6, 2, blue) {
			t.Errorf("%s: wrong picture %v", name, img.Bounds())
		}
	}
	raw, _ := base64.StdEncoding.DecodeString(webpClear)
	out, err := Clean(raw)
	if err != nil {
		t.Fatal(err)
	}
	if !near(decodeJPEG(t, out), 3, 2, white) {
		t.Error("a transparent WebP is not white")
	}
}

// Python keeps the first frame of an animated WebP. x/image/webp cannot decode
// animation, so Go refuses it (documented difference, brief 1641).
func TestAnimatedWebPIsRefused(t *testing.T) {
	raw, _ := base64.StdEncoding.DecodeString(webpAnimated)
	if _, err := Clean(raw); !errors.Is(err, ErrNotImage) {
		t.Errorf("animated WebP: %v", err)
	}
}

func TestRefusals(t *testing.T) {
	var g bytes.Buffer
	_ = gif.Encode(&g, halves(8, 4), nil)
	for name, data := range map[string][]byte{
		"gif":       g.Bytes(),
		"text":      []byte("hello, this is not a picture at all, not even close, really"),
		"empty":     nil,
		"truncated": encodeJPEG(t, halves(64, 64))[:200],
	} {
		if _, err := Clean(data); !errors.Is(err, ErrNotImage) {
			t.Errorf("%s: %v", name, err)
		}
	}
}

func TestTooManyPixelsBeforeDecoding(t *testing.T) {
	// A PNG header that claims 10000 x 4001 pixels (40,010,000). Nothing is
	// decoded, so the file does not need the pixel data.
	hdr := []byte("\x89PNG\r\n\x1a\n")
	ihdr := make([]byte, 0, 13)
	ihdr = binary.BigEndian.AppendUint32(ihdr, 10000)
	ihdr = binary.BigEndian.AppendUint32(ihdr, 4001)
	ihdr = append(ihdr, 8, 2, 0, 0, 0)
	chunk := binary.BigEndian.AppendUint32(nil, 13)
	chunk = append(chunk, "IHDR"...)
	chunk = append(chunk, ihdr...)
	chunk = binary.BigEndian.AppendUint32(chunk, crc(append([]byte("IHDR"), ihdr...)))
	if _, err := Clean(append(hdr, chunk...)); !errors.Is(err, ErrTooManyPixels) {
		t.Errorf("40,010,000 pixels: %v", err)
	}
}

func crc(b []byte) uint32 {
	var t [256]uint32
	for i := range t {
		c := uint32(i)
		for k := 0; k < 8; k++ {
			if c&1 == 1 {
				c = 0xEDB88320 ^ (c >> 1)
			} else {
				c >>= 1
			}
		}
		t[i] = c
	}
	c := ^uint32(0)
	for _, v := range b {
		c = t[byte(c)^v] ^ (c >> 8)
	}
	return ^c
}

func TestReencodeKeepsResolution(t *testing.T) {
	src := halves(40, 20)
	var buf bytes.Buffer
	if err := png.Encode(&buf, src); err != nil {
		t.Fatal(err)
	}
	out, err := Reencode(buf.Bytes())
	if err != nil {
		t.Fatal(err)
	}
	cfg, err := jpeg.DecodeConfig(bytes.NewReader(out))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Width != 40 || cfg.Height != 20 {
		t.Fatalf("reencode size %dx%d, want 40x20", cfg.Width, cfg.Height)
	}
}

func TestJPEGOrientationJunk(t *testing.T) {
	for name, b := range map[string][]byte{
		"short":   {0xFF, 0xD8, 0xFF},
		"no exif": encodeJPEG(t, halves(8, 4)),
		"bad len": {0xFF, 0xD8, 0xFF, 0xE1, 0xFF, 0xFF, 'E'},
	} {
		if o := jpegOrientation(b); o != 1 {
			t.Errorf("%s: %d", name, o)
		}
	}
}
