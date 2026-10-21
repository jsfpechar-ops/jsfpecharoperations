# Pages: Settings (`/settings`, `settings.html`), Archived (`/settings/archived`), Privacy requests (`/privacy-requests`), Smart locks (`/smart-locks`), admin pages

Master version: 2.0.0. Adds only.

## Settings
- nav: `settings`; body_kind: `settings`; title key: `nav.settings`; meta: none (the lede sentence is removed; groups explain themselves)
- primary action: none; secondary: none; tabs: none
- anchor list (1280): Account, Security, Data and archive, Privacy, Notifications, Help (existing six groups; the `host-property-grid` card index is replaced by the anchor list, and by the group titles on phone)
- groups and rows (each row: label and current value left, control right):
  - Account: login e-mail (value, "Change" secondary opens inline form); display name; business details link; language toggle; sign out everywhere (danger, confirm)
  - Security: passkeys (list + "Add passkey" secondary); authenticator app (toggle-like state, "Set up"); sessions
  - Data and archive: export workspace (secondary, `download`); backups; retention facts; archived records link
  - Privacy: privacy requests link; retention policy link; PostHog note stays as text
  - Notifications and mail: digest toggles; destination address
  - Help: guide, support e-mail, shortcuts, legal links
  - Phone app (`settings_group('phone')`, 0219/0227): install row (state per platform: installed, Add to Home Screen steps on iPhone, Install button where the browser offers one); urgent alerts row ("Turn on" / "Send a test" / "Turn off", `On` badge, iPhone hint to open from the Home Screen first); device list with Remove behind `data-confirm`. Only the four critical alerts exist; no per-kind toggles.
- badges: `attention` = no second factor; `done` = passkey added; `neutral` = default
- dangerous rows (delete workspace) sit last in a `section` with a `danger` button behind a confirm dialog

## Archived (`settings_archived.html`)
- body_kind: `list`; tabs = Stays, Properties, Guests, Entities (existing filters become tabs); columns = name, archived date, reason, actions (Restore secondary compact, menu); badge `neutral` "Archived"; empty state per tab

## Privacy requests, Smart locks, Users, Incidents, Operations, Funnel
- all `list` kind with `page_header` title, one primary where a create action exists (Add lock account, Invite user), otherwise none; Operations and Funnel are `detail` with `stat_row` and `table`s; admin pages keep `nav: admin` and appear only under Admin

## Tests
- `test_host_controls_browser.py`, `test_host_geometry.py`, `test_pwa_browser.py`, `test_push_settings_browser.py`; screenshots 390 and 1280 of Settings plus the settings skeleton
