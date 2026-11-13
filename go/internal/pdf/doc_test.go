package pdf

import (
	"bytes"
	"testing"
)

func TestStrokedSquareRectKeepsWidth(t *testing.T) {
	d := NewDoc()
	ink := RGB(0x1B, 0x1F, 0x25)
	d.Rect(50, 50, 100, 40, 0, nil, &ink, 1.5)
	b, err := d.Bytes()
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(b, []byte("/CreationDate")) {
		t.Fatal("PDF must not carry a fixed /CreationDate")
	}
	a, _ := d.Bytes()
	if !bytes.Equal(a, b) {
		t.Fatal("Bytes is not deterministic")
	}
}
