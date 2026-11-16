package mail

// A3 (owner 2026-11-16): the host's and the operator's daily mail while
// reportable guests wait and UbyHost cannot send them
// (calendar.RunFilingStalled). Go only (go-first): there is no Python builder.
// The English strings are host_i18n mail.filing_stalled.*.

import (
	"strconv"
	"strings"
)

const (
	strStalledSubject         = "Guests not reported to the police: %(property)s"
	strStalledSubjectOperator = "[Operator] Guests not reported: %(property)s (%(workspace)s)"
	strStalledPreheader       = "UbyHost cannot report %(count)s guests automatically right now."
	strStalledHeading         = "Guests are not reported to the police"
	strStalledIntro           = "%(property)s: %(count)s foreign guests are not reported to the police yet, and UbyHost cannot send them automatically right now."
	strStalledCountLabel      = "Guests not reported"
	strStalledWorkspaceLabel  = "Workspace"
	strStalledCauseLabel      = "Why"
	strStalledCauseSetup      = "The police (UbyPort) settings of this property are not finished. As soon as they are complete, UbyHost sends every waiting guest in one go, also for stays that are already over."
	strStalledCauseAuth       = "UbyPort refused the web-service login. Enter the UBY-WS password again in the property's police settings, then press Save and test connection. UbyHost then sends every waiting guest by itself."
	strStalledCauseManual     = "Automatic sending is off for this property, so UbyHost sends nothing by itself. Send the stays yourself, or switch automatic sending on in the police settings."
	strStalledCauseFailed     = "Sending to UbyPort failed. The alert in UbyHost says what went wrong. UbyHost keeps trying where it can; if this e-mail comes again tomorrow, send the stays by hand."
	strStalledCauseUnknown    = "These guests are past the time UbyHost sends them, and no error explains why. Often a guest form is not complete or the guest's dates lie outside the booking. Open the stays and check what is missing."
	strStalledActionStays     = "Open the stays"
	strStalledActionSetup     = "Finish police setup"
	strStalledFooter          = "You get this e-mail at most once a day per property while guests wait. It contains no guest names."
)

var stalledCauses = map[string]string{
	"setup":  strStalledCauseSetup,
	"auth":   strStalledCauseAuth,
	"manual": strStalledCauseManual,
	"failed": strStalledCauseFailed,
	"":       strStalledCauseUnknown,
}

// BuildFilingStalled builds the host mail (workspace "") or the operator copy
// (workspace set: other subject, one more fact). cause is "setup", "auth",
// "manual", "failed" or ""; anything else reads as "". actionURL is absolute.
func BuildFilingStalled(publicBaseURL, lang, propertyName string, count int, cause, actionURL, workspace string) (Content, error) {
	if normaliseLanguage(lang) != "en" {
		return Content{}, ErrLanguage
	}
	reason, ok := stalledCauses[cause]
	if !ok {
		reason = strStalledCauseUnknown
	}
	n := strconv.Itoa(count)
	subject := sub(strStalledSubject, "%(property)s", propertyName)
	if workspace != "" {
		subject = sub(strStalledSubjectOperator, "%(property)s", propertyName, "%(workspace)s", workspace)
	}
	preheader := sub(strStalledPreheader, "%(count)s", n)
	intro := sub(strStalledIntro, "%(property)s", propertyName, "%(count)s", n)
	action := strStalledActionStays
	if cause == "setup" || cause == "auth" {
		action = strStalledActionSetup
	}
	facts := [][2]string{{strRiskPropertyLabel, propertyName}, {strStalledCountLabel, n}}
	if workspace != "" {
		facts = append(facts, [2]string{strStalledWorkspaceLabel, workspace})
	}
	blocks := []string{
		blockHeading(strStalledHeading),
		blockParagraph(intro, false),
		blockButton(actionURL, action),
		blockLink(actionURL, strLinkFallback),
	}
	for _, f := range facts {
		blocks = append(blocks, blockFact(f[0], f[1]))
	}
	blocks = append(blocks, blockSection(strStalledCauseLabel, reason), blockNote(strRiskManualLabel, strRiskManual))
	lines := []string{intro, ""}
	for _, f := range facts {
		lines = append(lines, f[0]+": "+f[1])
	}
	lines = append(lines,
		"",
		strStalledCauseLabel+": "+reason,
		"",
		strRiskManualLabel+": "+strRiskManual,
		"",
		action+": "+actionURL,
		"",
		"--",
		"UbyHost",
		strStalledFooter,
	)
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    shell(publicBaseURL, propertyName, preheader, blocks, []string{"UbyHost", strStalledFooter}),
	}, nil
}
