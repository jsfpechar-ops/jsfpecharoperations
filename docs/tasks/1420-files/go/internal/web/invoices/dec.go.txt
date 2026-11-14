package invoices

// Decimal helpers: the money maths of App/app/invoices.py without a decimal
// dependency. math/big.Rat is exact, and roundHalfUp is Python's
// Decimal.to_integral_value(rounding=ROUND_HALF_UP): ties go away from zero.

import (
	"math/big"
	"regexp"
	"strconv"
	"strings"
)

// maxAmount is MAX_AMOUNT: ten million, a bigger figure is a typo.
var maxAmount = big.NewRat(10000000, 1)

// decimalRE is what Python's Decimal(str) accepts for a finite number, in
// ASCII: a sign, digits (single underscores between digits are allowed), a
// point, an exponent.
var decimalRE = regexp.MustCompile(`^([+-]?)((?:[0-9]+(?:_[0-9]+)*)?)(?:\.((?:[0-9]+(?:_[0-9]+)*)?))?(?:[eE]([+-]?[0-9]+))?$`)

// parseDecimal is _parse_decimal: the amount, or ok false when the text is
// not a finite number within maxAmount. Czech "1.000,50" is read as 1000.50.
func parseDecimal(text string) (*big.Rat, bool) {
	cleaned := strings.ReplaceAll(strings.ReplaceAll(text, " ", ""), "\u00a0", "")
	if strings.Contains(cleaned, ",") {
		cleaned = strings.ReplaceAll(strings.ReplaceAll(cleaned, ".", ""), ",", ".")
	}
	// Decimal() trims surrounding whitespace.
	cleaned = strings.TrimSpace(cleaned)
	m := decimalRE.FindStringSubmatch(cleaned)
	if m == nil || (m[2] == "" && m[3] == "") {
		return nil, false
	}
	exp := 0
	if m[4] != "" {
		e, err := strconv.Atoi(m[4])
		if err != nil || e > 400 || e < -400 {
			// Too large to be within maxAmount, unless the mantissa is zero;
			// too small to matter (it rounds to zero haler).
			if err == nil && e < -400 {
				return new(big.Rat), true
			}
			if strings.Trim(m[2]+m[3], "0_") == "" {
				return new(big.Rat), true
			}
			return nil, false
		}
		exp = e
	}
	digits := strings.ReplaceAll(m[2]+m[3], "_", "")
	num, ok := new(big.Int).SetString(digits, 10)
	if !ok {
		return nil, false
	}
	scale := exp - len(strings.ReplaceAll(m[3], "_", ""))
	value := new(big.Rat).SetInt(num)
	pow := new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(abs(scale))), nil)
	if scale >= 0 {
		value.Mul(value, new(big.Rat).SetInt(pow))
	} else {
		value.Quo(value, new(big.Rat).SetInt(pow))
	}
	if m[1] == "-" {
		value.Neg(value)
	}
	if new(big.Rat).Abs(value).Cmp(maxAmount) > 0 {
		return nil, false
	}
	return value, true
}

func abs(n int) int {
	if n < 0 {
		return -n
	}
	return n
}

// toDecimal is _to_decimal: 0 for anything parseDecimal refuses.
func toDecimal(text string) *big.Rat {
	if v, ok := parseDecimal(text); ok {
		return v
	}
	return new(big.Rat)
}

// roundHalfUp is to_integral_value(ROUND_HALF_UP).
func roundHalfUp(r *big.Rat) *big.Int {
	neg := r.Sign() < 0
	a := new(big.Rat).Abs(r)
	a.Add(a, big.NewRat(1, 2))
	q := new(big.Int).Quo(a.Num(), a.Denom())
	if neg {
		q.Neg(q)
	}
	return q
}

// toInt is _to_int: the decimal rounded half up. Text that is not a number
// reads as 0 (the Python default argument is never reached).
func toInt(text string) int64 {
	return roundHalfUp(toDecimal(text)).Int64()
}

// vatRates is VAT_RATES.
var vatRates = [3]int64{0, 12, 21}

// toRate is _to_rate: a listed rate, else 12.
func toRate(text string) int64 {
	v := toInt(text)
	for _, r := range vatRates {
		if v == r {
			return v
		}
	}
	return 12
}

// vatParts is vat_parts: base, VAT and gross in haler, computed up from the
// net unit price.
func vatParts(quantity int64, price *big.Rat, rate int64) (base, vat, gross int64) {
	b := new(big.Rat).Mul(price, big.NewRat(quantity*100, 1))
	base = roundHalfUp(b).Int64()
	v := new(big.Rat).Mul(big.NewRat(base, 1), big.NewRat(rate, 100))
	vat = roundHalfUp(v).Int64()
	return base, vat, base + vat
}

// grossNoVAT is int((price * quantity * 100).to_integral_value(ROUND_HALF_UP)).
func grossNoVAT(quantity int64, price *big.Rat) int64 {
	b := new(big.Rat).Mul(price, big.NewRat(quantity*100, 1))
	return roundHalfUp(b).Int64()
}

// moneyCZK is the money_czk template filter: haler divided by quantity,
// rounded half up to whole haler, "1\u00a0234,50 Kč": no-break spaces group the thousands, an ordinary space precedes Kč.
func moneyCZK(haler int64, quantity int64) string {
	if quantity == 0 {
		quantity = 1
	}
	r := big.NewRat(haler, quantity)
	cents := roundHalfUp(r)
	neg := cents.Sign() < 0
	cents.Abs(cents)
	whole, frac := new(big.Int).QuoRem(cents, big.NewInt(100), new(big.Int))
	s := whole.String()
	var parts []string
	for len(s) > 3 {
		parts = append([]string{s[len(s)-3:]}, parts...)
		s = s[:len(s)-3]
	}
	parts = append([]string{s}, parts...)
	out := strings.Join(parts, "\u00a0") + "," + pad2(frac.Int64()) + " Kč"
	if neg {
		out = "-" + out
	}
	return out
}

func pad2(n int64) string {
	if n < 10 {
		return "0" + strconv.FormatInt(n, 10)
	}
	return strconv.FormatInt(n, 10)
}

func itoa(n int64) string { return strconv.FormatInt(n, 10) }

func ratOf(a, b int64) *big.Rat { return big.NewRat(a, b) }
