# 0034 report

Status: review

## 1. Files changed

```
 docs/tasks/0034-posthog-copy.md
 App/app/privacy_policy_i18n.py
 App/app/templates/privacy.html
 App/app/subprocessors_i18n.py
 App/app/routes/legal.py
 App/app/cookie_inventory.py
 App/app/landing_i18n.py
 docs/ENVIRONMENT.md
 App/tests/test_privacy_legal_positions.py
 App/tests/test_umami_guard.py (PostHog copy assertions)
```

## 2. Commands

- `.venv/bin/python -m pytest tests/test_umami_guard.py tests/test_privacy_legal_positions.py tests/test_privacy_first.py -q` → `53 passed`
- `python3 scripts/context_lint.py` → FAIL on task brief headings (briefs copied from plan §5, not `docs/tasks/TEMPLATE.md` §1–9).

## 3. Acceptance

- [x] No `umami` under `App/`.
- [x] Privacy shows website + product paragraphs and opt-out.
- [x] Subprocessors list PostHog, Inc.
- [x] Screenshots: `docs/tasks/0034-screenshots/` for `/privacy` and `/subprocessors` (en/cs, 360/390/1280).

## 4. Deviations

- Context lint expects numbered sections in `docs/tasks/0033–0036-*.md`; owner/orchestrator may normalize or waive for plan-copied briefs.

## 5. Questions

None.

## 6. Owner steps left

Set `POSTHOG_PROJECT_API_KEY` in production `.env` only after merge and plan §6 (PostHog project + EU hosts).
