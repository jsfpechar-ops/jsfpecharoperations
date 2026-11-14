package payments

import (
	"bytes"
	"encoding/base64"
	"strings"
	"testing"
)

func TestQRDataURI(t *testing.T) {
	uri, err := QRDataURI(qrSPAYD("CZ6508000000192000145399", 6500, "42", "Stay 42"))
	if err != nil || !strings.HasPrefix(uri, "data:image/png;base64,") {
		t.Fatalf("%v %.30s", err, uri)
	}
	raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(uri, "data:image/png;base64,"))
	if err != nil || !bytes.HasPrefix(raw, []byte("\x89PNG\r\n\x1a\n")) {
		t.Fatalf("not a PNG: %v", err)
	}
	want, _ := qrPNGBytes(qrSPAYD("CZ6508000000192000145399", 6500, "42", "Stay 42"))
	if !bytes.Equal(raw, want) {
		t.Error("must be the same image the PNG routes serve")
	}
}
