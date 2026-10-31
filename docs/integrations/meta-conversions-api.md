# Integration: Meta Conversions API

Purpose: server-side sign-up events for advertising attribution.

- Code: `App/app/meta_capi.py` (endpoint built from graph version and dataset id; `TIMEOUT_SECONDS=10`, `MAX_ATTEMPTS=8`, 7-day window — from code review, subagent report 2026-10-31; re-check lines).
- Job: `meta_capi` every 10 min (`App/app/scheduler.py`).
- Env: `UBYHOST_META_DATASET_ID`, `UBYHOST_META_ACCESS_TOKEN` (secret), `UBYHOST_META_TEST_EVENT_CODE`, `UBYHOST_META_GRAPH_VERSION` (default `v26.0`; `App/app/config.py:411-418`). Only `UBYHOST_META_GRAPH_VERSION` is missing from `docs/ENVIRONMENT.md`.
- Official docs: https://developers.facebook.com/docs/marketing-api/conversions-api
- Personal data sent: `⚠️ UNKNOWN` — read `meta_capi.py` payload builder and confirm which fields are hashed.
- Consent basis: `⚠️ UNKNOWN` — see [gap report](../gap-report.md) Q23.
