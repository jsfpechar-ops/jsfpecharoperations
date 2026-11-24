// Package passportphotos is the Go twin of App/app/passport_photos.py for
// writing passport attachments at rest (brief 1597b). Routes still call
// Python today; demo seed will call Save once brief 1597 lands.
package passportphotos

import (
	"bytes"
	"errors"
	"fmt"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/imgproc"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const (
	maxImageBytes   = 5 * 1024 * 1024
	maxPDFBytes     = 15 * 1024 * 1024
	storedImageType = "image/jpeg"
	allowedPDFType  = "application/pdf"
	encSuffix       = ".enc"
)

// AllExtensions is passport_photos.ALL_EXTENSIONS, sorted like Python.
var AllExtensions = []string{".jpg", ".pdf", ".png", ".webp"}

var allowedImageTypes = map[string]string{
	"image/jpeg": ".jpg",
	"image/jpg":  ".jpg",
	"image/png":  ".png",
	"image/webp": ".webp",
}

// PhotosDir is passport_photos.PHOTOS_DIR under the data directory.
func PhotosDir(dataDir string) string { return filepath.Join(dataDir, "passport_photos") }

// Save is passport_photos.save_photo: validate, re-encode images as JPEG q90,
// encrypt with the data keys, write <guest_id><ext>.enc, chmod 600.
func Save(dataDir string, keys *secure.MultiFernet, guestID int64, content []byte, contentType string) error {
	if keys == nil {
		return errors.New("passportphotos: data encryption keys are not configured")
	}
	body, storeExt, err := Prepare(content, contentType)
	if err != nil {
		return err
	}
	return SavePrepared(dataDir, keys, guestID, body, storeExt)
}

// Prepare validates an upload and returns the bytes to store with their
// extension, so a caller can refuse a bad file before it writes anything.
func Prepare(content []byte, contentType string) ([]byte, string, error) {
	return prepareUpload(content, contentType)
}

// SavePrepared stores bytes returned by Prepare: encrypt, write
// <guest_id><ext>.enc, chmod 600. It replaces any prior photo for the guest.
func SavePrepared(dataDir string, keys *secure.MultiFernet, guestID int64, body []byte, storeExt string) error {
	if keys == nil {
		return errors.New("passportphotos: data encryption keys are not configured")
	}
	dir := PhotosDir(dataDir)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("passportphotos: create directory: %w", err)
	}
	if err := DeletePhoto(dataDir, guestID); err != nil {
		return err
	}
	token, err := keys.Encrypt(body)
	if err != nil {
		return fmt.Errorf("passportphotos: encrypt: %w", err)
	}
	target := filepath.Join(dir, strconv.FormatInt(guestID, 10)+storeExt+encSuffix)
	if err := os.WriteFile(target, []byte(token), 0o600); err != nil {
		return fmt.Errorf("passportphotos: write %s: %w", filepath.Base(target), err)
	}
	return nil
}

// DeletePhoto is passport_photos.delete_photo.
func DeletePhoto(dataDir string, guestID int64) error {
	dir := PhotosDir(dataDir)
	id := strconv.FormatInt(guestID, 10)
	for _, ext := range AllExtensions {
		for _, suffix := range []string{encSuffix, ""} {
			p := filepath.Join(dir, id+ext+suffix)
			info, err := os.Stat(p)
			if err != nil {
				if os.IsNotExist(err) {
					continue
				}
				return err
			}
			if info.Mode().IsRegular() {
				if err := os.Remove(p); err != nil && !os.IsNotExist(err) {
					return err
				}
			}
		}
	}
	return nil
}

// Read is passport_photos.read_photo for the guest privacy download path
// (brief 1734): prefer encrypted files, decrypt with the data keys.
func Read(dataDir string, keys *secure.MultiFernet, guestID int64) ([]byte, string, bool) {
	dir := PhotosDir(dataDir)
	id := strconv.FormatInt(guestID, 10)
	for _, ext := range AllExtensions {
		enc := filepath.Join(dir, id+ext+encSuffix)
		if info, err := os.Stat(enc); err == nil && info.Mode().IsRegular() {
			raw, err := os.ReadFile(enc)
			if err != nil || keys == nil {
				return nil, "", false
			}
			plain, err := keys.Decrypt(string(raw), 0, time.Now())
			if err != nil {
				return nil, "", false
			}
			return plain, ctypeForExt(ext), true
		}
		leg := filepath.Join(dir, id+ext)
		if info, err := os.Stat(leg); err == nil && info.Mode().IsRegular() {
			raw, err := os.ReadFile(leg)
			if err != nil {
				return nil, "", false
			}
			return raw, ctypeForExt(ext), true
		}
	}
	return nil, "", false
}

func prepareUpload(content []byte, contentType string) ([]byte, string, error) {
	ctype, err := validateUpload(content, contentType)
	if err != nil {
		return nil, "", err
	}
	if ctype == allowedPDFType {
		return content, ".pdf", nil
	}
	jpeg, err := imgproc.Reencode(content)
	if err != nil {
		if errors.Is(err, imgproc.ErrTooManyPixels) {
			return nil, "", errors.New("The photo has too many pixels. Take it again at the normal camera setting.")
		}
		return nil, "", errors.New("The file does not look like a valid image.")
	}
	return jpeg, ".jpg", nil
}

func validateUpload(content []byte, contentType string) (string, error) {
	ctype := strings.TrimSpace(strings.Split(contentType, ";")[0])
	ctype = strings.ToLower(ctype)
	if _, ok := allowedImageTypes[ctype]; !ok && ctype != allowedPDFType {
		return "", errors.New("Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).")
	}
	if len(content) < 64 {
		return "", errors.New("The uploaded file looks empty.")
	}
	if ctype == allowedPDFType {
		if len(content) > maxPDFBytes {
			return "", errors.New("The PDF is too large. Use a file under 15 MB.")
		}
		if !bytes.HasPrefix(content, []byte("%PDF-")) {
			return "", errors.New("The file does not look like a valid PDF.")
		}
		return ctype, nil
	}
	if len(content) > maxImageBytes {
		return "", errors.New("The photo is too large. Use a file under 5 MB.")
	}
	if !looksLikeImage(content, ctype) {
		return "", errors.New("The file does not look like a valid image.")
	}
	if ctype == "image/jpg" {
		ctype = storedImageType
	}
	return ctype, nil
}

func looksLikeImage(content []byte, contentType string) bool {
	switch contentType {
	case "image/jpeg", "image/jpg":
		return len(content) > 3 && content[0] == 0xFF && content[1] == 0xD8 && content[2] == 0xFF
	case "image/png":
		return bytes.HasPrefix(content, []byte("\x89PNG\r\n\x1a\n"))
	case "image/webp":
		return len(content) >= 12 && string(content[0:4]) == "RIFF" && string(content[8:12]) == "WEBP"
	default:
		return false
	}
}

func ctypeForExt(ext string) string {
	switch strings.ToLower(ext) {
	case ".jpg":
		return storedImageType
	case ".png":
		return "image/png"
	case ".webp":
		return "image/webp"
	case ".pdf":
		return allowedPDFType
	default:
		return "application/octet-stream"
	}
}

// DemoPassportPNG is demo._demo_passport_png: an 8×8 grey PNG for the Karlín
// demo stay (never sent to Police).
func DemoPassportPNG() ([]byte, error) {
	img := image.NewRGBA(image.Rect(0, 0, 8, 8))
	grey := color.RGBA{R: 200, G: 200, B: 200, A: 255}
	for y := 0; y < 8; y++ {
		for x := 0; x < 8; x++ {
			img.SetRGBA(x, y, grey)
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

// JPEGConfig returns width, height and JPEG format check for decrypted content.
func JPEGConfig(plain []byte) (width, height int, ok bool) {
	cfg, err := jpeg.DecodeConfig(bytes.NewReader(plain))
	if err != nil {
		return 0, 0, false
	}
	return cfg.Width, cfg.Height, true
}
