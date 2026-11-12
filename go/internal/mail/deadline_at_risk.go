package mail

// Port of App/app/mail_notify.py build_deadline_at_risk and
// build_deadline_digest (the WP23 filing watchdog mails), with the blocks they
// add to the shared ones (_block_fact, _block_link, _block_table). The English
// strings are copied from host_i18n.STRINGS["en"] and the guest catalogue's
// mail_link_fallback. Golden: App/scripts/filing_watchdog_run_golden.py writes
// the rendered parts into go/internal/calendar/testdata/filing_watchdog_run_golden.json.

import (
	"strconv"
	"strings"
)

const (
	strRiskSubject           = "Not reported to the police yet: %(property)s, deadline %(deadline)s"
	strRiskPreheader         = "Guests not filed with UbyPort yet: %(count)s"
	strRiskHeading           = "This stay may miss its police deadline"
	strRiskIntro             = "%(property)s, arrival %(arrival)s: foreign guests of this stay are not reported to the police yet. The deadline is %(deadline)s."
	strRiskPropertyLabel     = "Property"
	strRiskArrivalLabel      = "Arrival"
	strRiskUnfiledLabel      = "Guests not filed yet"
	strRiskDeadlineLabel     = "Deadline"
	strRiskNextLabel         = "What to do next"
	strRiskNextSteps         = "Open the stay, complete what is missing and send it."
	strRiskManualLabel       = "If UbyHost cannot file in time"
	strRiskManual            = "Sign in to the UbyPort web application with your own access, enter the guests by hand and keep the receipt. Then open the stay in UbyHost and choose \"I filed this stay by hand in UbyPort\", so UbyHost never sends it again. The duty to report stays with you as the host."
	strRiskAction            = "Open the stay"
	strRiskFooter            = "You get this e-mail once per stay, when its police deadline is less than 24 hours away or has passed and the stay is still not reported."
	strRiskNoGuestsSubject   = "No guest details yet: %(property)s, police deadline %(deadline)s"
	strRiskNoGuestsPreheader = "UbyHost cannot tell whether this stay must be reported."
	strRiskNoGuestsHeading   = "No guest details for this stay yet"
	strRiskNoGuestsIntro     = "%(property)s, arrival %(arrival)s: no guest details are entered yet, so UbyHost cannot tell whether the stay must be reported to the police. If any guest is not a Czech citizen, the deadline is %(deadline)s."
	strRiskNoGuestsNext      = "Open the stay and enter the guests, or send the guest link again. If all guests are Czech citizens, enter them for the house book; nothing has to be reported."
	strRiskNoGuestsFooter    = "You get this e-mail once per stay, when the guests have arrived, the police deadline is less than 24 hours away or has passed, and no guest details are entered yet."
	strLinkFallback          = "If the button does not work, copy this address into your browser:"

	strDigestSubject        = "Filing watchdog: stays at risk (%(count)s)"
	strDigestSubjectUnknown = "Filing watchdog: stays at risk (%(count)s), without guest details (%(unknown)s)"
	strDigestHeading        = "Stays that may miss the police deadline"
	strDigestIntro          = "Each stay below has foreign guests that UbyPort has not accepted yet, and its deadline is less than 24 hours away or has passed. This digest is sent at most every 3 days while any stay is at risk."
	strDigestColWorkspace   = "Workspace"
	strDigestColProperty    = "Property"
	strDigestColArrival     = "Arrival"
	strDigestColDeadline    = "Deadline"
	strDigestColUnfiled     = "Not filed"
	strDigestMore           = "And %(count)s more stays."
	strDigestFooter         = "Sent to UBYHOST_OPERATOR_EMAIL by the deadline job. It contains no guest names."
	strDigestUnknownHeading = "Stays without guest details (status unknown)"
	strDigestUnknownIntro   = "No guest is entered for these stays. The arrival has passed and the deadline is less than 24 hours away or has passed. If the guests are Czech citizens nothing has to be reported, so these stays do not set the filing heartbeat to failed."

	// DeadlineDigestMaxRows is DEADLINE_DIGEST_MAX_ROWS: the rest are counted.
	DeadlineDigestMaxRows = 50
)

// DigestRow is one stay of the operator digest, already formatted: Arrival is
// DD.MM.YYYY and Deadline is "DD.MM.YYYY HH:MM", as _digest_section prints them.
type DigestRow struct {
	Workspace string
	Property  string
	Arrival   string
	Deadline  string
	Unfiled   int
}

// sub is the "%" pass of host_i18n.lookup for these keys: each %(name)s is
// replaced. None of these templates contains %% or another placeholder.
func sub(tmpl string, pairs ...string) string {
	return strings.NewReplacer(pairs...).Replace(tmpl)
}

// blockFact is _block_fact.
func blockFact(label, value string) string {
	return `<tr><td style="padding:20px 24px 0 24px;"><div style="font:600 14px/1.4 ` + fontStack +
		`;color:` + colInk + `;padding:0 0 6px 0;">` + esc(label) + `</div>` +
		`<div style="font:400 15px/1.5 ` + fontStack + `;color:` + colInk + `;">` + esc(value) + `</div>` +
		`</td></tr>`
}

// blockLink is _block_link: the full address under a button.
func blockLink(url, label string) string {
	return `<tr><td style="padding:14px 24px 0 24px;"><div style="font:400 13px/1.6 ` + fontStack +
		`;color:` + colInkMuted + `;">` + esc(label) + `</div>` +
		`<div style="font:400 13px/1.6 ` + fontStack + `;color:` + colInkSecondary +
		`;word-break:break-all;"><a href="` + esc(url) + `" style="color:` + colBrandAction +
		`;text-decoration:underline;">` + esc(url) + `</a></div></td></tr>`
}

// blockTable is _block_table.
func blockTable(header []string, rows [][]string) string {
	cell := "padding:6px 8px;border-bottom:1px solid " + colLine + ";text-align:left;"
	var head, body strings.Builder
	for _, h := range header {
		head.WriteString(`<th style="` + cell + `font:600 13px/1.4 ` + fontStack + `;color:` + colInk + `;">` + esc(h) + `</th>`)
	}
	for _, row := range rows {
		body.WriteString("<tr>")
		for _, v := range row {
			body.WriteString(`<td style="` + cell + `font:400 13px/1.4 ` + fontStack + `;color:` + colInkSecondary + `;">` + esc(v) + `</td>`)
		}
		body.WriteString("</tr>")
	}
	return `<tr><td style="padding:20px 24px 0 24px;">` +
		`<table role="presentation" width="100%" cellpadding="0" cellspacing="0" ` +
		`border="0" style="border-collapse:collapse;">` +
		`<tr>` + head.String() + `</tr>` + body.String() + `</table></td></tr>`
}

// BuildDeadlineAtRisk is build_deadline_at_risk: the host's one warning that a
// stay may miss its police deadline. arrival is DD.MM.YYYY, deadline is
// "DD.MM.YYYY HH:MM" (_deadline_text), stayURL the absolute stay link.
// publicBaseURL carries the logo. noGuests is the variant for a stay with no
// guest on file, which has no "Guests not filed yet" fact.
func BuildDeadlineAtRisk(publicBaseURL, lang, propertyName, arrival, deadline string, unfiled int, stayURL string, noGuests bool) (Content, error) {
	if normaliseLanguage(lang) != "en" {
		return Content{}, ErrLanguage
	}
	subject, preheader, heading, intro := strRiskSubject, strRiskPreheader, strRiskHeading, strRiskIntro
	nextSteps, footer := strRiskNextSteps, strRiskFooter
	if noGuests {
		subject, preheader, heading, intro = strRiskNoGuestsSubject, strRiskNoGuestsPreheader, strRiskNoGuestsHeading, strRiskNoGuestsIntro
		nextSteps, footer = strRiskNoGuestsNext, strRiskNoGuestsFooter
	}
	count := strconv.Itoa(unfiled)
	subject = sub(subject, "%(property)s", propertyName, "%(deadline)s", deadline)
	preheader = sub(preheader, "%(count)s", count)
	intro = sub(intro, "%(property)s", propertyName, "%(arrival)s", arrival, "%(deadline)s", deadline)
	facts := [][2]string{{strRiskPropertyLabel, propertyName}, {strRiskArrivalLabel, arrival}}
	if !noGuests {
		facts = append(facts, [2]string{strRiskUnfiledLabel, count})
	}
	facts = append(facts, [2]string{strRiskDeadlineLabel, deadline})

	blocks := []string{
		blockHeading(heading),
		blockParagraph(intro, false),
		blockButton(stayURL, strRiskAction),
		blockLink(stayURL, strLinkFallback),
	}
	for _, f := range facts {
		blocks = append(blocks, blockFact(f[0], f[1]))
	}
	blocks = append(blocks, blockSection(strRiskNextLabel, nextSteps), blockNote(strRiskManualLabel, strRiskManual))

	lines := []string{intro, ""}
	for _, f := range facts {
		lines = append(lines, f[0]+": "+f[1])
	}
	lines = append(lines,
		"",
		strRiskNextLabel+": "+nextSteps,
		"",
		strRiskManualLabel+": "+strRiskManual,
		"",
		strRiskAction+": "+stayURL,
		"",
		"--",
		"UbyHost",
		footer,
	)
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    shell(publicBaseURL, propertyName, preheader, blocks, []string{"UbyHost", footer}),
	}, nil
}

// digestSection is _digest_section: header, at most DeadlineDigestMaxRows rows,
// and the "and N more" line ("" when nothing is hidden).
func digestSection(rows []DigestRow, withUnfiled bool) ([]string, [][]string, string) {
	header := []string{strDigestColWorkspace, strDigestColProperty, strDigestColArrival, strDigestColDeadline}
	if withUnfiled {
		header = append(header, strDigestColUnfiled)
	}
	shown := rows
	if len(shown) > DeadlineDigestMaxRows {
		shown = shown[:DeadlineDigestMaxRows]
	}
	var out [][]string
	for _, r := range shown {
		values := []string{r.Workspace, r.Property, r.Arrival, r.Deadline}
		if withUnfiled {
			values = append(values, strconv.Itoa(r.Unfiled))
		}
		out = append(out, values)
	}
	more := ""
	if hidden := len(rows) - len(shown); hidden > 0 {
		more = sub(strDigestMore, "%(count)s", strconv.Itoa(hidden))
	}
	return header, out, more
}

// BuildDeadlineDigest is build_deadline_digest: the operator's digest of every
// stay at risk across all workspaces, without guest names. unknown (stays with
// no guest on file) is a section of its own, without a count column.
func BuildDeadlineDigest(publicBaseURL, lang string, stays, unknown []DigestRow) (Content, error) {
	if normaliseLanguage(lang) != "en" {
		return Content{}, ErrLanguage
	}
	var subject string
	if len(unknown) > 0 {
		subject = sub(strDigestSubjectUnknown, "%(count)s", strconv.Itoa(len(stays)), "%(unknown)s", strconv.Itoa(len(unknown)))
	} else {
		subject = sub(strDigestSubject, "%(count)s", strconv.Itoa(len(stays)))
	}
	blocks := []string{blockHeading(strDigestHeading)}
	var lines []string
	if len(stays) > 0 {
		header, rows, more := digestSection(stays, true)
		blocks = append(blocks, blockParagraph(strDigestIntro, false), blockTable(header, rows))
		if more != "" {
			blocks = append(blocks, blockParagraph(more, true))
		}
		lines = append(lines, strDigestIntro, "", strings.Join(header, " | "))
		for _, r := range rows {
			lines = append(lines, strings.Join(r, " | "))
		}
		if more != "" {
			lines = append(lines, "", more)
		}
	}
	if len(unknown) > 0 {
		header, rows, more := digestSection(unknown, false)
		blocks = append(blocks,
			blockHeading(strDigestUnknownHeading),
			blockParagraph(strDigestUnknownIntro, false),
			blockTable(header, rows))
		if more != "" {
			blocks = append(blocks, blockParagraph(more, true))
		}
		if len(lines) > 0 {
			lines = append(lines, "")
		}
		lines = append(lines, strDigestUnknownHeading, strDigestUnknownIntro, "", strings.Join(header, " | "))
		for _, r := range rows {
			lines = append(lines, strings.Join(r, " | "))
		}
		if more != "" {
			lines = append(lines, "", more)
		}
	}
	lines = append(lines, "", "--", "UbyHost", strDigestFooter)
	preheader := strDigestUnknownIntro
	if len(stays) > 0 {
		preheader = strDigestIntro
	}
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    shell(publicBaseURL, strDigestHeading, preheader, blocks, []string{"UbyHost", strDigestFooter}),
	}, nil
}
