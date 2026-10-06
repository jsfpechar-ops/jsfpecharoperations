# WP12: Three lifecycle e-mails

## Summary
Three host tips go through the existing outbox, each at most once per account: no property 3 days after the first login, no calendar 3 days after the first property, and no completed guest 14 days after the first calendar connected. A new step in the existing mail job checks them once a day (after 09:00 Prague time), and only when `UBYHOST_LIFECYCLE_MAIL=1` (default `0`). A `lifecycle_mail_sent` row is claimed before queuing, so nothing goes out twice, even after the outbox purge.

Amended to match legal position 2 (`04_legal_positions.md`, owner's final decision):
- Per-account flag `user_account.onboarding_emails_opt_out` (INTEGER 0/1, default 0) plus `onboarding_emails_opt_out_at`. Both are added through `ADDED_COLUMNS`, which only adds a column if it is missing. A repeated entry is skipped, so the sign-up WP can add the same two entries and either WP can land first. The old name `lifecycle_mail_opt_out_at` is gone.
- Settings, Account panel: a "Setup tips by e-mail" / "Tipy k nastavení e-mailem" checkbox with a Save button, bound to the flag (`POST /account/onboarding-emails`, CSRF protected). Only a host sees it, and only on their own account, not in an admin preview. Each change is audited.
- Suppression table `mail_suppression (email_hash, scope, created_at)`, scope `'onboarding'`. The hash is HMAC-SHA256 of the normalised address (`mail.normalise_email`), keyed with `config.secret_key()`, the same pattern as `auth.recovery_code_hash`. The table holds no address and no account id. The unsubscribe link adds the recipient's hash to the table and sets the flag. The job skips accounts with the flag set and addresses on the list. Only `lifecycle_mail.py` reads either one, so transactional mail is never blocked.
- Footer: the EN and CS wording from the legal file, with "Unsubscribe with one click" / "Odhlásit jedním kliknutím" as the link. Sender name, IČO and address come from `config.OPERATOR_NAME`, `OPERATOR_ICO` and `OPERATOR_ADDRESS`, and the privacy link points to `/privacy?lang=..`. If any of the three operator values is empty, no tip is sent.
- `List-Unsubscribe: <https URL>` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, on the three lifecycle kinds only (see the SES finding below).
- The unsubscribe routes moved to a new public router (`routes/mail_unsubscribe.py`) with no host CSRF dependency. The reason is that an RFC 8058 one-click POST comes from the mailbox provider with no cookie and no form token. The signed token is the only credential. GET shows one button. POST unsubscribes. Only failed POSTs count toward the 30 per hour limit.
- Every unsubscribe token carries the account id and the recipient's address hash, and each recipient gets their own link.

SES finding: `mail.py` uses SES v1 `SendEmail` (`boto3.client("ses")`, Simple message). Its input has no header field. I checked this against the installed model, boto3 1.43.103 / botocore 1.43.107, `ses` 2010-12-01, `SendEmail` members `Source, Destination, Message{Subject, Body}, ReplyToAddresses, ReturnPath, SourceArn, ReturnPathArn, Tags, ConfigurationSetName`. SES v2 (`sesv2` 2019-09-27) `SendEmail` `Content.Simple` has `Subject, Body, Headers, Attachments`. `Headers` is a list of `{Name, Value}` with at most 15 entries: names are printable ASCII without a colon, up to 126 characters; values are printable ASCII, up to 995 characters. So `_send_ses` now sends lifecycle rows that carry a `list_unsubscribe` https URL through `_sesv2_client().send_email(...)` with the two headers. All other kinds still go through v1, unchanged.

Content rule (legal position 2): the tips are only about the host's own setup, with no discounts, pricing or third-party offers. If marketing content is ever added, the subject gets the prefix "Novinky:" and the e-mail is treated as a newsletter. This rule is in `AGENTS.md` (one line) and not in code comments.

Stacked on WP10, WP13 and WP11. Those three commits are unchanged (e9d6fde, 0d7de92, db1fca6). The amended WP12 is f9e53a2.

## Files changed
- `AGENTS.md`: one-line content rule for the onboarding e-mails.
- `App/app/lifecycle_mail.py`: new. Triggers, sent markers, token (account id plus address hash), `email_hash`, `suppress`/`is_suppressed`, `set_opt_out`/`resubscribe`/`unsubscribe`, sender-identity gate, daily gate.
- `App/app/mail.py`: the three kinds in `KINDS` and `HOST_KINDS`; `LIFECYCLE_KINDS`; `_sesv2_client`; `list_unsubscribe_headers`; v2 send path for the lifecycle kinds.
- `App/app/mail_notify.py`: `build_lifecycle()`; `_FooterSentence` (a footer sentence with named links: "label (URL)" in text, anchors in HTML); `import re`.
- `App/app/db.py`: tables `lifecycle_mail_sent` and `mail_suppression` (no triggers); the two flag columns in `ADDED_COLUMNS`.
- `App/app/config.py`: `LIFECYCLE_MAIL` from `UBYHOST_LIFECYCLE_MAIL`, default off.
- `App/app/scheduler.py`: `lifecycle` step in `_job_mail`.
- `App/app/routes/mail_unsubscribe.py`: new. Public `GET` and `POST /mail/unsubscribe/{token}`.
- `App/app/main.py`: includes the new router.
- `App/app/routes/admin_accounts.py`: `POST /account/onboarding-emails` (the Settings toggle).
- `App/app/routes/admin.py`: `onboarding_emails` in the Settings context (`_onboarding_emails`).
- `App/app/templates/settings.html`: the toggle row in the Account panel.
- `App/app/templates/mail_unsubscribe.html`: new, on `auth_base.html` (no analytics).
- `App/app/retention.py`: workspace deletion also deletes the account's `lifecycle_mail_sent` rows. Suppression rows are kept on purpose.
- `App/app/host_i18n.py`: `_LIFECYCLE_MAIL_STRINGS` (mail copy, legal footer, link label, unsubscribe page, Settings toggle and flashes, outbox kind names), EN and CS.
- `docs/ENVIRONMENT.md`: `UBYHOST_LIFECYCLE_MAIL` row, including the operator-identity requirement.
- `App/tests/test_claim_mail.py`: the pinned `KINDS` set gains the three kinds.
- `App/tests/test_lifecycle_mail.py`: new.

## Tests added
`tests/test_lifecycle_mail.py` (18 tests):
- each trigger fires once, and not again after the outbox purge;
- no tip before the due day or once the condition is met;
- no tip for a stall older than the window;
- the env switch stops it, and the default is off;
- a flagged account gets no tip but still gets service mail;
- `run_daily` runs once per local day, not before 09:00, and the mail job calls it;
- EN footer exact wording, with sender, IČO, address, privacy link, unsubscribe anchor and `list_unsubscribe` in the payload; CS footer exact wording;
- no tip without the operator identity;
- unsubscribe works signed out; GET changes nothing; POST sets the flag and timestamp, writes a suppression row (scope `onboarding`, no plain address) and audits;
- an RFC 8058 one-click POST with a foreign Origin and no cookie or CSRF token works;
- a suppressed address gets no tip even on another account, while the account's other address does, and service mail still reaches both;
- the Settings toggle renders in EN and CS, turns the flag off and on, and turning it on clears the workspace's addresses from the suppression list;
- the flag columns are declared as specified, and listing them twice in `ADDED_COLUMNS` is harmless;
- SES v2 request with both headers, validated by botocore `Stubber` against the installed `sesv2` model, and v1 not used;
- service mail goes through v1 with no headers, even when the payload has a URL;
- a forged token, or one signed with another salt, is refused.

## Test commands and results
- `python -m pytest -q tests/test_lifecycle_mail.py`: 18 passed.
- Mail and related: `tests/test_lifecycle_mail.py tests/test_ses_mail.py tests/test_claim_mail.py tests/test_auth_error_language.py tests/test_host_i18n.py tests/test_no_tracking.py tests/test_mail_failed_alert.py tests/test_admin_route_split.py tests/test_accounts.py`: 192 passed.
- Broad run at the amended commit (WP10 to WP12 stacked), three chunks:
  - `tests/test_[a-f]*.py`: 611 passed, 2 skipped.
  - `tests/test_[g-o]*.py` without the browser e2e: 798 passed, 1 skipped, 1 failed (`test_host_geometry.py::test_the_month_filter_shares_its_page_edges`).
  - `tests/test_[p-z]*.py tests/test_guest_browser_e2e.py`: 798 passed, 4 skipped, 1 failed (`test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`).
  - Total: 2207 passed, 7 skipped, 2 failed. Both failures also fail on `wpbase` (see the WP10 notes).
- Ruff (`--select E9,F63,F7,F82,F401,F841`): all checks passed.

## Deviations from the spec and why
- Recipient: host usernames are not e-mail addresses, so tips go to the workspace's legal-entity contact addresses (`mail_notify.workspace_contact_emails`), as the deletion notice does. A host with no legal entity yet gets no "no property" tip. No marker is written in that case, so the tip can still go out later inside the window.
- One click: the footer link opens a page with one button, and the POST unsubscribes. GET does not unsubscribe, because link scanners (for example Outlook Safe Links) open every link and would unsubscribe hosts who never asked. True one-click unsubscribing is the `List-Unsubscribe-Post` header, which Gmail, Yahoo and Apple Mail show as a button. If counsel wants the footer link itself to unsubscribe on GET, change `mail_unsubscribe_form` to call `lifecycle_mail.unsubscribe`. That is a few lines.
- Unsubscribe sets the account flag and suppresses the address that received the mail. Turning tips back on in Settings clears the flag and removes the suppression rows for the workspace's current contact addresses. The host's fresh choice overrides an earlier refusal; otherwise the toggle would show on while nothing could be sent.
- "No calendar" means no active feed at all (a host whose feed errors already gets sync alerts). "First calendar connected" uses `last_status = 'ok'`, as in the funnel.
- Two extra guards: no tip for a stall more than 30 days past its due day, and the daily check waits until 09:00 Prague time. Added later: no tip at all while any of `UBYHOST_OPERATOR_NAME`, `_ICO` or `_ADDRESS` is empty, because the legal file (Q17) requires the sender in every message.
- Language: tips use `mail_notify.HOST_MAIL_LANGUAGE` (English, owner decision E-14), like all host mail. The CS copy and footer are in the catalogue.
- Plain-text part: a link in the footer is printed as "Unsubscribe with one click (URL)" and "Privacy: URL." The HTML part uses anchors.
- The sign-up checkbox and the privacy-policy paragraph from legal position 2 are not in this WP. They belong to the sign-up WP and the legal-pages work.

## What Cursor must verify or adapt when applying on the real main
- `ADDED_COLUMNS` and `SCHEMA`: if WP18 moved migrations to numbered files, put the new tables and the two columns there. Keep the "add if missing" behaviour, because the sign-up WP adds the same `onboarding_emails_opt_out` columns. The declarations must match exactly: `INTEGER NOT NULL DEFAULT 0` and `TEXT`.
- The sign-up WP should write `onboarding_emails_opt_out = 1` and `onboarding_emails_opt_out_at` when its checkbox is ticked. It should not write to `mail_suppression`: only the link does that.
- IAM: SES v2 `SendEmail` uses the same IAM action `ses:SendEmail`, but check that the production policy has no condition that limits it to API v1. botocore 1.43.x is required. The pin is `boto3==1.43.103`. Do not downgrade below the version that added `Simple.Headers`.
- After the first real send, check in Gmail ("Show original") that `List-Unsubscribe` and `List-Unsubscribe-Post` are present and covered by the DKIM signature, and that Gmail offers its Unsubscribe button.
- `/mail/unsubscribe/{token}` must stay public and outside any CSRF or Origin check, including if WP04 or WP19 change the public allow-list, CSP or middleware. Mailbox providers post to it cross-site.
- If WP06 moved the scheduler to its own process, the `lifecycle` step stays inside the mail job there.
- If WP20 adds a per-host language, `build_lifecycle` should take it. The unsubscribe URL already carries `?lang=`.
- Rotating `UBYHOST_SECRET_KEY` breaks the existing suppression hashes and unsubscribe links. If the key is ever rotated, re-hash the list or keep the old key for this purpose.

## Manual steps for the owner
- Set `UBYHOST_OPERATOR_NAME`, `UBYHOST_OPERATOR_ICO` and `UBYHOST_OPERATOR_ADDRESS` in the production `.env`. Without them no tip is sent.
- Keep `UBYHOST_LIFECYCLE_MAIL=0` until the sign-up opt-out checkbox and the privacy-policy paragraph (legal position 2) are live. A host must be able to refuse before the first tip.
- Before turning it on, test on staging with `UBYHOST_MAIL_BACKEND=console` and read the messages in Settings. On production, send one tip to your own address and check the headers as described above.
