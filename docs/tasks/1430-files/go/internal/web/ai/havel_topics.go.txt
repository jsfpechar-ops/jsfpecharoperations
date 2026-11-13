package ai

// havel_topics.go: the quick-help layer, the port of the functions of
// App/app/havel_topics.py (the data is in havel_data.go). No model call.

import (
	"sort"
	"strings"
)

// HavelTopicIDs is havel_topics.TOPIC_IDS.
func HavelTopicIDs() []string {
	out := make([]string, len(havelTopics))
	for i, t := range havelTopics {
		out[i] = t.ID
	}
	return out
}

// HavelFindTopic is havel_topics.topic.
func HavelFindTopic(id string) *havelTopic {
	for i := range havelTopics {
		if havelTopics[i].ID == id {
			return &havelTopics[i]
		}
	}
	return nil
}

func havelFindQuestion(topicID, qID string) *havelQuestion {
	t := HavelFindTopic(topicID)
	if t == nil {
		return nil
	}
	for i := range t.Questions {
		if t.Questions[i].ID == qID {
			return &t.Questions[i]
		}
	}
	return nil
}

// HavelOrderedTopics is havel_topics.ordered(nav): the topic first for the
// page, the rest in order.
func HavelOrderedTopics(nav string) []havelTopic {
	out := append([]havelTopic{}, havelTopics...)
	first := havelFirstForNav[nav]
	sort.SliceStable(out, func(i, j int) bool {
		return out[i].ID == first && out[j].ID != first
	})
	return out
}

// HavelReadKeys is havel_topics.read_keys: the guide keys of one question.
func HavelReadKeys(topicID, qID string) []string {
	q := havelFindQuestion(topicID, qID)
	out := []string{}
	if q == nil {
		return out
	}
	for _, k := range q.Keys {
		if strings.HasPrefix(k, "guide.") {
			out = append(out, k)
		}
	}
	return out
}

// HavelAnswer is havel_topics.answer.
type HavelAnswer struct {
	Topic      string
	Question   havelQuestion
	Paragraphs []string
	Page       string
	Support    bool
}

// HavelTopicAnswer returns the paragraphs of one question in the host's
// language, or nil.
func HavelTopicAnswer(lang, topicID, qID string) *HavelAnswer {
	q := havelFindQuestion(topicID, qID)
	if q == nil {
		return nil
	}
	keys := q.Keys
	if q.Short != "" {
		keys = []string{q.Short}
	}
	paragraphs := []string{}
	for _, k := range keys {
		if t := havelCatalog.T(lang, k, nil); t != "" && t != "?" {
			paragraphs = append(paragraphs, t)
		}
	}
	return &HavelAnswer{Topic: topicID, Question: *q, Paragraphs: paragraphs, Page: q.Page, Support: q.Support}
}
