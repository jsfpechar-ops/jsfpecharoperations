# 0096: Guided setup of a new property

Status: review
Base: `3248c8d` (claude/quirky-lamport-9svmd1) | Executor: Claude (owner-authorized to implement)

## 1. Objective

Lead a first-time host through the whole property setup one step at a time, so it is set up right once ("make it for a child"). Replace the "Property created. What next?" box, give Door lock its own Settings group and let the guest link follow the property name.

## 2. Context

The owner tested staging. After Add property, the host had to choose between two primary buttons. Settings is grouped (0094), but nothing leads the host through it in order.

## 3. Files

| Path | What |
|---|---|
| `App/app/property_setup.py` | new: steps, order, state, current step |
| `App/app/routes/admin.py` | create starts the guide; `POST /apartments/<id>/setup`; feed add and Settings save move on; `lock` section; name → slug |
| `App/app/guest_slug.py` | `follow_name()` |
| `App/app/templates/_property_setup_guide.html` | new: the step panel |
| `App/app/templates/apartment_form.html`, `_property_calendars.html`, `_property_editor.html`, `_property_overview.html` | guide placement, calendar-only step, Door lock group, link-name field removed |
| `App/app/static/app.js`, `host.css`, `host_i18n.py` | `lock` section/hash, Continue toggle, `/* 0096 */` styles, `# 0096` strings |
| `App/tests/test_property_setup_guide_browser.py` | new |

## 4. Steps

1. After create: Bookings & calendars shows only the connect form (platform, iCal URL, optional name, one primary **Add calendar**) and one quiet link **Skip — I'll add stays manually**.
2. A step panel "Step N of 6 · title" with one primary action at a time:
   1. Calendar: done with a calendar, or skipped.
   2. Guest links: the ready message "Guest registration: <url> · PIN: <pin>" (EN/CS), **Copy link and PIN**, **Done, I've added it**.
   3. Police reporting: done when the police details are complete (no skip).
   4. Stay fee: optional. Done by Skip, a save from its section, or a fee rate.
   5. Door lock: optional, and only where door codes exist (otherwise 5 steps). Done by Skip, a save from its section, or a chosen lock.
   6. Automation: done by a save from its section or **Keep manual sending**.
   After the last step, the Overview shows the existing compact "Set up" line.
3. State has no schema change. It is one key in the existing `settings` table: `property_setup:<id>` → `{"steps": {...}, "finished": bool}`. The key is written on create, so older properties never show the guide.
4. Settings sub-nav: Property information · Guest experience · Reporting & fees · Door lock · Automation. The lock UI moves unchanged, and `#door-code` opens the new group.
5. The "Readable part of the link" field is removed. A name change calls `guest_slug.rename`, and old slugs keep redirecting.

## 5. Do not touch

Police reporting and Stay fee section contents, `_apply_police_defaults` (parallel worker). Filing, invoice, fee and lock logic. `base.html` `?v=`.

## 6. Commands

From `App/` with the staging/mock browser env: `pytest tests/test_property_setup_guide_browser.py` plus the property/lock/slug/acceptance files named in the report.

## 7. Acceptance

The full EN/CS journey passes at 360 and 1280 px, plus the no-JS journey. Each step has one visible primary. A pre-0096 property shows no guide. The slug follows a rename, and the old link redirects.

## 8. Stop and ask

A schema need: none arose.

## 9. Report

[0096-report](0096-report.md).
