# 1082: S5 server draft of an unfinished guest form: storage, route, purge (ships dark)

Status: review
Tier: A | Depends on: nothing (main alone) | Base commit: f1ca4288 | Branch: claude/1082-guest-form-draft
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: a fresh Fable reviews the diff against this brief before the PR opens.
Report: docs/tasks/1082-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md): decision **7b** and queue item **S5**, "Server draft (decision 7b): 'Welcome back. Continue where you left off.'". Benefit: closing the tab loses nothing. S13 (poor signal) depends on this and is not built here.

This brief is the server half: the table, the encrypted store, the autosave route, loading a draft into the new-guest form's values, deleting the draft on send, and the purge. **It ships dark**: nothing in the page posts to `/draft` yet, so no guest gets a draft or the cookie until [1087](1087-guest-form-draft-ui.md) adds the script, the form attributes and the "Welcome back" line.

**Owner rule (confirmed 2026-11-10):** the draft is deleted when the form is sent; otherwise 7 days after its last change or the day after check-out, whichever comes first.

**Tier A (orchestrator decision):** a new personal-data table, a new cookie, encryption at rest, a purge, and code next to the guest form. Filing stays byte-identical.

## 2. Context

### Design decisions (fixed; do not reopen)

- **Scope:** only the new-guest form, `GET /l/{token}/{reservation_id}/new` (`guest_form_new`). No draft for an edit of a saved guest (`/edit/{guest_id}`), for the host preview (`_host_owns_apartment`), or for the relang and 422 re-renders (they keep their posted values as today).
- **Keying (privacy):** a row is keyed by `(reservation_id, device_key_hash)`. The device key is `secrets.token_urlsafe(32)` in a new strictly-necessary cookie `ubyhost_draft` (HttpOnly, SameSite=Lax, Secure like the other guest cookies, path `/`, 7 days), set only by the first `/draft` post. The server stores only the `sha256` hex of the key. The row also stores:
  - `claim_generation`: `reservation_claim.token_version` when mail is on, else 0. A draft loads only for the same device key **and** the same generation, so a host release or a fresh claim secret cuts the old device off.
  - `owned_count`: how many guests this device had already sent when the page was rendered (`len(_owned_ids(request))`, posted back as `draft_owned`, clamped 0 to 40, the cap of `_remember_owned`). On load, a draft whose `owned_count` differs from the device's current count is deleted. A late autosave from the page of a guest who was just sent carries the old count, so it can never fill the next person's form on the same phone.
  Another guest of the same booking is on another device: another key, another row, nothing visible.
- **Encryption:** the whole draft is one JSON object in `fields_enc`, written with `db.encrypt_field` and read with `db.decrypt_field` (the MultiFernet behind `ENCRYPTED_GUEST_COLUMNS`, `db.py:2327`, key rotation included). No plaintext column holds a field value. Do not add the table to `ENCRYPTED_COLUMNS` (it has no plaintext twin).
- **Never in the draft:** `passport_photo`, `signature`, `legal_ack`, `_csrf`, `guest_id`, `stay_from`, `stay_to`, `_step`. The allowlist is `guest_draft.DRAFT_FIELDS`; the server drops every other name. Each value is cut to 60 characters (the form's longest `maxlength` is 50).
- **Purge (owner rule):** `guest_draft.purge()` deletes rows with `updated_at` more than 7 days ago, or whose reservation is not `active`, or whose `date_to` is before today (Prague date; the last day a draft lives is the check-out day). It runs in the 12-hour `_job_photo_sweep` (`scheduler.py:312`), next to `passport_photos.purge_stale`, the existing non-dry-run precedent. It is **not** a `retention.STEPS` entry: every step there honours the dry run (`test_retention_alignment.py:447`), and the owner rule must hold with `UBYHOST_RETENTION_AUTOPURGE=0`. `load` applies the same test and deletes a stale, foreign-generation, wrong-count or undecryptable row on read. Workspace deletion deletes drafts explicitly; the reservation foreign key cascades.
- **Sent form deletes the draft:** after a successful save of a new guest, `guest_form_save` deletes this device's draft for the stay. Belt and braces: `_load_draft` also drops a draft whose `doc_number`, or whose first name, surname and birth date, match a guest already on the stay.
- **Filing never reads drafts:** only `guest_draft.py`, `routes/guest.py`, `retention.py`, `scheduler.py` and the migration file under `App/app/` name the table or the module. A draft never creates a `guest` row, so `reporting.reservation_progress`, `submit_stay_if_complete` and the worker cannot see it. Test 5d pins both.
- **Throttle and CSRF:** own rate-limit scope `guest_draft`, 120 writes per 15 min per link and peer, a bare 429 when over (the 1087 script writes at most once per 15 s). CSRF is the existing middleware (`security.py:180`, `_supplied_csrf_token`), as for every guest POST.
- **Copy:** none here. The cookie gets its inventory row in all six languages (step 4). The `draft_welcome` key is 1087's.
- **No new dependency, no outbound request, no third-party script.**

### Anchors (verified on f1ca4288; re-check each with `grep -nF`)

1. `App/app/routes/guest.py:42` `CLAIM_COOKIE = "ubyhost_claim"`; `:48` `GUEST_POST_MAX_ATTEMPTS = 30`; `:23` `from fastapi.responses import JSONResponse, RedirectResponse`; `:29` the `from .. import alerts, auth, claim, ...` line.
2. `App/app/routes/guest.py:303` `def _with_lang(response, lang: str):` (new helpers go directly above it, after `_remember_claim`).
3. `App/app/routes/guest.py:1795` `    prefill, copied_from = _residence_prefill(request, reservation)` and `:1810` `    return _with_lang(render_guest(request, "guest/form.html", new_context), lang)` (in `guest_form_new`, `:1772`).
4. `App/app/routes/guest.py:2337` `    _remember_owned(response, _owned_ids(request) + [saved_id])` (end of `guest_form_save`, `:2038`; `guest_id` is `None` for a new guest).
5. `App/app/routes/guest.py:2343` `@router.post("/l/{token}/{reservation_id}/scan")` (the new route goes directly above it).
6. `App/app/scheduler.py:333` `        signup_counts = signup.purge()` (in `_job_photo_sweep`); the `from . import (` list at `:14` with `    guest_guide_import,`.
7. `App/app/retention.py:196` the `# 0947: ubyhost_device` comment line; `:346` `        cur.execute(f"DELETE FROM submission WHERE apartment_id IN {apartments}", (owner_id,))`.
8. `App/app/cookie_inventory.py:86` `        "set_by": "routes/guest.py:remember_claim",` (its row ends at `:95`); `:346` `    "ubyhost_claim": {` in the de/es/fr table. `App/app/guest_uk_i18n.py:98` `    "ubyhost_claim": (`.
9. Migrations: `App/app/migrations/0041_claim_fee_mailed.sql` is the last (next **0042**); `App/migrations_pg/00012_claim_fee_mailed.sql` is the last (next **00013**). Model for a new table: `0040_stay_fee_rate_history.sql` and `00011_stay_fee_rate_history.sql`.
10. Schema pins: `App/tests/test_migrations.py:245` (`== 41`); `App/tests/test_db_postgres.py` version pins at 250, 290, 309, 318, 334, 345, 1055, 1068 and table pins at 251, 345, 944, 1016, 1032, 1077, 1081, 1137, 1311 (step 1).
11. `App/tests/test_privacy_first.py:161` `def test_a_full_crawl_sets_exactly_the_strictly_necessary_cookies`; its `/save` post at `:190` (`        saved = guest.post(`); `:242` `        "ubyhost_leon",`. `App/tests/test_cookie_inventory.py:76` `    for name in ("ubyhost_owned", "ubyhost_claim", "ubyhost_guest_lang"):`.
12. `docs/privacy/RETENTION.md:17` the `| Claim e-mail |` row; `docs/privacy/ROPA.md:25` the `| Retention | \`RETENTION.md\` (LD-3)` row of section A.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0042_guest_form_draft.sql` | create | Table (step 1) |
| `App/migrations_pg/00013_guest_form_draft.sql` | create | Goose twin (step 1) |
| `App/app/guest_draft.py` | create | save, load, delete, purge (step 2) |
| `App/app/scheduler.py` | edit | Purge call in `_job_photo_sweep` (step 2) |
| `App/app/retention.py` | edit | Retention comment, workspace delete (step 2) |
| `App/app/routes/guest.py` | edit | Cookie helpers, `_load_draft`, the draft route, `guest_form_new`, delete on save (step 3) |
| `App/app/cookie_inventory.py`, `App/app/guest_uk_i18n.py` | edit | `ubyhost_draft` row and its texts (step 4) |
| `docs/privacy/RETENTION.md`, `docs/privacy/ROPA.md` | edit | One row each (step 4) |
| `App/tests/test_migrations.py`, `App/tests/test_db_postgres.py` | edit | Version and table pins only (step 1) |
| `App/tests/test_privacy_first.py`, `App/tests/test_cookie_inventory.py` | edit | Crawl reaches `/draft`; `ubyhost_draft` (step 4) |
| `App/tests/test_guest_form_draft_1082.py` | create | Unit and route tests (step 5) |
| `docs/tasks/1082-report.md` | create | Report, plus `Status: review` here |

## 4. Steps (commit after each: `1082 step k`)

1. **Migrations.** Confirm anchors 1 to 12 with `grep -nF`; any missing: STOP. Create `0042_guest_form_draft.sql`:
   ```sql
   -- Brief 1082 (S5, decision 7b): the server draft of an unfinished guest form.
   -- Personal data, encrypted in fields_enc. Deleted when the form is sent, else
   -- 7 days after updated_at or the day after check-out (guest_draft.purge).
   CREATE TABLE IF NOT EXISTS guest_form_draft (
       id               INTEGER PRIMARY KEY AUTOINCREMENT,
       reservation_id   INTEGER NOT NULL REFERENCES reservation(id) ON DELETE CASCADE,
       device_key_hash  TEXT NOT NULL,
       claim_generation INTEGER NOT NULL DEFAULT 0,
       owned_count      INTEGER NOT NULL DEFAULT 0,
       fields_enc       TEXT NOT NULL,
       created_at       TEXT NOT NULL,
       updated_at       TEXT NOT NULL,
       UNIQUE (reservation_id, device_key_hash)
   );
   CREATE INDEX IF NOT EXISTS idx_guest_form_draft_updated ON guest_form_draft (updated_at);
   ```
   Create `00013_guest_form_draft.sql` as the twin, line for line on `00011` (anchor 9): `-- +goose Up`, a twin comment, the same table with `id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY`, `reservation_id BIGINT`, `claim_generation BIGINT`, `owned_count BIGINT`, the same index, `INSERT INTO schema_migrations (version, name, applied_at) VALUES (42, 'guest_form_draft', '2026-11-10T00:00:00+00:00') ON CONFLICT (version) DO NOTHING;`, then `-- +goose Down` with `DELETE FROM schema_migrations WHERE version = 42;` and `DROP TABLE IF EXISTS guest_form_draft;`.
   Pins (anchor 10), nothing else in those files: `test_migrations.py:245` `41` to `42`. `test_db_postgres.py`: 250, 309, 318, 1055, 1068 `41` to `42`; 290 `range(1, 42)` to `range(1, 43)`; 334 `schema version 41` to `42`; 345 `version=41` to `42` and `tables=70` to `tables=71`; 251 `expected_tables"] == 69` to `70` and `actual_tables"] == 70` to `71`; 944, 1016, 1032, 1077, 1081, 1137, 1311 `69` to `70`. Then `grep -n "\b69\b\|\b41\b" tests/test_db_postgres.py` must show no other pin of either (line 1302's `42` is a sequence value, leave it). Run section 6 command A.
2. **`App/app/guest_draft.py`** (new; only `db`, stdlib and a lazy `from .claim import prague_today`). Module docstring naming brief 1082. Contents:
   - `MAX_AGE_DAYS = 7`, `MAX_FIELD_LENGTH = 60`, `MAX_OWNED = 40`, `DRAFT_FIELDS = ("party_size", "first_name", "surname", "birth_date", "nationality", "doc_number", "child_in_passport", "parent_doc_number", "visa_number", "purpose", "res_country", "res_city", "res_street")`, `_TYPED = ("first_name", "surname", "birth_date", "doc_number", "parent_doc_number", "visa_number", "res_city", "res_street")`.
   - `key_hash(device_key: str) -> str`: `hashlib.sha256(device_key.encode("utf-8")).hexdigest()`.
   - `clamp_owned(value) -> int`: `int(value)` clamped to 0..`MAX_OWNED`; anything not an int: 0.
   - `_clean(fields) -> Dict[str, str]`: for each name in `DRAFT_FIELDS`, `str(fields.get(name) or "").strip()[:MAX_FIELD_LENGTH]`, keep non-empty only.
   - `_cutoff_iso() -> str`: now UTC minus `MAX_AGE_DAYS`, `replace(microsecond=0).isoformat()` (the format of `db.utcnow()`).
   - `save(reservation_id: int, device_hash: str, generation: int, owned_count: int, fields) -> bool`: `clean = _clean(fields)`; if no `_TYPED` name is in `clean`, `delete(...)` and return False. Else one `db.execute`: `INSERT INTO guest_form_draft (reservation_id, device_key_hash, claim_generation, owned_count, fields_enc, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (reservation_id, device_key_hash) DO UPDATE SET claim_generation = excluded.claim_generation, owned_count = excluded.owned_count, fields_enc = excluded.fields_enc, updated_at = excluded.updated_at`, with `clamp_owned(owned_count)`, `db.encrypt_field(json.dumps(clean, ensure_ascii=False, sort_keys=True))` and `db.utcnow()` twice. Return True.
   - `delete(reservation_id: int, device_hash: str) -> int`: `db.execute_rowcount("DELETE FROM guest_form_draft WHERE reservation_id = ? AND device_key_hash = ?", ...)`.
   - `load(reservation_id: int, device_hash: str, generation: int, owned_count: int, today: Optional[date] = None) -> Optional[Dict[str, str]]`: `today = today or prague_today()`. `db.query_one` selecting `d.id, d.claim_generation, d.owned_count, d.fields_enc, d.updated_at, r.status, r.date_to` from `guest_form_draft d JOIN reservation r ON r.id = d.reservation_id` for the pair. None: return None. Fresh means `r.status == "active"`, `str(date_to)[:10] >= today.isoformat()`, `updated_at >= _cutoff_iso()`, `int(claim_generation) == int(generation)` and `int(row["owned_count"]) == clamp_owned(owned_count)`. If fresh, `json.loads(db.decrypt_field(row["fields_enc"]) or "")` in `try/except (ValueError, TypeError)`. Not fresh, or not a dict: `DELETE ... WHERE id = ?`, return None. Else return `_clean(value)`.
   - `purge(today: Optional[date] = None) -> int`: `today = today or prague_today()`. `where = "updated_at < ? OR reservation_id IN (SELECT r.id FROM reservation r WHERE r.status <> 'active' OR " + db.sqlite_date_expr("r.date_to") + " < ?)"`, params `(_cutoff_iso(), today.isoformat())`. Return `db.execute_rowcount(f"DELETE FROM guest_form_draft WHERE {where}", params)`. Log the count only. Docstring: the owner rule, and why it is not a retention step (section 2).
   In `scheduler.py`: add `    guest_draft,` to the `from . import (` list directly above anchor 6's `guest_guide_import,`. Directly above anchor 6's `signup_counts` line, at its indent, add a `# Brief 1082:` comment (owner rule, runs with autopurge off too) and:
   ```python
           drafts = guest_draft.purge()
           if drafts:
               log.info("guest draft purge deleted %s draft(s)", drafts)
   ```
   In `retention.py`: under anchor 7's `# 0947` line add `# 1082: guest_form_draft (an unfinished guest form, encrypted) goes when the form is sent, else 7 days after its last change or the day after check-out, whichever comes first (guest_draft.purge in the 12-hour photo sweep, never a dry run; workspace deletion below).` Directly above anchor 7's `DELETE FROM submission` line add, at the same indent and written like the `DELETE FROM guest` call above it (lines 342-345), `cur.execute("DELETE FROM guest_form_draft WHERE reservation_id IN " f"(SELECT id FROM reservation WHERE apartment_id IN {apartments})", (owner_id,))`. Do not add a `STEPS` entry. Run command A.
3. **Routes (`routes/guest.py`).** Add `guest_draft` to anchor 1's `from .. import` line (after `guest_uk_i18n`), `Response` to the `fastapi.responses` import, and `import secrets` / `import re` with the stdlib imports if missing (`grep -n "^import secrets\|^import re$"`). Under `CLAIM_COOKIE` add `DRAFT_COOKIE = "ubyhost_draft"` and `DRAFT_COOKIE_MAX_AGE = 60 * 60 * 24 * 7`; under `GUEST_POST_MAX_ATTEMPTS` add `GUEST_DRAFT_MAX_WRITES = 120`. Above anchor 2:
   - `_draft_key(request) -> Optional[str]`: the cookie value if `re.fullmatch(r"[A-Za-z0-9_-]{32,64}", value)`, else None.
   - `_remember_draft_key(response, key: str) -> None`: `response.set_cookie(DRAFT_COOKIE, key, max_age=DRAFT_COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=auth.secure_cookies(), path="/")`.
   - `_draft_generation(reservation) -> int`: 0 unless `mail.mail_enabled()`; then `row = claim.ensure_row(reservation["id"])`, `int(row["token_version"] or 0) if row else 0`.
   - `_draft_owned(request) -> int`: `guest_draft.clamp_owned(len(_owned_ids(request)))`.
   - `_load_draft(request, reservation, guests) -> Optional[dict]`: no key: None. `values = guest_draft.load(reservation["id"], guest_draft.key_hash(key), _draft_generation(reservation), _draft_owned(request))`. If values and a guest in `guests` has the same `doc_number` (`.strip().upper()`, both non-empty) or the same `first_name`, `surname` and `birth_date` (all non-empty, `.strip().casefold()`): `guest_draft.delete(...)`, return None. Else return values. Log nothing about values.
   New route directly above anchor 5:
   ```python
   @router.post("/l/{token}/{reservation_id}/draft")
   async def guest_form_draft(token: str, reservation_id: int, request: Request):
       """Brief 1082: autosave of the unfinished new-guest form. Never filed."""
   ```
   Body, in this order: `lang`; `_open_link` (return `early`); `_require_pin` (return it); `_reservation_for_guest` (None: `Response(status_code=404)`); throttle (`key = rate_limit.client_key(request, f"guest_draft:{_lock_token(token)}")`; `rate_limit.blocked("guest_draft", key, GUEST_DRAFT_MAX_WRITES)`: `Response(status_code=429)`; else `rate_limit.record("guest_draft", key)`); `_require_claim_session` (any guard: `Response(status_code=403)`); `_host_owns_apartment(request, apartment)`: `Response(status_code=204)`; `int(request.headers.get("content-length") or 0) > 16384`: `Response(status_code=413)`. `form = await request.form()`; a non-empty `guest_id`: 204, nothing saved. Device key from `_draft_key`, else `secrets.token_urlsafe(32)`, remembering that it is new. `fields = {n: form.get(n) for n in guest_draft.DRAFT_FIELDS if isinstance(form.get(n), str)}`. `guest_draft.save(reservation_id, guest_draft.key_hash(device_key), _draft_generation(reservation), form.get("draft_owned") or 0, fields)` (the posted count, not the cookie: a late post must carry the count of the page it came from). Return `Response(status_code=204)`, with `_remember_draft_key` when the key is new.
   In `guest_form_new`, replace anchor 3's `prefill` line with:
   ```python
       prefill, copied_from = _residence_prefill(request, reservation)
       draft_on = not _host_owns_apartment(request, apartment)
       draft_values = _load_draft(request, reservation, progress["guests"]) if draft_on else None
       if draft_values:
           prefill = {**dict(prefill or {}), **draft_values}
   ```
   and directly above anchor 3's `return` add `new_context["draft_restored"] = bool(draft_values)` and, under `if draft_on:`, `new_context["draft_url"] = f"/l/{token}/{reservation_id}/draft" + _lang_q(lang)`, `new_context["draft_fields"] = " ".join(guest_draft.DRAFT_FIELDS)` and `new_context["draft_owned"] = _draft_owned(request)`. The template does not read these keys yet (1087). Directly above anchor 4 add:
   ```python
       if not guest_id:
           draft_key = _draft_key(request)
           if draft_key:
               guest_draft.delete(reservation_id, guest_draft.key_hash(draft_key))
   ```
   Change nothing else in `guest_form_save`. Run command A.
4. **Cookie, privacy tests, docs.** Cookie row after the `ubyhost_claim` row (anchor 8), same keys as it: `"name": "ubyhost_draft"`, `"set_by": "routes/guest.py:remember_draft_key"`, `"party": "first"`, `"kind": "cookie"`, `"surface": "guest"`, purpose en `"Keeps your unfinished form on this device so you can continue it"`, cs `"Uchová rozpracovaný formulář na tomto zařízení, abyste mohli pokračovat"`, lifetime en `"7 days"`, cs `"7 dní"`. de/es/fr entry after the `"ubyhost_claim": {` block: de `"Bewahrt Ihr nicht fertiges Formular auf diesem Gerät auf, damit Sie weitermachen können"` / `"7 Tage"`, es `"Guarda su formulario sin terminar en este dispositivo para que pueda continuarlo"` / `"7 días"`, fr `"Conserve votre formulaire inachevé sur cet appareil pour que vous puissiez le reprendre"` / `"7 jours"`. uk, after anchor 8's uk line: `    "ubyhost_draft": ("Зберігає незавершену форму на цьому пристрої, щоб ви могли продовжити", "7 днів"),`.
   `test_privacy_first.py`: add `        "ubyhost_draft",` under anchor 11's `ubyhost_leon` line. In the crawl, directly above anchor 11's `saved = guest.post(` line, add a `/draft` post with the same client, the way the `/save` post is made:
   ```python
           drafted = guest.post(
               f"/l/{TOKEN}/{stay_id}/draft?lang=en",
               data={"surname": "Novak", "first_name": "Demo", "doc_number": "123456789", "draft_owned": "0"},
           )
           assert drafted.status_code == 204, drafted.text
   ```
   (if the `/save` post passes a CSRF field or header, pass it the same way). `test_cookie_inventory.py`: after anchor 11's loop add `assert "7 days" in rows["ubyhost_draft"]["lifetime"]["en"]` and `assert guest_routes.DRAFT_COOKIE_MAX_AGE == 60 * 60 * 24 * 7` (with `from app.routes import guest as guest_routes` at the top if missing).
   `RETENTION.md`: under anchor 12's row add `| Unfinished guest form (draft) | \`guest_form_draft\` (encrypted) | last change, check-out | sent: at once; else 7 days after the last change or the day after check-out, whichever is first | \`guest_draft.purge\` in the 12-hour photo sweep, on read, on send, workspace deletion | Storage limitation |`. `ROPA.md`: under anchor 12's row add `| Unfinished form drafts | The fields a guest typed into an unsent check-in form (no photo, no signature), encrypted, keyed to the guest's device by the \`ubyhost_draft\` cookie; never sent to the police; deleted when the form is sent, else after 7 days or the day after check-out (RETENTION) |`. Run commands B and C.
5. **`App/tests/test_guest_form_draft_1082.py`** (no browser). Seed with `_cleanup`, `_seed`, `_payload` of `App/tests/test_guest_child_document.py` (read lines 39 to 130 only); routes with `TestClient` as that file does; mail off unless a test says otherwise. Synthetic data only (`SYN...` document numbers). Post `/draft` with the CSRF handling that file uses for `/save`.
   a. **Save and load:** `save` then `load` returns the cleaned fields; a second save updates the same row (one row, newer `updated_at`); a dict with `passport_photo`, `signature`, `legal_ack`, `stay_from`, `guest_id` keeps none of them; a 200-character surname comes back 60 long; party size and nationality only: nothing stored.
   b. **Encrypted at rest:** after a save with `doc_number="SYN1082X"`, no column of the raw row contains `SYN1082X`, and `db.decrypt_field(fields_enc)` is JSON with it.
   c. **Isolation:** device A saves; `load` with device B's hash on the same stay is None; A's draft on stay 1 is None for A on stay 2; a bumped generation returns None and deletes the row. Route level: client A posts `/draft`, client B (own cookie jar) opens `/new`: none of A's values in the HTML; client A opens `/new`: the values are in the inputs and `draft_restored` is in the context (assert on the rendered values; the welcome line is 1087's). The `ubyhost_draft` cookie is HttpOnly and SameSite=Lax; the DB holds `key_hash(cookie)`, never the value.
   d. **Filing never reads drafts:** (1) every file under `App/app/` containing `guest_form_draft` or `guest_draft` is one of `guest_draft.py`, `routes/guest.py`, `retention.py`, `scheduler.py`, `migrations/0042_guest_form_draft.sql`; so `reporting.py`, `worker.py`, `housebook.py`, `deadlines.py`, `filing_watchdog.py`, `stay_fee_filing.py` and `App/app/ubyport/` name neither. (2) A stay with a full draft and no guest: `reporting.reservation_progress(reservation)["filled"] == 0`; `reporting.submit_stay_if_complete(apartment_id, reservation_id)` creates no `submission` row and no `guest` row.
   e. **Sent deletes:** post `/draft`, then a valid `/save` of a new guest from the same client: no draft row left; `/new` has none of the draft values. A draft written after that save with the sent guest's doc number: not restored, row gone.
   f. **Stale draft after submit (same phone):** client A posts `/draft` with `draft_owned=0` and person 1's fields; A saves person 1 (the owned cookie now holds one id); A then posts a late `/draft` with `draft_owned=0` and **different** fields (not matching person 1); `/new` restores nothing and the row is gone. A `/draft` with `draft_owned=1` after that is restored. A posted `draft_owned` of `-5`, `abc` or `999` is stored clamped.
   g. **Purge (owner rule):** `guest_draft.purge(today)`: a draft changed 8 days ago goes; one changed 6 days ago on a stay ending tomorrow stays; one whose `date_to` is yesterday goes; one whose `date_to` is today stays; a cancelled stay's draft goes. It deletes with `config.RETENTION_AUTOPURGE` false (monkeypatch). `_job_photo_sweep()` runs it (an expired draft is gone after the call; stub nothing else unless the call needs it, as `test_scheduler.py` does). Workspace deletion of the owner removes its drafts. `load` of a stale row returns None and deletes it. `"guest_drafts"` is not a name in `retention.STEPS`.
   h. **Throttle and CSRF:** a `/draft` post without the CSRF token is refused like `/save` without it (assert the same status); the 121st post inside the window answers 429 and stores nothing new; a body over 16 KB answers 413.
   i. **No draft surfaces:** `/edit/{guest_id}` restores nothing and has no `draft_url` in its context; the host preview of `/new` has none; a post with `guest_id` stores nothing.
   Run command B.
6. Run section 6, then write the report.

## 5. Do not touch

`reporting.py`, `validation.py`, `worker.py`, `housebook.py`, `deadlines.py`, `submit_*`, `App/app/ubyport/`, `stay_fee*.py`, every template, every CSS and JS file, `i18n.py`, `db.py` (no edit to `SCHEMA`, `ADDED_COLUMNS` or `ENCRYPTED_COLUMNS`), `retention.STEPS`, `docs/ENVIRONMENT.md`, any route but `guest_form_new`, `guest_form_save` (the one block in step 3) and the new route, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`:
- A: `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_postgres.py tests/test_retention_job.py tests/test_scheduler.py -q --tb=short -x -rs` (Postgres tests may skip locally without a server; CI runs them; say so in the report).
- B: `.venv/bin/python -m pytest tests/test_guest_form_draft_1082.py tests/test_retention.py tests/test_retention_alignment.py tests/test_retention_job.py tests/test_pii_encryption.py tests/test_scheduler.py -q --tb=short -x`.
- C: `.venv/bin/python -m pytest tests/test_privacy_first.py tests/test_cookie_inventory.py tests/test_no_tracking.py tests/test_guest_languages.py tests/test_guest_child_document.py tests/test_endtoend.py -q --tb=short -x`.

Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Draft keyed by `(reservation_id, sha256(device key))` plus claim generation and owned count; the cookie value is never stored; another device on the same booking gets nothing (5c); a late autosave never reaches the next guest on the same phone (5f).
- [ ] `fields_enc` holds no plaintext document number (5b); photo, signature and tick never stored.
- [ ] Sent form deletes the draft; `purge` pins 7 days and the day after check-out and runs in the 12-hour sweep with autopurge off; workspace deletion removes drafts; no `STEPS` entry; retention comment, `RETENTION.md` and `ROPA.md` rows.
- [ ] Filing pin (5d) green: no filing module names the table; a draft-only stay files nothing.
- [ ] Throttle 120 per 15 min; CSRF refused without the token; 413 over 16 KB.
- [ ] Migrations 0042 and goose 00013; every version and table pin bumped; command A green.
- [ ] Privacy crawl reaches `ubyhost_draft`; cookie inventory translated in six languages.
- [ ] `git diff --stat origin/main` touches only section 3 files; no template, CSS, JS or i18n change (ships dark).

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; `db.execute` cannot run the `ON CONFLICT ... DO UPDATE` upsert on SQLite or Postgres; the change would need a filing, template or `db.py` edit; a cookie or privacy test needs a change beyond step 4; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1082-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions. Set this brief `Status: review`. After the fresh Fable diff review, open one PR. The PR body states: new personal-data table with a retention line, new strictly-necessary cookie `ubyhost_draft`, encrypted at rest, filing untouched, no new outbound request, no dependency, ships dark until 1087. Merge only with `scripts/merge-pr-on-green.sh`.

## 10. Open questions (not blocking)

- **Q1:** the relang and 422 re-renders do not autosave (scope). If the owner wants it, a follow-up adds the draft keys to `_form_context` for new guests.
