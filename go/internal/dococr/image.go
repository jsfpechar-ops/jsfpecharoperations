package dococr

import (
	"bytes"
	"image"
	"image/color"
	"image/jpeg"
	"math"
	"strings"

	xdraw "golang.org/x/image/draw"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/imgproc"
)

var tiltAngles = []float64{-8, -6, -4, -2, 0, 2, 4, 6, 8}

// PrepareImage validates a JPEG/PNG/WebP upload, fixes EXIF orientation, strips
// metadata, shrinks the longest side to MaxEdge, and returns a greyscale JPEG.
func PrepareImage(content []byte, contentType string) ([]byte, error) {
	if len(content) == 0 || len(content) > MaxImageBytes {
		return nil, ErrBadDocument
	}
	ct := strings.ToLower(strings.TrimSpace(strings.SplitN(contentType, ";", 2)[0]))
	if ct == "application/pdf" || bytes.HasPrefix(content, []byte("%PDF-")) {
		return nil, ErrBadDocument
	}
	clean, err := imgproc.Reencode(content)
	if err != nil {
		return nil, ErrBadDocument
	}
	src, err := jpeg.Decode(bytes.NewReader(clean))
	if err != nil {
		return nil, ErrBadDocument
	}
	b := src.Bounds()
	w, h := b.Dx(), b.Dy()
	if w <= 0 || h <= 0 {
		return nil, ErrBadDocument
	}
	var gray *image.Gray
	if w > MaxEdge || h > MaxEdge {
		scale := float64(MaxEdge) / float64(max(w, h))
		nw := max(1, int(math.Round(float64(w)*scale)))
		nh := max(1, int(math.Round(float64(h)*scale)))
		dst := image.NewRGBA(image.Rect(0, 0, nw, nh))
		xdraw.CatmullRom.Scale(dst, dst.Bounds(), src, b, xdraw.Src, nil)
		gray = toGray(dst)
	} else {
		gray = toGray(src)
	}
	var out bytes.Buffer
	if err := jpeg.Encode(&out, gray, &jpeg.Options{Quality: GreyQuality}); err != nil {
		return nil, err
	}
	return out.Bytes(), nil
}

// MRZBand extracts the bottom (or top flipped 180°) MRZ band of a greyscale
// JPEG, enlarges it to BandWidth, autocontrasts, and deskews tilted lines.
func MRZBand(jpegBytes []byte, flip bool) ([]byte, error) {
	src, err := jpeg.Decode(bytes.NewReader(jpegBytes))
	if err != nil {
		return nil, ErrBadDocument
	}
	gray := toGray(src)
	w, h := gray.Bounds().Dx(), gray.Bounds().Dy()
	if w <= 0 || h <= 0 {
		return nil, ErrBadDocument
	}
	var band *image.Gray
	if flip {
		bh := max(1, int(float64(h)*BandFraction))
		band = rotate180(cropGray(gray, 0, 0, w, bh))
	} else {
		y0 := int(float64(h) * (1 - BandFraction))
		if y0 >= h {
			y0 = max(0, h-1)
		}
		band = cropGray(gray, 0, y0, w, h)
	}
	bh := band.Bounds().Dy()
	targetH := max(1, int(math.Round(float64(bh)*float64(BandWidth)/float64(w))))
	enlarged := scaleGray(band, BandWidth, targetH)
	autoContrast(enlarged, 1.0)

	smallH := max(1, int(math.Round(float64(enlarged.Bounds().Dy())*400.0/float64(enlarged.Bounds().Dx()))))
	small := scaleGray(enlarged, 400, smallH)

	bestAngle := 0.0
	bestVar := -1.0
	for _, angle := range tiltAngles {
		rot := rotateGray(small, angle, true, 255)
		v := rowVariance(rot)
		if v > bestVar {
			bestVar = v
			bestAngle = angle
		}
	}
	straight := enlarged
	if bestAngle != 0 {
		straight = rotateGray(enlarged, bestAngle, false, 255)
	}
	var out bytes.Buffer
	if err := jpeg.Encode(&out, straight, &jpeg.Options{Quality: 90}); err != nil {
		return nil, err
	}
	return out.Bytes(), nil
}

func toGray(src image.Image) *image.Gray {
	if g, ok := src.(*image.Gray); ok && g.Bounds().Min == (image.Point{}) {
		cp := image.NewGray(g.Bounds())
		copy(cp.Pix, g.Pix)
		return cp
	}
	b := src.Bounds()
	w, h := b.Dx(), b.Dy()
	dst := image.NewGray(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			r, g, bl, _ := src.At(b.Min.X+x, b.Min.Y+y).RGBA()
			luma := (299*(r>>8) + 587*(g>>8) + 114*(bl>>8) + 500) / 1000
			dst.SetGray(x, y, color.Gray{Y: uint8(min(255, luma))})
		}
	}
	return dst
}

func cropGray(src *image.Gray, x0, y0, x1, y1 int) *image.Gray {
	w, h := max(1, x1-x0), max(1, y1-y0)
	dst := image.NewGray(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		si := src.PixOffset(x0, y0+y)
		di := dst.PixOffset(0, y)
		copy(dst.Pix[di:di+w], src.Pix[si:si+w])
	}
	return dst
}

func rotate180(src *image.Gray) *image.Gray {
	w, h := src.Bounds().Dx(), src.Bounds().Dy()
	dst := image.NewGray(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			dst.Pix[dst.PixOffset(w-1-x, h-1-y)] = src.Pix[src.PixOffset(x, y)]
		}
	}
	return dst
}

func scaleGray(src *image.Gray, w, h int) *image.Gray {
	dst := image.NewGray(image.Rect(0, 0, w, h))
	xdraw.CatmullRom.Scale(dst, dst.Bounds(), src, src.Bounds(), xdraw.Src, nil)
	return dst
}

func autoContrast(img *image.Gray, cutoffPercent float64) {
	var hist [256]int
	w, h := img.Bounds().Dx(), img.Bounds().Dy()
	for y := 0; y < h; y++ {
		row := img.Pix[y*img.Stride : y*img.Stride+w]
		for _, v := range row {
			hist[v]++
		}
	}
	cut := int(float64(w*h) * cutoffPercent / 100.0)
	lo, acc := 0, 0
	for lo < 255 && acc+hist[lo] <= cut {
		acc += hist[lo]
		lo++
	}
	hi, acc := 255, 0
	for hi > 0 && acc+hist[hi] <= cut {
		acc += hist[hi]
		hi--
	}
	if hi <= lo {
		return
	}
	var lut [256]uint8
	scale := 255.0 / float64(hi-lo)
	for i := 0; i < 256; i++ {
		switch {
		case i <= lo:
			lut[i] = 0
		case i >= hi:
			lut[i] = 255
		default:
			lut[i] = uint8(math.Round(float64(i-lo) * scale))
		}
	}
	for y := 0; y < h; y++ {
		row := img.Pix[y*img.Stride : y*img.Stride+w]
		for i, v := range row {
			row[i] = lut[v]
		}
	}
}

// rotateGray rotates src counter-clockwise by angleDeg degrees with bilinear
// interpolation and fill outside the source bounds.
func rotateGray(src *image.Gray, angleDeg float64, expand bool, fill uint8) *image.Gray {
	sw, sh := src.Bounds().Dx(), src.Bounds().Dy()
	rad := angleDeg * math.Pi / 180.0
	cosA, sinA := math.Cos(rad), math.Sin(rad)

	dw, dh := sw, sh
	if expand {
		dw = max(1, int(math.Ceil(math.Abs(float64(sw)*cosA)+math.Abs(float64(sh)*sinA))))
		dh = max(1, int(math.Ceil(math.Abs(float64(sw)*sinA)+math.Abs(float64(sh)*cosA))))
	}
	dst := image.NewGray(image.Rect(0, 0, dw, dh))
	scx, scy := float64(sw-1)/2.0, float64(sh-1)/2.0
	dcx, dcy := float64(dw-1)/2.0, float64(dh-1)/2.0

	for y := 0; y < dh; y++ {
		dy := float64(y) - dcy
		rowOff := y * dst.Stride
		for x := 0; x < dw; x++ {
			dx := float64(x) - dcx
			sx := dx*cosA - dy*sinA + scx
			sy := dx*sinA + dy*cosA + scy
			x0, y0 := int(math.Floor(sx)), int(math.Floor(sy))
			if x0 < 0 || y0 < 0 || x0+1 >= sw || y0+1 >= sh {
				if x0 >= 0 && y0 >= 0 && x0 < sw && y0 < sh {
					dst.Pix[rowOff+x] = src.Pix[y0*src.Stride+x0]
				} else {
					dst.Pix[rowOff+x] = fill
				}
				continue
			}
			fx, fy := sx-float64(x0), sy-float64(y0)
			p00 := float64(src.Pix[y0*src.Stride+x0])
			p10 := float64(src.Pix[y0*src.Stride+x0+1])
			p01 := float64(src.Pix[(y0+1)*src.Stride+x0])
			p11 := float64(src.Pix[(y0+1)*src.Stride+x0+1])
			top := p00*(1-fx) + p10*fx
			bot := p01*(1-fx) + p11*fx
			dst.Pix[rowOff+x] = uint8(math.Round(top*(1-fy) + bot*fy))
		}
	}
	return dst
}

func rowVariance(img *image.Gray) float64 {
	w, h := img.Bounds().Dx(), img.Bounds().Dy()
	if w == 0 || h == 0 {
		return 0
	}
	means := make([]float64, h)
	var sumAll float64
	invW := 1.0 / float64(w)
	for y := 0; y < h; y++ {
		row := img.Pix[y*img.Stride : y*img.Stride+w]
		var sum int
		for _, v := range row {
			sum += int(v)
		}
		m := float64(sum) * invW
		means[y] = m
		sumAll += m
	}
	mean := sumAll / float64(h)
	var sq float64
	for _, m := range means {
		d := m - mean
		sq += d * d
	}
	return sq / float64(h)
}
