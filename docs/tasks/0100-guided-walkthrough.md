# 0100: Guided walk-through, police-login waiting path, guide for existing properties

Status: review
Base: `bd77446` (claude/quirky-lamport-9svmd1) | Executor: Claude (owner-authorized to implement)

## 1. Objective

The owner tested 0096 on staging. A first-time host needs the guide to teach how the app works, one idea per screen. It must also let a host go on while the police login is on its way, and it must reach existing properties too.

## 2. Context

0096 ([brief](0096-guided-setup.md)) had no Police reporting skip, showed the guide only to new properties and had no try-out. The built-in demo ("Preview only", `App/app/demo.py`) only recognises whole demo properties. A per-stay demo inside a real property did not exist, so 0100 adds one. It reuses the same "Preview only" pill and is pinned by tests on every filing path.

## 3. Files

| Path | What |
|---|---|
| `App/app/property_setup.py` | 8 steps, `waiting` mark, `hidden`, `legacy` |
| `App/app/routes/admin.py` | facts from the record, legacy state, actions `wait`/`demo`/`hide`/`show`, demo delete |
| `App/app/demo.py` | `DEMO_STAY_SOURCE`, create/delete the demo stay |
| `App/app/reporting.py`, `filing_watchdog.py`, `door_codes.py`, `stay_fee.py`, `invoices.py`, `routes/invoices.py`, `housebook.py`, `stays_export.py`, `mail.py`, `routes/guest.py`, `lifecycle_mail.py`, `admin_funnel.py` | demo stay excluded |
| `App/app/templates/_property_setup_guide.html`, `_property_overview.html`, `reservation_detail.html` | steps, waiting note, Hide/Show, demo banner |
| `App/app/templates/reservations.html`, `dashboard.html` | one-line "Preview only" pill for a demo stay (parallel worker's files) |
| `App/app/host_i18n.py`, `templating.py`, `static/host.css` | `# 0100` strings, source label, `/* 0100 */` styles |
| `App/tests/test_property_setup_guide_browser.py`, `App/tests/test_demo_stay_exclusion.py` | tests |

## 4. Steps

Order: Calendar, Guest link, PIN, Try it out, Police reporting, Stay fee (optional), Door lock (optional), Automation.

1. **Guest link**: what it is and where to paste it, Copy link and PIN, **Done, I've added it**.
2. **PIN**: why guests need it, the PIN, the same snippet, **Got it**.
3. **Try it out**: **Create a demo stay**, then **Open the guest form** (new tab). After a test registration: "This is what you see when a guest registers", with the status pill, the guest count and a link to the stay. Then **Delete demo stay**. Skip deletes it too.
4. **Police reporting**: Save is the primary. A quiet **I'm still waiting for my police login** marks the step `waiting`, and the guide moves on. A "Police reporting: waiting for login" pill stays at the top of the guide. When everything else is done, the guide comes back to Police reporting. It never says "Setup complete" until the police details are complete.
5. The state key is still `property_setup:<id>` (no schema change), now `{"steps", "finished", "hidden", "legacy"}`.
6. A property with no key (made before 0096) shows the guide unless it is set up: police details complete and a calendar or a stay. Stays and a guest who registered through the link count as done for the calendar, guest link, PIN and try-out steps. Automation counts as done. Archived, inactive and built-in demo properties never show it. Fee and Door lock stay optional: once the police details are complete and there are stays, the guide is finished. Apart from the panel on top, such a property's pages behave as before:
   - it opens on Overview and keeps its checklist;
   - Bookings is not reduced to the connect form, and the calendar step's quiet skip sits in the panel;
   - saves carry no `setup_step` and are not redirected.
7. **Hide setup guide** on every step. **Show setup guide** on Overview while the guide is hidden and unfinished.

### Verified waiting behaviour (code read and pinned by tests)

With the login missing, `submit_for_apartment` stops at `validate_apartment` (`not_configured`, alert `apartment_setup`). Nothing is leased or sent, and the guests stay `pending`. Guest routes do not check police details. The deadline alerts and the filing watchdog keep running.

- **scheduled / immediate**: the `submit` sweep runs every `UBYHOST_SUBMIT_SWEEP_MINUTES` (10) for every property not in `manual` mode. After the login is saved, it sends each complete, signed registration whose wait has passed (completion + `submit_after_hours`, 0 for immediate) or that is within 6 h of its deadline. `due_for_automatic_send` has no cut-off after the deadline, so late stays go too (the police code 112 is a late accept). Saving the settings sends nothing by itself.
- **manual**: the sweep skips the property. Stays show "Ready to report" until the host presses Send to UbyPort.

Copy (EN):
- Always: "You can keep setting up, and guests can register as usual. Nothing goes to the police until your login is saved."
- Manual: "Then finished stays wait in Stays as “Ready to report” until you press Send to UbyPort."
- Automatic: "Then UbyHost sends every finished registration by itself: stays that are already due go out within about 10 minutes, late ones too."
- Always: "The legal deadline still applies: report foreign guests within 3 working days of arrival." It is followed by the link "If your login won't come in time, report them by hand" to `/guide#manual-filing`.

### Demo stay exclusion

The demo stay is `reservation.source = 'demo'`. It is never reported. `collect_sendable` drops it for every caller, so it is never leased by `claim_sendable`. `submit_batch` refuses it before a submission row exists. `send_controls` hides Send, and filing by hand is refused. It is also left out of:

- the guest stay picker, the guest claim, and guest-link access for anyone but the signed-in host;
- deadline alerts and both watchdog lists;
- door-code eligibility and the stay view;
- guest e-mail;
- the stay fee lines and the unsigned count;
- the invoice picker and `stay_problem`;
- the house book and its archived rows;
- the stays CSV;
- the "no guest yet" lifecycle mail and the funnel's first guest.

The stay is deleted only through `demo.delete_demo_stay`, which refuses a real stay.

## 5. Do not touch

Filing logic beyond the demo exclusion, the SOAP client, `base.html` `?v=`, and the list pages beyond the two pill lines.

## 6. Commands

From `App/` with the staging/mock browser env: `pytest tests/test_property_setup_guide_browser.py tests/test_demo_stay_exclusion.py`. Then the navigation, UX acceptance and submit_state/scheduler/automation/demo/preview files named in the report.

## 7. Acceptance

The EN/CS journey passes at 360 and 1280 px, plus the no-JS journey. The demo stay is never filed (mock UbyPort), claimed, charged, invoiced or exported. The waiting path never finishes early. Existing incomplete properties show the guide, and set-up ones do not. Hide and Show work.

## 8. Stop and ask

None needed. No schema change: the stay uses the free-text `source` column and the guide uses the existing settings key.

## 9. Report

[0100-report](0100-report.md).
