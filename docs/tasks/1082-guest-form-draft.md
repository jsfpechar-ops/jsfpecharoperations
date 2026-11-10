# 1082: S5 server draft of an unfinished guest form ("Welcome back")

Status: todo (ready for the executor; the lint has no "ready" status)
Tier: A | Depends on: nothing (main alone) | Base commit: f1ca4288 | Branch: claude/1082-guest-form-draft
Executor: Fable 5.2 | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a fresh Fable reviews the diff against this brief before the PR opens.
Report: docs/tasks/1082-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md): decision **7b** and queue item **S5**, "Server draft (decision 7b): 'Welcome back. Continue where you left off.'", benefit "Closing the tab loses nothing". S13 (poor signal) needs this and is not built here.

A guest who closes the new-guest form half-filled and opens it again on the same device sees one line, "Welcome back. Continue where you left off.", above the form, with the fields they typed filled in.

**Owner rule (confirmed 2026-11-10):** the draft is deleted when the form is sent; otherwise 7 days after its last change or the day after check-out, whichever comes first.

**Tier A (orchestrator decision):** new personal-data table, a new cookie, encryption at rest, a retention step, and the guest form next to police fields. Filing stays byte-identical.

## 2. Context

### Design decisions (fixed; do not reopen)

- **Scope:** only the new-guest form, `GET /l/{token}/{reservation_id}/new` (`guest_form_new`). No draft for an edit of a saved guest (`/edit/{guest_id}`), for the host preview (`_host_owns_apartment`), or on the relang and 422 re-renders (they keep their posted values as today; an existing draft stays until the next autosave).
- **Keying (privacy):** a draft row is keyed by `(reservation_id, device_key_hash)`. The device key is a random `secrets.token_urlsafe(32)` in a new strictly-necessary cookie `ubyhost_draft` (HttpOnly, SameSite=Lax, Secure as the other guest cookies, path `/`, 7 days), set only by the first autosave. The server stores only `sha256(device key)` hex, never the key. The row also stores `claim_generation` (`reservation_claim.token_version` when mail is on, else 0). A draft loads only when the request carries the same device key **and** the claim generation is still the same, so a host release or a fresh claim secret cuts the old device off. Another guest of the same booking is on another device (other key, other row) and never sees it. Two guests sharing one phone: the draft is what this device typed and is deleted once that guest is sent.
- **Encryption:** the whole draft is one JSON object, stored in `fields_enc` with `db.encrypt_field` and read with `db.decrypt_field` (the same MultiFernet as `ENCRYPTED_GUEST_COLUMNS` in `db.py:2327`, key rotation included). No plaintext column holds a field value, so document numbers, visa number, birth date and address are encrypted at rest. Do not add the table to `ENCRYPTED_COLUMNS` (it has no plaintext twin).
- **Never in the draft:** `passport_photo`, `signature`, `legal_ack`, `_csrf`, `guest_id`, `stay_from`, `stay_to`, `_step`. The allowlist is `guest_draft.DRAFT_FIELDS` (step 2); the server drops every other name. Each value is cut to 60 characters (the form's longest `maxlength` is 50).
- **Purge (owner rule):** `guest_draft.purge` deletes rows with `updated_at` more than 7 days ago, or whose reservation is not `active`, or whose `date_to` is before today (so the last day a draft lives is the check-out day). `load` applies the same test and deletes a stale or undecryptable row on read, so an expired draft is never shown even before the job runs. The step runs in the existing `retention.run` job (`STEPS`). **It deletes even on a dry run** (production has `UBYHOST_RETENTION_AUTOPURGE=0`, `docs/ENVIRONMENT.md:60`): a draft is never a record the dry run protects, and the owner rule must hold. Workspace deletion deletes drafts explicitly, and the reservation foreign key cascades.
- **Sent form deletes the draft:** `guest_form_save` deletes this device's draft for the reservation after a successful save of a new guest. A late autosave that lands after the save cannot bring the sent guest back: `_load_draft` drops a draft whose `doc_number`, or whose first name, surname and birth date, match a guest already on the stay. The script also stops autosaving once the form is submitted.
- **Filing never reads drafts:** only `guest_draft.py`, `routes/guest.py`, `retention.py` and the two migration files name `guest_form_draft`. A draft never creates a `guest` row, so `reporting.reservation_progress`, `submit_stay_if_complete` and the worker cannot see it. Step 5d pins both.
- **Autosave:** `initGuestDraft` in `signature.js`. Debounce 2 s after the last `input` or `change`, at most one write per 15 s, flush with `fetch(..., {keepalive: true})` on `pagehide` and on `visibilitychange` to hidden. Body: a new `FormData` with `_csrf` (read from `form.elements._csrf.value`, as `_ocr_scan.html:98-104`) and the allowlisted names only. CSRF is enforced by the existing middleware (`security.py:180` `_supplied_csrf_token`). Server throttle: own scope `guest_draft`, 60 writes per 15 min per link and peer, a bare 429 when over. No JavaScript: no autosave, no cookie, the form works as today.
- **Design (owner request, hard):** the guest form keeps its exact design. The only visible change is one line, `<p class="g-ok" id="draft-welcome" role="status">`, using the existing `.g-ok` style (`guest.css:943`, the flash line in `base.html:56`), shown only when a draft was restored. Two `data-` attributes on the form tag. No CSS change.
- **Copy:** one new i18n key `draft_welcome`, in `en cs de es fr uk` (text in step 6). The cookie gets an inventory row in all six languages.
- **No new dependency, no outbound request, no third-party script.**

### Anchors (verified on f1ca4288; re-check each with `grep -nF`)

1. `App/app/routes/guest.py:42` `CLAIM_COOKIE = "ubyhost_claim"`; `:48` `GUEST_POST_MAX_ATTEMPTS = 30`; `:23` `from fastapi.responses import JSONResponse, RedirectResponse`; `:29` the `from .. import alerts, auth, claim, ...` line.
2. `App/app/routes/guest.py:303` `def _with_lang(response, lang: str):` (new helpers go directly above it, after `_remember_claim`).
3. `App/app/routes/guest.py:1795` `    prefill, copied_from = _residence_prefill(request, reservation)` and `:1810` `    return _with_lang(render_guest(request, "guest/form.html", new_context), lang)` (inside `guest_form_new`, `:1772`).
4. `App/app/routes/guest.py:2337` `    _remember_owned(response, _owned_ids(request) + [saved_id])` (end of `guest_form_save`, `:2038`; `guest_id` is `None` for a new guest).
5. `App/app/routes/guest.py:2343` `@router.post("/l/{token}/{reservation_id}/scan")` (the new route goes directly above it).
6. `App/app/templates/guest/form.html:60` `      enctype="multipart/form-data" data-guest-wizard` and `:76` `  <noscript><p class="g-err g-nojs-note" role="alert">{{ t('nojs_needed') }}</p></noscript>`.
7. `App/app/static/signature.js:930` `  function initCheckinRail() {` (the new function goes above its comment block, which starts at `:926`); `:996` `    initLegalAck();`.
8. `App/app/templates/guest/base.html:84` and `App/app/templates/_signature_script.html:2`: `signature.js?v=20261110-1079`; `App/tests/static_versions.json:162` `"signature.js": {`.
9. `App/app/retention.py:554` `    ("guest_chats", _guest_chat_step),`; `:346` `        cur.execute(f"DELETE FROM submission WHERE apartment_id IN {apartments}", (owner_id,))`; `:196` the `# 0947: ubyhost_device` comment line.
10. `App/app/cookie_inventory.py:86` `        "set_by": "routes/guest.py:remember_claim",` (its row ends at `:95`); `:346` `    "ubyhost_claim": {` in the de/es/fr table. `App/app/guest_uk_i18n.py:98` `    "ubyhost_claim": (`.
11. `lang_draft_warning` key: `App/app/i18n.py` lines 391 (en), 1153 (cs), 1872 (de), 2414 (es), 2956 (fr); `App/app/guest_uk_i18n.py:354` (uk).
12. Migrations: `App/app/migrations/0041_claim_fee_mailed.sql` is the last (next **0042**); `App/migrations_pg/00012_claim_fee_mailed.sql` is the last (next **00013**). Model for a new table: `0040_stay_fee_rate_history.sql` and `00011_stay_fee_rate_history.sql`.
13. Schema pins to bump: `App/tests/test_migrations.py:245` (`== 41`); `App/tests/test_db_postgres.py` lines 250, 251, 290, 309, 318, 334, 345, 1055, 1068 (see step 1).
14. `App/tests/test_privacy_first.py:242` `        "ubyhost_leon",`; `App/tests/test_cookie_inventory.py:76` `    for name in ("ubyhost_owned", "ubyhost_claim", "ubyhost_guest_lang"):`.
15. `App/tests/test_guest_form_input_browser.py`: `_open_url` (42), `_fill_step_one` (27), the import line 15: the model for the browser test.
16. `docs/privacy/RETENTION.md:17` the `| Claim e-mail |` row; `docs/ENVIRONMENT.md:60` the `UBYHOST_RETENTION_AUTOPURGE` row.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0042_guest_form_draft.sql` | create | Table (step 1) |
| `App/migrations_pg/00013_guest_form_draft.sql` | create | Goose twin (step 1) |
| `App/app/guest_draft.py` | create | save, load, delete, purge (step 2) |
| `App/app/routes/guest.py` | edit | Cookie helpers, `_load_draft`, draft route, `guest_form_new`, delete on save (step 3) |
| `App/app/templates/guest/form.html` | edit | Two data attributes, the welcome line (step 4) |
| `App/app/static/signature.js` | edit | `initGuestDraft` and its init call (step 4) |
| `App/app/templates/guest/base.html`, `App/app/templates/_signature_script.html` | edit | Cache key `?v=20261110-1082` |
| `App/tests/static_versions.json` | regenerate | Only by `--write` (step 4) |
| `App/app/i18n.py`, `App/app/guest_uk_i18n.py` | edit | `draft_welcome`; uk cookie text (step 6) |
| `App/app/cookie_inventory.py` | edit | `ubyhost_draft` row and de/es/fr text (step 6) |
| `App/app/retention.py` | edit | Retention line, step, workspace delete (step 2) |
| `docs/privacy/RETENTION.md`, `docs/ENVIRONMENT.md` | edit | One row; one sentence (step 6) |
| `App/tests/test_migrations.py`, `App/tests/test_db_postgres.py` | edit | Version and table pins only (step 1) |
| `App/tests/test_privacy_first.py`, `App/tests/test_cookie_inventory.py` | edit | Add `ubyhost_draft` (step 6) |
| `App/tests/test_guest_form_draft_1082.py` | create | Unit and route tests (step 5) |
| `App/tests/test_guest_form_draft_1082_browser.py` | create | Browser tests (step 7) |
| `docs/tasks/screenshots-1082/` | create | `welcome-back-390.png`, `fresh-390.png` |
| `docs/tasks/1082-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1082 step k`)

1. **Migrations.** Confirm anchors 1 to 16 with `grep -nF`; any missing: STOP. Create `0042_guest_form_draft.sql`:
   ```sql
   -- Brief 1082 (S5, decision 7b): the server draft of an unfinished guest form.
   -- Personal data, encrypted in fields_enc. Deleted when the form is sent, else
   -- 7 days after updated_at or the day after check-out (retention.py, guest_drafts).
   CREATE TABLE IF NOT EXISTS guest_form_draft (
       id               INTEGER PRIMARY KEY AUTOINCREMENT,
       reservation_id   INTEGER NOT NULL REFERENCES reservation(id) ON DELETE CASCADE,
       device_key_hash  TEXT NOT NULL,
       claim_generation INTEGER NOT NULL DEFAULT 0,
       fields_enc       TEXT NOT NULL,
       created_at       TEXT NOT NULL,
       updated_at       TEXT NOT NULL,
       UNIQUE (reservation_id, device_key_hash)
   );
   CREATE INDEX IF NOT EXISTS idx_guest_form_draft_updated ON guest_form_draft (updated_at);
   ```
   Create `00013_guest_form_draft.sql` as the twin, modelled line for line on `00011` (anchor 12): `-- +goose Up`, a twin comment, the same table with `id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY`, `reservation_id BIGINT`, `claim_generation BIGINT`, the same index, `INSERT INTO schema_migrations (version, name, applied_at) VALUES (42, 'guest_form_draft', '2026-11-10T00:00:00+00:00') ON CONFLICT (version) DO NOTHING;`, then `-- +goose Down` with `DELETE FROM schema_migrations WHERE version = 42;` and `DROP TABLE IF EXISTS guest_form_draft;`. Pins (anchor 13), nothing else in those files: `test_migrations.py:245` `41` to `42`; `test_db_postgres.py` 250, 309, 1068 `41` to `42`; 318 and 1055 `41` to `42`; 290 `range(1, 42)` to `range(1, 43)`; 334 `schema version 41` to `42`; 345 `version=41` to `42` and `tables=70` to `tables=71`; 251 `expected_tables"] == 69` to `70` and `actual_tables"] == 70` to `71`. Run section 6 command A.
2. **`App/app/guest_draft.py`** (new; only `db`, stdlib and a lazy `from .claim import prague_today`). Module docstring naming brief 1082. Contents:
   - `MAX_AGE_DAYS = 7`, `MAX_FIELD_LENGTH = 60`, `DRAFT_FIELDS = ("party_size", "first_name", "surname", "birth_date", "nationality", "doc_number", "child_in_passport", "parent_doc_number", "visa_number", "purpose", "res_country", "res_city", "res_street")`, `_TYPED = ("first_name", "surname", "birth_date", "doc_number", "parent_doc_number", "visa_number", "res_city", "res_street")`.
   - `key_hash(device_key: str) -> str`: `hashlib.sha256(device_key.encode("utf-8")).hexdigest()`.
   - `_clean(fields) -> Dict[str, str]`: for each name in `DRAFT_FIELDS`, `str(fields.get(name) or "").strip()[:MAX_FIELD_LENGTH]`, keep non-empty only.
   - `_cutoff_iso() -> str`: now UTC minus `MAX_AGE_DAYS`, `replace(microsecond=0).isoformat()` (same format as `db.utcnow()`).
   - `save(reservation_id: int, device_hash: str, generation: int, fields) -> bool`: `clean = _clean(fields)`; if no `_TYPED` name is in `clean`, call `delete(...)` and return False. Else one `db.execute` of `INSERT INTO guest_form_draft (reservation_id, device_key_hash, claim_generation, fields_enc, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (reservation_id, device_key_hash) DO UPDATE SET claim_generation = excluded.claim_generation, fields_enc = excluded.fields_enc, updated_at = excluded.updated_at` with `db.encrypt_field(json.dumps(clean, ensure_ascii=False, sort_keys=True))` and `db.utcnow()` twice. Return True.
   - `delete(reservation_id: int, device_hash: str) -> int`: `db.execute_rowcount("DELETE FROM guest_form_draft WHERE reservation_id = ? AND device_key_hash = ?", ...)`.
   - `load(reservation_id: int, device_hash: str, generation: int, today: Optional[date] = None) -> Optional[Dict[str, str]]`: `today = today or prague_today()`. `db.query_one` selecting `d.id, d.claim_generation, d.fields_enc, d.updated_at, r.status, r.date_to` from `guest_form_draft d JOIN reservation r ON r.id = d.reservation_id` for the pair. None: return None. Fresh means `r.status == "active"`, `str(date_to)[:10] >= today.isoformat()`, `updated_at >= _cutoff_iso()`, `int(claim_generation) == int(generation)`. If fresh, `json.loads(db.decrypt_field(row["fields_enc"]) or "")` inside `try/except (ValueError, TypeError)`. Not fresh, or not a dict: `DELETE ... WHERE id = ?` and return None. Else return `_clean(value)`.
   - `purge(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int`: `where = "(reservation_id IN (SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE (? IS NULL OR a.owner_user_id = ?) AND (r.status <> 'active' OR " + db.sqlite_date_expr("r.date_to") + " < ?)) OR (updated_at < ? AND reservation_id IN (SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE (? IS NULL OR a.owner_user_id = ?))))"` with params `(owner, owner, today.isoformat(), _cutoff_iso(), owner, owner)`. Count with `SELECT COUNT(*) AS n`, then always `DELETE ... WHERE {where}` when the count is above 0 (`dry_run` is accepted and ignored, see section 2; say so in the docstring). Log the count only. Return the count.
   In `retention.py`: under anchor 9's `# 0947` line add `# 1082: guest_form_draft (an unfinished guest form, encrypted) goes when the form is sent, else 7 days after its last change or the day after check-out, whichever comes first (guest_drafts step, also on a dry run; workspace deletion).` Above the `# Each step takes` comment (line 534) add `def _guest_draft_step(today, dry_run, owner_user_id) -> int:` (typed like `_guest_chat_step`, `:528`) with a one-line docstring, `from . import guest_draft` and `return guest_draft.purge(today, dry_run, owner_user_id)`. After anchor 9's `guest_chats` line add `    ("guest_drafts", _guest_draft_step),`. Directly above anchor 9's `DELETE FROM submission` line add, at the same indent, `cur.execute("DELETE FROM guest_form_draft WHERE reservation_id IN " f"(SELECT id FROM reservation WHERE apartment_id IN {apartments})", (owner_id,))` written as the `DELETE FROM guest` call above it (lines 342-345). Run command A.
3. **Routes (`routes/guest.py`).** Add `guest_draft` to anchor 1's `from .. import` line (alphabetical, after `guest_uk_i18n`), `Response` to the `fastapi.responses` import, and `import secrets` with the stdlib imports if it is not there (`grep -n "^import secrets"`). Under anchor 1's `CLAIM_COOKIE` add `DRAFT_COOKIE = "ubyhost_draft"` and `DRAFT_COOKIE_MAX_AGE = 60 * 60 * 24 * 7`; under `GUEST_POST_MAX_ATTEMPTS` add `GUEST_DRAFT_MAX_WRITES = 60`. Above anchor 2:
   - `_draft_key(request) -> Optional[str]`: the cookie value if it is 32 to 64 characters of `A-Za-z0-9_-` (`re.fullmatch`), else None.
   - `_remember_draft_key(response, key: str) -> None`: `response.set_cookie(DRAFT_COOKIE, key, max_age=DRAFT_COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=auth.secure_cookies(), path="/")`.
   - `_draft_generation(reservation) -> int`: 0 unless `mail.mail_enabled()`; then `row = claim.ensure_row(reservation["id"])` and `int(row["token_version"] or 0) if row else 0`.
   - `_load_draft(request, reservation, guests) -> Optional[dict]`: no key: None. `values = guest_draft.load(reservation["id"], guest_draft.key_hash(key), _draft_generation(reservation))`. If values and a guest in `guests` has the same `doc_number` (compare `.strip().upper()`, both non-empty), or the same `first_name`, `surname` and `birth_date` (all three non-empty, `.strip().casefold()`): `guest_draft.delete(...)` and return None. Else return values. Log nothing about values.
   New route directly above anchor 5:
   ```python
   @router.post("/l/{token}/{reservation_id}/draft")
   async def guest_form_draft(token: str, reservation_id: int, request: Request):
       """Brief 1082: autosave of the unfinished new-guest form. Never filed."""
   ```
   Body, in this order: `lang`, `_open_link` (return `early`), `_require_pin`, `_reservation_for_guest` (None: `Response(status_code=404)`), throttle (`key = rate_limit.client_key(request, f"guest_draft:{_lock_token(token)}")`; `rate_limit.blocked("guest_draft", key, GUEST_DRAFT_MAX_WRITES)`: `Response(status_code=429)`; else `rate_limit.record("guest_draft", key)`), `_require_claim_session` (any guard: `Response(status_code=403)`), `_host_owns_apartment(request, apartment)`: `Response(status_code=204)`. `int(request.headers.get("content-length") or 0) > 16384`: `Response(status_code=413)`. `form = await request.form()`; a non-empty `guest_id`: 204, nothing saved. Device key from `_draft_key`, else `secrets.token_urlsafe(32)` and remember that it is new. `fields = {n: form.get(n) for n in guest_draft.DRAFT_FIELDS if isinstance(form.get(n), str)}`. `guest_draft.save(reservation_id, guest_draft.key_hash(device_key), _draft_generation(reservation), fields)`. Return `Response(status_code=204)`, with `_remember_draft_key` when the key is new.
   In `guest_form_new`, replace anchor 3's `prefill` line with:
   ```python
       prefill, copied_from = _residence_prefill(request, reservation)
       draft_on = not _host_owns_apartment(request, apartment)
       draft_values = _load_draft(request, reservation, progress["guests"]) if draft_on else None
       if draft_values:
           prefill = {**dict(prefill or {}), **draft_values}
   ```
   and directly above anchor 3's `return` add `new_context["draft_restored"] = bool(draft_values)` and, under `if draft_on:`, `new_context["draft_url"] = f"/l/{token}/{reservation_id}/draft" + _lang_q(lang)` and `new_context["draft_fields"] = " ".join(guest_draft.DRAFT_FIELDS)`. Directly above anchor 4 add:
   ```python
       if not guest_id:
           draft_key = _draft_key(request)
           if draft_key:
               guest_draft.delete(reservation_id, guest_draft.key_hash(draft_key))
   ```
   Change nothing else in `guest_form_save`. Run command A.
4. **Template and script.** `form.html` anchor 6 line becomes `      enctype="multipart/form-data" data-guest-wizard{% if draft_url %} data-draft-url="{{ draft_url }}" data-draft-fields="{{ draft_fields }}"{% endif %}`. Directly under the `<noscript>` line add `  {% if draft_restored %}<p class="g-ok" id="draft-welcome" role="status">{{ t('draft_welcome') }}</p>{% endif %}`. Nothing else in `form.html`. In `signature.js`, above anchor 7's comment block, add a comment (what, why, no JavaScript means no draft) and `function initGuestDraft()`, 2-space indent like its neighbours:
   - Return early unless `#guest-form` has `data-draft-url` and `window.fetch` and `window.FormData` exist.
   - `DEBOUNCE_MS = 2000`, `MIN_GAP_MS = 15000`; state `timer`, `last = 0`, `dirty = false`, `stopped = false`.
   - `body()`: `new FormData()`, append `_csrf` from `form.elements._csrf.value`, then for each name of `data-draft-fields`: a checkbox appends `"1"` only when checked; any other element appends its `value`.
   - `send(keepalive)`: if `stopped || !dirty` return; `dirty = false; last = Date.now();` `fetch(url, {method: "POST", body: body(), credentials: "same-origin", keepalive: !!keepalive}).catch(function () { dirty = true; });`.
   - `schedule()`: if `stopped` return; `dirty = true`; clear `timer`; wait `Math.max(DEBOUNCE_MS, MIN_GAP_MS - (Date.now() - last))`, then `send(false)`.
   - Listeners: `form` `input` and `change` call `schedule`; `window` `pagehide` and `document` `visibilitychange` (only when `document.visibilityState === "hidden"`) clear the timer and `send(true)`; `form` `submit`: if `event.defaultPrevented` return (the offline hold of `initSaveRetry` keeps autosave on), else `stopped = true` and clear the timer.
   - It never reads `#passport_photo`, `#signature` or `#legal_ack`, never writes any field, and never touches the DOM.
   Add `    initGuestDraft();` directly under anchor 7's `initLegalAck();`. Bump both cache keys (anchor 8) to `20261110-1082`. From `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30` and commit `tests/static_versions.json` (diff: only the `signature.js` entry). If you edit `signature.js` again later, bump to `20261110-1082b` and rerun it.
5. **`App/tests/test_guest_form_draft_1082.py`** (no browser). Seed with `_cleanup`, `_seed`, `_payload` of `App/tests/test_guest_child_document.py` (read lines 39 to 130 only); routes with `TestClient` as that file does; mail off unless a test says otherwise. Synthetic data only (`SYN...` document numbers).
   a. **Save and load:** `guest_draft.save` then `load` returns the cleaned fields; a second save updates the same row (one row, newer `updated_at`); a dict with `passport_photo`, `signature`, `legal_ack`, `stay_from`, `guest_id` keeps none of them; a 200-character surname comes back 60 long; party size and nationality only: nothing stored.
   b. **Encrypted at rest:** after a save with `doc_number="SYN1082X"`, the raw `fields_enc` (`db.query_one("SELECT fields_enc ...")`) does not contain `SYN1082X`, no column of the row does, and `db.decrypt_field` of it gives JSON with it.
   c. **Isolation:** device A saves; `load` with device B's hash on the same reservation is None; A's draft on reservation 1 is None for A on reservation 2; a bumped generation returns None and deletes the row. Route level: client A posts `/draft` with fields, client B (own cookie jar) opens `/new`: no `draft-welcome`, none of A's values in the HTML; client A opens `/new`: `draft-welcome` present and the values filled; the `ubyhost_draft` cookie is HttpOnly and SameSite=Lax; the DB holds `key_hash(cookie)`, never the cookie value.
   d. **Filing never reads drafts:** (1) every file under `App/app/` that contains `guest_form_draft` is one of `guest_draft.py`, `routes/guest.py`, `retention.py`, `migrations/0042_guest_form_draft.sql`; `App/app/reporting.py`, `worker.py`, `housebook.py`, `deadlines.py`, `filing_watchdog.py`, `stay_fee_filing.py` and every file in `App/app/ubyport/` contain neither `guest_form_draft` nor `guest_draft`. (2) A stay with a full draft and no guest: `reporting.reservation_progress(reservation)["filled"] == 0`, `reporting.submit_stay_if_complete(apartment_id, reservation_id)` creates no `submission` row and no `guest` row.
   e. **Sent deletes:** post `/draft`, then a valid `/save` of a new guest from the same client: no draft row left; `/new` shows no welcome line. A draft written after the save with the sent guest's doc number: `/new` shows no welcome line and the row is gone.
   f. **Purge (owner rule):** with `retention.run(today=..., dry_run=True)` and `dry_run=False`: a draft changed 8 days ago goes; one changed 6 days ago on a stay ending tomorrow stays; one on a stay whose `date_to` is yesterday goes; one whose `date_to` is today stays; a cancelled stay's draft goes; `owner_user_id` of another owner deletes nothing of this owner. `counts["guest_drafts"]` is the number deleted. Workspace deletion of the owner removes its drafts. `load` of a stale row returns None and deletes it.
   g. **Throttle and CSRF:** a `/draft` post without `_csrf` is refused like the existing guest posts (assert the same status the middleware gives `/save` without it); the 61st post inside the window answers 429 and stores nothing new; a body over 16 KB answers 413.
   h. **No draft surfaces:** `/edit/{guest_id}` renders no `data-draft-url`; the host preview of `/new` renders none; with `guest_id` in the post nothing is stored.
   Run command B.
6. **Copy, cookie, docs.** `draft_welcome` directly under each `lang_draft_warning` line (anchor 11): en `"Welcome back. Continue where you left off."`, cs `"Vítejte zpět. Pokračujte tam, kde jste skončili."`, de `"Willkommen zurück. Machen Sie dort weiter, wo Sie aufgehört haben."`, es `"Bienvenido de nuevo. Continúe donde lo dejó."`, fr `"Bon retour. Reprenez là où vous vous êtes arrêté."`, uk `"З поверненням. Продовжте з того місця, де зупинилися."`. Cookie row after the `ubyhost_claim` row (anchor 10), same keys: `"name": "ubyhost_draft"`, `"set_by": "routes/guest.py:remember_draft_key"`, `"surface": "guest"`, purpose en `"Keeps your unfinished form on this device so you can continue it"`, cs `"Uchová rozpracovaný formulář na tomto zařízení, abyste mohli pokračovat"`, lifetime en `"7 days"`, cs `"7 dní"`. de/es/fr entry after `"ubyhost_claim": {` block: de `"Bewahrt Ihr nicht fertiges Formular auf diesem Gerät auf, damit Sie weitermachen können"` / `"7 Tage"`, es `"Guarda su formulario sin terminar en este dispositivo para que pueda continuarlo"` / `"7 días"`, fr `"Conserve votre formulaire inachevé sur cet appareil pour que vous puissiez le reprendre"` / `"7 jours"`. uk after anchor 10's uk line: `"ubyhost_draft": ("Зберігає незавершену форму на цьому пристрої, щоб ви могли продовжити", "7 днів"),`. `test_privacy_first.py`: add `"ubyhost_draft",` under anchor 14's line. `test_cookie_inventory.py`: after anchor 14's loop add `assert "7 days" in rows["ubyhost_draft"]["lifetime"]["en"]` and `assert guest.DRAFT_COOKIE_MAX_AGE == 60 * 60 * 24 * 7` (import `from app.routes import guest` if missing). `RETENTION.md`: under anchor 16's row add `| Unfinished guest form (draft) | \`guest_form_draft\` (encrypted) | last change, check-out | sent: at once; else 7 days after the last change or the day after check-out, whichever is first | \`retention.py\` guest-drafts step (also on a dry run), on read, on send | Storage limitation |`. `ENVIRONMENT.md:60`: append ` Guest form drafts (1082) are deleted on every run.` to the description cell. Run commands B and C.
7. **`App/tests/test_guest_form_draft_1082_browser.py`**, modelled on anchor 15 (`_open_url` with mail off, `_fill_step_one`, `Guest`, `browser`, `live_server`). One `browser.new_context(viewport={"width": 390, "height": 812})` per device:
   a. **Close and return at 390 px:** fill step one, wait for the `/draft` response (`page.expect_response` on `**/draft*`, status 204), `page.close()`, open a new page in the **same** context at the same URL: `#draft-welcome` visible with the English text, every step-one field has the typed value, the signature and photo are empty, the wizard is on step one, no horizontal scroll (`scrollWidth <= innerWidth`), `Guest.check_layout` where it fits. Screenshot `docs/tasks/screenshots-1082/welcome-back-390.png` (full page).
   b. **Another device:** a second context opens the same URL: no `#draft-welcome`, `#first_name` empty. Screenshot `fresh-390.png`.
   c. **Throttle in the page:** type into `#surname` ten times within 3 s: at most one `/draft` request in those 3 s (count with `page.on("request")`).
   d. **Sent:** complete and send the form as `test_guest_browser_e2e.py` does for one guest, then open `/new` again in the same context: no `#draft-welcome`, fields empty.
   e. **Design unchanged:** on the restored page, record the `#first_name` top and the step-one card's height, then remove `#draft-welcome` with `page.evaluate`: the card's height and the field's top drop by the line's own height plus its vertical margins, within 1 px, and nothing else moves sideways (same `left` and `width` for every `.g-field` on step one). On the fresh page (b) there is no `#draft-welcome` at all.
   f. **No JavaScript** (`java_script_enabled=False`, as `test_guest_form_input_browser.py:87`): the form renders, no `ubyhost_draft` cookie is set after typing and submitting nothing, no `#draft-welcome`.
   Look at each screenshot once and write one line each in the report. Run command D.
8. Run section 6, then write the report.

## 5. Do not touch

`reporting.py`, `validation.py`, `worker.py`, `housebook.py`, `deadlines.py`, `submit_*`, `App/app/ubyport/`, `stay_fee*.py`, `_ocr_scan.html`, `guest_form_admin.html`, archive templates, any CSS file, `db.py` (no edit to `SCHEMA`, `ADDED_COLUMNS` or `ENCRYPTED_COLUMNS`), any route but `guest_form_new`, `guest_form_save` (the one block in step 3) and the new route, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`:
- A: `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_postgres.py tests/test_retention_job.py -q --tb=short -x -rs` (Postgres tests may skip locally without a server; CI runs them; note it in the report).
- B: `.venv/bin/python -m pytest tests/test_guest_form_draft_1082.py tests/test_retention.py tests/test_retention_alignment.py tests/test_retention_job.py tests/test_pii_encryption.py tests/test_static_versions.py -q --tb=short -x`.
- C: `.venv/bin/python -m pytest tests/test_privacy_first.py tests/test_cookie_inventory.py tests/test_no_tracking.py tests/test_guest_languages.py tests/test_no_em_dashes.py tests/test_guest_child_document.py tests/test_guest_child_visa_1079.py tests/test_endtoend.py -q --tb=short -x`.
- D (0 skipped): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_form_draft_1082_browser.py tests/test_guest_form_input_browser.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`.
- Test-map guest row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py -q --tb=short -x -rs` (0 skipped).

Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Close and return on the same device at 390 px: "Welcome back. Continue where you left off." and the typed fields; another device on the same booking sees nothing; photo and signature never stored.
- [ ] Draft keyed by `(reservation_id, sha256(device key))` plus claim generation; the cookie value is never stored.
- [ ] `fields_enc` holds no plaintext document number (test 5b).
- [ ] Sent form deletes the draft; purge test pins 7 days and the day after check-out, on a dry run too; workspace deletion removes drafts; retention line in `retention.py` and a row in `RETENTION.md`.
- [ ] Filing pin (test 5d) green: no filing module names the table; a draft-only stay files nothing.
- [ ] Autosave debounced (2 s) and throttled (15 s client, 60 per 15 min server); CSRF refused without the token; no JavaScript: the form works, no cookie.
- [ ] Migrations 0042 and goose 00013 present; schema pins bumped; command A green.
- [ ] Browser tests 0 skipped; layout lint run (guest pages report-only, findings in the report); two 390 px screenshots in `docs/tasks/screenshots-1082/`.
- [ ] `git diff --stat origin/main` touches only section 3 files; guest form design unchanged apart from the one line; cache keys bumped and `static_versions.json` regenerated.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; `db.execute` cannot run the `ON CONFLICT ... DO UPDATE` upsert on SQLite or Postgres; the change would need a filing, CSS or `db.py` edit; a cookie or privacy test needs a change beyond step 6; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1082-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per screenshot on what you saw, layout-lint findings for the guest form, deviations, questions. Set this brief `Status: review`. After the fresh Fable diff review, open one PR. The PR body states: new personal-data table with retention line, new strictly-necessary cookie `ubyhost_draft`, encrypted at rest, filing untouched, no new outbound request, no dependency. Merge only with `scripts/merge-pr-on-green.sh`.

## 10. Open questions (not blocking)

- **Q1:** the relang and 422 re-renders do not autosave (scope). If the owner wants it, a follow-up adds `draft_url` to `_form_context` for new guests.
- **Q2:** the purge ignores the retention dry run for drafts. If the owner prefers the dry-run contract to hold, drafts would then stay up to the read-time check only; the owner decides.
