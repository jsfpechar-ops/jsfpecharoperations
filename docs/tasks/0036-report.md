# 0036 report — Host property and operator controls

Status: review

## Follow-up: regression expectations and global menu labels

The existing Property tools translation test now exercises the global menu in
its actual `/entities` navigation context. The Properties landing separately
checks that its direct Guest links and Automation links remain localized and
reachable. Restored the missing English and Czech `host.property_tools` labels;
the individual property detail pages still omit the duplicate menu.

Updated the superseded reporting-pill assertions: both English and Czech now
verify the pill is absent while each of the eight reporting fields retains its
localized label and matching input control. Existing readiness/checklist,
optional-field and validation assertions remain in place.

Additional validation, from `App/`:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest -q tests/test_properties_table_chips.py tests/test_property_readiness.py
```

Result: `26 passed, 1 warning in 1.41s`.

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest -q tests/test_host_property_controls_browser.py tests/test_host_controls_browser.py
```

Result: `2 passed, 1 warning in 21.34s`; zero skips. Chromium required an
escalated local run because the sandbox blocked process/socket startup. The
synthetic property screenshots were regenerated after restoring the global
menu labels.

## Changed files

- `App/app/templates/apartment_form.html`: removed every visible reporting
  badge while keeping readiness and validation; aligned address labels and
  input tops on desktop and restored natural mobile label height; changed the
  property archive button and confirmation only.
- `App/app/templates/entities.html`: Edit, Invoice settings and More stay
  visible in the same row positions. Every row has More. Linked Delete is
  keyboard-focusable, marked unavailable, explains why, and is a non-submitting
  button. Eligible Delete retains the archive POST and server guard.
- `App/app/templates/apartments.html`: changed only the property archive
  action label and confirmation.
- `App/app/templates/_host_navigation.html`: Properties has direct Guest links
  and Automation overview links, and the enabled lock overview; property detail
  pages no longer repeat the Property tools dropdown.
- `App/app/host_i18n.py`: restored the EN/CS `host.property_tools` labels used
  by the global navigation menu.
- `App/tests/test_host_property_controls_browser.py`: synthetic browser and
  route-guard coverage in English and Czech.
- `App/tests/test_properties_table_chips.py`: tests the global menu in its
  actual navigation context and localized direct Properties overview links.
- `App/tests/test_property_readiness.py`: tests all eight localized labels and
  controls with no reporting pills in English and Czech.
- `docs/tasks/0036-host-property-operator-controls.md`: scoped implementation
  task and acceptance criteria.

Shared localization owner added the four requested EN/CS strings. No
application validation or archive route behavior was changed.

## Validation

Run from `App/`:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_PROPERTY_CONTROLS=1 .venv/bin/python -m pytest tests/test_host_property_controls_browser.py -q
```

Result: `1 passed, 1 warning in 5.46s`; zero skips. The warning is an existing
Starlette `TestClient` deprecation warning. The test covers 360, 390 and 1280
CSS px in EN/CS, aligned desktop rows, mobile stacking, visible operator
actions, keyboard/touch access to the linked-property explanation, no POST from
the disabled action, the linked-operator server guard and Properties/detail
navigation.

From the repository root:

```sh
python3 scripts/context_lint.py
```

Result: `context lint: OK` (exit 0). It reports existing orchestration warnings:
0032/0033 share `host_i18n.py`, and 10 application commits need the status
document refreshed at review. The root agent owns those cross-task updates.

## Screenshots

Synthetic fixtures only. All images are under
`/workspace/generated_images/host-design-application/properties/`.

| Screen | English | Czech |
|---|---|---|
| Address form, 360 px | [EN](/workspace/generated_images/host-design-application/properties/address-360-en.png) | [CS](/workspace/generated_images/host-design-application/properties/address-360-cs.png) |
| Address form, 390 px | [EN](/workspace/generated_images/host-design-application/properties/address-390-en.png) | [CS](/workspace/generated_images/host-design-application/properties/address-390-cs.png) |
| Address form, 1280 px | [EN](/workspace/generated_images/host-design-application/properties/address-1280-en.png) | [CS](/workspace/generated_images/host-design-application/properties/address-1280-cs.png) |
| Operator list, 360 px | [EN](/workspace/generated_images/host-design-application/properties/operators-360-en.png) | [CS](/workspace/generated_images/host-design-application/properties/operators-360-cs.png) |
| Operator list, 390 px | [EN](/workspace/generated_images/host-design-application/properties/operators-390-en.png) | [CS](/workspace/generated_images/host-design-application/properties/operators-390-cs.png) |
| Operator list, 1280 px | [EN](/workspace/generated_images/host-design-application/properties/operators-1280-en.png) | [CS](/workspace/generated_images/host-design-application/properties/operators-1280-cs.png) |

## Acceptance and follow-up

- [x] Reporting badges removed; existing field names and optional markers,
  readiness and validation retained.
- [x] Desktop input tops aligned; mobile fields stack without horizontal
  clipping at 360 and 390 px.
- [x] Operator actions remain visible; linked Delete has a readable reason and
  cannot submit; eligible route keeps its existing archive protection.
- [x] Global overview links remain accessible from Properties; detail pages
  retain local cards and do not show the duplicate dropdown.
- [x] Only property/operator archive actions changed to Delete; confirmation
  says the item moves to Archived; restore and permanent-delete paths untouched.
- [x] Browser screenshots and command outcomes are recorded above.

The success messages still come from `flash.entities.archived` and
`flash.apartments.archived` in the existing route handlers. The new
`host.delete_to_archived.success` translation exists, but wiring those
archive-only success callsites is a route-handler follow-up outside this
template/test scope. No push, merge, staging deploy or production deploy was
performed; the root agent coordinates staging review.
