# 0313 report (Havel quick-help topics)

Status: blocked
Done: steps 1 to 2. Left: steps 3 to 10.

## Files changed
- App/app/havel_topics.py (new, step 2)

## Commands
- Step 1 (branch check): `grep -n "def _page_context\|x-havel\|_havel_thread.html" App/app/routes/havel.py` printed 4 lines. OK.
- Step 2: `cd App && .venv/bin/python -c "from app import havel_topics as h; print(...)"` printed `5 guest_link 4`. OK.

## Deviations
- Step 3 stopped: the anchor `    "havel.topic.guide": "Đọc thêm trong hướng dẫn",` does not exist in App/app/host_vi_i18n.py. That file has no `havel.*` keys at all (grep count 0). The en and cs inserts were applied, verified, and then reverted, so the tree holds no step 3 change.
- Drift from brief: base.html cache key is `20261025-0312` (not `20261024-0312`). Step 6 will use `20261025-0313`.
- Drift from brief: `havel.py` already uses `host_i18n.lang_from_request(request)` in `_t`. The `_page_context` replacement in step 4b uses `request.state.lang`; it will be replaced with `host_i18n.lang_from_request(request)`.
- Planned for step 5: `havel.page_url` returns `/properties` for a `{id}` page when `property_id` is None, so the topics template will pass `ids[0] if ids else None`.

## Questions
1. Where should the Vietnamese copy for `havel.topic.support_body` go? Vietnamese has no `havel.*` keys in host_vi_i18n.py. Options: add the key to host_i18n.py's vi block, or add a new vi block in host_vi_i18n.py. Or skip vi, so it falls back to en.

## Owner steps left
- Answer question 1, then the executor can resume at step 3.
