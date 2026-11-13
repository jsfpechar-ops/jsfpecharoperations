# 1241: Go stay-fee host mails (`BuildStayFeeReport`, `BuildStayFeeBlocked`, `PeriodLabel`), parity-checked against Python in cs, en and vi

Status: todo
Depends on: none | Base commit: a83df54 | Branch: claude/1240-go-stay-fee-mail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add pure Go builders for the two host mails the daily `stay_fee_mail` job queues (`mail_notify.build_stay_fee_report` and `build_stay_fee_blocked`) and `stay_fee_auto.period_label`, byte-identical to Python for every host language (cs, en, vi, and the fallback of any other code to en). This is the mail part of the Go port of `stay_fee_mail` (docs/plans/go-full-move.md section 7); nothing calls the new functions yet (the job is another brief). Files are added only, no existing code changes, so there is no failing-first step.

## 2. Context

Rules (AGENTS.md): 1 filing correctness (not touched, no filing code); 2 privacy: no new personal-data field and no outbound request (the golden uses invented data and `example.test` hosts); 3 no real data in the repo; 4 no new dependency (stdlib and `hostweb`, already in the module); 5 no SQL.

**Where the code goes.** `go/internal/stayfeemail/` (new package `stayfeemail`), new files only. `go/internal/mail/` is owned by another thread (a sibling thread may create `i18n_keys.txt` and `i18n.json` there, which is why this brief does not use that package) and `go/internal/stayfee/` is another writer's package: do not touch either.

**Why not reuse the existing builders' shell and helpers.** The Go `shell` in go/internal/mail/submission_problem.go hardcodes `<html lang="en">` and takes plain-text footer lines; the stay-fee mails need `lang` in the tag and a footer anchor (`_FooterLink`). The new package carries its own `stayFeeShell`, copied from `_shell` (App/app/mail_notify.py 484-542), and `helpers.go` holds copies (comment names the source) of the unexported `esc`, `normaliseLanguage`, `preheaderSpacer`, `blockParagraph`, `button`, `blockButton` and the colour, font and logo constants, plus a local `Content` with the same three fields as `mail.Content` (not imported: the callers of this package are the job, which needs no dependency on the mail package's other builders). The existing builders refuse every language but `en` (`ErrLanguage`); these two do not, because Python's `build_stay_fee_*` use `host_i18n.normalise_language(lang or HOST_MAIL_LANGUAGE)`: cs, en, vi pass, anything else is `en`.

**Strings.** The repo already has a per-package host catalog mechanism: `go/internal/<pkg>/i18n_keys.txt` lists keys and `App/scripts/go_host_i18n.py` (which globs every `*/i18n_keys.txt`, so it needs no edit) writes the sibling `i18n.json` with `{lang: {key: text}}`. The new `go/internal/stayfeemail/i18n_keys.txt` lists the 36 keys these mails read (16 `mail.stay_fee*`, 7 `stay_fees.issue.*`, `stay_fees.quarter`, `month.1` to `month.12`); `i18n.json` is generated, embedded with `go:embed`, and read with `hostweb.Load` and `Catalog.T` (host_i18n.translate with its `lookup()` guard: fallback to en, then to the key itself, raw text on a placeholder mismatch, raw text when no params are given). `hostweb` does not import `stayfeemail` (checked with `go list -deps`), so there is no cycle. Chosen over copying strings into Go constants because three languages times 36 keys would drift, and `go_host_i18n.py --check` already fails CI when the catalog is stale. A key outside `i18n_keys.txt` (an unknown issue key) prints as the key itself; Python does the same for a key that does not exist in host_i18n, but would print the text for a real key missing from the list. The golden covers `stay_fees.issue.not_a_key`; the seven real keys are all in the list (six from `stay_fee.report_issues`: `period_running`, `no_vs`, `no_authority`, `no_payer`, `overlaps_saved`, `scope_ruling`, plus `unsigned` from `stay_fee_auto.check`).

**Behaviour to match** (Python, base a83df54): report subject uses `subject_zero` when `total_czk == 0`, else `subject`; `step_send` when the data box is non-empty, else `step_send_plain`; pay step is `zero` when zero, `step_pay` when there is a QR, else `step_pay_plain`; the QR `<img src="cid:stayfeeqr">` row and the `qr_alt` text line appear only when `has_qr` and not zero; `fix`, then the report URL, then the footer and the "turn off" link `<appBase>/settings/account#settings-stay-fee-emails` (text part: `label: url`; HTML: an anchor in the third footer line). Blocked mail: intro, one paragraph per issue (text: `- item`), `after`, button. `PeriodLabel`: quarterly gives `stay_fees.quarter` with `n=(month-1)//3+1` and the year, anything else gives `<month.N text> <year>`. Callers pass the already built `Amount` (`stay_fee.format_czk`, "12 345 Kč") and `ReportURL` (absolute), as `queue_stay_fee_*` does.

**Parity mechanism** (same as mail_golden.py): `App/scripts/stay_fee_mail_golden.py` sets `UBYHOST_APP_BASE_URL=https://app.example.test` and `UBYHOST_PUBLIC_BASE_URL=https://www.example.test`, runs the real Python and writes `go/internal/stayfeemail/testdata/stay_fee_cases.json`: 144 period labels (6 language codes x monthly/quarterly x 12 months), 54 report cases (9 variants x 6 language codes: monthly/quarterly, with and without QR, with and without data box, zero total, empty authority, HTML special characters in property name, authority, data box, VS and URL, large amount) and 66 blocked cases (none, each of the 7 issues, all, an unknown key, and a special-character property, x 6 language codes). The language codes are `en cs vi de ""` and `CS-cz`, which proves the fallback and the lower-case two-letter cut. `stay_fee_test.go` compares subject, text and HTML byte for byte.

**Verified by the brief writer** on the working tree of a83df54 (files created, tested, then deleted): `gofmt -l internal/stayfeemail` empty, `go vet ./internal/stayfeemail/` clean, `go test ./internal/stayfeemail/ ./internal/mail/` ok (the three new tests; the mail package is unchanged), `cd go && go build ./internal/stayfeemail/` ok, `go_host_i18n.py --check` clean, golden generation deterministic (same sha twice). Generated file hashes: `go/internal/stayfeemail/i18n.json` sha256 `601c489a5995f66758df440c54f5bcb4cc488d18197c9b756b1b3ea480fe4bf7` (116 lines), `go/internal/stayfeemail/testdata/stay_fee_cases.json` sha256 `a062aa1f6592cc608d777472eaee928539db5e93d59b273dfbf9cc5394d7ec43` (3190 lines). They must match exactly; a different hash means the base differs: STOP.

Anchors that must exist verbatim (step 0): in go/internal/mail/submission_problem.go (the source of the copies, read only): `func esc(s string) string {`, `func blockParagraph(text string, muted bool) string {`, `func blockButton(url, label string) string {`; in go/internal/hostweb/i18n.go: `func Load(data []byte) Catalog {` and `func (c Catalog) T(lang, key string, params map[string]any) string {`; in App/app/mail_notify.py: `def build_stay_fee_report(` and `def build_stay_fee_blocked(`; in App/app/stay_fee_auto.py: `def period_label(`; in App/scripts/go_host_i18n.py: `glob("*/i18n_keys.txt")`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/scripts/stay_fee_mail_golden.py` | create | renders the real Python builders, writes the golden JSON |
| `go/internal/stayfeemail/i18n_keys.txt` | create | the keys the new mails read |
| `go/internal/stayfeemail/i18n.json` | create (generated by `go_host_i18n.py`) | cs, en, vi texts of those keys |
| `go/internal/stayfeemail/helpers.go` | create | copies of the small mail helpers and constants, local `Content` |
| `go/internal/stayfeemail/stay_fee_mail.go` | create | `PeriodLabel`, `BuildStayFeeReport`, `BuildStayFeeBlocked`, `StayFeeReport` |
| `go/internal/stayfeemail/stay_fee_test.go` | create | Go vs golden, byte for byte |
| `go/internal/stayfeemail/testdata/stay_fee_cases.json` | create (generated by the golden script) | inputs and Python outputs |
| `docs/tasks/1241-report.md` | create | the report (section 9) |

No other file may change.

## 4. Steps

0. Checks (one call, from the repo root): `git branch --show-current` prints `claude/1240-go-stay-fee-mail`; `ls App/scripts/stay_fee_mail_golden.py go/internal/stayfeemail/helpers.go go/internal/stayfeemail/stay_fee_mail.go go/internal/stayfeemail/stay_fee_test.go go/internal/stayfeemail/i18n.json go/internal/stayfeemail/i18n_keys.txt go/internal/stayfeemail/testdata 2>&1 | tail -30` says "No such file" seven times; `grep -c` each anchor of section 2 prints 1 in its file; `git status --short go/internal | tail` shows no other change. If `App/.venv/bin/python` is missing: `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5`. Anything missing or present: STOP (section 8).

1. Create `App/scripts/stay_fee_mail_golden.py` (sha256 `e0f545bfdbf577cf206140def136697ccd36caa7f00b3ad3038086ce66685946`) with exactly this content:

```python
#!/usr/bin/env python3
"""Write the Python oracle for the Go stay-fee mails (brief 1241).

Dev tool, never run in production. Invented data only; no database, no
network, no .env. From App/:

    .venv/bin/python scripts/stay_fee_mail_golden.py [--out FILE]

It renders mail_notify.build_stay_fee_report, build_stay_fee_blocked and
stay_fee_auto.period_label for every host language and writes the inputs and
the exact outputs to go/internal/stayfeemail/testdata/stay_fee_cases.json, which
go/internal/stayfeemail/stay_fee_test.go compares byte for byte.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR.parent / "go" / "internal" / "stayfeemail" / "testdata" / "stay_fee_cases.json"

APP_BASE = "https://app.example.test"
PUBLIC_BASE = "https://www.example.test"
# config reads these at import time. The origins differ on purpose: the logo
# uses the public one and the links the app one.
os.environ["UBYHOST_APP_BASE_URL"] = APP_BASE
os.environ["UBYHOST_PUBLIC_BASE_URL"] = PUBLIC_BASE
sys.path.insert(0, str(APP_DIR))

from app import mail_notify, stay_fee, stay_fee_auto  # noqa: E402

# "de", "" and "CS-cz" prove the language fallback and normalisation.
LANGS = ["en", "cs", "vi", "de", "", "CS-cz"]
ISSUES = [
    "stay_fees.issue.period_running",
    "stay_fees.issue.no_vs",
    "stay_fees.issue.no_authority",
    "stay_fees.issue.no_payer",
    "stay_fees.issue.overlaps_saved",
    "stay_fees.issue.scope_ruling",
    "stay_fees.issue.unsigned",
]
SPECIAL = "Byt <b>\"U Řeky\"</b> & 'Co' 100%"
URL = APP_BASE + "/stay-fees/7?month=2026-05"


def report_inputs() -> list[dict]:
    base = dict(property_name="Apartmán Louka", amount=stay_fee.format_czk(12345), total_czk=12345,
                authority="Magistrát města Brna", databox="abc123x", account="123456789/0800",
                vs="9001234", has_qr=True, report_url=URL)
    variants = [
        ("monthly_qr_databox", {}, "monthly", 2026, 5),
        ("quarterly_plain_databox", {"has_qr": False}, "quarterly", 2026, 2),
        ("monthly_qr_no_databox", {"databox": ""}, "monthly", 2025, 12),
        ("quarterly_qr_no_databox", {"databox": ""}, "quarterly", 2026, 11),
        ("zero_qr", {"total_czk": 0, "amount": stay_fee.format_czk(0)}, "monthly", 2026, 1),
        ("zero_plain_no_databox", {"total_czk": 0, "amount": stay_fee.format_czk(0), "has_qr": False,
                                   "databox": ""}, "quarterly", 2026, 7),
        ("empty_authority", {"authority": "", "databox": "", "has_qr": False}, "monthly", 2026, 9),
        ("special_chars", {"property_name": SPECIAL, "authority": SPECIAL, "databox": "a&b<c>",
                           "report_url": URL + "&x=\"1\"", "vs": "1<2"}, "monthly", 2026, 3),
        ("large_amount", {"total_czk": 1234567, "amount": stay_fee.format_czk(1234567)}, "monthly", 2026, 4),
    ]
    cases = []
    for lang in LANGS:
        for name, over, cadence, year, month in variants:
            cases.append({"name": f"report_{name}_{lang or 'empty'}", "lang": lang, "cadence": cadence,
                          "year": year, "month": month, **{**base, **over}})
    return cases


def render_report(case: dict) -> dict:
    period = stay_fee_auto.period_label(case["lang"], case["cadence"], date(case["year"], case["month"], 1))
    built = mail_notify.build_stay_fee_report(
        lang=case["lang"], property_name=case["property_name"], period=period, amount=case["amount"],
        total_czk=case["total_czk"], authority=case["authority"], databox=case["databox"],
        account=case["account"], vs=case["vs"], has_qr=case["has_qr"], report_url=case["report_url"],
    )
    return {**case, "period": period, **built}


def blocked_inputs() -> list[dict]:
    sets = [("none", [])] + [(key.rsplit(".", 1)[1], [key]) for key in ISSUES]
    sets += [("all", list(ISSUES)), ("unknown", ["stay_fees.issue.no_vs", "stay_fees.issue.not_a_key"])]
    cases = []
    for lang in LANGS:
        for name, issues in sets:
            cases.append({"name": f"blocked_{name}_{lang or 'empty'}", "lang": lang, "cadence": "monthly",
                          "year": 2026, "month": 5, "property_name": "Apartmán Louka", "issues": issues,
                          "report_url": URL})
        cases.append({"name": f"blocked_special_{lang or 'empty'}", "lang": lang, "cadence": "quarterly",
                      "year": 2026, "month": 8, "property_name": SPECIAL, "issues": list(ISSUES[:2]),
                      "report_url": URL + "&x=\"1\""})
    return cases


def render_blocked(case: dict) -> dict:
    period = stay_fee_auto.period_label(case["lang"], case["cadence"], date(case["year"], case["month"], 1))
    built = mail_notify.build_stay_fee_blocked(
        lang=case["lang"], property_name=case["property_name"], period=period,
        issues=case["issues"], report_url=case["report_url"],
    )
    return {**case, "period": period, **built}


def period_cases() -> list[dict]:
    out = []
    for lang in LANGS:
        for cadence in ("monthly", "quarterly"):
            for month in range(1, 13):
                label = stay_fee_auto.period_label(lang, cadence, date(2026, month, 1))
                out.append({"lang": lang, "cadence": cadence, "year": 2026, "month": month, "label": label})
    return out


def build() -> dict:
    return {
        "app_base": APP_BASE,
        "public_base": PUBLIC_BASE,
        "periods": period_cases(),
        "reports": [render_report(c) for c in report_inputs()],
        "blocked": [render_blocked(c) for c in blocked_inputs()],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    data = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"golden written: {len(data['periods'])} periods, {len(data['reports'])} reports, "
          f"{len(data['blocked'])} blocked -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

2. Create `go/internal/stayfeemail/i18n_keys.txt` (sha256 `0b7fca2e6264a8c591e09cf4075317312027f957daf049d472121c50045ebe6a`) with exactly this content:

```text
# Host strings read by the stay-fee mails (stay_fee_mail.go), one key per line.
mail.stay_fee.subject
mail.stay_fee.subject_zero
mail.stay_fee.intro
mail.stay_fee.step_send
mail.stay_fee.step_send_plain
mail.stay_fee.step_pay
mail.stay_fee.step_pay_plain
mail.stay_fee.zero
mail.stay_fee.qr_alt
mail.stay_fee.fix
mail.stay_fee.open
mail.stay_fee.footer
mail.stay_fee.turn_off
mail.stay_fee_blocked.subject
mail.stay_fee_blocked.intro
mail.stay_fee_blocked.after
stay_fees.issue.period_running
stay_fees.issue.no_vs
stay_fees.issue.no_authority
stay_fees.issue.no_payer
stay_fees.issue.overlaps_saved
stay_fees.issue.scope_ruling
stay_fees.issue.unsigned
stay_fees.quarter
month.1
month.2
month.3
month.4
month.5
month.6
month.7
month.8
month.9
month.10
month.11
month.12
```

3. Create `go/internal/stayfeemail/stay_fee_mail.go` (sha256 `5e55e7232bcdb2c981c81ce70422b73cf55c3c83b1ac067fc73292722010bfae`) with exactly this content:

```go
package stayfeemail

// Port of App/app/mail_notify.py build_stay_fee_report and
// build_stay_fee_blocked (the two host mails of the daily stay_fee_mail job)
// and App/app/stay_fee_auto.py period_label. Unlike the other mails in this
// package they follow the host's language (cs, en, vi; any other code falls
// back to en as host_i18n.normalise_language does), so the strings come from
// the generated catalog i18n.json (keys in i18n_keys.txt, written by
// App/scripts/go_host_i18n.py) read through hostweb.Catalog.T, which is
// host_i18n.translate with its lookup() guard. The shell is rendered here
// because it needs the language in <html lang> and a footer link.
// Golden: App/scripts/stay_fee_mail_golden.py writes testdata/stay_fee_cases.json.

import (
	_ "embed"
	"strconv"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

//go:embed i18n.json
var stayFeeJSON []byte

var stayFeeStrings = hostweb.Load(stayFeeJSON)

const (
	stayFeeQRContentID  = "stayfeeqr" // mail.QR_CONTENT_ID
	stayFeeTurnOffPath  = "/settings/account#settings-stay-fee-emails"
	stayFeeQRImgPadding = `<tr><td style="padding:8px 24px 0 24px;">`
)

// StayFeeReport is the input of BuildStayFeeReport, as queue_stay_fee_report
// computes it. Amount is stay_fee.format_czk(TotalCZK) ("1 234 Kč"), Period is
// PeriodLabel, ReportURL the absolute report link.
type StayFeeReport struct {
	PropertyName string
	Period       string
	Amount       string
	TotalCZK     int
	Authority    string
	Databox      string
	Account      string
	VS           string
	HasQR        bool
	ReportURL    string
}

// stayFeeLang is host_i18n.normalise_language (cs, en, vi).
func stayFeeLang(lang string) string {
	switch code := normaliseLanguage(lang); code {
	case "cs", "vi":
		return code
	}
	return "en"
}

// stayFeeT is mail_notify._text: pairs are name, value, name, value.
func stayFeeT(lang, key string, pairs ...string) string {
	if len(pairs) == 0 {
		return stayFeeStrings.T(lang, key, nil)
	}
	params := make(map[string]any, len(pairs)/2)
	for i := 0; i+1 < len(pairs); i += 2 {
		params[pairs[i]] = pairs[i+1]
	}
	return stayFeeStrings.T(lang, key, params)
}

// PeriodLabel is stay_fee_auto.period_label: "Q2 2026" for a quarterly
// cadence, else "<month name> <year>", in the host's language.
func PeriodLabel(lang, cadence string, year, month int) string {
	lang = stayFeeLang(lang)
	if cadence == "quarterly" {
		return stayFeeStrings.T(lang, "stay_fees.quarter", map[string]any{
			"n": (month-1)/3 + 1, "year": year,
		})
	}
	return stayFeeStrings.T(lang, "month."+strconv.Itoa(month), nil) + " " + strconv.Itoa(year)
}

// stayFeeShell is _shell with the language and the footer given as HTML lines.
func stayFeeShell(publicBaseURL, lang, title, preheader string, blocks, footerHTML []string) string {
	var footer strings.Builder
	for i, line := range footerHTML {
		if i > 0 {
			footer.WriteString(`<div style="padding:4px 0 0 0;">` + line + `</div>`)
		} else {
			footer.WriteString(`<div>` + line + `</div>`)
		}
	}
	preheaderHTML := ""
	if preheader != "" {
		preheaderHTML = `<div style="display:none;font-size:1px;line-height:1px;max-height:0;` +
			`max-width:0;opacity:0;overflow:hidden;mso-hide:all;">` + esc(preheader) + preheaderSpacer + `</div>`
	}
	logoURL := publicBaseURL + logoPath
	width := strconv.Itoa(logoWidth)
	return `<!doctype html>
<html lang="` + esc(lang) + `">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only">
<title>` + esc(title) + `</title>
</head>
<body style="margin:0;padding:0;background:` + colCanvas + `;">
` + preheaderHTML + `
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:` + colCanvas + `;border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:` + colSurface + `;border:1px solid ` + colLine + `;border-radius:14px;border-collapse:separate;">
<tr><td style="padding:28px 24px 0 24px;">
<img src="` + esc(logoURL) + `" width="` + width + `" alt="UbyHost" style="display:block;border:0;outline:none;text-decoration:none;width:` + width + `px;max-width:100%;height:auto;">
</td></tr>
` + strings.Join(blocks, "") + `
<tr><td style="padding:28px 24px 28px 24px;">
<div style="border-top:1px solid ` + colLine + `;padding:16px 0 0 0;font:400 13px/1.6 ` + fontStack + `;color:` + colInkMuted + `;">
` + footer.String() + `
</div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
`
}

// stayFeeFooter is footer_lines=["UbyHost", footer, [_FooterLink(turn_off, url)]].
func stayFeeFooter(footer, turnOff, turnOffURL string) []string {
	return []string{
		esc("UbyHost"),
		esc(footer),
		`<a href="` + esc(turnOffURL) + `" style="color:` + colInkSecondary + `;text-decoration:underline;">` + esc(turnOff) + `</a>`,
	}
}

// BuildStayFeeReport is build_stay_fee_report: the finished report mail (PDF
// attached and QR inline by the sender, not here). appBaseURL carries the
// "turn off" link and publicBaseURL the logo.
func BuildStayFeeReport(appBaseURL, publicBaseURL, lang string, r StayFeeReport) Content {
	lang = stayFeeLang(lang)
	zero := r.TotalCZK == 0
	var subject string
	if zero {
		subject = stayFeeT(lang, "mail.stay_fee.subject_zero", "period", r.Period, "property", r.PropertyName)
	} else {
		subject = stayFeeT(lang, "mail.stay_fee.subject", "period", r.Period, "amount", r.Amount, "property", r.PropertyName)
	}
	intro := stayFeeT(lang, "mail.stay_fee.intro", "period", r.Period, "property", r.PropertyName)
	var stepSend string
	if r.Databox != "" {
		stepSend = stayFeeT(lang, "mail.stay_fee.step_send", "authority", r.Authority, "databox", r.Databox)
	} else {
		stepSend = stayFeeT(lang, "mail.stay_fee.step_send_plain", "authority", r.Authority)
	}
	var stepPay string
	switch {
	case zero:
		stepPay = stayFeeT(lang, "mail.stay_fee.zero")
	case r.HasQR:
		stepPay = stayFeeT(lang, "mail.stay_fee.step_pay", "amount", r.Amount, "account", r.Account, "vs", r.VS)
	default:
		stepPay = stayFeeT(lang, "mail.stay_fee.step_pay_plain", "amount", r.Amount, "vs", r.VS)
	}
	qrAlt := stayFeeT(lang, "mail.stay_fee.qr_alt")
	fix := stayFeeT(lang, "mail.stay_fee.fix")
	openLabel := stayFeeT(lang, "mail.stay_fee.open")
	footer := stayFeeT(lang, "mail.stay_fee.footer")
	turnOff := stayFeeT(lang, "mail.stay_fee.turn_off")
	turnOffURL := appBaseURL + stayFeeTurnOffPath
	showQR := r.HasQR && !zero

	lines := []string{intro, "", stepSend, stepPay}
	if showQR {
		lines = append(lines, qrAlt)
	}
	lines = append(lines, "", fix, r.ReportURL, "", "--", "UbyHost", footer, turnOff+": "+turnOffURL)

	blocks := []string{blockParagraph(intro, false), blockParagraph(stepSend, false), blockParagraph(stepPay, false)}
	if showQR {
		blocks = append(blocks, stayFeeQRImgPadding+
			`<img src="cid:`+stayFeeQRContentID+`" width="200" height="200" alt="`+esc(qrAlt)+`" `+
			`style="display:block;border:0;width:200px;height:200px;"></td></tr>`)
	}
	blocks = append(blocks, blockParagraph(fix, false), blockButton(r.ReportURL, openLabel))
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    stayFeeShell(publicBaseURL, lang, r.PropertyName, intro, blocks, stayFeeFooter(footer, turnOff, turnOffURL)),
	}
}

// BuildStayFeeBlocked is build_stay_fee_blocked: the "what to fix" mail. issues
// are catalog keys (stay_fee.report_issues plus stay_fees.issue.unsigned); a
// key the catalog lacks prints as the key itself, as in Python.
func BuildStayFeeBlocked(appBaseURL, publicBaseURL, lang, propertyName, period string, issues []string, reportURL string) Content {
	lang = stayFeeLang(lang)
	subject := stayFeeT(lang, "mail.stay_fee_blocked.subject", "period", period, "property", propertyName)
	intro := stayFeeT(lang, "mail.stay_fee_blocked.intro", "period", period, "property", propertyName)
	items := make([]string, 0, len(issues))
	for _, key := range issues {
		items = append(items, stayFeeT(lang, key))
	}
	after := stayFeeT(lang, "mail.stay_fee_blocked.after")
	openLabel := stayFeeT(lang, "mail.stay_fee.open")
	footer := stayFeeT(lang, "mail.stay_fee.footer")
	turnOff := stayFeeT(lang, "mail.stay_fee.turn_off")
	turnOffURL := appBaseURL + stayFeeTurnOffPath

	lines := []string{intro, ""}
	for _, item := range items {
		lines = append(lines, "- "+item)
	}
	lines = append(lines, "", after, reportURL, "", "--", "UbyHost", footer, turnOff+": "+turnOffURL)

	blocks := []string{blockParagraph(intro, false)}
	for _, item := range items {
		blocks = append(blocks, blockParagraph(item, false))
	}
	blocks = append(blocks, blockParagraph(after, false), blockButton(reportURL, openLabel))
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    stayFeeShell(publicBaseURL, lang, propertyName, intro, blocks, stayFeeFooter(footer, turnOff, turnOffURL)),
	}
}
```

4. Create `go/internal/stayfeemail/helpers.go` (sha256 `a1bcdbda81ff02aaa3ba4ffcc533154f6465fe98a8c57ef7b213f614cc0c5cd3`) with exactly this content:

```go
package stayfeemail

// Copies of the small helpers of go/internal/mail (submission_problem.go) and
// the constants of App/app/mail_notify.py they use: esc (html.escape), the
// language cut of host_i18n.normalise_language, blockParagraph, button and
// blockButton (_block_paragraph, _button, _block_button), the colours, font
// stack and the preheader spacer. Copied, not imported, because they are
// unexported there and that package is owned by another thread.

import "strings"

// Content is the subject, text part and HTML part of one message (same fields
// as mail.Content).
type Content struct {
	Subject string
	Text    string
	HTML    string
}

const (
	colInk          = "#20201e"
	colInkSecondary = "#50504c"
	colInkMuted     = "#73736e"
	colCanvas       = "#f7f7f5"
	colSurface      = "#ffffff"
	colLine         = "#e4e4e1"
	colBrandAction  = "#ad4942"
	fontStack       = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
	logoPath        = "/static/ubyhost-logo.jpg"
	logoWidth       = 180
)

// preheaderSpacer is PREHEADER_SPACER.
var preheaderSpacer = strings.Repeat("\u2007\ufeff\u034f", 40)

var escaper = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&quot;", "'", "&#x27;")

func esc(s string) string {
	return escaper.Replace(s)
}

// normaliseLanguage cuts to two lower-case characters; empty is "en".
func normaliseLanguage(lang string) string {
	code := []rune(strings.ToLower(lang))
	if len(code) > 2 {
		code = code[:2]
	}
	if len(code) == 0 {
		return "en"
	}
	return string(code)
}

func blockParagraph(text string, muted bool) string {
	colour, size := colInkSecondary, "16"
	if muted {
		colour, size = colInkMuted, "14"
	}
	return `<tr><td style="padding:12px 24px 0 24px;"><p style="margin:0;font:400 ` + size +
		`px/1.6 ` + fontStack + `;color:` + colour + `;">` + esc(text) + `</p></td></tr>`
}

func button(url, label string) string {
	return `<table role="presentation" cellpadding="0" cellspacing="0" border="0" ` +
		`style="border-collapse:separate;margin:0 0 8px 0;">` +
		`<tr><td style="background:` + colBrandAction + `;border-radius:8px;padding:14px 24px;">` +
		`<a href="` + esc(url) + `" style="display:block;padding:0;font:600 16px/20px ` + fontStack +
		`;color:` + colSurface + `;text-decoration:none;">` + esc(label) + `</a>` +
		`</td></tr></table>`
}

func blockButton(url, label string) string {
	return `<tr><td style="padding:8px 24px 0 24px;">` + button(url, label) + `</td></tr>`
}
```

5. Create `go/internal/stayfeemail/stay_fee_test.go` (sha256 `405bcd98fbd86e04f0106af034c247414565252d0a474c3763d4a4ea601c0512`) with exactly this content:

```go
package stayfeemail

import (
	"encoding/json"
	"os"
	"testing"
)

const stayFeeGolden = "testdata/stay_fee_cases.json"

type stayFeeCase struct {
	Name         string   `json:"name"`
	Lang         string   `json:"lang"`
	Cadence      string   `json:"cadence"`
	Year         int      `json:"year"`
	Month        int      `json:"month"`
	Label        string   `json:"label"`
	Period       string   `json:"period"`
	PropertyName string   `json:"property_name"`
	Amount       string   `json:"amount"`
	TotalCZK     int      `json:"total_czk"`
	Authority    string   `json:"authority"`
	Databox      string   `json:"databox"`
	Account      string   `json:"account"`
	VS           string   `json:"vs"`
	HasQR        bool     `json:"has_qr"`
	ReportURL    string   `json:"report_url"`
	Issues       []string `json:"issues"`
	Subject      string   `json:"subject"`
	Text         string   `json:"text"`
	HTML         string   `json:"html"`
}

type stayFeeFile struct {
	AppBase    string        `json:"app_base"`
	PublicBase string        `json:"public_base"`
	Periods    []stayFeeCase `json:"periods"`
	Reports    []stayFeeCase `json:"reports"`
	Blocked    []stayFeeCase `json:"blocked"`
}

func loadStayFee(t *testing.T) stayFeeFile {
	t.Helper()
	raw, err := os.ReadFile(stayFeeGolden)
	if err != nil {
		t.Fatal(err)
	}
	var f stayFeeFile
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatal(err)
	}
	if len(f.Periods) == 0 || len(f.Reports) == 0 || len(f.Blocked) == 0 {
		t.Fatal("empty stay fee golden")
	}
	return f
}

func compareStayFee(t *testing.T, c stayFeeCase, got Content) {
	t.Helper()
	if got.Subject != c.Subject {
		t.Errorf("%s: subject\n got %q\nwant %q", c.Name, got.Subject, c.Subject)
	}
	if got.Text != c.Text {
		t.Errorf("%s: text\n got %q\nwant %q", c.Name, got.Text, c.Text)
	}
	if got.HTML != c.HTML {
		t.Errorf("%s: html differs from Python", c.Name)
	}
}

func TestPeriodLabelMatchesPython(t *testing.T) {
	for _, c := range loadStayFee(t).Periods {
		if got := PeriodLabel(c.Lang, c.Cadence, c.Year, c.Month); got != c.Label {
			t.Errorf("%q %s %d: got %q want %q", c.Lang, c.Cadence, c.Month, got, c.Label)
		}
	}
}

func TestBuildStayFeeReportMatchesPython(t *testing.T) {
	f := loadStayFee(t)
	for _, c := range f.Reports {
		if got := PeriodLabel(c.Lang, c.Cadence, c.Year, c.Month); got != c.Period {
			t.Errorf("%s: period got %q want %q", c.Name, got, c.Period)
		}
		got := BuildStayFeeReport(f.AppBase, f.PublicBase, c.Lang, StayFeeReport{
			PropertyName: c.PropertyName, Period: c.Period, Amount: c.Amount, TotalCZK: c.TotalCZK,
			Authority: c.Authority, Databox: c.Databox, Account: c.Account, VS: c.VS,
			HasQR: c.HasQR, ReportURL: c.ReportURL,
		})
		compareStayFee(t, c, got)
	}
}

func TestBuildStayFeeBlockedMatchesPython(t *testing.T) {
	f := loadStayFee(t)
	for _, c := range f.Blocked {
		got := BuildStayFeeBlocked(f.AppBase, f.PublicBase, c.Lang, c.PropertyName, c.Period, c.Issues, c.ReportURL)
		compareStayFee(t, c, got)
	}
}
```

6. Generate the two data files (do not type them): from the repo root run `App/.venv/bin/python App/scripts/go_host_i18n.py 2>&1 | tail -5` (prints a line ending in `go/internal/stayfeemail/i18n.json`), then `cd App && .venv/bin/python scripts/stay_fee_mail_golden.py 2>&1 | tail -5` (prints `golden written: 144 periods, 54 reports, 66 blocked`). Then `sha256sum go/internal/stayfeemail/i18n.json go/internal/stayfeemail/testdata/stay_fee_cases.json` must print the two hashes of section 2. Any difference: STOP.

7. Run section 6.

## 5. Do not touch

Everything in `go/internal/mail/` (another thread owns the package) and `go/internal/stayfee/` (another writer's), `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/`, all Python under `App/app/` and `App/tests/` (including conftest.py), `App/scripts/go_host_i18n.py`, `docs/context/*`. Rules 1 to 5 of AGENTS.md as in section 2. No `go.mod` change.

## 6. Commands

From the repo root:

- `App/.venv/bin/python App/scripts/go_host_i18n.py --check 2>&1 | tail -5` prints nothing and exits 0.
- `cd go && gofmt -l internal/stayfeemail 2>&1 | tail -5` prints nothing.
- `cd go && go vet ./internal/stayfeemail/ ./internal/mail/ 2>&1 | tail -30` prints nothing.
- `cd go && go test ./internal/stayfeemail/ ./internal/mail/ 2>&1 | tail -30` prints `ok` for both packages.
- `cd go && go build ./internal/stayfeemail/ 2>&1 | tail -10` prints nothing but `go: downloading` lines at most.
- `cd App && .venv/bin/python scripts/stay_fee_mail_golden.py 2>&1 | tail -3 && cd .. && git status --short | tail -20` lists only the files of section 3 (plus the report) and the golden file hash is unchanged (deterministic).

Test-map row: new Go package `stayfeemail`; no Python test file changes, so no pytest run is needed.

## 7. Acceptance

- [ ] `git status --short` lists exactly the files of section 3 (the report included) and nothing else; `git status --short go/internal/mail` prints nothing.
- [ ] `go test ./internal/stayfeemail/ ./internal/mail/` is ok, with the new tests `TestPeriodLabelMatchesPython`, `TestBuildStayFeeReportMatchesPython`, `TestBuildStayFeeBlockedMatchesPython` run (`go test -run StayFee -v ./internal/stayfeemail/ 2>&1 | tail -10` shows PASS for both builders).
- [ ] `go vet` and `gofmt -l` are clean; `go_host_i18n.py --check` exits 0.
- [ ] The two generated files match the hashes of section 2.
- [ ] Exported API unchanged from this brief: `PeriodLabel(lang, cadence string, year, month int) string`, `BuildStayFeeReport(appBaseURL, publicBaseURL, lang string, r StayFeeReport) Content`, `BuildStayFeeBlocked(appBaseURL, publicBaseURL, lang, propertyName, period string, issues []string, reportURL string) Content`.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, or a generated hash differs;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1241-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git status --short`; the files are untracked, so `git diff --stat` shows nothing).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/stayfeemail/stay_fee_mail.go` and `helpers.go`: the shell and helper copies (drift from `_shell`, `_block_*`, `_button`) and the strings lookup (a drift from `_shell` or `lookup()` is a silent mail change); the language fallback (`stayFeeLang`) and the strings lookup.
- `go/internal/stayfeemail/stay_fee_test.go` and the golden script: cases cover every branch of both builders in three languages.
- New package imports `hostweb` (no cycle, `go list -deps`); the copies in `helpers.go` must stay in step with go/internal/mail if its shell ever changes.

## Owner steps

1. None for this brief: the functions are not called until the job brief that follows. Merge when CI is green.
