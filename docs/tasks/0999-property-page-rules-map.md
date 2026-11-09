# 0999: Property page, house rules and "Open in map"

Status: todo
Depends on: none | Base commit: 47640cf3 | Branch: task/0999-property-page-rules-map
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The public property page (`/p/<slug>`) gets a "House rules" section (editable text, prefilled once from the Airbnb import) and an "Open in map" link next to the town. The exact address never reaches the public page. Brief 1000 (photo reorder) is separate and runs after this one.

## 2. Context

Owner decisions 2026-11-07. Rules that apply: 2 (privacy: no embedded map, no third-party script, the link is a plain `<a>` the guest clicks; the PR names it as the only new outbound destination), 5 (migration file), 6 (light mode), 7 (browser + geometry + one 390 px screenshot), 9 (one explanation in one place; here the same key `pp.rules` labels both the public section and the host field), 10 (UX gate).

Facts, verified in the code:

- `property_page` columns come from `App/app/migrations/0029_property_page.sql` (`description`, `checkin_text`, `checkout_text`, `amenities_json`, `photos_json` ...). The last SQLite migration is `0037_stay_fee_guest_default_rail.sql`; the last Postgres twin is `App/migrations_pg/00008_full_scan_indexes.sql` (no SQLite twin) and `00007` is the twin of 0037 (see its header for the pattern: `ADD COLUMN IF NOT EXISTS`, `INSERT INTO schema_migrations`, `-- +goose Down`).
- The import (`App/app/guest_guide_import.py`, `trim()`) keeps `houseRules` for **Airbnb only**, as a list of short lines (`_LIST_FIELDS["airbnb"]`), and `address` as one string. `_run_one` calls `property_page.prefill_from_import(...)`. The Booking actor has **no recorded house-rules field** (0347 lists only name, description, checkIn, checkOut, address.full): Booking rules are out of scope, do not guess a key.
- Exact address stays private: it lives in `apartment.addr_street` / `addr_house_no` and in `guide_import.raw_json`. The public page already shows only `addr_obec` and `addr_obec_cast` (`routes/property_page.py::_page_context`, key `district`).

Anchors (each must be found verbatim, else STOP, section 8):

`App/app/property_page.py` (prefill):
```python
    if not page["amenities_json"] and isinstance(data.get("amenities"), list):
        updates["amenities_json"] = _json.dumps(data["amenities"], ensure_ascii=False)
```
`App/app/property_page.py` (save):
```python
def save_page(apartment_id: int, *, description: str, amenities: list) -> None:
    """The host's review-screen save: overwrites, this is the host writing."""
    page_for(apartment_id)
    db.execute(
        "UPDATE property_page SET description = ?, amenities_json = ?, updated_at = ?"
        " WHERE apartment_id = ?",
        (
            description or None,
            _json.dumps(amenities, ensure_ascii=False) if amenities else None,
            db.utcnow(),
            apartment_id,
        ),
    )
```
`App/app/routes/property_page.py`:
```python
        "description": c.get("description") or "",
```
`App/app/routes/payments.py`:
```python
    pp.save_page(
        apartment_id,
        description=str(form.get("description") or "").strip(),
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0038_property_page_house_rules.sql` | create | `house_rules TEXT` column |
| `App/migrations_pg/00009_property_page_house_rules.sql` | create | Postgres twin, schema_migrations version 38 |
| `App/tests/test_db_postgres.py` | edit | the two `== 37` schema-version asserts become `== 38` |
| `App/app/property_page.py` | edit | prefill + save `house_rules` |
| `App/app/routes/property_page.py` | edit | context: `house_rules` lines and `map_url` |
| `App/app/routes/payments.py` | edit | host save passes `house_rules` |
| `App/app/templates/property_page.html` | edit | rules section, map link |
| `App/app/templates/property_page_review.html` | edit | rules textarea |
| `App/app/host_i18n.py` | edit | `pp.rules`, `pp.map` in en and cs |
| `App/tests/test_property_page_rules.py` | create | tests |
| `docs/context/test-map.md` | edit | add the new test file to the "Public property pages" row |

No other file may change. Retention: no line needed (the host's own listing text, no personal data; same as the 0430-0434 comment in `App/app/retention.py`). No new dependency.

## 4. Steps

Run all commands from `App/`. Commit after each step as `0999 step k`.

1. Create `App/app/migrations/0038_property_page_house_rules.sql`:
```sql
-- Brief 0999: the host's house rules for the public page, prefilled once from the Airbnb import.
-- Host content, no personal data; a re-import fills it only while empty.
ALTER TABLE property_page ADD COLUMN house_rules TEXT;
```
   Create `App/migrations_pg/00009_property_page_house_rules.sql`:
```sql
-- +goose Up
-- Twin of App/app/migrations/0038_property_page_house_rules.sql. pg_schema
-- apply runs the SQLite file first, so the statement is IF NOT EXISTS.
ALTER TABLE property_page ADD COLUMN IF NOT EXISTS house_rules TEXT;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (38, 'property_page_house_rules', '2026-11-07T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 38;
ALTER TABLE property_page DROP COLUMN IF EXISTS house_rules;
```
   In `App/tests/test_db_postgres.py` change `== db.expected_schema_version() == 37` to `== 38` and `assert db.schema_version() == 37` to `== 38` (use `grep -nF "37" App/tests/test_db_postgres.py`, change only those two). Command: `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_postgres.py -q --tb=short -x 2>&1 | tail -30`. Expected: passes (Postgres tests may skip without a server; skips here are fine, the browser rule 0-skip applies to browser tests only).

2. `App/app/property_page.py`, prefill: after the amenities lines (anchor above) insert, same indentation:
```python
    if not page.get("house_rules") and isinstance(data.get("houseRules"), list):
        rules = "\n".join(str(r).strip() for r in data["houseRules"] if str(r).strip())
        if rules:
            updates["house_rules"] = rules
```
   Never overwrites: the `not page.get("house_rules")` guard is the whole rule.

3. `App/app/property_page.py`, `save_page`: replace the whole function (anchor above) with:
```python
def save_page(apartment_id: int, *, description: str, amenities: list,
              house_rules: str = "") -> None:
    """The host's review-screen save: overwrites, this is the host writing."""
    page_for(apartment_id)
    db.execute(
        "UPDATE property_page SET description = ?, amenities_json = ?,"
        " house_rules = ?, updated_at = ? WHERE apartment_id = ?",
        (
            description or None,
            _json.dumps(amenities, ensure_ascii=False) if amenities else None,
            house_rules or None,
            db.utcnow(),
            apartment_id,
        ),
    )
```

4. `App/app/routes/payments.py`: in the `pp.save_page(` call add after the `description=` line:
```python
        house_rules=str(form.get("house_rules") or "").strip()[:4000],
```

5. `App/app/routes/property_page.py::_page_context`: before `return {` add
```python
    from urllib.parse import quote

    where = " ".join(p for p in (apartment["addr_obec"], apartment["addr_obec_cast"]) if p)
    # Town and district only; the street and number never leave the host side.
    map_url = f"https://mapy.cz/zakladni?q={quote(where)}" if where else ""
```
   and after the `"description": ...` line (anchor) add
```python
        "house_rules": [
            ln.strip() for ln in (c.get("house_rules") or "").splitlines() if ln.strip()
        ],
        "map_url": map_url,
```

6. `App/app/templates/property_page.html`: replace the line `<p class="pp-location">{{ page.district }}</p>` with
```html
    <p class="pp-location">{{ page.district }}{% if page.map_url %} · <a href="{{ page.map_url }}" target="_blank" rel="noopener noreferrer">{{ t('pp.map') }}</a>{% endif %}</p>
```
   And directly before `{% if page.cards %}` insert
```html
    {% if page.house_rules %}
    <h2>{{ t('pp.rules') }}</h2>
    <ul class="pp-amenities">
      {% for r in page.house_rules %}<li>{{ r }}</li>{% endfor %}
    </ul>
    {% endif %}
```
   (Reuses the amenities list style: no new CSS. Jinja autoescape stays on; do not use `|safe`.)

7. `App/app/templates/property_page_review.html`: inside the first `ui-section` of the main form, after the amenities `</label>` and before the Save button, insert
```html
    <label class="ui-field">
      <span>{{ t('pp.rules') }}</span>
      <textarea class="ui-input" name="house_rules" rows="6">{{ page.house_rules or '' }}</textarea>
    </label>
```

8. `App/app/host_i18n.py`: next to `"pp.amenities": "What this place offers",` add `"pp.rules": "House rules",` and `"pp.map": "Open in map",`; next to `"pp.amenities": "Co tu najdete",` add `"pp.rules": "Pravidla ubytování",` and `"pp.map": "Otevřít na mapě",`. Command: `.venv/bin/python -m pytest tests/test_flash_literals.py tests/test_i18n*.py -q --tb=short -x 2>&1 | tail -30`.

9. Create `App/tests/test_property_page_rules.py`. Copy the `OWNER`/`_cleanup`/`owner` fixture pattern from `App/tests/test_property_page_photos.py` lines 1-60 (own username `ruleshost`; no photo cleanup needed). Tests:
   - `test_prefill_takes_airbnb_rules`: `property_page.prefill_from_import(aid, {"raw_json": json.dumps({"houseRules": ["No parties", "Quiet after 22:00"]})})`; `page_for(aid)["house_rules"] == "No parties\nQuiet after 22:00"`.
   - `test_prefill_never_overwrites_host_rules`: `save_page(aid, description="", amenities=[], house_rules="Mine")`, then prefill as above; value still `"Mine"`.
   - `test_public_page_shows_rules_and_map_not_street`: set `addr_obec="Brno"`, `addr_street="Tajna"`, `addr_house_no="42"` on the apartment (`db.execute("UPDATE apartment SET ...")`), `save_page(... house_rules="No pets\nNo smoking")`, `property_page.publish_page(aid, published=True)`, `slug = property_page.ensure_slug(aid)["slug"]`, `TestClient(app).get(f"/p/{slug}")`; assert 200, `"No pets"` and `"mapy.cz"` in body, `"Tajna"` not in body, `"42"` not in the href. Assert no `<iframe` and no `<script src` pointing at a third party.
   - `test_no_map_link_without_town`: apartment without `addr_obec`: no `mapy.cz` in body.
   Command: `.venv/bin/python -m pytest tests/test_property_page_rules.py -q --tb=short -x 2>&1 | tail -30`.

10. `docs/context/test-map.md`: in the "Public property pages" row add `test_property_page_rules.py` after `test_property_page_photos.py`.

## 5. Do not touch

`App/app/guest_guide_import.py` (the import already delivers Airbnb `houseRules`), any file under `App/app/templates` other than the two named, CSS files, `App/app/retention.py`, `App/app/analytics.py`, secrets, deploy. Hard rules 2, 3, 4, 5, 6, 7, 9, 10. Never expose `addr_street`, `addr_house_no` or `guide_import.address` on a public page.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

- `.venv/bin/python -m pytest tests/test_property_slug.py tests/test_property_page.py tests/test_property_page_photos.py tests/test_property_page_meta.py tests/test_property_page_rules.py tests/test_migrations.py -q --tb=short -x`
- Browser, geometry, 0 skipped (`-rs`, `UBYHOST_REQUIRE_BROWSER=1`): `tests/test_property_page_audit_browser.py tests/test_property_page_buttons_browser.py tests/test_0541_property_page_phone_browser.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py`
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` (0 skipped, zero host findings).
- Repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] Migration 0038 and pg twin 00009 exist; schema version asserts say 38.
- [ ] Prefill fills `house_rules` only when empty; the host save overwrites it.
- [ ] `/p/<slug>` shows the rules list and "Open in map" (cs and en); no street or number anywhere in the HTML; no iframe, no third-party script.
- [ ] The test commands in section 6 are green, browser files with 0 skipped.
- [ ] One 390 px screenshot of the public page with rules and map link, and one of the host review page (`/apartments/<id>/page`); 768 and 1280 read for the UX gate.
- [ ] PR body: per page "390: ...; 768: ...; 1280: ..." for both touched pages, the design-system checklist ticked, and the sentence "New outbound destination: a plain link to mapy.cz, opened only when a guest clicks; no request from our server or page."

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; 25 tool calls or about 50k tokens; a file outside section 3 needs a change; a Booking house-rules key seems needed (not recorded, owner decision); the owner wants Google or OpenStreetMap instead of mapy.cz (one constant in step 5); push, merge, secrets, SSH or deploy is needed.

## 9. Report

`docs/tasks/0999-report.md` (600 tokens at most): files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left. Set `Status: review`.

## Risk list (for the reviewer)

`App/app/routes/property_page.py` (public output: confirm no address leak), `App/app/property_page.py` (prefill guard), both migration files.

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh <PR number>` once CI is green.
2. Deploy as usual; migration 0038 / 00009 run on start. No new secret.
3. Open `/apartments/<id>/page`, check the "House rules" box is filled after an Airbnb import, and open the public page to see the section and the map link.
