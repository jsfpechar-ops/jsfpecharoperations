# 0195 report: AI and scraper crawlers (robots.txt, tdmrep, Terms §11)

Status: review

## Files changed

- `App/app/seo.py`: PRIVATE_PREFIXES extended, AI_AND_SCRAPER_AGENTS, TDM_NOTICE, TDMREP_JSON, robots_txt body (steps 1 to 3)
- `App/app/main.py`: `/.well-known/tdmrep.json` route (step 4)
- `App/app/terms_i18n.py`: §11 clause en (step 5) and cs (step 6)
- `App/tests/test_public_seo.py`: three tests (step 7)

Commits: `0195 step 1` (bec287c) to `0195 step 7` (c435127), plus this report.

## Commands

§6 pytest (from App/):
```
Stopped with -q: 90 passed, 1 warning in 4.61s
```
Last 5 lines:
```
  /home/user/jsfpecharoperations/App/.venv/lib/python3.13/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
90 passed, 1 warning in 4.61s
```

§6 context lint (repo root): FAILS, see Deviations.
Last 5 lines:
```
WARN  docs/design/catalog.json is named by open briefs ...
WARN  37 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
ERROR docs/tasks/0195-robots-ai-terms.md: needs a 'Status: <blocked|done|in-progress|replaced|review|todo>' line
next free: task 0196 | migration 0011
context lint: FAIL
```

## §7 done when

- [x] All §6 tests pass (90 passed, 0 skipped).
- [x] `/robots.txt` starts with the notice, then the AI group with `Disallow: /`, then `User-agent: *` (checked by test_robots_refuses_ai_and_scraper_bots_but_not_search_engines).
- [x] `/.well-known/tdmrep.json` returns the JSON (checked by test_tdmrep_reserves_text_and_data_mining).
- [x] Terms §11 has the clause in English and Czech (checked by test_terms_reserve_scraping_and_ai_training_in_both_languages).

## Deviations

- Context lint fails on the brief itself: `docs/tasks/0195-robots-ai-terms.md` has `Status: ready`, which the lint does not accept. The brief was not edited (executor rule: change nothing the brief does not name). Owner or orchestrator should set a valid status line, for example `Status: review`.
- Steps 5 and 6 were edited together, then split into two commits by writing the en-only file, committing, and restoring the full file. Final content is the brief's content.
- No template, CSS or JS changed, so no screenshots were taken.
- No push, no PR.

## Questions

None.

## Owner steps left

1. Fix the Status line in the brief (or let the orchestrator do it), then rerun `python3 scripts/context_lint.py`.
2. Review the Terms §11 wording with the lawyer (legal v1.7 is still pending review; `TERMS_VERSION` stays 1.7).
3. Push the branch and open the PR (orchestrator).
