package ai

import "testing"

func TestLeonCardTitleInPageLanguage(t *testing.T) {
	tests := []struct {
		name string
		card LeonCard
		lang string
		want string
	}{
		{"checkin cs", LeonCard{Kind: "checkin"}, "cs", "Příjezd a ubytování"},
		{"checkin en", LeonCard{Kind: "checkin"}, "en", "Check-in and arrival"},
		{"checkin de reads English", LeonCard{Kind: "checkin"}, "de", "Check-in and arrival"},
		{"custom keeps own title", LeonCard{Kind: "custom", Title: "Garage code"}, "cs", "Garage code"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := LeonCardTitleIn(tt.card, tt.lang); got != tt.want {
				t.Fatalf("LeonCardTitleIn(%q, %q) = %q, want %q", tt.card.Kind, tt.lang, got, tt.want)
			}
		})
	}
}

func TestGuideTopicTitleInPageLanguage(t *testing.T) {
	if got := GuideTopicTitle("arrival", "cs"); got != "Příjezd a cesta" {
		t.Fatalf("cs arrival = %q", got)
	}
	if got := GuideTopicTitle("arrival", "en"); got != "Arrival and getting here" {
		t.Fatalf("en arrival = %q", got)
	}
}
