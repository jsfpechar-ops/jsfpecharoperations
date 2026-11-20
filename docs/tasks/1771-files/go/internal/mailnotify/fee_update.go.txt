package mailnotify

import (
	"strings"
)

// FeeUpdateInput is build_fee_update's keyword arguments. The JSON tags are the
// golden file's keys (testdata/fee_update_golden.json).
type FeeUpdateInput struct {
	Lang         string `json:"lang"`
	PropertyName string `json:"property_name"`
	Dates        string `json:"dates"`
	Host         *Host  `json:"host"`
	OldTotal     int    `json:"old_total"`
	NewTotal     int    `json:"new_total"`
	VS           string `json:"vs"`
}

// BuildFeeUpdate is build_fee_update (brief 1078): the stay-fee total changed
// after the completion mail. It states the amounts and the variable symbol
// only. The pay details stay in the earlier mail, so there is no added image,
// QR or pay link, and no line says the fee was paid. The variable symbol is
// repeated only when the total went up. publicBaseURL is the logo's origin.
func BuildFeeUpdate(publicBaseURL string, in FeeUpdateInput) Content {
	lang := in.Lang
	oldText := GuestText(lang, "fee_amount", Args{"amount": in.OldTotal})
	newText := GuestText(lang, "fee_amount", Args{"amount": in.NewTotal})
	subject := GuestText(lang, "mail_fee_update_subject", Args{
		"property": in.PropertyName, "total": newText,
	})
	heading := GuestText(lang, "mail_fee_update_heading", nil)
	body := GuestText(lang, "mail_fee_update_body", Args{
		"property": in.PropertyName, "dates": in.Dates, "old": oldText, "new": newText,
	})
	footerLines := GuestFooterLines(lang, in.PropertyName, in.Host)

	blocks := []string{BlockHeading(heading), BlockParagraph(body, false)}
	textLines := []string{body}
	up := in.NewTotal > in.OldTotal
	if in.VS != "" && up {
		vsLine := GuestText(lang, "mail_fee_update_vs", Args{"vs": in.VS})
		blocks = append(blocks, BlockParagraph(vsLine, false))
		textLines = append(textLines, vsLine)
	}
	var difference string
	if up {
		difference = GuestText(lang, "mail_fee_update_more", Args{
			"diff": GuestText(lang, "fee_amount", Args{"amount": in.NewTotal - in.OldTotal}),
		})
	} else {
		difference = GuestText(lang, "mail_fee_update_less", nil)
	}
	blocks = append(blocks, BlockParagraph(difference, false))
	textLines = append(textLines, "", difference)

	lines := append(textLines, "", "--")
	lines = append(lines, FooterText(footerLines)...)
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML: Shell(ShellParams{
			PublicBaseURL: publicBaseURL,
			Lang:          in.Lang,
			Title:         in.PropertyName,
			Preheader:     heading,
			Blocks:        blocks,
			FooterLines:   footerLines,
		}),
	}
}
