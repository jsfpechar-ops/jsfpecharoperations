# Combined release — magic link + today's Cursor bug fixes

Status: review

## Scope (one PR)

| Source | Content |
|--------|---------|
| Patches | 0002 account e-mails, 0003 e-mail link login, 0004 passkeys + 2FA prompt |
| Task 0005 | Legal/privacy v1.7 (LAWYER REVIEW paragraphs flagged) |
| PR #283 | Do not rewrite stay dates during in-flight UbyPort send (`icalsync`) |
| PR #289 | Doručenka preview access, impersonation config tests, Litestream env tests |
| `task/0002c` (no PR) | Stay-fee download skeleton, town-office row, police answer codes 112/late filing, reconcile script, download browser check |

**Not included:** PR #284 (workflow/docs only — merge separately).

## Verification

- Targeted pytest (icalsync, police answers, Doručenka access, passkeys, account emails): **99 passed**
- Browser e2e + geometry (`UBYHOST_REQUIRE_BROWSER=1`): **25 passed, 0 skipped**
- **Full** `pytest tests` in one session: **not green** (~85 failed / 171 errors after ~2100 tests; modules pass in isolation). **Do not merge until fixed** or owner accepts risk and runs CI investigation.

## Owner

1. Lawyer review on 0005 LAWYER REVIEW strings.
2. After deploy: fill every login e-mail in `/admin/users` before production cutover.
3. Close #283 and #289 when this PR merges (superseded).
