# 1163 report: Cloudflare "we're down" page

Status: review

## 1. Files changed (`git diff --stat 8000926`)

```
 deploy/cloudflare/down-page-worker.js    |  56 ++++++++
 docs/CLOUDFLARE.md                       |   2 +
 docs/DISASTER_RECOVERY.md                |  13 ++
 docs/plans/portable-disaster-recovery.md |   4 +-
 docs/tasks/1163-cloudflare-down-page.md  | 227 +++++++++++++++++++++++++++++++
 5 files changed, 300 insertions(+), 2 deletions(-)
```

The brief file is the orchestrator's commit (listed as "done" in §3). The report file is added in step 5.

## 2. Commands (last lines of output)

1. `node --check deploy/cloudflare/down-page-worker.js`: no output, exit 0.
2. Smoke test (copy at the scratchpad, not /tmp): `503 3600 no-store 1509` and `503 0`.
3. `grep -c '<script' ...`: `0`.
4. `grep -c 'fetch(' ...`: `1`.
5. `grep -oE 'https?://...' ... | sort -u`: `https://ubyport.policie.cz/`.
6. `grep -c 'show-the-were-down-page' docs/CLOUDFLARE.md`: `1`.
7. `python3 scripts/context_lint.py | tail -5`: `next free: task 1164 | migration 0046` then `context lint: OK`. Three WARN lines about other open briefs were printed above that line; they are not from this change.
8. `git diff --stat 8000926`: see §1, only §3 files.

No pytest run: the test-map has no row for this change.

## 3. Acceptance (§7)

- [x] Worker matches step 1; commands 1 to 5 as expected.
- [x] GET returns 503 with the four headers; HEAD returns 503 and an empty body.
- [x] DISASTER_RECOVERY.md: new section before "Rebuild on a new box"; step 4 in "Point Cloudflare at the new box".
- [x] CLOUDFLARE.md pointer line; anchor matches the heading.
- [x] Plan step 5 row and gap 6 line updated.
- [x] `context lint: OK`; only §3 files changed.

## 4. Deviations

- Smoke test copy was written to the session scratchpad instead of `/tmp/dpw.mjs` (session rule on temp files).
- A stray copy of the Worker was made once outside the repo and deleted before the commit. Nothing in the repo was affected.

## 5. Questions

None.

## 6. Owner steps left

1. Review the Czech copy in `deploy/cloudflare/down-page-worker.js` (text between `<main>` and `<hr>`).
2. Nothing to deploy: no server change.
3. Optional before an outage: create the `ubyhost-down` Worker from `deploy/cloudflare/down-page-worker.js` (steps 1 and 2 of the new DISASTER_RECOVERY section), without adding a route.
