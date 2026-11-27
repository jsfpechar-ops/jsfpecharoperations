package onboarding

import "testing"

// TestWizardPagesMatchesPython: the police and property step pages (brief 1600).
func TestWizardPagesMatchesPython(t *testing.T) {
	wizardRunGoldenWith2092(t, "testdata/wizard_golden_pages.json")
}
