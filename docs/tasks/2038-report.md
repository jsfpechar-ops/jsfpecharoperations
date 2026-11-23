# 2038 report: Go property setup round-trip

**Status: blocked** · **Staging SHA tested:** `ffd8c17bc8193e6379fc7d6efda8f0dddd7bd51c` (`/healthz` 200, DB ok)

## Checks

| Check | Result | Notes |
|---|---|---|
| SHA / #1276+#1277 on candidate | **PASS** | Staging version matches deploy; `ffd8c17` is on `main` after merges for #1276 and #1277 |
| `TestGuestPayValuesRails` | **PASS** | 3 subtests green |
| `TestStayFeeGuestPaySwitchOff` | **PASS** | Switch-off leaves column count unchanged |
| `TestApartmentUpdateWizardSteps` | **BLOCKED** | Skipped: `UBYHOST_TEST_DATABASE_URL` not set in executor VM |
| Signup enabled | **PASS** | `/signup` 200, localized “Create your UbyHost account” (EN screenshots) |
| Login email-only | **PASS** | `/login` 200; no `type="password"` field |
| Add property / wizard | **BLOCKED** | `UBYHOST_STAGING_NO_LOGIN` off: `/apartments`, `/apartments/new` → 303 → login; no session |
| Calendar / police / guest link / fee / lock persistence | **BLOCKED** | Needs authenticated disposable property + owner police/calendar/lock fixtures |
| Guest-pay staging readback | **BLOCKED** | Needs logged-in create/update on staging profile with guest-pay enabled |
| RÚIAN on staging | **BLOCKED** | `GET /apartments/ruian-suggest` → 401 without session; detail → [2039](2039-go-address-lookup-staging.md) |
| Code anchor `applyPoliceDefaults` | **PASS** | Empty `uby_mark` → `MarkFromWSUser`; empty `uby_contact` → operator email (grep only, no runtime proof) |

## Layout (auth entry only)

Screenshots: `docs/tasks/media/2038/login-en-{390,768,1280}.png`, `signup-en-*.png`. Login/signup: one primary action, email field, CSRF present. `/apartments/new` unauthenticated shows Czech login title (redirect). Wizard/add-property layout not captured.

## §7 acceptance

- [ ] Calendar, police, guest link, fee, lock — **blocked** (no host session)
- [x] Guest-pay unit switch-off safe — **pass** (Go test)
- [ ] Guest-pay staging readback — **blocked**
- [ ] Property POSTs — **blocked**
- [ ] Manual address + police default runtime — **blocked**; code default logic present; address → 2039

## Commands (last lines)

```text
--- SKIP: TestApartmentUpdateWizardSteps (0.00s) ... UBYHOST_TEST_DATABASE_URL is not set
--- PASS: TestGuestPayValuesRails (0.00s)
--- PASS: TestStayFeeGuestPaySwitchOff (0.00s)
PASS ok .../go/internal/web/properties 0.048s
```

## Deviations

**Done:** brief copy, §6 Go tests (partial), staging SHA/signup/login/ruian curl, Playwright auth-entry screenshots. **Left:** steps 1–5 wizard walk, DB wizard test, guest-pay staging, layout on setup pages.

## Owner-only

1. Provide magic-link login (test mail sink) or a short `UBYHOST_STAGING_NO_LOGIN=1` host window for the same SHA.
2. Provision mock police credentials, harmless iCal URL, lock skip/mock, and stay-fee guest-pay on the isolated profile.
3. Set `UBYHOST_TEST_DATABASE_URL` on CI or hand executor a sanitized URL for wizard DB test.

**Files:** `docs/tasks/2038-go-property-setup-round-trip.md`, `docs/tasks/2038-report.md`, `docs/tasks/media/2038/*.png`.