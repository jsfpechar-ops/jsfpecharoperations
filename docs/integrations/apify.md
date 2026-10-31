# Integration: Apify (guest guide import)

- Used by `App/app/guest_guide_import.py` to run actors (`APIFY_API = "https://api.apify.com/v2/acts/"`, line 26).
- Auth: `UBYHOST_APIFY_TOKEN` (Bearer; secret). Run cap `UBYHOST_APIFY_MONTHLY_RUNS` (default 40); actor timeout `UBYHOST_APIFY_TIMEOUT` (default 120 s) (`App/app/config.py:183-185`).
- Usage is tracked per month in `lock_api_usage` with provider `apify` (`App/app/guest_guide_import.py:124`).
- Job: `guide_import` every 1 min (`App/app/scheduler.py`).
- Data sent to Apify: `⚠️ UNKNOWN` — read the actor input builder before answering.
- Official docs: https://docs.apify.com/api/v2/actors-runs-post
