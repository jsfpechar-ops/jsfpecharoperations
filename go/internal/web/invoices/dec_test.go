package invoices

import "testing"

func TestParseDecimal(t *testing.T) {
	for _, c := range []struct {
		in   string
		want string // "" = refused, else value as num/den string
	}{
		{"1500", "1500/1"}, {"1.234,50", "2469/2"}, {"1 234\u00a0567", "1234567/1"}, {"99,5", "199/2"},
		{"1e3", "1000/1"}, {"1_000", "1000/1"}, {"+5", "5/1"}, {"-5", "-5/1"}, {" 7 ", "7/1"}, {".5", "1/2"}, {"5.", "5/1"},
		{"", ""}, {"abc", ""}, {"inf", ""}, {"nan", ""}, {"1e", ""}, {".", ""}, {"1__0", ""},
		{"10000000", "10000000/1"}, {"10000001", ""}, {"1e999", ""}, {"0e999", "0/1"}, {"1e-999", "0/1"},
	} {
		got, ok := parseDecimal(c.in)
		switch {
		case c.want == "" && ok:
			t.Errorf("%q: accepted %v, want refused", c.in, got)
		case c.want != "" && (!ok || got.String() != c.want):
			t.Errorf("%q: got %v %v, want %s", c.in, got, ok, c.want)
		}
	}
}

func TestRounding(t *testing.T) {
	for _, c := range []struct {
		in   string
		want int64
	}{{"0.5", 1}, {"1.5", 2}, {"2.5", 3}, {"-0.5", -1}, {"-2.5", -3}, {"0.49", 0}, {"0.005", 1}} {
		d := toDecimal(c.in)
		if c.in == "0.005" {
			if got := grossNoVAT(1, d); got != c.want {
				t.Errorf("gross %s: got %d want %d", c.in, got, c.want)
			}
			continue
		}
		if got := toInt(c.in); got != c.want {
			t.Errorf("toInt %s: got %d want %d", c.in, got, c.want)
		}
	}
	if toInt("") != 0 || toInt("zz") != 0 {
		t.Error("unparseable text reads as 0")
	}
	if toRate("") != 0 || toRate("21") != 21 || toRate("15") != 12 || toRate("12.4") != 12 {
		t.Error("toRate")
	}
}

func TestVATParts(t *testing.T) {
	// App/app/invoices.py: vat_parts(2, Decimal("1234.5"), 21) == (246900, 51849, 298749)
	base, vat, gross := vatParts(2, toDecimal("1234.5"), 21)
	if base != 246900 || vat != 51849 || gross != 298749 {
		t.Errorf("got %d %d %d", base, vat, gross)
	}
}

func TestMoneyCZK(t *testing.T) {
	for _, c := range []struct {
		haler, qty int64
		want       string
	}{
		{0, 1, "0,00 Kč"}, {150000, 1, "1\u00a0500,00 Kč"}, {123456789, 1, "1\u00a0234\u00a0567,89 Kč"},
		{9950, 1, "99,50 Kč"}, {1000, 3, "3,33 Kč"}, {1001, 2, "5,01 Kč"}, {-150000, 1, "-1\u00a0500,00 Kč"},
		{500, 0, "5,00 Kč"},
	} {
		if got := moneyCZK(c.haler, c.qty); got != c.want {
			t.Errorf("%d/%d: got %q want %q", c.haler, c.qty, got, c.want)
		}
	}
}
