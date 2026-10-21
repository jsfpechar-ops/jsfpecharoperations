# 0207 report: daily stay-fee job

Status: review

## Files changed (this brief)

- `App/app/stay_fee_auto.py`: added `due_month`, `run`, `_run_apartment`; imports `claim`, `demo`, `mail_notify`.
- `App/app/scheduler.py`: `stay_fee_auto` import, `_JOB_LEVELS["stay_fee_mail"]`, `job_intervals()["stay_fee_mail"] = 24*60`, `_job_stay_fee_mail()`, cron job at 07:00 in `start()`.
- `App/tests/test_stay_fee_auto_job.py` (new): 6 tests (due window, clean seal once, switch off, blocked then fixed, hand-saved report).
- `App/tests/test_scheduler.py`: not edited (it passed unchanged).

## Commands

- `.venv/bin/python -m pytest tests/test_stay_fee_auto_job.py tests/test_stay_fee_auto.py tests/test_scheduler.py -q --tb=short -x -rs`
  last lines: `............................ [100%]` / `28 passed, 1 warning in 3.64s` (0 skipped)
- `python3 scripts/context_lint.py`
  last lines: `ERROR docs/context/status.md: ~747 tokens > cap 700` / `ERROR docs/context/decisions.md: ~2307 tokens > cap 2200` / `context lint: FAIL`
  Not from this brief: both files are modified in the working tree by other agents. This brief did not edit them.

## Steps

- [x] 1 due_month (verified: Nov 2 gives Oct 1, Nov 16 gives None, quarterly Oct 2 gives Jul 1)
- [x] 2 run (confirm / blocked / report loop, per-apartment try/except)
- [x] 3 scheduler job
- [x] 4 tests
- [x] Tests pass, lint run (fails on the two token caps above)

## Deviations

- No git commit, as the lead asked (the brief's "NNNN step k" commits were skipped).
- `_JOB_LEVELS` needed a `stay_fee_mail` entry. Without it `_job_failed` would raise KeyError. This is in `scheduler.py`, so it is within scope.
- No `notification.job_name.stay_fee_mail` translation exists. The brief says not to touch i18n files, so a failure alert would show the raw key. Follow-up needed.
- The test checks the report count per owner and does not check that the outbox row carries the filing id.
- Demo skip uses `demo.is_demo_apartment` (the brief's grep hint pointed there).

## Questions

- Should the `stay_fee_mail` job name be added to i18n (host_i18n.py and host_vi_i18n.py) in a separate brief?

## Owner steps left

1. After deploy, check `/admin` Operations shows `stay_fee_mail` with a run time after 07:00 the next morning.
