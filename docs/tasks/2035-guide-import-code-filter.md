# 2035: Code filter for imported guide text — pure Go function with table tests

Status: todo (runnable now; no dependency, no caller yet)
Depends on: none | Base commit: fill from `git rev-parse --short HEAD` | Branch: task/2035-guide-import-code-filter
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (privacy filter, no UI)

## 1. Objective

Owner decision 2026-11-22 (D4): text imported from a host's public page must not carry access codes into the model or into guide cards. Add one pure function `FilterCodes(text string) (clean string, removed int)` in `go/internal/guideimport/codefilter.go`. It removes anything that looks like an access code, PIN, door, gate or Wi-Fi password and returns only the count of removals, never the values. Brief 2034 calls it twice (before the model sees the page text, and on every model output field). This brief wires nothing.

## 2. Context (verified on main)

- Package `go/internal/guideimport` (Go port of the guide import job). Existing pure helpers live in `merge.go` (`normalise` :92, `listingText` :100, `userTurn` :160, `clean` :292) and `trim.go` (`Trim` :116). The card text fields are `title`, `location`, `steps`, `watch_out` (`Limits`, `kinds.go`). Nothing in the package logs text; keep it that way.
- Go's `regexp` (RE2) has **no lookahead or lookbehind**. Boundary checks (a digit run must not be part of a longer number, a time, a price, a date) are done in Go code on the match indices, not in the regexp.
- No new dependency (rule 4): `regexp`, `strings`, `unicode` only.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/guideimport/codefilter.go` | new | `FilterCodes` and helpers |
| `go/internal/guideimport/codefilter_test.go` | new | table tests of step 3 |

No other file may change.

## 4. Steps

1. Define, case-insensitive (`(?i)`), after folding the text for matching only (lower-case plus removing diacritics with a fixed `strings.NewReplacer` map for á→a é→e ě→e í→i ó→o ú→u ů→u ý→y č→c ď→d ň→n ř→r š→s ť→t ž→z ä→a ö→o ü→u ß→ss; the folded string has the same byte length per rune only if you map rune by rune, so build `folded []rune` and map indices rune-to-rune; the removal is done on the original runes):
   - `kw` (access words): `code`, `kod`, `kody`, `pin`, `door`, `dvere`, `dveri`, `brana`, `brany`, `gate`, `garaz`, `garaze`, `garage`, `tor`, `tur`, `turcode`, `zugangscode`, `zugang`, `eingang`, `wifi`, `wi-fi`, `wlan`, `keypad`, `klavesnice`, `domovni`, `vchod`, `entrance`, `lock`, `zamek`, `schloss`, `box`, `keybox`, `klicovnik`. Match as whole words (`\b` on the folded string; `tor` and `tur` and `box` and `lock` only as whole words).
   - `pw` (password words): `heslo`, `hesla`, `password`, `passwort`, `kennwort`, `passcode`, `psk`.
2. Four rules; every match is a span `[start,end)` of the digits or token only (not the keyword):
   - **A (code after keyword):** a `kw` or `pw` word, then at most 40 characters on the same line that contain no `.`, `!`, `?` (sentence end; a `:` is allowed), then a digit run `\d(?:[ -]?\d){3,7}` (4 to 8 digits, single spaces or hyphens allowed inside). Span = the digit run.
   - **B (code before keyword):** a digit run (same shape) then at most 40 characters (same restriction) then a `kw` or `pw` word. Span = the digit run. Example "1234 is the door code".
   - **C (keypad):** anywhere, no keyword needed: `\*\d{2,8}#`, `\d{3,8}[#*]`, `[#*]\d{3,8}`. Span = the whole match.
   - **D (password token):** a `pw` word, optionally preceded within 30 characters on the line by a `kw` word (so "wifi password: x" works), then a separator `[:=]` or the words `is`, `je`, `ist`, `lautet`, `byl`, then optional quotes and a token `[^\s,;"'()]{4,64}`. Span = the token. A `kw` word alone (without `pw`) never triggers D, so "Wi-Fi network: Casa123" keeps the network name.
3. Digit-run guards (A and B only; a run that fails a guard is not a code): reject when the run is directly adjacent to another digit, `:`, `.`, `/`, `,` followed by a digit, or `+` (a time, date, decimal, phone number with prefix); when it is 4 digits that read as a year 1900-2099 and the keyword is `code` or `kod` and the next word is `compliance`, `of`, `civil`, `zakon`, `zakoník` (skip this one sub-guard if it takes more than 10 lines: then only keep the adjacency guards); when it is followed within 1 character by `kc`, `czk`, `eur`, `€`, `$`, `usd`, `%`, `m2`, `m²`, `km`, `kg`, `min`, `h`, `uhr`, `eur`, or preceded within 1 character by `€`, `$`, `+`. A phone number written `+420 123 456 789` is therefore never removed, and "15:00" never is.
4. `FilterCodes`: collect spans from A to D on the folded runes, sort, merge overlaps, replace each merged span in the original runes with `[left out]`, and return `(clean, len(mergedSpans))`. Idempotent: running it on its own output returns the same string and 0 (so the second pass on model output counts only new codes; the existing `[left out]` text contains no digit). Empty input returns `("", 0)`. A match never spans a newline. Input is capped by the caller; the function itself must be linear (no nested quantifiers on unbounded text; the 40-character windows are bounded).
5. `func FilterCardFields(card map[string]any) int`: applies `FilterCodes` to the string values of `title`, `location`, `steps`, `watch_out` in place and returns the sum of counts. `FilterTrimmed(data Trimmed) (Trimmed, int)` is NOT needed here; 2034 builds it.
6. Table tests (`codefilter_test.go`, `TestFilterCodes`, one table, each row `{name, in, want, n}`; `want` is the exact output). Required rows (add more; every row must pass):
   - EN removed: `The door code is 4827.` → `The door code is [left out].`, 1; `Gate PIN: 1234#` → one removal; `Entrance code 12 34 56` → 1; `1234 is the garage code` → `[left out] is the garage code`, 1; `Press *4411# to open` → 1; `keypad: 9876*` → 1; `Wifi password: Sunny-Day22` → the token removed, 1; `Wi-Fi network: CasaBlanca` → unchanged, 0.
   - CZ removed: `Kód od dveří je 5521.` → 1; `Heslo na wifi: slunce2024` → 1; `PIN k bráně: 8890` → 1; `Garáž: kód 3344` → 1; `Domovní vchod, kód 1357 8` → 1 (spaces inside the run, 5 digits).
   - DE removed: `Türcode: 7788` → 1; `Das WLAN-Passwort lautet Sonne12345` → 1; `Der Zugangscode für das Tor ist 4455` → 1; `Garagencode 5566` → 1 (word `garage` as prefix of `garagencode`: use the prefix rule for `garage`, `tur`, `zugang` only if the match test row demands; if the whole-word rule makes this row fail, change the row to `Garage code 5566` and note it in the report).
   - Kept (0 removals, unchanged): `Check-in from 15:00 to 22:00.`; `The apartment is on floor 3, 65 m2, 1200 CZK per night.`; `Call +420 123 456 789 if you are lost.`; `Built in 1998, renovated 2019.`; `Bus 119 stops at Zlicin`; `Postal code 110 00 Prague`; `Open 7:30-19:00`; `Room 4827` (digits, no keyword); `Poštovní kód: 11000` is a postal code (kept: the word list has no match for `postovni kod`; if rule A removes it, add a pre-guard for `postal|postovni|zip|psc|psč` within 20 characters before the keyword and keep the row).
   - Two codes in one line count 2; two overlapping matches (`PIN code 1234`) count 1; idempotence (`FilterCodes(FilterCodes(x))` second count 0); a 20000-character line with no match finishes (use `testing.AllocsPerRun` not needed; just run it); the output never contains a removed value (assert `!strings.Contains(clean, "4827")` etc. in the removed rows).
   - `FilterCardFields`: a card with codes in `steps` and `watch_out` returns the sum and leaves `kind` and `topic` untouched.
7. Run §6, commit per step.

## 4b. Shared keywords

Export the keyword list as `CodeKeywords` and a helper `AsksForCode(text string) bool` (same CZ/EN/DE table tests) so Leon (2037) reuses it.

## 5. Do not touch

`job.go`, `merge.go`, `trim.go`, the web package, any template, any Python file, `go.mod`.

## 6. Commands

From `go/`: `gofmt -l internal/guideimport/ 2>&1 | tail -5`; `go vet ./internal/guideimport/ 2>&1 | tail -10`
From `go/`: `go test ./internal/guideimport/ -run 'FilterCodes|FilterCardFields' -v 2>&1 | tail -40`
From `go/`: `go test ./internal/guideimport/ 2>&1 | tail -30` (the existing golden tests stay green; DB tests skip without `UBYHOST_TEST_DATABASE_URL`)
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Every row of the table passes; kept rows unchanged with 0.
- [ ] The function returns counts only; no `log`, `slog` or `fmt.Print` in the file (`rg -n 'log\.|slog\.|fmt\.Print' go/internal/guideimport/codefilter.go | tail -5` prints nothing).
- [ ] No new import outside the standard library; `go.mod` unchanged.
- [ ] Existing guideimport tests green.

## 8. Stop and ask

Stop if: a required row cannot pass without breaking a kept row (report both, do not weaken a kept row); you want a lookaround or a new package; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change.

## 9. Report

`docs/tasks/2035-report.md` (≤600 tokens), `Status: review`, one PR. List any row you changed and why.

## Risk list (for the reviewer)

False negatives let a code reach a card (the host still approves every card); false positives remove a harmless number (the host sees the count and can re-add text). Nothing is logged.

## Owner steps

1. None.
