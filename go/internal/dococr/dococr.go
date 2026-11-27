// Package dococr reads a guest's travel-document MRZ locally with Tesseract.
//
// Privacy-first: nothing leaves the server and nothing is stored. Tesseract
// reads the photo's machine-readable zone (ICAO 9303 TD3, TD2, or TD1) and
// ICAO 7-3-1 check digits validate the read before any field is returned.
package dococr

import (
	"bytes"
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	MaxEdge       = 1568
	GreyQuality   = 80
	BandFraction  = 0.4
	BandWidth     = 1800
	MaxImageBytes = 5 * 1024 * 1024

	whitelist  = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
	ocrTimeout = 15 * time.Second
)

var (
	// ErrBadDocument marks an upload that is not a readable JPEG, PNG, or WebP image.
	ErrBadDocument = errors.New("dococr: bad document image")
	// ErrNoEngine marks that the local tesseract binary is not installed.
	ErrNoEngine = errors.New("dococr: tesseract engine not installed")
	// ErrNothingRead marks that no check-digit-verified MRZ was found.
	ErrNothingRead = errors.New("dococr: no valid MRZ found")

	// lookPath and runOCR are package seams so tests can stub Tesseract without spawning it.
	lookPath = exec.LookPath
	runOCR   = runTesseractDefault
)

// EngineAvailable reports whether the local tesseract binary is installed.
func EngineAvailable() bool {
	p, err := lookPath("tesseract")
	return err == nil && p != ""
}

// SetEngineForTest overrides tesseract discovery and execution for tests and
// returns a restore function. Passing nil leaves the corresponding seam unchanged.
func SetEngineForTest(lp func(string) (string, error), run func(context.Context, []byte) (string, error)) func() {
	origLP, origRun := lookPath, runOCR
	if lp != nil {
		lookPath = lp
	}
	if run != nil {
		runOCR = run
	}
	return func() {
		lookPath = origLP
		runOCR = origRun
	}
}

// RunTesseract invokes the local tesseract binary on a single JPEG image.
func RunTesseract(ctx context.Context, jpegBytes []byte) (string, error) {
	return runOCR(ctx, jpegBytes)
}

func runTesseractDefault(ctx context.Context, jpegBytes []byte) (string, error) {
	bin, err := lookPath("tesseract")
	if err != nil || bin == "" {
		return "", ErrNoEngine
	}
	tmpDir, err := os.MkdirTemp("", "ubyocr-")
	if err != nil {
		return "", err
	}
	defer func() { _ = os.RemoveAll(tmpDir) }()

	imgPath := filepath.Join(tmpDir, "doc.jpg")
	if err := os.WriteFile(imgPath, jpegBytes, 0o600); err != nil {
		return "", err
	}
	runCtx, cancel := context.WithTimeout(ctx, ocrTimeout)
	defer cancel()

	cmd := exec.CommandContext(runCtx, bin,
		imgPath,
		"stdout",
		"-l", "eng",
		"--psm", "6",
		"-c", "tessedit_char_whitelist="+whitelist,
	)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return "", ErrNothingRead
	}
	return stdout.String(), nil
}

// ReadDocument runs Tesseract on up to three views of jpegBytes (bottom MRZ
// band, full image, flipped top band) and returns normalised guest fields.
func ReadDocument(ctx context.Context, jpegBytes []byte) (map[string]string, error) {
	attempts := []func() []byte{
		func() []byte { return bandOrPlain(jpegBytes, false) },
		func() []byte { return jpegBytes },
		func() []byte { return bandOrPlain(jpegBytes, true) },
	}
	var values map[string]string
	for _, build := range attempts {
		text, err := RunTesseract(ctx, build())
		if err != nil {
			if errors.Is(err, ErrNothingRead) {
				continue
			}
			return nil, err
		}
		parsed, perr := ParseMRZ(text)
		if perr == nil {
			values = parsed
			break
		}
		if !errors.Is(perr, ErrNothingRead) {
			return nil, perr
		}
	}
	if values == nil {
		return nil, ErrNothingRead
	}
	if !validation.KnownCountry(values["nationality"]) {
		values["nationality"] = ""
	}
	return values, nil
}

func bandOrPlain(jpegBytes []byte, flip bool) []byte {
	band, err := MRZBand(jpegBytes, flip)
	if err != nil || len(band) == 0 {
		return jpegBytes
	}
	return band
}
