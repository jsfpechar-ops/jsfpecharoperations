# 2056: Go guest fixes: missing keys and remove page, hub host card, Leon gate, Person badge

Status: todo
Depends on: 2055 may add some of the keys in (a) first: skip keys already present | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step). Steps (a) to (d) are independent: if the cap hits, the report says which are left.

## 1. Objective

Four Go guest differences from the 2042 parity run (Option 1: Go equals the Python function and text). Guest registration correctness first. All six guest languages stay: en cs de es fr uk (Python `i18n.LANGUAGES` = Go `i18n.json` languages; the Python default served set is en,cs via `UBYHOST_GUEST_LANGS`, but every catalogue is kept).

## 2. Context (orchestrator verified)

- (a) `go/internal/web/guest/i18n.json` has 278-280 keys per language. A key diff (Python guest-template keys `t('...')` against Go json) found **68 keys missing in every one of the 6 languages** (408 entries); Python has all 68 in all 6 languages (no English fallback needed). Go-only keys: 2 in cs and en (leave). The list (one per language, same list):
```
add_another add_person all_done_body all_done_body_fee all_done_receipt all_done_title assigned_body assigned_last_sent assigned_not_mine assigned_resend assigned_stay_label assigned_title continue_filling door_code_failed door_code_first_use door_code_preparing door_code_sent door_code_times door_code_title edit filed_short form_locked_short leon_error leon_error_reload leon_host_answered leon_host_answered_plain leon_intro leon_label leon_name leon_needs_js leon_other_prompt leon_placeholder leon_queued leon_role leon_see_card leon_send leon_sending leon_sit_emergency_help leon_sit_other leon_tag leon_waiting leon_welcome leon_you not_filled party_confirm passport_photo_bad_type passport_photo_selected passport_photo_too_large_image passport_photo_too_large_pdf people_progress remove_help remove_keep remove_person remove_title remove_yes removed_ok reported_body reported_title saved_body saved_title sign_for_who someone_missing stay_dates still_missing summary_fold_saved summary_title tw_email_more tw_email_short
```
  Not to add: `claim_error_*` (Go has `claimErrorText`, pages.go:151) and `leon_sit_*` dynamic keys (only the two static `leon_sit_emergency_help`, `leon_sit_other` above) belong to Python's Leon partial; add them anyway (cheap), the other dynamic `leon_sit_<x>` keys are out of scope: say so in the report. The raw keys visible on the remove page are `remove_title remove_help remove_yes remove_keep` (Python `App/app/i18n.py` en ~249-252, cs ~1017; `App/app/guest_uk_i18n.py` ~224; de/es/fr in the same `STRINGS` dict).
  Go template for the remove page: `go/internal/web/guest/templates/remove_content.tmpl`; Python: `App/app/templates/guest/remove.html` (12 lines) has a footer link "How your data is handled" (key `privacy_link`) that Go drops.
- (b) `g-hub-claimed` (`/l/{tok}`): `pickStay` (`go/internal/web/guest/pick.go:103`) builds `PickView.Page` by hand (pick.go ~166-172) and never sets `Host`. Python `_shared` sets `host = _host_contact(apartment)` (guest.py:1063). The shared builder `guestAccess.page` (page_shell.go:76-90) does it: `host := hostContact(ctx, g.pool, apt); p.Host = HostContact{Name, Email, Phone}`.
- (c) `guideLive` (`go/internal/web/guest/leon_questions.go:683`) is "at least 1 done card and total > 0"; Python `guest_guide.progress(apt)["live"]` (App/app/guest_guide.py:283-294) is: every MUST_HAVE kind (`checkin wifi heating checkout emergency`) has state done or skipped. Go already has the exact function: `ai.LeonProgressOf(items).Live` (`go/internal/web/ai/leon_facts.go:187`; `guide_page.go:36` uses it) and `guideMustHave` (go/internal/web/ai/guide_data.go:50). Callers of `guideLive`: leon_questions.go lines ~764, 795, 824, 862 (4 call sites; all routes under `/l/{token}/{reservation_id}/guide/leon` and the Leon pages). Python gate: `guest_leon.py:61-65`: `guest_guide.progress(...)["live"]` and `leon.switched_on(apartment)` (leon.py:473: `leon_enabled` and `terms_current` and `ai.owner_on_test_list`). Go `leonSwitched` must be compared with it (grep `func (s \*lqServer) leonSwitched`).
- (d) Python `person_number` (guest.py:2000) is `progress["filled"] + 1 if guest is None else None`: only on the NEW form, and `filled` counts COMPLETE (or filed-by-hand) guests (`reporting.reservation_progress`). Go `form_pages.go:613` sets `PersonNumber: prog.filled + 1` where `filled` is the live guest ROW count (`formPagesProgress`, line 549-562), on every mode including edit. Result: a "Person 3" chip on edit pages and on /new with 2 partial guests. Decision: fix the number to match Python (do not remove the badge): complete-count + 1, and 0 (no chip, no "person_progress" line) when editing a guest.

## 3. Files

| Path | Action |
|---|---|
| `go/internal/web/guest/i18n.json` | add the 68 keys, 6 languages (skip existing) |
| `go/internal/web/guest/templates/remove_content.tmpl` | add footer link |
| `go/internal/web/guest/pick.go` | set `Host` in `PickView.Page` |
| `go/internal/web/guest/leon_questions.go` | `guideLive` |
| `go/internal/web/guest/form_pages.go` | `PersonNumber` (lines ~549-562, 613) |
| `go/internal/web/guest/*_test.go` | one test per fix (new file `guest_fixes_2056_test.go`) |
| `docs/tasks/2056-report.md` | report |

## 4. Steps

(a1) Write a throwaway script in the scratch dir (NOT in the repo), `cd App && .venv/bin/python <script>`: for every language L in `en cs de es fr uk` and every key K in the list: `value = i18n.STRINGS[L][K]` (for `uk`: `guest_uk_i18n.STRINGS.get(K, i18n.STRINGS['uk'][K])`); if K not in `go[L]` set it; write the json back with the file's own formatting (`head -c 200 go/internal/web/guest/i18n.json` first; keep indent and key order; use `ensure_ascii=False`; sort only if the file is sorted). Also copy the same keys into `go/internal/web/guest/i18n_keys.txt` only if that file lists catalogue keys (check `grep -c remove_title`; if the file is a pure allowlist append the keys, else leave). Check: `python3 -c "import json;d=json.load(open('go/internal/web/guest/i18n.json'));print({l:len(d[l]) for l in sorted(d)}); print([k for k in ('remove_title','remove_help','remove_yes','remove_keep') if k not in d['cs']])" 2>&1 | tail -3` expected counts +68 minus keys 2055 already added, and `[]`.
(a2) `grep -n 'privacy\|footer\|g-foot' App/app/templates/guest/remove.html go/internal/web/guest/templates/remove_content.tmpl | head`; copy the Python footer link markup (key `privacy_link`, href = privacy URL of the page, as other Go templates use `.PrivacyURL`) to the same place in the Go template. Anchor: the closing of the main card in `remove_content.tmpl`.
(a3) Test: render the remove page for en and cs (pattern: `form_pages_test.go` remove test; `grep -n 'remove' go/internal/web/guest/form_pages_test.go | head -5`) and assert the body has no literal `remove_title`, contains the Python en/cs title text, and contains the privacy link. Also a unit test that loads `i18n.json` and asserts all 68 keys exist in all 6 languages.
(b) Edit pick.go: add `Host: hostContactPage(...)`: concretely before `view := PickView{` add `host := hostContact(r.Context(), d.pool, apt)` and inside `Page{...}` add `Host: HostContact{Name: host.Name, Email: host.Email, Phone: host.Phone},`. Test: seeded apartment with a legal entity that has contact email and phone -> GET `/l/{token}` body contains the entity name and email and not the `host_details_missing` text (en). `grep -n 'legal_entity' go/internal/web/guest/*_test.go | head -3` for seeding.
(c1) `guideLive`: replace the body with the Python rule using the existing `ai` helper, read the items the way `guide_page.go:20-40` does (`grep -n 'LeonItem\|LeonProgressOf' go/internal/web/guest/guide_page.go`), return `ai.LeonProgressOf(items).Live`. Do not change the signature.
(c2) Compare `leonSwitched` (leon_questions.go) with `leon.switched_on` and with `ai.LeonStore.Offered` (leon_facts.go:89, which adds the billing-paused check Python's `switched_on` does not have): list the difference in the report; change nothing unless `leonSwitched` lacks one of: `leon_enabled`, terms version current, owner on the test list (`ai.HavelAIOn`) .
(c3) Check every other "live" helper: `grep -rn 'Live\b\|guideLive\|guide_live\|GuideLive' go/internal/web/guest/*.go go/internal/web/ai/*.go | grep -v _test | head -20`. The guide pages (`guide_page.go`) already use `LeonProgressOf`; confirm and say so. Any other helper with a looser rule: make it call `LeonProgressOf` too (one line each) and list it in the report.
(c4) Tests: seed a property with guide cards where the five MUST_HAVE kinds are NOT all done/skipped but some cards are done: `stay_leon_history` (GET `/l/{token}/{res}/guide/leon`) returns 404 `{"error":"not_found"}`-shaped like Python (`_gone`); with all five done or skipped and Leon switched on it returns 200. Seed with `guide_item` rows (columns: see `seed` SQL in `leon_questions_db_test.go`).
(d) In `form_pages.go`: `PersonNumber` must be 0 when `guest != nil` (edit mode) and `completeCount + 1` otherwise, where `completeCount` counts live guests for which the Go equivalent of `reporting.guest_is_complete` (or filed by hand) holds: use the same helper form_pages already uses for completeness (`grep -n 'GuestIsComplete\|guestIsComplete' go/internal/web/guest/*.go | head`; if none is usable in form_pages, STOP and ask). Keep `formPagesProgress.filled` itself unchanged for other callers (line 260 uses `remaining`), add a separate count. Template already shows the chip only when `gt .PersonNumber 1` and the progress line only when `and .PersonNumber .ExpectedPeople`: the Python guards are the same, no template change. Test: new form with 2 declared guests and 2 partial guests -> no `g-chip`; with 1 complete + expected 2 -> "Person 2"; edit page -> no `g-chip`.

## 5. Do not touch

`App/app/**`, `stay_claim.go` (2055 owns it), harness scripts, other i18n keys or any copy not listed, other Go packages.

## 6. Commands

```
cd /home/user/jsfpecharoperations/go && go build ./... 2>&1 | tail -30
cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test go test ./internal/web/guest/ -count=1 2>&1 | tail -30
cd /home/user/jsfpecharoperations && source scripts/e2e/parity_env.sh && cd App && PARITY_GROUP=H PARITY_ONLY=g-remove,g-hub-claimed,g-leon-stay,g-form-new,g-form-edit-complete,g-form-edit-partial PARITY_WIDTHS=390,768,1280 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -15
```
Expected: build clean; `ok` with 0 skipped (`-v | grep -c SKIP` is 0 for the new tests); parity rows `identical`/`invisible` for g-remove, g-hub-claimed, g-form-*; g-leon-stay: if seed makes Python 404 and Go 404, identical (the seed may need all MUST_HAVE cards: that is 2057, so a remaining difference caused only by the seed is reported, not fixed here).

## 7. Acceptance

- [ ] 68 keys x 6 languages present; remove page shows no raw key and has the footer link.
- [ ] Hub shows host name and email.
- [ ] `guideLive` equals Python MUST_HAVE rule; all callers listed in the report.
- [ ] Person chip matches Python on new and edit forms.
- [ ] Parity rows above not `visible` except a seed-only g-leon-stay; one 390 px screenshot each of g-remove, g-hub-claimed and g-form-new in the report.

## 8. Stop and ask

An anchor not found; no complete-guest helper in Go; `leonSwitched` differs in a way not listed in (c2); 25 tool calls (commit, report which of a-d are left).

## 9. Report

`docs/tasks/2056-report.md`, 600 tokens at most.
