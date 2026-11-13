package pdf

import (
	"fmt"
	"strings"
	"unicode"

	"github.com/skip2/go-qrcode"
	"golang.org/x/text/unicode/norm"
)

const qrChars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $+-./:"

// asciiUpper is payments.ascii_upper in Python (same as payments.qrASCIIUpper in Go).
func asciiUpper(text string, limit int) string {
	var up strings.Builder
	for _, r := range norm.NFKD.String(text) {
		if norm.NFC.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		if r == 'ß' {
			up.WriteString("SS")
			continue
		}
		up.WriteRune(unicode.ToUpper(r))
	}
	var b strings.Builder
	lastSpace := false
	for _, r := range up.String() {
		if !strings.ContainsRune(qrChars, r) {
			r = ' '
		}
		if r == ' ' {
			if lastSpace {
				continue
			}
			lastSpace = true
		} else {
			lastSpace = false
		}
		b.WriteRune(r)
	}
	plain := strings.TrimSpace(b.String())
	if len(plain) > limit {
		plain = plain[:limit]
	}
	return strings.TrimRight(plain, " ")
}

// spayd is payments.spayd in Python; amount is in haler (Python formats
// Decimal(haler)/100 with two decimals).
func spayd(iban string, haler int64, vs, message, bic string) string {
	account := iban
	if bic != "" {
		account += "+" + strings.ToUpper(bic)
	}
	sign := ""
	if haler < 0 {
		sign, haler = "-", -haler
	}
	return strings.Join([]string{
		"SPD", "1.0", "ACC:" + account,
		fmt.Sprintf("AM:%s%d.%02d", sign, haler/100, haler%100),
		"CC:CZK", "X-VS:" + vs, "MSG:" + asciiUpper(message, 60),
	}, "*")
}

// qrPNG is payments.qr_png_bytes: medium correction, 6 px modules, 4-module border.
func qrPNG(payload string) ([]byte, error) {
	code, err := qrcode.New(payload, qrcode.Medium)
	if err != nil {
		return nil, err
	}
	return code.PNG(-6)
}
