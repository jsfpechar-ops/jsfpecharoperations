package guest

import (
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

func TestBuildFeePanel(t *testing.T) {
	const iban = "CZ6508000000192000145399"
	const cash = "cash default"

	t.Run("group line when all guests have the same nights", func(t *testing.T) {
		fee := &stayfee.CompletionFee{Total: 300, Rate: 50, Lines: [][2]int{{2, 100}, {2, 100}, {2, 100}}}
		p := buildFeePanel(fee, payments.QRDataURI, cash)
		if p == nil || !p.Group || p.Guests != 3 || p.Days != 2 || p.Total != 300 {
			t.Fatalf("group panel = %+v", p)
		}
	})

	t.Run("rate line when nights differ", func(t *testing.T) {
		fee := &stayfee.CompletionFee{Total: 250, Rate: 50, Lines: [][2]int{{2, 100}, {3, 150}}}
		p := buildFeePanel(fee, payments.QRDataURI, cash)
		if p == nil || p.Group || p.Guests != 2 {
			t.Fatalf("rate panel = %+v", p)
		}
	})

	t.Run("iban QR payload is the SPAYD output", func(t *testing.T) {
		spd := stayfee.SPAYD(iban, 100, "123", "Stay fee 123")
		if !strings.HasPrefix(spd, "SPD*1.0*ACC:") {
			t.Fatalf("spayd = %q", spd)
		}
		want, err := payments.QRDataURI(spd)
		if err != nil {
			t.Fatal(err)
		}
		fee := &stayfee.CompletionFee{Total: 100, Rate: 50, Lines: [][2]int{{2, 100}}, VS: "123",
			Ways: []stayfee.CompletionWay{{Key: "iban", Payee: "Payee", Account: iban, SPAYD: spd}}}
		p := buildFeePanel(fee, payments.QRDataURI, cash)
		if p == nil || len(p.Rails) != 1 || !p.Rails[0].HasQR || string(p.Rails[0].QR) != want {
			t.Fatalf("iban rail = %+v", p)
		}
		if p.Payee != "Payee" || p.VS != "123" {
			t.Fatalf("payee/vs = %q/%q", p.Payee, p.VS)
		}
	})

	t.Run("iban without SPAYD has no QR", func(t *testing.T) {
		fee := &stayfee.CompletionFee{Total: 100, Lines: [][2]int{{1, 100}},
			Ways: []stayfee.CompletionWay{{Key: "iban", Account: iban}}}
		p := buildFeePanel(fee, payments.QRDataURI, cash)
		if p == nil || len(p.Rails) != 1 || p.Rails[0].HasQR {
			t.Fatalf("rail = %+v", p)
		}
	})

	t.Run("cash without note uses the default", func(t *testing.T) {
		fee := &stayfee.CompletionFee{Total: 100, Lines: [][2]int{{1, 100}},
			Ways: []stayfee.CompletionWay{{Key: "cash"}}}
		p := buildFeePanel(fee, payments.QRDataURI, cash)
		if p == nil || len(p.Rails) != 1 || p.Rails[0].Note != cash {
			t.Fatalf("cash rail = %+v", p)
		}
	})

	t.Run("nil fee gives nil panel", func(t *testing.T) {
		if p := buildFeePanel(nil, payments.QRDataURI, cash); p != nil {
			t.Fatalf("panel = %+v, want nil", p)
		}
	})

	t.Run("iban groups", func(t *testing.T) {
		if g := ibanGroups("CZ65 0800 0000"); len(g) != 3 || g[0] != "CZ65" {
			t.Fatalf("spaced groups = %v", g)
		}
		if g := ibanGroups(iban); len(g) != 6 || g[5] != "5399" {
			t.Fatalf("plain groups = %v", g)
		}
	})
}
