package dococr

import (
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"math"
	"os"
	"testing"

	"golang.org/x/image/font"
	"golang.org/x/image/font/opentype"
	"golang.org/x/image/math/fixed"
)

func TestPrepareImageShrinksGreyscalesAndRefusesPDF(t *testing.T) {
	if _, err := PrepareImage([]byte("%PDF-1.7\n"), "application/pdf"); !errors.Is(err, ErrBadDocument) {
		t.Fatalf("PDF should return ErrBadDocument, got %v", err)
	}
	big := image.NewRGBA(image.Rect(0, 0, 2400, 1600))
	for y := 0; y < 1600; y++ {
		for x := 0; x < 2400; x++ {
			big.SetRGBA(x, y, color.RGBA{R: 200, G: 100, B: 50, A: 255})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, big); err != nil {
		t.Fatal(err)
	}
	out, err := PrepareImage(buf.Bytes(), "image/png")
	if err != nil {
		t.Fatalf("PrepareImage: %v", err)
	}
	img, err := jpeg.Decode(bytes.NewReader(out))
	if err != nil {
		t.Fatalf("decode output JPEG: %v", err)
	}
	if img.Bounds().Dx() != MaxEdge {
		t.Fatalf("width = %d, want %d", img.Bounds().Dx(), MaxEdge)
	}
	if _, ok := img.(*image.Gray); !ok {
		t.Fatalf("expected greyscale *image.Gray, got %T", img)
	}
}

func jpegWithEXIFOrientation(t *testing.T, img image.Image, orient uint16) []byte {
	t.Helper()
	var plain bytes.Buffer
	if err := jpeg.Encode(&plain, img, &jpeg.Options{Quality: 90}); err != nil {
		t.Fatal(err)
	}
	raw := plain.Bytes()
	var tiff bytes.Buffer
	tiff.WriteString("II")
	_ = binary.Write(&tiff, binary.LittleEndian, uint16(42))
	_ = binary.Write(&tiff, binary.LittleEndian, uint32(8))
	_ = binary.Write(&tiff, binary.LittleEndian, uint16(1))
	_ = binary.Write(&tiff, binary.LittleEndian, uint16(0x0112))
	_ = binary.Write(&tiff, binary.LittleEndian, uint16(3))
	_ = binary.Write(&tiff, binary.LittleEndian, uint32(1))
	_ = binary.Write(&tiff, binary.LittleEndian, orient)
	_ = binary.Write(&tiff, binary.LittleEndian, uint16(0))
	_ = binary.Write(&tiff, binary.LittleEndian, uint32(0))

	payload := append([]byte("Exif\x00\x00"), tiff.Bytes()...)
	var out bytes.Buffer
	out.Write(raw[:2])
	out.Write([]byte{0xFF, 0xE1})
	_ = binary.Write(&out, binary.BigEndian, uint16(len(payload)+2))
	out.Write(payload)
	out.Write(raw[2:])
	return out.Bytes()
}

func TestPrepareImageFixesEXIFOrientation(t *testing.T) {
	src := image.NewRGBA(image.Rect(0, 0, 200, 100))
	raw := jpegWithEXIFOrientation(t, src, 6)
	out, err := PrepareImage(raw, "image/jpeg")
	if err != nil {
		t.Fatalf("PrepareImage EXIF: %v", err)
	}
	img, err := jpeg.Decode(bytes.NewReader(out))
	if err != nil {
		t.Fatal(err)
	}
	if img.Bounds().Dx() != 100 || img.Bounds().Dy() != 200 {
		t.Fatalf("dimensions = %dx%d, want 100x200 after EXIF orientation 6", img.Bounds().Dx(), img.Bounds().Dy())
	}
}

func TestMRZBandEnlargesAndStraightensTilt(t *testing.T) {
	w, h := 800, 500
	base := image.NewGray(image.Rect(0, 0, w, h))
	for i := range base.Pix {
		base.Pix[i] = 250
	}
	for _, cy := range []int{370, 420} {
		for x := 60; x < w-60; x++ {
			y := cy + int(math.Round(float64(x-w/2)*math.Tan(6*math.Pi/180)))
			for dy := -5; dy <= 5; dy++ {
				if y+dy >= 0 && y+dy < h {
					base.SetGray(x, y+dy, color.Gray{Y: 20})
				}
			}
		}
	}
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, base, &jpeg.Options{Quality: 90}); err != nil {
		t.Fatal(err)
	}
	bandBytes, err := MRZBand(buf.Bytes(), false)
	if err != nil {
		t.Fatalf("MRZBand: %v", err)
	}
	bandImg, err := jpeg.Decode(bytes.NewReader(bandBytes))
	if err != nil {
		t.Fatal(err)
	}
	if bandImg.Bounds().Dx() != BandWidth {
		t.Fatalf("band width = %d, want %d", bandImg.Bounds().Dx(), BandWidth)
	}
	tiltedCrop := cropGray(base, 0, int(float64(h)*(1-BandFraction)), w, h)
	tiltedScaled := scaleGray(tiltedCrop, BandWidth, bandImg.Bounds().Dy())
	if rowVariance(toGray(bandImg)) <= rowVariance(tiltedScaled) {
		t.Fatalf("expected deskewed row variance (%v) > tilted (%v)", rowVariance(toGray(bandImg)), rowVariance(tiltedScaled))
	}
}

func TestReadDocumentAttemptOrderAndNationalityCheck(t *testing.T) {
	orig := runOCR
	t.Cleanup(func() { runOCR = orig })

	dummy := image.NewGray(image.Rect(0, 0, 100, 60))
	var buf bytes.Buffer
	_ = jpeg.Encode(&buf, dummy, &jpeg.Options{Quality: 80})

	calls := 0
	runOCR = func(ctx context.Context, _ []byte) (string, error) {
		calls++
		return td3Sample("NOVAK", "JAN", "P1234567", "ZZZ", "900101"), nil
	}
	vals, err := ReadDocument(context.Background(), buf.Bytes())
	if err != nil {
		t.Fatalf("ReadDocument: %v", err)
	}
	if calls != 1 {
		t.Fatalf("calls = %d, want 1", calls)
	}
	if vals["nationality"] != "" {
		t.Fatalf("unknown nationality ZZZ should be cleared, got %q", vals["nationality"])
	}

	calls = 0
	runOCR = func(ctx context.Context, _ []byte) (string, error) {
		calls++
		if calls < 3 {
			return "GARBAGE", nil
		}
		return td3Sample("SMITH", "JOHN", "P1234567", "GBR", "900101"), nil
	}
	vals, err = ReadDocument(context.Background(), buf.Bytes())
	if err != nil || calls != 3 || vals["nationality"] != "GBR" {
		t.Fatalf("3rd attempt: vals=%v err=%v calls=%d", vals, err, calls)
	}

	calls = 0
	runOCR = func(ctx context.Context, _ []byte) (string, error) {
		calls++
		return "", ErrNoEngine
	}
	if _, err := ReadDocument(context.Background(), buf.Bytes()); !errors.Is(err, ErrNoEngine) || calls != 1 {
		t.Fatalf("ErrNoEngine: err=%v calls=%d", err, calls)
	}
}

func TestReadDocumentEndToEndWithTesseract(t *testing.T) {
	if !EngineAvailable() {
		t.Skip("tesseract not installed")
	}
	fontBytes, err := os.ReadFile("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
	if err != nil {
		t.Skip("DejaVuSansMono.ttf not installed")
	}
	tt, err := opentype.Parse(fontBytes)
	if err != nil {
		t.Fatal(err)
	}
	face, err := opentype.NewFace(tt, &opentype.FaceOptions{Size: 36, DPI: 72, Hinting: font.HintingFull})
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = face.Close() }()

	mrz := td3Sample("ERIKSSON", "ANNA<MARIA", "L898902C3", "SWE", "740812")
	lines := bytes.Split([]byte(mrz), []byte("\n"))

	img := image.NewGray(image.Rect(0, 0, 1200, 750))
	for i := range img.Pix {
		img.Pix[i] = 255
	}
	d := &font.Drawer{
		Dst:  img,
		Src:  image.NewUniform(color.Black),
		Face: face,
	}
	d.Dot = fixed.P(80, 560)
	d.DrawString(string(lines[0]))
	d.Dot = fixed.P(80, 640)
	d.DrawString(string(lines[1]))

	var pngBuf bytes.Buffer
	if err := png.Encode(&pngBuf, img); err != nil {
		t.Fatal(err)
	}
	prepared, err := PrepareImage(pngBuf.Bytes(), "image/png")
	if err != nil {
		t.Fatalf("PrepareImage: %v", err)
	}
	vals, err := ReadDocument(context.Background(), prepared)
	if err != nil {
		t.Fatalf("ReadDocument (real tesseract): %v", err)
	}
	if vals["surname"] != "ERIKSSON" || vals["first_name"] != "ANNA MARIA" ||
		vals["birth_date"] != "12081974" || vals["nationality"] != "SWE" || vals["doc_number"] != "L898902C3" {
		t.Fatalf("real tesseract parsed %v", vals)
	}
}
