# A2 report

Status: blocked

## Done
- Branch `feat/ubyport-copy-and-logs` created from origin/main (aa6f48fb8, includes PR 1058).
- Anchors checked (steps 1 to 3 inputs). No code or copy changed yet.

## Left
- Steps 1 to 9 (copy in host_i18n.py and host_vi_i18n.py, Go transportLogLine, tests, catalogs, known-issues line).

## Stop reason (brief section 8: an existing test asserts old copy)
- `App/tests/test_flash_next_step.py:226-227` asserts the old `flash.apartments.connection_ok` copy ("Connection works. UbyPort accepted your web-service login." and "Spojení funguje. UbyPort přijal vaše přihlašovací údaje.") in `test_each_confirmation_carries_the_audited_copy`.
- That file is not in brief section 3, and section 3 says no other file may change.
- Decision needed: add `App/tests/test_flash_next_step.py` to section 3 and update those two tuples to the new en/cs copy, or change the plan.

## Anchor drift (not a stop)
- cs `letter_test_ok` is at `App/app/host_i18n.py:2975` (brief said 2955). cs `connection_ok` value is at `:2979` (brief said 2959).
- en `:795`, en `:799`, vi `:908`, `:911` match.
- `go/internal/ubyport/submit.go`: log line at `:275` (brief 243), `batchTransport` at `:251`, call site at `:113` (brief 111).
- `UBYHOST_UBYPORT_ENV` defaults to "mock" in `go/internal/hostweb/layout/layout.go:596` and in Python `App/app/config.py:296`. The endpoint default was not checked yet.
- `ubyportEnv` already exists in package `stayfeemail` (`go/internal/stayfeemail/job.go:80`). Name clash in package `ubyport` not checked yet.

## Tests
- None run. Nothing to test before the stop.

## Owner steps
- None.
