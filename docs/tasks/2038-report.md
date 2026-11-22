# 2038 report

## Files changed

- `go/internal/web/ai/guide/templates/guide_index.tmpl` — Leon help tip in `guide_section_open`
- `go/internal/web/ai/guide/templates/guide_card.tmpl` — one primary save submit via `HasNext`
- `go/internal/web/ai/guide_cards.go` — `HasNext` from `nextOpen`
- `go/internal/web/ai/guide_cards_test.go` — `TestGuideCardFormSaveButtons`
- `go/internal/web/ai/guide_index_test.go` — `TestGuideIndexLeonHelpInSectionHeading`

## Commands (last 5 lines)

**gofmt / vet / go test** (`go/`):

```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai	26.554s
```

**layout lint** (`App/`):

```
3 passed, 1 warning in 16.63s
```

**context_lint** (repo root):

```
next free: task 2039 | goose migration 00023 (App/app/migrations/ is frozen)
context lint: OK
```

## Acceptance

- [x] Layout lint: 0 findings, 3 passed, 0 skipped
- [x] Go tests green; gofmt clean
- [x] 390 px screenshots reviewed (copied to `/opt/cursor/artifacts/2038/`)

## 390 px screenshots

- **guide-390.png:** Guest guide index with topic tables; scroll is long on 390 px (Leon block with “Leon (AI) for your guests” and the `?` help control in the section heading is below the first viewport in this full-page capture).
- **guide-card-wifi-390.png:** Wi‑Fi card form with a single red primary **Save and next card** button in the form actions (no second Save).

## Deviations

None.

## Questions

None.