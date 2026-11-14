// Package imgproc is the Go twin of the host photo pipeline of the Python app:
// passport_photos.reencode_image followed by guide_photos._shrink (brief 1641).
// It turns an uploaded JPEG, PNG or WebP into a clean JPEG: first frame only,
// EXIF orientation applied to the pixels, transparency on white, no metadata,
// at most MaxSide pixels on the longest side. Nothing here touches a file or
// the network.
package imgproc

import (
	"bytes"
	"encoding/binary"
	"errors"
	"image"
	"image/color"
	"image/draw"
	"image/jpeg"
	_ "image/png" // registers the PNG decoder
	"math"

	xdraw "golang.org/x/image/draw"
	_ "golang.org/x/image/webp" // registers the WebP decoder
)

const (
	// MaxPixels is passport_photos.MAX_IMAGE_PIXELS.
	MaxPixels = 40_000_000
	// MaxSide is guide_photos.MAX_SIDE.
	MaxSide = 1600
	// Quality is guide_photos.JPEG_QUALITY, the quality of the stored file.
	Quality = 82
)

var (
	// ErrNotImage is Python's ValueError "does not look like a valid image":
	// not a JPEG, PNG or WebP, or one that cannot be fully decoded.
	ErrNotImage = errors.New("imgproc: the file is not a valid JPEG, PNG or WebP image")
	// ErrTooManyPixels is Python's ValueError for width*height > MaxPixels.
	ErrTooManyPixels = errors.New("imgproc: the photo has too many pixels")
)

// slot lets one picture at a time through the decoder: a 40 megapixel photo
// needs about 220 MB, and the Go container has little memory.
var slot = make(chan struct{}, 1)

// Clean is guide_photos._shrink(passport_photos.reencode_image(content)): a
// JPEG of quality Quality, EXIF-free, upright, at most MaxSide on its longest
// side (a smaller picture is never enlarged).
func Clean(content []byte) ([]byte, error) {
	if !isJPEG(content) && !isPNG(content) && !isWebP(content) {
		return nil, ErrNotImage // GIF, BMP, PDF and the rest are refused, as in Python
	}
	cfg, _, err := image.DecodeConfig(bytes.NewReader(content))
	if err != nil || cfg.Width <= 0 || cfg.Height <= 0 {
		return nil, ErrNotImage
	}
	if int64(cfg.Width)*int64(cfg.Height) > MaxPixels {
		return nil, ErrTooManyPixels
	}
	slot <- struct{}{}
	defer func() { <-slot }()

	src, _, err := image.Decode(bytes.NewReader(content))
	if err != nil {
		return nil, ErrNotImage
	}
	flat := flatten(src)
	src = nil
	flat = shrink(flat)
	if isJPEG(content) {
		flat = orient(flat, jpegOrientation(content))
	}
	var out bytes.Buffer
	if err := jpeg.Encode(&out, flat, &jpeg.Options{Quality: Quality}); err != nil {
		return nil, err
	}
	return out.Bytes(), nil
}

func isJPEG(b []byte) bool { return len(b) > 3 && b[0] == 0xFF && b[1] == 0xD8 && b[2] == 0xFF }
func isPNG(b []byte) bool  { return bytes.HasPrefix(b, []byte("\x89PNG\r\n\x1a\n")) }
func isWebP(b []byte) bool {
	return len(b) > 12 && string(b[0:4]) == "RIFF" && string(b[8:12]) == "WEBP"
}

// flatten is passport_photos._flatten: an RGB copy, transparency composited on
// white. The result is always opaque, so the JPEG encoder gets plain RGBA.
func flatten(src image.Image) *image.RGBA {
	b := src.Bounds()
	dst := image.NewRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
	draw.Draw(dst, dst.Bounds(), image.NewUniform(color.White), image.Point{}, draw.Src)
	draw.Draw(dst, dst.Bounds(), src, b.Min, draw.Over)
	return dst
}

// shrink is Image.thumbnail((MaxSide, MaxSide)): keep the aspect ratio, fit the
// longest side to MaxSide, never enlarge. Orientation turns the picture by a
// multiple of 90 degrees, which keeps the longest side, so shrinking first is
// the same and uses less memory.
func shrink(src *image.RGBA) *image.RGBA {
	w, h := src.Bounds().Dx(), src.Bounds().Dy()
	if w <= MaxSide && h <= MaxSide {
		return src
	}
	nw, nh := MaxSide, MaxSide
	if w >= h {
		nh = max(1, int(math.Round(float64(h)*MaxSide/float64(w))))
	} else {
		nw = max(1, int(math.Round(float64(w)*MaxSide/float64(h))))
	}
	dst := image.NewRGBA(image.Rect(0, 0, nw, nh))
	xdraw.CatmullRom.Scale(dst, dst.Bounds(), src, src.Bounds(), xdraw.Src, nil)
	return dst
}

// orient is ImageOps.exif_transpose for the eight EXIF orientations.
func orient(src *image.RGBA, o int) *image.RGBA {
	if o < 2 || o > 8 {
		return src
	}
	w, h := src.Bounds().Dx(), src.Bounds().Dy()
	dw, dh := w, h
	if o >= 5 {
		dw, dh = h, w
	}
	dst := image.NewRGBA(image.Rect(0, 0, dw, dh))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			var nx, ny int
			switch o {
			case 2: // mirrored left to right
				nx, ny = w-1-x, y
			case 3: // turned 180 degrees
				nx, ny = w-1-x, h-1-y
			case 4: // mirrored top to bottom
				nx, ny = x, h-1-y
			case 5: // transposed
				nx, ny = y, x
			case 6: // turned 90 degrees clockwise
				nx, ny = h-1-y, x
			case 7: // transversed
				nx, ny = h-1-y, w-1-x
			case 8: // turned 90 degrees counter-clockwise
				nx, ny = y, w-1-x
			}
			si := src.PixOffset(x, y)
			di := dst.PixOffset(nx, ny)
			copy(dst.Pix[di:di+4], src.Pix[si:si+4])
		}
	}
	return dst
}

// jpegOrientation reads the EXIF orientation (tag 0x0112) from the APP1
// segment of a JPEG; 1 when there is none or it cannot be read. PNG and WebP
// orientation is not read (a documented difference, brief 1641).
func jpegOrientation(b []byte) int {
	i := 2
	for i+4 <= len(b) {
		if b[i] != 0xFF {
			return 1
		}
		marker := b[i+1]
		if marker == 0xFF { // fill byte
			i++
			continue
		}
		if marker == 0xD8 || (marker >= 0xD0 && marker <= 0xD7) || marker == 0x01 {
			i += 2
			continue
		}
		if marker == 0xDA || marker == 0xD9 { // start of scan or end: no EXIF after it
			return 1
		}
		n := int(binary.BigEndian.Uint16(b[i+2 : i+4]))
		if n < 2 || i+2+n > len(b) {
			return 1
		}
		seg := b[i+4 : i+2+n]
		if marker == 0xE1 && bytes.HasPrefix(seg, []byte("Exif\x00\x00")) {
			return tiffOrientation(seg[6:])
		}
		i += 2 + n
	}
	return 1
}

func tiffOrientation(t []byte) int {
	if len(t) < 8 {
		return 1
	}
	var bo binary.ByteOrder
	switch string(t[0:2]) {
	case "II":
		bo = binary.LittleEndian
	case "MM":
		bo = binary.BigEndian
	default:
		return 1
	}
	if bo.Uint16(t[2:4]) != 42 {
		return 1
	}
	off := int(bo.Uint32(t[4:8]))
	if off < 8 || off+2 > len(t) {
		return 1
	}
	count := int(bo.Uint16(t[off : off+2]))
	for k := 0; k < count; k++ {
		e := off + 2 + 12*k
		if e+12 > len(t) {
			return 1
		}
		if bo.Uint16(t[e:e+2]) == 0x0112 && bo.Uint16(t[e+2:e+4]) == 3 && bo.Uint32(t[e+4:e+8]) == 1 {
			if v := int(bo.Uint16(t[e+8 : e+10])); v >= 1 && v <= 8 {
				return v
			}
			return 1
		}
	}
	return 1
}
