package guest

import (
	"context"
	"testing"
)

// Guest form parity (#1252 / 2010): purpose options read in the guest's language.
func TestFormPurposeOptionsUsesGuestLanguage(t *testing.T) {
	ctx := context.Background()
	en, err := formPurposeOptions(ctx, nil, "en")
	if err != nil {
		t.Fatal(err)
	}
	de, err := formPurposeOptions(ctx, nil, "de")
	if err != nil {
		t.Fatal(err)
	}
	label := func(opts []formPurposeOption) string {
		for _, o := range opts {
			if o.Code == "10" {
				return o.Label
			}
		}
		return ""
	}
	enLabel, deLabel := label(en), label(de)
	if enLabel == "" || deLabel == "" {
		t.Fatalf("code 10 labels en=%q de=%q", enLabel, deLabel)
	}
	if enLabel == deLabel {
		t.Fatalf("purpose code 10 must differ by language: en=%q de=%q", enLabel, deLabel)
	}
	if deLabel != "Tourismus" {
		t.Fatalf("German tourism label = %q, want Tourismus", deLabel)
	}
}