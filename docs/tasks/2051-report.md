# 2051 report

Status: blocked (steps 1-3 done and committed; steps 4-7 stopped, see Deviations)

## Files changed (committed)

- `go/internal/web/submissions/data.go` (steps 1-2)
- `go/internal/web/submissions/null_rows_test.go` (new, step 3)

## Commands and results

- Step 1 build: `go build ./internal/web/submissions/` exit 0, no output.
- Step 2 build: same, exit 0.
- Step 3: `UBYHOST_TEST_DATABASE_URL=... go test ./internal/web/submissions/...` -> `ok`. `-v -run NullRow` -> `TestLoadListNullRows PASS`, `TestLoadDetailNullRow PASS`.

## Section 7 acceptance

- [x] data.go: COALESCE on mode and guest_ids (list and detail) and record_errors (detail); header_errors left raw.
- [x] NULL-row tests pass; submissions golden test passes (same package run).
- [ ] guide card two Save buttons: not done (step 4 reverted).
- [ ] Leon "?" first in body: not done (step 6 reverted).
- [ ] layout lint browser tests: not run.
- [ ] 390/768/1280 screenshots: none taken.

## Column changes (COALESCE)

- List (`listSQL`): `s.mode` -> `COALESCE(s.mode, '')`, `s.guest_ids` -> `COALESCE(s.guest_ids, '')`.
- Detail (`detailSQL`): `s.mode` -> `COALESCE(s.mode, '')`, `s.guest_ids` -> `COALESCE(s.guest_ids, '')`, `s.record_errors` -> `COALESCE(s.record_errors, '')`.

## Filing-path findings (report only, not changed)

Per brief section 2, not re-verified in this run: `go/internal/ubyport/notify.go:135` and `go/internal/ops/reconcile.go:30-45` scan these columns as `*string`. Reconcile skips rows with NULL guest_ids via `continue`.

## Owner production check

Not run (executor cannot run it). Owner to run:
```
SELECT count(*) FROM submission WHERE mode IS NULL OR guest_ids IS NULL;
SELECT count(*) FROM submission WHERE record_errors IS NULL;
```

## Deviations

1. Step 3 seed also inserts a `legal_entity` row, because the apartment insert needs `legal_entity_id` (copied from `visible_text_test.go`).
2. Step 4 (guide card Save buttons) reverted, not committed. Existing test `TestGuideCardFormSaveButtons` (`go/internal/web/ai/guide_cards_test.go:217`) asserts a single submit button and no `then` on the last card. It fails with the intended change. That file is not in the brief's allowed list.
3. Step 6 (Leon help in body) reverted, not committed. Existing test `TestGuideIndexLeonHelpInSectionHeading` (`go/internal/web/ai/guide_index_test.go:171`) pins the old placement. Not in the allowed list.
4. Step 5 new tests not written (depend on step 4).
5. Step 7 browser lint and parity screenshots not run.

## Questions

Should the two existing tests (`guide_cards_test.go:217`, `guide_index_test.go:171`) be updated to the new behavior, and may the executor touch them? Once answered, steps 4-6 are the brief's exact diffs.

Exact step 4 replacement (guide_card.tmpl line 47):
```
{{ui_button (t "guest_guide.save_next") "primary" (kv "type" "submit" "attrs" (safe `name="then" value="next"`))}}
{{ui_button (t "guest_guide.save") "secondary" (kv "type" "submit")}}
```

Exact step 6 replacement (guide_index.tmpl line 59):
```
{{guide_section_open "leon" (t "guest_guide.leon.title") ""}}
{{help_tip "guide-leon-help" (t "guest_guide.leon.help")}}
```
