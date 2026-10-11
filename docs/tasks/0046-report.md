# 0046 report — Copy settings from another property

Status: review

## Files

| Path | Change |
|---|---|
| `App/app/routes/admin.py` | `copy_from` GET handling, allowed-key extraction, owner-scoped 404 |
| `App/app/templates/apartment_form.html` | Copy GET form, notice, section open state, new-form prefill |
| `App/app/host_i18n.py` | `apartment.form.copy_from.*` EN + CS |
| `App/tests/test_copy_property_settings.py` | New coverage |
| `App/tests/test_stay_fee_property_panel.py` | Fee-template peer assert scoped to `#fee-copy-source` (property copy list lists every other flat) |

## Tests

From `App/`:

```sh
.venv/bin/python -m pytest tests/test_copy_property_settings.py -q
```

```
4 passed, 1 warning in 1.05s
```

Full suite (this VM, no system Chromium):

```sh
.venv/bin/python -m pytest tests -q
```

```
3052 passed, 2 skipped, 7 failed (browser/geometry; Playwright executable missing at /usr/bin/chromium)
```

Root: `python3 scripts/context_lint.py` → OK.

## Screenshots

Rendered from authenticated `TestClient` HTML at 360, 390 and 1280 px (new before/after Copy, edit after Copy):

- `/opt/cursor/artifacts/screenshots/0046-new-before-360.png` (and 390, 1280)
- `/opt/cursor/artifacts/screenshots/0046-new-after-360.png` (and 390, 1280)
- `/opt/cursor/artifacts/screenshots/0046-edit-after-360.png` (and 390, 1280)

## Notes

- §8 stop: council account is stored as plain text; Czech account parts prefill safely. VS is left empty with hint.
- Guest-link day fields copy only into empty DB values (defaults 2 / 365 on existing rows are kept).
