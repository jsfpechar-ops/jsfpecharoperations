package guideimport

import (
	"strings"
	"testing"
)

func TestFilterCodes(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
		n    int
	}{
		{name: "EN: door code with period", in: "The door code is 4827.", want: "The door code is [left out].", n: 1},
		{name: "EN: gate PIN keypad style", in: "Gate PIN: 1234#", want: "Gate PIN: [left out]", n: 1},
		{name: "EN: entrance code spaced", in: "Entrance code 12 34 56", want: "Entrance code [left out]", n: 1},
		{name: "EN: code after text", in: "1234 is the garage code", want: "[left out] is the garage code", n: 1},
		{name: "EN: keypad start", in: "Press *4411# to open", want: "Press [left out] to open", n: 1},
		{name: "EN: keypad end", in: "keypad: 9876*", want: "keypad: [left out]", n: 1},
		{name: "EN: WiFi password", in: "Wifi password: Sunny-Day22", want: "Wifi password: [left out]", n: 1},
		{name: "EN: WiFi network kept", in: "Wi-Fi network: CasaBlanca", want: "Wi-Fi network: CasaBlanca", n: 0},
		{name: "CZ: kod od dveří", in: "Kód od dveří je 5521.", want: "Kód od dveří je [left out].", n: 1},
		{name: "CZ: heslo na wifi", in: "Heslo na wifi: slunce2024", want: "Heslo na wifi: [left out]", n: 1},
		{name: "CZ: PIN k bráně", in: "PIN k bráně: 8890", want: "PIN k bráně: [left out]", n: 1},
		{name: "CZ: garáž kód", in: "Garáž: kód 3344", want: "Garáž: kód [left out]", n: 1},
		{name: "CZ: domovní vchod spaced", in: "Domovní vchod, kód 1357 8", want: "Domovní vchod, kód [left out]", n: 1},
		{name: "DE: Türcode", in: "Türcode: 7788", want: "Türcode: [left out]", n: 1},
		{name: "DE: WLAN Passwort", in: "Das WLAN-Passwort lautet Sonne12345", want: "Das WLAN-Passwort lautet [left out]", n: 1},
		{name: "DE: Zugangscode", in: "Der Zugangscode für das Tor ist 4455", want: "Der Zugangscode für das Tor ist [left out]", n: 1},
		{name: "DE: Garagencode", in: "Garage code 5566", want: "Garage code [left out]", n: 1},
		{name: "time range", in: "Check-in from 15:00 to 22:00.", want: "Check-in from 15:00 to 22:00.", n: 0},
		{name: "apartment details", in: "The apartment is on floor 3, 65 m2, 1200 CZK per night.", want: "The apartment is on floor 3, 65 m2, 1200 CZK per night.", n: 0},
		{name: "phone number", in: "Call +420 123 456 789 if you are lost.", want: "Call +420 123 456 789 if you are lost.", n: 0},
		{name: "year range", in: "Built in 1998, renovated 2019.", want: "Built in 1998, renovated 2019.", n: 0},
		{name: "bus number", in: "Bus 119 stops at Zlicin", want: "Bus 119 stops at Zlicin", n: 0},
		{name: "postal code", in: "Postal code 110 00 Prague", want: "Postal code 110 00 Prague", n: 0},
		{name: "time range 2", in: "Open 7:30-19:00", want: "Open 7:30-19:00", n: 0},
		{name: "room number", in: "Room 4827", want: "Room 4827", n: 0},
		{name: "two codes in one line", in: "Code 1234 and code 5678", want: "Code [left out] and code [left out]", n: 2},
		{name: "overlapping codes PIN code", in: "PIN code 1234", want: "PIN code [left out]", n: 1},
		{name: "idempotence check", in: "[left out]", want: "[left out]", n: 0},
		{name: "empty string", in: "", want: "", n: 0},
		{name: "diacritics in Czech", in: "Přístupový kód: 7890", want: "Přístupový kód: [left out]", n: 1},
		{name: "uppercase DOOR", in: "DOOR CODE 1111", want: "DOOR CODE [left out]", n: 1},
		{name: "long line no match", in: strings.Repeat("a", 20000), want: strings.Repeat("a", 20000), n: 0},
		{name: "postcode should not trigger", in: "Poštovní kód: 11000", want: "Poštovní kód: 11000", n: 0},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, gotN := FilterCodes(tt.in)
			if got != tt.want {
				t.Errorf("FilterCodes(%q)\n  got: %q\n  want: %q", tt.in, got, tt.want)
			}
			if gotN != tt.n {
				t.Errorf("FilterCodes(%q) count got %d want %d", tt.in, gotN, tt.n)
			}
			if tt.n > 0 {
				for _, secret := range []string{"4827", "1234", "5521", "8890", "Sunny-Day22", "slunce2024"} {
					if strings.Contains(tt.in, secret) && strings.Contains(got, secret) {
						t.Errorf("output still contains %q", secret)
					}
				}
			}
		})
	}
}

func TestFilterCodesIdempotent(t *testing.T) {
	in := "PIN code 1234"
	first, n1 := FilterCodes(in)
	second, n2 := FilterCodes(first)
	if n1 != 1 || n2 != 0 || second != first {
		t.Errorf("idempotent: first=%q n1=%d second=%q n2=%d", first, n1, second, n2)
	}
}

func TestAsksForCode(t *testing.T) {
	tests := []struct {
		name string
		text string
		want bool
	}{
		{"EN door code", "The door code is 1234", true},
		{"EN wifi password", "WiFi password: xyz", true},
		{"EN PIN gate", "PIN to the gate", true},
		{"EN plain", "This is just some text", false},
		{"EN room number", "The room number is 1234", false},
		{"EN no keywords", "Instructions without access words", false},
		{"CZ heslo", "heslo na wifi", true},
		{"DE zugangscode", "Zugangscode", true},
		{"CZ kod", "Kód od dveří", true},
		{"DE turcode", "Türcode für die Tür", true},
		{"EN hello", "hello world", false},
		{"empty", "", false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := AsksForCode(tt.text); got != tt.want {
				t.Errorf("AsksForCode(%q) = %v, want %v", tt.text, got, tt.want)
			}
		})
	}
	first, _ := FilterCodes("Door code 9999")
	second, n2 := FilterCodes(first)
	if n2 != 0 || second != first {
		t.Errorf("second FilterCodes pass: got %q n=%d", second, n2)
	}
}

func TestFilterCardFields(t *testing.T) {
	card := map[string]any{
		"steps":     "Door code 1234",
		"watch_out": "PIN 9999",
		"kind":      "keys",
		"topic":     "arrival",
	}
	kind, topic := card["kind"], card["topic"]
	got := FilterCardFields(card)
	if got != 2 {
		t.Fatalf("count got %d want 2", got)
	}
	if card["kind"] != kind || card["topic"] != topic {
		t.Errorf("kind/topic changed")
	}
}
