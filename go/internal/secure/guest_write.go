package secure

import (
	"fmt"
)

var guestWriteFields = map[string]string{
	"birth_date":      "birth_date_enc",
	"doc_number":      "doc_number_enc",
	"visa_number":     "visa_number_enc",
	"res_street":      "res_street_enc",
	"res_city":        "res_city_enc",
	"signature_png":   "signature_png_enc",
	"fee_host_reason": "fee_host_reason_enc",
}

// GuestWriteValues mirrors Python's _write_values for protected guest fields.
// It returns a fresh map and clears legacy plaintext columns in the same write.
func GuestWriteValues(keys *MultiFernet, values map[string]any) (map[string]any, error) {
	out := make(map[string]any, len(values)*2)
	for key, value := range values {
		enc, protected := guestWriteFields[key]
		if !protected {
			out[key] = value
			continue
		}
		out[key] = nil
		if value == nil {
			out[enc] = nil
			continue
		}
		plain, ok := value.(string)
		if !ok {
			return nil, fmt.Errorf("protected guest field %s must be a string or nil", key)
		}
		if plain == "" {
			out[enc] = nil
			continue
		}
		if keys == nil {
			return nil, fmt.Errorf("data keys unavailable for protected guest field %s", key)
		}
		token, err := keys.EncryptField(plain)
		if err != nil {
			return nil, fmt.Errorf("encrypt protected guest field %s: %w", key, err)
		}
		out[enc] = token
	}
	return out, nil
}
