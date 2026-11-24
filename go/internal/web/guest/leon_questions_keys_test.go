package guest

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestLeonQuestionPageKeysAndSections(t *testing.T) {
	raw, err := leonQuestionsFS.ReadFile("templates/leon_questions.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	var cat map[string]map[string]string
	if err := json.Unmarshal(lqI18n, &cat); err != nil {
		t.Fatal(err)
	}
	keys := []string{"guest_question.urgent_banner", "guest_question.shown_to_guest", "guest_question.field.answer", "guest_question.field.answer_help", "guest_question.dismiss_help", "guest_question.dismissed_banner", "guest_question.card.title", "guest_question.card.help", "guest_question.card.button", "guest_question.card.done", "guest_question.card.open", "guest_guide.add.topic", "guest_guide.more.title"}
	for _, topic := range lqTopics {
		keys = append(keys, "guest_guide.topic."+topic)
	}
	if len(lqTopics) != 11 {
		t.Fatalf("topics %d", len(lqTopics))
	}
	for _, lang := range []string{"en", "cs"} {
		for _, k := range keys {
			if cat[lang][k] == "" {
				t.Errorf("%s: missing %s", lang, k)
			}
		}
	}
	s := string(raw)
	for _, want := range []string{`id="question"`, `id="answer"`, `id="card"`, `id="more"`, `"question-topic"`, `"answer"`, `guest_question.urgent_banner`, `guest_question.dismissed_banner`} {
		if !strings.Contains(s, want) {
			t.Errorf("template missing %s", want)
		}
	}
}
