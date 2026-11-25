package mail

import (
	"fmt"
	"strings"
)

// BuildAIBudget is build_ai_budget for HOST_MAIL_LANGUAGE (English).
func BuildAIBudget(publicBaseURL, appBaseURL, operatorEmail, feature, month string, spent, cap float64) Content {
	percent := 100
	if cap > 0 {
		percent = int(spent / cap * 100)
	}
	subject := fmt.Sprintf("AI budget %d%% spent: %s", percent, feature)
	body := fmt.Sprintf("%s has spent $%.2f of its $%.2f budget for %s. At 100%% it switches off until the 1st.", feature, spent, cap, month)
	action := "Open Operations"
	link := strings.TrimRight(appBaseURL, "/") + "/admin/operations"
	footer := authFooter(hostMailLanguage, operatorEmail)
	text := strings.Join(append([]string{body, "", action + ": " + link, "", "--"}, footer...), "\n")
	blocks := []string{blockHeading(subject), blockParagraph(body, false), blockButton(link, action)}
	return Content{Subject: subject, Text: text, HTML: authShell(strings.TrimRight(publicBaseURL, "/"), hostMailLanguage, subject, body, blocks, footer)}
}
