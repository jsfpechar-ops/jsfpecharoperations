# 0959 report (executor, review pass)

Status: review.

Verdict: review, with the exception below.

## Scope
- Branch codex/0959-guest-draft-language, base 7b0355c.
- `git diff --name-only 7b0355c..HEAD`: the section 3 files, the brief and this report. The stray binary `docs/tasks/screenshots-0402/guide-table-1280.png` is restored by cleanup commit 6313b205. Cause: `App/tests/test_guest_guide_table_browser.py` writes into that folder on every run. The test was not edited.
- Reviewed head before this commit: 89772982. The final `0959 review` SHA is reported by the executor, since a commit cannot record its own SHA.

## Checks (from the step 7 pass, not rerun in this review)
- `pytest tests/test_guest_browser_e2e.py -k 0959` (UBYHOST_REQUIRE_BROWSER=1): 3 passed, 0 skipped.
- `pytest tests/test_guest_*.py`: 571 passed, 0 skipped.
- `pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`: 16 passed, 0 skipped.
- `git diff --check`: clean. `python3 scripts/context_lint.py`: OK.

## Screenshots (inspected, /tmp/ubyhost-b01)
- EN 390, 768, 1280 and CS 768, 1280: all rows present, no horizontal overflow. EN 390 and 768: the birth-date label is clipped under the sticky step bar in the full-page capture.
- CS 390: birth-date row missing (exception below).
- Language menu at 390: six languages, all tappable.

## Accepted exception
- The RUIAN address-suggest GET query (`ruian-suggest?q=...`) carries typed address text.
- Pre-existing on base 7b0355c. Not introduced by B01, out of scope for B01.
- Needs a separate privacy review.
- The birth-date row missing at 390 px Czech is pre-existing and also out of scope.
- Every URL the language switch creates (page URLs, navigation requests, the `/relang` request) carries no entered value.
