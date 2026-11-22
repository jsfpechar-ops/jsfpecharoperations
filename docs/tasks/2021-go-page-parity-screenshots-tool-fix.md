# 2021: The 1820 screenshot tool works again (Go-vs-Python visual diff)

Status: todo | Depends on: — | Branch: task/2021-screenshot-tool-fix
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens | Tier: C (tooling)

## 1. Objective

`App/scripts/go_page_parity_screenshots.py` — the tool brief **1820** built — cannot run. Two defects, both reproduced 2026-11-22 on `vibe/go-parity-all-d1d44c`:

```
$ cd App && .venv/bin/python scripts/go_page_parity_screenshots.py --name smoke-login --path '/login?lang=en' --out /tmp/shots-smoke --widths 390
ModuleNotFoundError: No module named 'app'

$ cd App && .venv/bin/python -m scripts.go_page_parity_screenshots --name smoke-login --path '/login?lang=en' --out /tmp/shots-smoke --widths 390
TypeError: ensure_go_running() got an unexpected keyword argument 'public_base'
```

1. **Import**: run as `scripts/go_page_parity_screenshots.py` it puts `App/scripts` on `sys.path`, so `from app import db` fails. It only gets further under `-m`.
2. **Signature drift**: it calls `ensure_go_running(public_base="http://127.0.0.1:1")`, which the helper no longer accepts.

Note the sentinel `http://127.0.0.1:1` in both calls: the tool passes a dummy base and then reads the real one from the return value. Whatever the fix, the *server* still has to be reachable at the URL the page requests are made against — do not "fix" it by pinning a real port.

Consequence, and why this brief is first: **there is no Go-vs-Python visual diff in the whole parity series.** The 2016 pass recorded its screenshots as "skipped" for this reason, and the 26-page UX gate of 2026-11-22 could describe findings but not attribute them. Every visual claim in this series is currently unbacked.

## 2. Context

- `App/scripts/go_page_parity_screenshots.py` — the tool. `App/tests/test_go_page_parity_screenshots.py` — its tests.
- `ensure_go_running` lives in the e2e helpers; find the current signature before editing: `grep -rn 'def ensure_go_running' App/ go/ scripts/ | head -5`.
- `scripts/e2e/page_parity_audit.py` starts `ubyhost-web` correctly today (`go build -o /var/tmp/ubyhost-web-parity ./cmd/ubyhost-web`, env dict near the top). Use it as the reference for both the signature and the environment, instead of inventing a third way.
- Output contract must stay: `parity-report.json` + `parity-report.md` in `--out`, verdicts `identical` / `invisible` / `visible`, `--fail-on-visible` exits 1.
- Python may change here under [go-first](docs/context/go-first.md) exception **1** (port plumbing a Go brief needs: parity tests). No filing data is involved, so no Python golden script.

## 3. Files

- `App/scripts/go_page_parity_screenshots.py`
- `App/tests/test_go_page_parity_screenshots.py`
- If `ensure_go_running` must change: the helper module that defines it, and its tests.

## 4. Steps

1. `grep -rn 'def ensure_go_running' App/ go/ scripts/` and read the current signature and return shape.
2. Fix the import so the documented invocation works from `App/` (make the script insert `App/` on `sys.path` itself, or fix the documented invocation and the test together — do not require the caller to export `PYTHONPATH`).
3. Fix the call to match the real signature. Keep the dummy-base-but-return-real-URL behaviour.
4. Prove it end to end on one page that needs no session, then one that does.

## 5. Do not touch

`App/app/`, `go/`, deploy files, Caddy, `UBYHOST_GO_PATHS`, secrets. No new dependency.

## 6. Commands

```bash
cd App && .venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q -x 2>&1 | tail -30

# end to end, seeded DB + the audit env (see page_parity_audit.py ENV)
cd App && .venv/bin/python scripts/go_page_parity_screenshots.py \
  --name smoke-login --path '/login?lang=en' --out /tmp/parity-2021 --widths 390 --fail-on-visible 2>&1 | tail -30
ls /tmp/parity-2021 2>&1 | tail -10 && sed -n '1,20p' /tmp/parity-2021/parity-report.md 2>&1 | tail -20
```

## 7. Acceptance

- Both invocations in §1 run; the `-m` one and the plain one both work.
- One page produces 390/768/1280 PNGs plus `parity-report.json`/`.md` with a verdict per width.
- `--fail-on-visible` exits 1 only when a verdict is `visible`.
- A short run over two real pages (one anon, one host) is pasted in the report with its verdicts.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if the fix would need a change under `App/app/`; if a page cannot be captured and the reason is not the tool.

## 9. Report

`docs/tasks/2021-report.md`, ≤600 tokens: the two command tails, the verdicts, what changed in the signature relationship, deviations.
