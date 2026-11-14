# Plan: building entry code + external guide link on the stay page and in the completion receipt

Status 2026-11-14, main at `d39b1351`. Briefs: [1631](../tasks/1631-entry-code-schema-retention.md), [1632](../tasks/1632-host-ui-entry-code-guide-url.md), [1633](../tasks/1633-stay-page-access-guide-blocks.md), [1634](../tasks/1634-completion-mail-entry-code-guide.md) (run in order, each `Depends on` the previous).

Goal: a host-typed building/gate entry code and an optional external (e.g. Notion) guide URL, shown to the guest on the gated stay page and in the completion receipt, right after the apartment door code.

## Decisions (owner, 2026-11-14)

- Entry code lives in exactly two places: the gated stay page (`/l/{token}/{reservation_id}`, behind permalink + PIN + device claim) and the completion receipt mail. Never in the late-PIN door-code notice (`build_door_code`), the public QR guide `/g/{token}`, logs, audit values, analytics, exports, or Leon (`leon.guide_block` reads guide cards only, so an apartment-level field is excluded by construction).
- Visibility window: the existing `booked_level()` rule (day before check-in through checkout day, `routes/guest_guide_view.py:57`) AND `entry_code_until` when set — a stale gate code must not linger on old permalinks. Already-sent mail cannot be retracted; the page is the source of truth if the host changes the code mid-stay.
- Secrets handling copies the door-code pattern: encrypted at rest (`db.encrypt_field`), stored encrypted in the outbox payload, decrypted only at send via a marker (`ENTRY_CODE_MARKER`/`ENTRY_CODE_KEY` next to `DOOR_CODE_MARKER`/`DOOR_CODE_KEY` in `mail.py`), missing secret fails the send (`db.DecryptionError`). The plain-text fallback (`claim._guest_fallback_text`) gets the guide links (non-secret) but not the entry code — same as the door code today.
- External guide URL is host-controlled, https-only (pattern: `guest_guide.py:186-188` plus the strict parse in `guest_guide_import.py:89`: https scheme, no userinfo, no port), shown in the UI with its domain.
- Go-first (AGENTS.md rule 11, `docs/context/go-first.md`): every path this feature touches (guest stay page, guide editor, apartment settings, mail/door-code jobs) is still Python-served — `UBYHOST_GO_PATHS` unset, mail + door_codes still Python jobs (status 2026-11-14). **Pending owner:** port first vs. build in Python now with the switch in owner steps. Recorded in [decisions](../context/decisions.md).

## Build order

1. **1631 — schema + retention + exports.** Goose file `App/migrations_pg/00018_*.sql` (next after `00017`; `App/app/migrations/` is frozen at 0045, `db.SCHEMA` never changes — new columns are read via the `ADDED_COLUMNS`-style path). Columns on `apartment`: `entry_code_enc` (encrypted), `entry_code_label`, `entry_code_until` (nullable date), `guide_external_url` (nullable). Additive-only goose file; rerun `App/scripts/pg_schema_golden.py` (regenerates `go/internal/schema/expected_schema.json` + parity). Retention: a line in `App/app/retention.py` plus a purge step that nulls `entry_code_enc` like `_door_code_pin_step` (`retention.py:495`) nulls `pin_enc`. Workspace export (`App/app/routes/exports.py`) must not carry `entry_code_enc`.
2. **1632 — host UI.** Entry code (label + code + optional valid-until) in the Smart lock section (`routes/admin.py` next to `apartment_door_codes` at :2496, template `_smart_locks_panel.html`): encrypt on write, `db.audit("entry_code_set", ...)` with no value, write-only masked display. External guide URL field on the guide editor (`routes/guest_guide.py`, `guide.html`), https-enforced. UX gate applies (host pages): geometry tests 0 skipped, 390/768/1280 screenshots, design-system checklist in the PR.
3. **1633 — stay page.** `routes/guest.py` `stay_overview` context: decrypt entry code at render only; new Access block at the top of the completed state (entry code line, then the existing door-code block, then fee); guide block after the door code: prominent internal-guide button when `guide_live`, plus external link (`rel="noopener noreferrer" target="_blank"`, domain shown) when `guide_external_url` is set. Bump the `?v=` cache key in `templates/guest/base.html` if CSS/JS changes. Guest-page rules: `test_guest_*.py` + `test_guest_browser_e2e.py` 0 skipped, one 390 px screenshot.
4. **1634 — completion mail.** `mail.py`: `ENTRY_CODE_MARKER`/`ENTRY_CODE_KEY` + `_with_entry_code()` next to `_with_door_code` (:358), wired into both delivery chains (:423, :440). `mail_notify.build_completion` (:1724): entry code line next to the door-code block (:1805-1820), then the guide block (button to the absolute internal guide URL via `config_public` like `_stay_link`, plus the external URL); guide links also into the fallback text. `claim.maybe_notify_completion` sets `payload[mail.ENTRY_CODE_KEY]` next to :860. i18n keys in every language catalog in `i18n.py`. Mail goldens (`test_claim_mail.py`, `test_completion_fee_mail_1077.py`, `App/tests/golden/`) are pinned — update them.

Resulting receipt order: stay panel → what you sent → fee → entry code + door code → guide → host link → note.

## Verification per area (test-map rows)

- DB/migrations: `test_migrations.py test_db_*.py`; retention: `test_retention*.py test_privacy_*.py test_pii_encryption.py`; goldens: `App/scripts/pg_schema_golden.py` + `go test ./internal/schema/...`.
- Host UI: `test_host_*.py test_host_geometry.py` (0 skipped) + screenshots.
- Guest page: `test_guest_*.py test_guest_browser_e2e.py` (0 skipped) + 390 px shot; Leon/QR untouched: `test_leon.py test_guest_guide*.py`.
- Mail: `test_ses_mail.py test_mail_*.py test_*_mail.py` + mail goldens.
- Copy: `test_*_i18n.py test_copy_cleanup.py test_flash_literals.py`.
