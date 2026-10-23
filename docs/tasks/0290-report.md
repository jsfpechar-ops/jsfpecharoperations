# 0290 report

Status: review

## Change

Passkey login now bounds network/body reads to 15 seconds and explicit system sheets to 90 seconds, aborts expired work and ignores late results. It owns and cancels autofill before the asynchronous capability check, prevents late cancelled credentials from submitting, validates JSON/options/redirect responses, and restores the button after completion. Failed taps no longer automatically spend another options request. Shared request/sheet deadlines also cover adding a passkey. Both live script references and the static hash are updated.

## Verification

- 19 deterministic cases passed in the tools' V8 runtime with controlled DOM, network, time and WebAuthn promises.
- The base reproduced the stuck network/body/sheet and three autofill race failures.
- Native Node and browser CI pending. Browser matrix: Chromium and WebKit; 390/820/1024/1180 touch and 1280 desktop; 95 cases per engine; 390 px screenshots uploaded by CI.
- Existing CI supplies auth/passkey/security, cache and geometry checks.
- Workspace never started: managed network requirements require sandbox enforcement. Local pytest, context lint and physical-device checks were unavailable.
- No real passkey, live Cloudflare challenge or physical iPhone was used. The precise trigger on the owner's phone remains unconfirmed.

## Turnstile UX finding

Application passkey routes do not require Turnstile. docs/CLOUDFLARE.md documents both Turnstile and Managed Challenge on login plus broad private-app/guest paths, including APIs. Those overlapping layers could explain repeated prompts; live rules, challenge passage and Security Events were inaccessible. No 30-second refresh loop was found in the inspected auth/passkey scripts. Recommend reviewing the matched live rules and avoiding blanket interactive challenges on routine authenticated navigation or JSON endpoints. Keep application validation and rate limits. No production setting was changed.

## Owner work

Review CI and the full JavaScript diff; merge through scripts/merge-pr-on-green.sh; deploy manually; reproduce early tap/cancel/retry on iPhone and desktop. Investigate repeated challenges against Cloudflare Security Events before adjusting rule scope.
