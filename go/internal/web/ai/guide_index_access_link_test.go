package ai

import (
	"strings"
	"testing"
)

func TestGuideIndexAccessLinkEnv(t *testing.T) {
	w := newGuideCardWorld(t)
	off := guideTestDo(t, w.mux, "GET", w.path(""), w.host, nil).Body.String()
	if strings.Contains(off, "/access") {
		t.Fatal("access link shown without UBYHOST_GO_ACCESS_PAGE")
	}
	onMux := guideTestMux(w.pool, map[string]string{"UBYHOST_GO_ACCESS_PAGE": "1"})
	on := guideTestDo(t, onMux, "GET", w.path(""), w.host, nil).Body.String()
	if !strings.Contains(on, "/access") {
		t.Fatal("missing access link when UBYHOST_GO_ACCESS_PAGE=1")
	}
}
