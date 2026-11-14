package onboarding

import "testing"

// TestWizardPostMatchesPython: POST /apartments/{id}/setup (brief 1602).
func TestWizardPostMatchesPython(t *testing.T) {
	wizardRunGolden(t, "testdata/wizard_golden_post.json")
}
