# 0100 report: guided walk-through, waiting path, guide for existing properties

Base: `bd77446`, merged with `claude/quirky-lamport-9svmd1` (0101) before handing over. Executor: Claude (owner-authorized). Brief: [0100-guided-walkthrough](0100-guided-walkthrough.md).

## What changed

- **Guide, 8 steps** (7 without door codes): Calendar, Guest link, PIN, Try it out, Police reporting, Stay fee, Door lock, Automation. Each step has one primary button. Every step also has a quiet **Hide setup guide**, and Overview has **Show setup guide**.
- **Try it out** makes a demo stay in this property: today to tomorrow, 1 guest, `reservation.source = 'demo'`. The host opens the guest form in a new tab, then sees "This is what you see when a guest registers": a link to the stay, the "Preview only" pill and the guest count. Then **Delete demo stay**. Skip deletes it too.
- **I'm still waiting for my police login** (quiet button on Police reporting): the guide moves on, and a "Police reporting: waiting for login" pill stays at its top. When everything else is done, the guide comes back to Police reporting. "Setup complete" shows only once the police details are complete.
- **Existing properties** (no stored key) get the guide unless they are set up (police details complete, plus a calendar or a stay). Steps the record already answers count as done. Their pages otherwise behave as before (Overview first, checklist kept, saves and calendar adds not redirected). No schema change: the same `property_setup:<id>` key, now with `hidden` and `legacy`.
- **Stay page** of a demo stay: banner, **Delete demo stay** (asks first), the "Preview only" pill, no Send button and no filing by hand.
- **Fix**: the 0096 guide panel's `margin: 0 0 16px` pulled it out of the centred lane on wide screens. The geometry test caught it once existing properties showed the guide.
- **Parallel worker's files**: in `reservations.html` and `dashboard.html`, one `is_demo=` expression each, so the "Preview only" pill also covers a demo stay.

## Verified waiting behaviour (pinned by `test_demo_stay_exclusion.py` against mock UbyPort)

With the login missing, nothing is leased or sent. `submit_for_apartment` returns `not_configured`, and guests stay `pending`.

- **scheduled / immediate**: after the login is saved, the next 10-minute sweep sends every finished registration that is due, late ones included.
- **manual**: stays wait as "Ready to report" until the host presses Send.

The copy is chosen by the property's own mode:

- "You can keep setting up, and guests can register as usual. Nothing goes to the police until your login is saved."
- Manual: "Then finished stays wait in Stays as “Ready to report” until you press Send to UbyPort."
- Automatic: "Then UbyHost sends every finished registration by itself: stays that are already due go out within about 10 minutes, late ones too."
- "The legal deadline still applies: report foreign guests within 3 working days of arrival." It is followed by the link "If your login won't come in time, report them by hand" to `/guide#manual-filing`.

## Demo stay exclusion (each line has a test)

- **Filing**: `collect_sendable` drops it for every flag combination, so `claim_sendable` never leases it. `submit_batch` refuses a forged pair before a submission row exists. The sweep, host send, resend, completion send and bulk send never send it. `send_controls` hides Send, and filing by hand is refused.
- **Deadlines and watchdog**: no deadline alert, and it is in neither watchdog list (at risk, unknown risk).
- **Door codes and mail**: not eligible for a door code, and no door view. No guest e-mail is queued.
- **Guest pages**: never in the stay picker and never claimable. Only the signed-in host reaches it; anyone else gets 404.
- **Money and records**: no stay fee line, and not in the unsigned count. Not in the invoice picker, and `stay_problem` refuses it. Not in the house book, its archived rows or the stays CSV.

## Tests (App/, staging/mock env, pinned Chromium, `UBYHOST_REQUIRE_BROWSER=1`)

- `test_property_setup_guide_browser.py`: 15 passed (17 with capture on). It covers:
  - the full beginner journey, EN and CS, at 360 and 1280. A real guest form is filled in the popup. CS takes the waiting path and checks "complete" never shows early.
  - the no-JS CS journey;
  - legacy, complete and archived properties;
  - Hide and Show;
  - refusals.
- `test_demo_stay_exclusion.py`: 15 passed.
- Full suite before the 0101 merge: 3435 passed, 3 skipped (capture gates), 2 failed. Both failures are environmental: `test_feed_dns_pinning` (no IPv6) and `test_posthog_snippet_browser` (headless-shell binary missing). The first also fails at `bd77446`.
- Updated for the intentional changes, each with a replacement assertion:
  - "a pre-0096 property never sees the guide" now reads "existing properties get it until set up";
  - "unreadable state hides the guide" now reads "it starts again".
- After the 0101 merge: full suite 3453 passed, 3 skipped, 3 failed. The two environmental failures are the same as before. The third (`test_calendar_platform_required`: adding a feed to an existing property jumped to the guide) is fixed, because legacy properties keep the old redirect. Re-run after the fix: guide, exclusion, calendar, `test_no_dead_internal_links`, navigation and UX acceptance, 81 passed.

## Evidence

`docs/tasks/0100-evidence/` (`UBYHOST_CAPTURE_0100=1`), synthetic data only. Every step at 390 and 1280, EN and CS, plus `-1280-cs-nojs`: `01-calendar` … `14-complete`, including `06-guest-form-sent`, `07-try-registered`, `08-demo-stay-page` and `13-reporting-waiting`.

## Open points

1. The dashboard "Ready to send" count still includes an undeleted demo stay. It is the parallel worker's file. Send is refused anyway.
2. A demo stay the host never deletes stays excluded forever, and Delete is on its stay page.
3. Legacy rule: Stay fee and Door lock never hold an existing property's guide open.
