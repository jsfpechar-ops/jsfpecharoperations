package payments

// QRDataURI is payments.qr_data_uri (App/app/payments.py 162-163): the PNG of
// a payment QR code as a data: URI, for a page that shows it inline. The code
// is the one the QR PNG routes serve (medium error correction, 6 px modules,
// 4-module border). Brief 1543.

import "encoding/base64"

// QRDataURI returns "data:image/png;base64,..." for the payload.
func QRDataURI(payload string) (string, error) {
	png, err := qrPNGBytes(payload)
	if err != nil {
		return "", err
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(png), nil
}
