# 2058: Go guest guide parity: card titles in the page language, topic headings, Leon block, QR host name, tests

Status: todo
Depends on: 2057 merged | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step)
Next: 2059 (harness, seed, reruns) runs AFTER this brief is merged. Do not touch scripts/.

## 1. Objective

The 2057 parity run showed the Go guest guide differs from Python (cs, all widths, g-guide-apt and g-guide-stay): Go prints English card titles, no topic headings, no Leon chat block, and on the QR page (`/g/{token}`) no property name in the header and no host name in the host card. Port Python's behaviour to Go and add Go tests. Also add the two tests 2056 left open.

## 2. Context (Python is the reference)

- Titles: `App/app/routes/guest_guide_view.py` `_copy_lang` (line 66: `cs` if lang is cs, else `en`), `_cards` (title = card title for kind `custom`, else `host_i18n.translate(_copy_lang(lang), "guest_guide.kind.<kind>.title")`), `_groups` (one group per topic in `guest_guide.TOPICS` order, title `guest_guide.topic.<topic>`, only topics that have cards).
- Leon gate, `_page` line ~108: `leon_url` only when the guide is live AND `ai.enabled(leon.FEATURE)` AND `leon.switched_on(apartment)`; else empty. `leon_host` = first name of the host (`leon.host_first_name`). Markup: `App/app/templates/guest/_leon.html` (44 lines), included at the end of `guest/guide.html` when `leon_url` is set.
- Go today: `go/internal/web/ai/leon_core.go:244` `LeonCardTitle` always uses `"en"`. `go/internal/web/guest/guide_page.go:97-122` `groupCards` returns one group with no title (comment says topic is not carried). `go/internal/web/guest/templates/guide.tmpl` has no Leon block (`{{if .Title}}` kicker already exists at line ~34). `guide_view.go:86` `qrGuide` passes `leonURL ""`; line 126 stay passes `base+"/guide/leon"` unconditionally. `guide_page.go:17` resolves the apartment with `ResolveKey(..., displayLink(qrToken))`; on the QR door the token is the GUIDE token, not the permalink token, so `aptRow` is nil: no property name, no host name (Python `qr_guide` keeps the host name only).
- Catalogs: card kind titles (en, cs) are in `go/internal/web/ai/leon_i18n.json` (`leonStrings`, `hostweb.Load`); topic titles `guest_guide.topic.<topic>` (en, cs) are in `go/internal/web/ai/guide/i18n.json` (`guideCatalog`, `ai/guide_common.go:37`). `LeonItem` already has `Topic` (`ai/leon_facts.go:113`), `LeonCard` (leon_core.go:226) has not.
- Leon JS needs `data-` attributes only; `guest/templates/base.tmpl:77` already loads `guest-leon.js` when `.LeonURL` is set. The Go guest catalog already holds all `leon_*` keys used by `_leon.html` (test `TestI18nFixes2056KeysInAllLanguages`, guest_fixes_2056_test.go:15).
- Leon switch: `ai.LeonStore{HavelStore: ai.HavelStore{Pool: pool, Env: lookupEnv}}.SwitchedOn(ctx, ai.LeonApartment{...})` (see `leonSwitched`, `guest/leon_chat.go:108`, and `leonApartment` line 94 for building `ai.LeonApartment`). Feature switch: `anthropic.ConfigFromEnv(lookupEnv).Enabled("leon")` (see `ai/guide_index.go:154`). Host first name: `ai/leon_core.go:198` `leonHostFirstName` (unexported).

## 3. Files

| Path | Action |
|---|---|
| `go/internal/web/ai/leon_core.go` | add `Topic` to `LeonCard`; add exported `LeonCardTitleIn`, `GuideTopicTitle`, `LeonHostFirstName` |
| `go/internal/web/ai/leon_try.go` | set `Topic: it.Topic` in the `LeonCard{...}` literal (line ~63) |
| `go/internal/web/guest/guide_page.go` | titles by language, topic groups, Leon gate, apartment by id |
| `go/internal/web/guest/guide_view.go` | pass the Leon URL on the QR door (`base` = `"/g/"+token`) |
| `go/internal/web/guest/templates/guide.tmpl` | Leon block |
| `go/internal/web/guest/guide_page_test.go` | new |
| `go/internal/web/ai/leon_titles_test.go` | new |
| `go/internal/web/guest/guest_fixes_2056_test.go` | append the two open tests |
| `docs/tasks/2058-report.md` | report |

## 4. Steps

1. Exports in `ai/leon_core.go`. `grep -nF 'func LeonCardTitle(c LeonCard) string {' go/internal/web/ai/leon_core.go` (once). Add field `Topic string` to `LeonCard` (after `Kind, Title, Location, Steps string` line: new line `Topic string`). Keep `LeonCardTitle` (used by the Leon prompt, English on purpose). Add below it:
```go
// copyLang is guest_guide_view._copy_lang: card and topic titles are host copy in cs and en; other guest languages read English.
func copyLang(lang string) string {
	if lang == "cs" {
		return "cs"
	}
	return "en"
}

// LeonCardTitleIn is the card title in the page language (guest_guide_view._cards).
func LeonCardTitleIn(c LeonCard, lang string) string {
	if c.Kind == "custom" {
		return leonClean(c.Title)
	}
	return leonStrings.T(copyLang(lang), "guest_guide.kind."+c.Kind+".title", nil)
}

// GuideTopicTitle is host_i18n guest_guide.topic.<topic> in the page language (guest_guide_view._groups).
func GuideTopicTitle(topic, lang string) string {
	return guideCatalog.T(copyLang(lang), "guest_guide.topic."+topic, nil)
}

// LeonHostFirstName is leon.host_first_name.
func LeonHostFirstName(name string) string { return leonHostFirstName(name) }
```
   Check that `LeonCardTitle` for `custom` in Python uses the raw title: Python `item["title"]`; the Go existing function cleans `<>`; keep as is. In `ai/leon_try.go` change `card := LeonCard{ID: it.ID, Kind: it.Kind, Title: it.Title,` to also set `Topic: it.Topic,`. Also add `guideTopics` order access: `grep -n 'guideTopicIndex' go/internal/web/ai/guide_data.go` exists (line 84); add `func GuideTopicIndex(topic string) int { return guideTopicIndex(topic) }` and `func GuideTopics() []string { return append([]string(nil), guideTopics...) }` in the same new block. Check: `cd go && go build ./internal/web/ai/ 2>&1 | tail -30`. Commit `2058 step 1`.
2. `guest/guide_page.go`. (a) `groupCards(cards, level, token)` becomes `groupCards(cards []ai.LeonCard, lang string) []guideGroup`. Replace the loop so each card keeps its view with `Title: ai.LeonCardTitleIn(c, lang)` and is bucketed by `c.Topic`; then build groups in `ai.GuideTopics()` order, `Title: ai.GuideTopicTitle(topic, lang)`, only topics with cards (Python `_groups`). A card whose topic is not in the list is dropped, exactly as Python. Remove the stale "topic kicker ... left out" comment. Update the one caller (`view.Groups = groupCards(cards, level, token)` -> `groupCards(cards, lang)`; `grep -nF 'groupCards(' go/internal/web/guest/*.go` to find every caller, tests included, and update them). (b) Apartment for the page: replace the `ResolveKey(... displayLink(qrToken))` block with `if row, ok := loadApartmentByID(r.Context(), h.pool, apt.ID); ok { aptRow = row }` (works for both doors; `displayLink` stays if used elsewhere, else delete it and its comment). (c) Leon gate. Add to `guidePageView` the field `LeonHost string`. Add a private helper `guideLeonOn(ctx, aptID int64) bool` on `*GuideHandlers` that returns true only when `anthropic.ConfigFromEnv(env).Enabled("leon")` AND `ai.LeonStore{HavelStore: ai.HavelStore{Pool: h.pool, Env: env}}.SwitchedOn(ctx, la)` are true, with `la` built exactly as `leonApartment` does (`go/internal/web/guest/leon_chat.go:94-107`: read it, copy its `SELECT`) and `env` the lookup-func type `lqServer.lookupEnv` has (`func(string) (string, bool)`; wrap `h.getenv` if its type differs). Any error returns false (Python hides the chat). After `live := ...` do: `if !live || !h.guideLeonOn(r.Context(), apt.ID) { leonURL = "" }`. Set `view.LeonURL = leonURL` and `view.LeonHost = ai.LeonHostFirstName(page.Host.Name)`. Imports: add `anthropic` (`github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic`) as needed. Check: `cd go && go build ./internal/web/guest/ 2>&1 | tail -30`. Commit `2058 step 2`.
3. `guest/guide_view.go` line 86: change the last argument `""` to `"/g/"+token+"/leon"` (Python `qr_guide`: `leon_url=f"/g/{token}/leon"`). `grep -nF 'h.renderGuidePage(w, r, lang, apt, nil, "everyone", "qr", token, "", "")' go/internal/web/guest/guide_view.go` first. The stay call (line 126) stays; the gate in step 2 now hides it when Leon is off. Commit `2058 step 3`.
4. `guest/templates/guide.tmpl`. Immediately before the last two `{{end}}` lines (after the `{{range .Groups}}...{{end}}` block closes, still inside the `{{else}}` of `NotReady`) add `{{if .LeonURL}}{{template "leon" .}}{{end}}` and define the block `leon` at the end of the file, copied 1:1 from `App/app/templates/guest/_leon.html` (read it in two ranges of 25 lines). Translation rules: `{{ leon_url }}` -> `{{.LeonURL}}`; `t('x')` -> `{{.T "x"}}`; `csrf_token` -> `{{.CSRFToken}}`; `{{ t('leon_host_answered', host=leon_host) if leon_host else t('leon_host_answered_plain') }}` -> `{{if .LeonHost}}{{.T "leon_host_answered" "host" .LeonHost}}{{else}}{{.T "leon_host_answered_plain"}}{{end}}`; the `{% for key, kinds in [...] %}` list -> `{{range $s := .LeonSituations}}` is NOT needed: write the five `<li>` out literally from the Python list (read the exact pairs from `_leon.html` line ~28 and the `emergency` `data-help` rule). The svg and class names are copied byte for byte. Check that `guestAccess.render` exposes `.CSRFToken` on `guidePageView` (`grep -n 'CSRFToken' go/internal/web/guest/page_shell.go go/internal/web/guest/pages.go | head`); if the field is missing, STOP and ask. Check: `cd go && go build ./internal/web/guest/ 2>&1 | tail -30`. Commit `2058 step 4`.
5. Tests (new files; copy the DB test pattern of `TestGuideLiveFixes2056NeedsAllMustHaveKinds`, `guest_fixes_2056_test.go:137`, including `testPoolOptional`). `ai/leon_titles_test.go`: table test `LeonCardTitleIn` (kind `checkin`: cs -> `Příjezd a ubytování`, en -> `Check-in and arrival`, de -> English; kind `custom` -> the card title) and `GuideTopicTitle("arrival", "cs")` -> `Příjezd a cesta`, `"en"` -> `Arrival and getting here`. `guest/guide_page_test.go`: (a) `groupCards` pure test: cards of topics checkin(arrival), wifi, checkout in shuffled input come out grouped in `ai.GuideTopics()` order with cs topic titles and cs card titles; a topic without cards gives no group; (b) DB test: an apartment with a guide token and the five MUST_HAVE cards done (copy the `add(...)` helper; kinds checkin, wifi, heating, checkout, emergency), GET `/g/<guidetoken>?lang=cs` through the same mux the other guide tests use (`grep -n 'qrGuide\|RegisterGuide' go/internal/web/guest/*_test.go | head`): body contains `Příjezd a ubytování` and `data-guide-topic`, does NOT contain `Check-in and arrival`; the header shows the property name; the host card shows the host name. With Leon switched off (default test env, no key) the body has no `id="leon"`. Add a second case with env `UBYHOST_ANTHROPIC_API_KEY`-style switch that `anthropic.ConfigFromEnv(...).Enabled("leon")` reads (read `ai/guide_index.go:154` and the helper it uses for the exact env names) and the apartment Leon switch set the way `SwitchedOn` reads it (`ai/leon_reply.go:57`): body contains `id="leon"` and `data-leon-url="/g/<guidetoken>/leon"`. If the switch cannot be set up in 3 tool calls, keep only the Leon-off assertion and say so in the report. Commit `2058 step 5`.
6. The two open 2056 tests, appended to `guest/guest_fixes_2056_test.go` (same helpers): (a) `TestStayLeonHistoryFixes2056NeedsLiveGuide`: with the apartment from the existing guide test, GET the stay Leon history route (`grep -n 'leon' go/internal/web/guest/leon_chat.go go/internal/web/guest/leon_questions.go | grep -n 'Handle\|GET' | head` finds it; Python `stay_leon_history`, guest_leon.py:62) answers 404 when only 3 must-have cards are done and 200 (JSON with `messages`) when all five are done and Leon is switched on; (b) `TestPersonNumberChip2056NewVsEdit`: the guest form `/l/<tok>/<res>/new` contains the person-number chip text and the edit form of an existing guest does not (read the chip class from `go/internal/web/guest/templates/form_content.tmpl` with `grep -n 'person' ...` and the 2056 test above for the assertion style). Both use `testPoolOptional` like their neighbours. Commit `2058 step 6`.
7. Run (from `go/`): `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/web/guest/... ./internal/web/ai/... 2>&1 | tail -30`. Then `go vet ./internal/web/guest/ ./internal/web/ai/ 2>&1 | tail -30`. Then `python3 scripts/context_lint.py 2>&1 | tail -3` from the repo root. Check no new skip: add `-v 2>&1 | grep -c SKIP` before and after is NOT needed; instead run the changed tests with `-run 'Guide|Leon|2056' -v 2>&1 | grep -c 'SKIP'` and report the number (must be 0).
8. Write `docs/tasks/2058-report.md` (600 tokens). Set `Status: review`. Open one PR (draft).

## 5. Do not touch

`App/**`, `scripts/**`, other Go packages, `guide_gate_stub.go`, the Leon prompt (`LeonCardTitle` stays English), `base.tmpl`, CSS and JS (no CSS or JS change: the Python markup is copied so existing guest CSS applies; if a class is missing from Go's CSS bundle, STOP and ask).

## 6. Commands

Steps 1 to 7 only. Never `go test ./...` and never the Python suite.

## 7. Acceptance

- [ ] cs guide shows Czech card titles and topic headings; en shows English; de shows English (Python `_copy_lang`).
- [ ] QR page shows the property name and the host name only (no e-mail, no phone).
- [ ] Leon block appears only when guide live AND feature on AND switched on; Leon-off page has no `id="leon"`.
- [ ] New tests green, 0 skipped among them; both 2056 tests present.
- [ ] `context_lint` OK.

## 8. Stop and ask

Anchor not found; `LeonItem.Topic` empty for built-in kinds (then bucket by `guideKindTopicOf(kind)` for non-custom kinds and tell the owner); `CSRFToken` or a CSS class missing; the Leon switch cannot be derived; 25 tool calls (commit, report what is left).

## 9. Report

`docs/tasks/2058-report.md`, 600 tokens at most. Trailers on every commit:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf
```

## 10. Orchestrator decision (after run 2)

`go/internal/web/ai/leon_try_test.go:274` compares Leon cards with Python fixtures and now fails because step 1 added `LeonCard.Topic`. Do NOT edit that test or its fixtures. The card output Leon and its parity fixtures see must stay identical to Python: keep `Topic` out of every serialized or compared form of `LeonCard` (e.g. `json:"-"` if the comparison or the AI payload goes through JSON; otherwise carry the topic in a separate grouping structure used only by the guest guide page). Verify: `go test ./internal/web/ai/... -count=1` passes with the test unchanged. Then continue with steps 4-7.
