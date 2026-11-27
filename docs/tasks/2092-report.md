# Report 2092: Mandatory check-in/out hours & scheduled 24 h default

- Made `checkin_hour` and `checkout_hour` mandatory (`0..23`) on Property create, Property settings, and Onboarding Step 1 (prefilled `15:00` / `10:00`, zero DB migration).
- Changed new-property default from `manual` to `scheduled` with `submit_after_hours = 24`, bounded to `1..24`.
- Verified green with Postgres 16: `go test ./internal/web/properties/... ./internal/web/onboarding/... -count=1`.
