# 0037 report: PostHog hardening

Status: review

## 1. Files changed

```
 App/app/posthog_sync.py                      |  46 +++++++++-------
 App/app/templates/_posthog.html              |  59 ++++++++++++--------
 App/tests/test_posthog_snippet_browser.py     | 129 (new)
 App/tests/test_posthog_sync.py               | 117 ++++++++++++++++++++++++++++++++++++++--
 App/tests/test_umami_guard.py                |  19 ++++++-
 docs/ENVIRONMENT.md                           |   5 ++
 docs/privacy/RETENTION.md                    |   1 +
 docs/privacy/ROPA.md                          |   1 +
 8 files changed, 334 insertions(+), 43 deletions(-)
```

## 2. Commands

```bash
cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_posthog_sync.py tests/test_umami_guard.py tests/test_posthog_snippet_browser.py -q
```
```
..................................................                       [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /workspace/App/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
50 passed, 1 warning in 2.72s
```

```bash
cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests -q
```
```
tests/test_ubyport_sample_pdf.py::test_watermark_renders_as_non_white_pixels
  /workspace/App/tests/test_ubyport_sample_pdf.py:152: DeprecationWarning: Image.Image.getdata is deprecated and will be removed in Pillow 14 (2027-10-15). Use get_flattened_data instead.
    grey_pixels = sum(1 for px in crop.getdata() if px < 235)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2986 passed, 2 skipped, 7 warnings in 341.73s (0:05:41)
```

```bash
python3 scripts/context_lint.py
```
```
ERROR docs/tasks/0036-posthog-funnel-page.md: missing section '## 9. Report'
next free: task 0038 | migration 0009
context lint: FAIL
```

```bash
grep -n '"identified" + "_only"' App/app/templates/_posthog.html; grep -c 'posthog_stage = ?' App/app/posthog_sync.py
```
```
grep exit: 1
1
```

## 3. Acceptance (brief §7)

- [x] The browser test passes with `UBYHOST_REQUIRE_BROWSER=1`, 0 skipped.
- [x] `grep -n '"identified" + "_only"' App/app/templates/_posthog.html` prints nothing.
- [x] `grep -c 'posthog_stage = ?' App/app/posthog_sync.py` is 1 and that line is inside the per-stage loop (line 177).
- [x] The four new sync tests pass.
- [x] ROPA and RETENTION rows exist, marked `LAWYER REVIEW`.

## 4. Deviations

- `test_partial_failure_resumes_without_duplicates` compares the resumed event to `expected[2]` from the funnel row (the third truthy stage), not `our_events[2]`, because only successful HTTP captures are stored in `our_events`.
- `context_lint.py` fails on pre-existing `docs/tasks/0036-posthog-funnel-page.md` structure; this brief forbids editing that file.

## 5. Questions

None.

## 6. Owner steps left

From brief §Owner steps (also added to `docs/ENVIRONMENT.md`):

1. In PostHog, open **Settings**, then **Project**, then **IP data capture**. Turn on **Discard client IP data**.
2. In the same project settings, find **Cookieless server hash mode** and turn it on. Without it, the cookieless page views are dropped.
3. Later, and only if you want automatic deletion: decide whether UbyHost may hold a PostHog personal API key. Until then, when you delete a host account, also delete that person in PostHog (**People**, search the e-mail, **Delete person**).
