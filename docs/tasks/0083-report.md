# 0083 report: account settings navigation

Base: 34bffcb (coordinator branch). Lane mode per combined plan §2 (patch gate lifted).

## What changed
- `settings.html` regrouped into six visible groups with ordinary header bars, in order: Account, Security, Data & archive, Privacy, Technical, Help. An index (reusing `.host-property-grid`) links each group; Technical points at the existing `#settings-technical` block.
- Admin links (Team, Incidents) appear only in Account for admins; ordinary users render no `/admin/` link.
- Login e-mail change is now a visible form (was a `<details>`); same action `/account/email`, field `email`, CSRF. Language stays in the account menu (`/language`); there is no combined save.
- Single link to the business editor: `#settings-business` row in Account, `/entities`. 0076 can retarget it (e.g. `/entities?edit=<id>`) in that one place. No editor built.
- Routine helper text moved behind the shared `?` tip (`settings_heading` macro): Security, Archive, Data protection, Privacy consents, Guest form access, and the new-email field (`aria-describedby="account-new-email-help"`).
- New rows: Privacy requests (Privacy), Help guide (Help). Specialized actions kept as is: purge-expired (with confirm), passkeys (add/rename/remove), 2FA setup/move/disable, archive hub, legal documents, audit log, technical details.
- Search (`api.py`): added Settings security and Data & archive destinations; admin entries stay admin-only.
- New macros at the end of `_components.html`: `settings_group`, `settings_heading`. i18n block `_SETTINGS_GROUP_STRINGS` (EN+CS). `/* 0083 */` block at end of host.css.

## Deviations
- The Technical details `<details>` stays collapsed: existing `test_settings_technical.py` asserts it, and it holds operator diagnostics, not host settings. The 2FA move/disable and passkey rename disclosures also stay (their tests assert the current markup); plan §4.2 would unfold them, a follow-up decision.
- `base.html` and `_host_navigation.html` needed no change (account menu and local nav already role-aware, rail unchanged).
- Plan §3 files outside the brief list: none beyond brief, except the new test is `test_host_account_navigation.py` (listed).

## Tests (from App/, mock/staging/REQUIRE_BROWSER, 0 skipped)
- test_host_account_navigation.py: 11 pass (groups, order, roles, forms, EN/CS, palette, browser geometry 360/390/1280 EN/CS with no horizontal overflow and ? tip inside viewport).
- test_settings_technical, account_emails, auth_forms_no_js, move_to_new_phone, passkeys, lifecycle_mail, property_hub, copy_cleanup: 107 pass.
- Wider set and ruff: see final message.

## Evidence
`docs/tasks/0083-evidence/settings-{360,390,1280}-{en,cs}.png` (synthetic account, `UBYHOST_CAPTURE_0083=1`).
