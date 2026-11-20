# 1629: Go guest guide view (GET /l/{token}/{reservation_id}/guide, /g/{token} and their photos)

Status: todo — ready for executor after briefs 1720–1721 merge (exact-diff pass, 2026-11-20).
Depends on: 1720, 1721, 1726 (guest shell, gate, i18n, Leon; executor runs after those PRs) | Base commit: current tip of the working branch | Branch: task/1629-go-public-guest-guide-view
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1629 step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1629 step'`.

## 1. Objective

Port the four routes of `App/app/routes/guest_guide_view.py`: `stay_guide`, `stay_guide_photo`, `qr_guide` and `qr_guide_photo` to Go, showing exactly the cards, host name and photos the Python page shows for the same token and nothing else from the host's data.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first (QR door: host name only, no phone or e-mail; no privacy link with a stay token); 3 fixtures `@example.test`; 4 no new dependency; 5 PostgreSQL through `pgxpool`; 6 light mode; 11 Go first.

**Python source of truth:** `App/app/routes/guest_guide_view.py`; `guest_guide` / `guide_facts` / `guide_photos` / `guide_token` / `guide_translate`; guest templates `guest/guide.html` via `render_guest`.

**Routes in scope:**

| Method | Path |
|---|---|
| GET | `/l/{token}/{reservation_id}/guide` |
| GET | `/l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}` |
| GET | `/g/{token}` |
| GET | `/g/{token}/photos/{item_id}/{photo_id}` |

**Risk:** Gate checks (link, PIN, claim) on the stay door; no host field beyond the QR door's host name; photos only for cards `for_guest` returns. Rule 2.

**Parity method:** `App/scripts/go_guest_guide_view_golden.py` seeds booked-level cases and route list; `guide_view_test.go` covers `BookedLevel`; browser parity uses `tests/test_guest_guide_view.py` after wave G (brief 1728).

**All implementation code is pre-written.** Sidecars: `docs/tasks/1629-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Checksums:

| sha256 | file | action |
|---|---|---|
| `5010d5b5055b9ae4399dfca06dbf0e999f4339cb3a9170e0a5175fc43a61171d` | `App/scripts/go_guest_guide_view_golden.py` | create |
| `bd48e86d0bc912765a2bbe99d36ead83027aa2f5ee0d28f88202398cd6b98576` | `App/tests/test_go_guest_guide_view_golden.py` | create |
| `c7d62bebd0e978b6f296efdf7453ade8263d1bb5ea5835cda2412b9b19719800` | `go/cmd/ubyhost-web/register_web_guest_guide_view.go` | create |
| `19ade6f258a0136bc5d19423cd8e390147bacbe12a28579ae2fce5077a4c476a` | `go/cmd/ubyhost-web/register_web_guest_guide_view_test.go` | create |
| `c7cff2e65947c959631e6c344140900658ddf45a0305bf294570d60d4fd319aa` | `go/internal/web/guest/guide_gate_stub.go` | create |
| `1de75d1f4497321f86a099aeaf80d4c071eec4ba1d8b522557ac5c8c5762a3ae` | `go/internal/web/guest/guide_page.go` | create |
| `2bbda950ded49517ea76df471b9867acf433a7336379bafc6f3c3e5ebea943be` | `go/internal/web/guest/guide_photo.go` | create |
| `b2b5e960eaefaadc72dd40ab7ea734bc9c9998b41b6bf2a907ed448099a7fd4a` | `go/internal/web/guest/guide_view.go` | create |
| `424351476f651c3b90cc0ba5b449d7a182785b46de0f23fde5e0bb96a06bced4` | `go/internal/web/guest/guide_view_test.go` | create |
| `b565be64db1820c26931777093568fc518329c1ec06c2354548a9841726e8aee` | `go/internal/web/guest/lang.go` | create |
| `c8a4b10f33bd148a63c808ee337789222e6e9897d72f504eae986ad94dc8e0f0` | `go/internal/web/guest/prague_today.go` | create |
| `ef7eaccbce18bc6c4c32a0da82d716989d7207df32ef60a06fd73e8a339ece8d` | `go/internal/web/guest/rate.go` | create |
| `0ffac733993cd9fcc4bb8692f681c0b870c337904eafe0529756cc010be2d4fa` | `go/internal/web/guest/testdata/guest_guide_view_golden.json` | create |
| `0f1f8061e1ea9d1076c141e318fee8e8639636f7b0158f81a605533052470143` | `go/internal/web/guest/types.go` | create |
| `49b9e8912de3a631e71e19b42383c7b240117ecdc26718f81a2002609f83a51c` | `go/internal/web/guest/unavailable.go` | create |

Full manifest: `docs/tasks/1629-files/MANIFEST.sha256`.

**Verified by the brief writer:** sidecars dry-run on current `main` with step 1 copy — `sha256sum -c docs/tasks/1629-files/MANIFEST.sha256` all OK; `gofmt -l` empty on copied paths; `go build ./...` OK after copy; `go test ./internal/web/guest/... -count=1 -run BookedLevel` OK; `pytest tests/test_go_guest_guide_view_golden.py` OK when `App/.venv` exists. Executor must replace `guide_gate_stub.go` with brief 1721 claim gate before cutover.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/guide_view.go` | create | four routes, `BookedLevel`, register helper |
| `go/internal/web/guest/guide_gate_stub.go` | create | stay gate stub until 1721 lands |
| `go/internal/web/guest/guide_page.go` | create | page render and card grouping |
| `go/internal/web/guest/guide_photo.go` | create | JPEG serve and headers |
| `go/internal/web/guest/lang.go` | create | guest language |
| `go/internal/web/guest/rate.go` | create | QR view rate limit |
| `go/internal/web/guest/prague_today.go` | create | booked window |
| `go/internal/web/guest/types.go` | create | row types |
| `go/internal/web/guest/unavailable.go` | create | 404/429 guest page stub until 1720 shell |
| `go/internal/web/guest/guide_view_test.go` | create | `BookedLevel` parity |
| `go/internal/web/guest/testdata/guest_guide_view_golden.json` | create | golden from Python script |
| `go/cmd/ubyhost-web/register_web_guest_guide_view.go` | create | dormant registration |
| `go/cmd/ubyhost-web/register_web_guest_guide_view_test.go` | create | route patterns |
| `App/scripts/go_guest_guide_view_golden.py` | create | golden generator (go-first exception 1) |
| `App/tests/test_go_guest_guide_view_golden.py` | create | golden freshness test |
| `docs/tasks/1629-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1629-report.md` | create | the report (§9) |

No other file may change. Run only after briefs **1720** and **1721** executors finish (shared `go/internal/web/guest/` package).

## 4. Steps

0. Checks (repo root). Anything other than the stated result: STOP (§8). Each line in `docs/tasks/1629-files/ANCHORS.txt` must print `1` before copy; `find docs/tasks/1629-files -name '*.txt' ! -name 'ANCHORS.txt' | wc -l` prints `15`.

1. Copy sidecars (one call, repo root). Never retype or edit them:

   ```bash
   S=docs/tasks/1629-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'ANCHORS.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done && sha256sum -c "$S/MANIFEST.sha256" 2>&1 | tail -20
   ```

   Commit `1629 step 1`.

2. `cd go && gofmt -l internal/web/guest cmd/ubyhost-web/register_web_guest_guide_view.go` empty; `go build ./...` and `go test ./internal/web/guest/... -count=1` pass. Commit `1629 step 2` if gofmt changed anything.

3. From `App/`: `.venv/bin/python scripts/go_guest_guide_view_golden.py --check`; `pytest tests/test_go_guest_guide_view_golden.py -q`. Commit `1629 step 3`.

4. Wire full guest shell from 1720, replace `unavailable.go` stub and `guide_gate_stub.go` with 1721 gate; port `guide_translate.apply`/`fill` or document owner decision to leave `fill` on Python worker.

5. Run §6; write report. Routes stay dormant until wave G (brief 1728).

## 5. Do not touch

`UBYHOST_GO_PATHS` until 1728; anything under `App/app/` except §3; filing code.

## 6. Commands

- `cd go && gofmt -l internal/web/guest | tail -5` empty
- `cd go && go test ./internal/web/guest/... -count=1 2>&1 | tail -30` passes
- `cd App && .venv/bin/python -m pytest tests/test_go_guest_guide_view_golden.py tests/test_guest_guide_view.py -q --tb=short -x 2>&1 | tail -30` passes when executor runs with DB
- `python3 scripts/context_lint.py 2>&1 | tail -10` clean
- Guest pages: 390/768/1280 screenshots per rule 10 after shell merge

## 7. Acceptance

- Headers: `Cache-Control: no-store`, `X-Robots-Tag: noindex, nofollow`, `Referrer-Policy: no-referrer` on HTML; photos `private, max-age=3600`.
- QR rate limit 120 per window; 429 through guest 404.
- `BookedLevel` matches Python golden edges.
- Stay door uses the same gate as the stay page after 1721.
- `git log --oneline --grep='^1629 step'` one commit per step; only §3 paths change.

## 8. Stop and ask

Stop when: anchor missing; golden stale without regen; file outside §3 needed; 1720/1721 not merged.

## 9. Report

`docs/tasks/1629-report.md`: commits, command tails, accepted differences, screenshots, `guide_translate.fill` decision.

## Rollout wave and rollback

- **Rollout:** Dormant until brief 1728 adds `/g/*` and guide paths under `/l/*` to `UBYHOST_GO_PATHS` with the rest of the guest thread.
- **Rollback:** Revert the PR.

## Owner steps

None.

## Risk list (for the reviewer)

Gate checks (link, PIN, claim); no host field beyond QR host name; photo only when card is in `for_guest` list; `guide_translate.fill` outbound model call disclosed in PR when ported.