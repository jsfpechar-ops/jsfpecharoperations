package ai

import (
	"bytes"
	"context"
	"image/png"
	"strings"
	"testing"

	"github.com/skip2/go-qrcode"
)

func TestGuideQRPNGMatchesTheCode(t *testing.T) {
	const url = "https://ubyhost.example/g/abcdefghijklmnopqrstuvwxyz012345"
	for _, pixels := range []int{6, 20} {
		raw, err := guideQRPNG(url, pixels)
		if err != nil {
			t.Fatal(err)
		}
		img, err := png.Decode(bytes.NewReader(raw))
		if err != nil {
			t.Fatal(err)
		}
		code, _ := qrcode.New(url, qrcode.Medium)
		bits := code.Bitmap() // modules with the four-module border
		if img.Bounds().Dx() != len(bits)*pixels || img.Bounds().Dy() != len(bits)*pixels {
			t.Fatalf("%d px: image %v for %d modules", pixels, img.Bounds(), len(bits))
		}
		for y, row := range bits {
			for x, dark := range row {
				r, _, _, _ := img.At(x*pixels+pixels/2, y*pixels+pixels/2).RGBA()
				if (r < 0x8000) != dark {
					t.Fatalf("%d px: module %d,%d differs", pixels, x, y)
				}
			}
		}
	}
}

func TestGuideQRRoutes(t *testing.T) {
	w := newGuideCardWorld(t)
	ctx := context.Background()
	page := guideTestDo(t, w.mux, "GET", w.path("/qr"), w.host, nil)
	if page.Code != 200 {
		t.Fatalf("qr page: %d %s", page.Code, page.Body.String())
	}
	token, _ := w.s.currentToken(ctx, w.apt)
	if len(token) != 32 {
		t.Fatalf("the page did not create a token: %q", token)
	}
	body := page.Body.String()
	for _, want := range []string{"https://ubyhost.example/g/" + token, `src="data:image/png;base64,`, `href="` + w.path("/qr.png") + `"`, `action="` + w.path("/qr/rotate") + `"`, "ui-banner-attention"} {
		if !strings.Contains(body, want) {
			t.Errorf("page lacks %q", want)
		}
	}
	if page.Header().Get("Cache-Control") != "no-store" {
		t.Errorf("Cache-Control = %q", page.Header().Get("Cache-Control"))
	}
	pngRec := guideTestDo(t, w.mux, "GET", w.path("/qr.png"), w.host, nil)
	if pngRec.Code != 200 || pngRec.Header().Get("Content-Type") != "image/png" ||
		pngRec.Header().Get("Content-Disposition") != `attachment; filename="guest-guide-qr.png"` || pngRec.Header().Get("Cache-Control") != "no-store" {
		t.Errorf("png: %d %v", pngRec.Code, pngRec.Header())
	}
	if _, err := png.Decode(pngRec.Body); err != nil {
		t.Errorf("png does not decode: %v", err)
	}
	// rotate: a new token, the old one is gone, and only the owner may do it
	if rec := guideTestDo(t, w.mux, "POST", w.path("/qr/rotate"), w.stranger, nil); rec.Code != 404 {
		t.Errorf("rotate by another account: %d", rec.Code)
	}
	if cur, _ := w.s.currentToken(ctx, w.apt); cur != token {
		t.Fatal("a stranger rotated the token")
	}
	rec := guideTestDo(t, w.mux, "POST", w.path("/qr/rotate"), w.host, nil)
	if rec.Code != 303 || !strings.HasPrefix(location(rec), w.path("/qr")+"?msg=") {
		t.Errorf("rotate: %d %q", rec.Code, location(rec))
	}
	if cur, _ := w.s.currentToken(ctx, w.apt); cur == token || len(cur) != 32 {
		t.Errorf("token after rotate = %q", cur)
	}
	// another property's QR is not reachable
	if rec := guideTestDo(t, w.mux, "GET", "/apartments/"+itoa64(w.otherApt)+"/guide/qr.png", w.host, nil); rec.Code != 404 {
		t.Errorf("foreign qr.png: %d", rec.Code)
	}
	if rec := guideTestDo(t, w.mux, "GET", w.path("/qr.png"), 0, nil); rec.Code != 303 {
		t.Errorf("signed-out qr.png: %d", rec.Code)
	}
}
