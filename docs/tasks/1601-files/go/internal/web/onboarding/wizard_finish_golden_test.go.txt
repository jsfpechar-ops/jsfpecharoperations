package onboarding

import "testing"

// TestWizardFinishMatchesPython: the finish and try-it pages (brief 1601).
func TestWizardFinishMatchesPython(t *testing.T) {
	wizardRunGolden(t, "testdata/wizard_golden_finish.json")
}
