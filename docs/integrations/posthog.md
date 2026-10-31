# Integration: PostHog (analytics)

Two uses, both in code:

1. **Server-side capture** from the `posthog` job every 15 min (`App/app/posthog_sync.py`, `App/app/scheduler.py`). Uses stdlib `urllib.request`, `_TIMEOUT=3` (subagent report; re-check `posthog_sync.py:20`).
2. **Browser tag** only on pages listed in `App/app/analytics.py` (`AGENTS.md` rule 2).

- Hosts: `POSTHOG_HOST` default `https://eu.i.posthog.com`; assets `https://eu-assets.i.posthog.com`; app `https://eu.posthog.com` (`App/app/config.py:299-303`).
- Auth: `POSTHOG_PROJECT_API_KEY` (project key, not a secret in the usual sense; still in env, not in repo).
- Official docs: https://posthog.com/tutorials/api-capture-events
- Personal data: `⚠️ UNKNOWN` — confirm which event properties `posthog_sync.py` sends.
- Consent basis: `⚠️ UNKNOWN` — see [gap report](../gap-report.md) Q23.
