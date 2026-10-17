# 0036 report — Host property and operator controls

Status: review

## Changes and checks

Restored English/Czech `host.property_tools` labels. The Properties overview
keeps localized Guest and Automation links; property details omit the duplicate
menu. Property forms retain readiness, validation and all eight reporting
fields, without the superseded reporting badges. Address labels align on
desktop and stack on mobile. Operator rows keep Edit, Invoice settings and More
visible; Delete is keyboard accessible, explains why when unavailable, and
cannot submit in that state. Eligible Delete still uses the existing archive
POST and server guard. Restore/permanent-delete behavior is unchanged.

From `App/`:

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest -q tests/test_properties_table_chips.py tests/test_property_readiness.py
```

Result: 26 passed, 1 warning (1.41s).

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest -q tests/test_host_property_controls_browser.py tests/test_host_controls_browser.py
```

Result: 2 passed, 1 warning, zero skips (21.34s). Chromium needed an escalated
local run because the sandbox blocked process/socket startup.

```sh
UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_CAPTURE_PROPERTY_CONTROLS=1 .venv/bin/python -m pytest tests/test_host_property_controls_browser.py -q
```

Result: 1 passed, 1 warning, zero skips (5.46s). Coverage includes 360, 390
and 1280 px in EN/CS, row alignment, mobile stacking, actions, keyboard/touch
access, disabled-action behavior, the server guard and overview/detail links.
The warning is an existing Starlette `TestClient` deprecation.

## Evidence and limitations

Synthetic screenshots are under
`/workspace/generated_images/host-design-application/properties/`:

| Screen | English | Czech |
|---|---|---|
| Address form, 360 px | [EN](/workspace/generated_images/host-design-application/properties/address-360-en.png) | [CS](/workspace/generated_images/host-design-application/properties/address-360-cs.png) |
| Address form, 390 px | [EN](/workspace/generated_images/host-design-application/properties/address-390-en.png) | [CS](/workspace/generated_images/host-design-application/properties/address-390-cs.png) |
| Address form, 1280 px | [EN](/workspace/generated_images/host-design-application/properties/address-1280-en.png) | [CS](/workspace/generated_images/host-design-application/properties/address-1280-cs.png) |
| Operator list, 360 px | [EN](/workspace/generated_images/host-design-application/properties/operators-360-en.png) | [CS](/workspace/generated_images/host-design-application/properties/operators-360-cs.png) |
| Operator list, 390 px | [EN](/workspace/generated_images/host-design-application/properties/operators-390-en.png) | [CS](/workspace/generated_images/host-design-application/properties/operators-390-cs.png) |
| Operator list, 1280 px | [EN](/workspace/generated_images/host-design-application/properties/operators-1280-en.png) | [CS](/workspace/generated_images/host-design-application/properties/operators-1280-cs.png) |

The archive success messages still use the existing `flash.entities.archived`
and `flash.apartments.archived` route strings; wiring the new
`host.delete_to_archived.success` label is a separate route-handler follow-up.
No deploy was performed; staging review is coordinated by the root agent.
