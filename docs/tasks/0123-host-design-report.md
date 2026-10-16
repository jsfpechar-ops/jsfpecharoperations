# 0123 implementation report

Status: in-progress
Branch: feature/host-design0123-20261016 | PR: #397
Base: 7835b528cec95a1d7a25798e0002d28c0255f346
Brief: docs/tasks/0123-host-design.md

## Work in progress

Properties settings and the setup wizard Property step now own the canonical check-in/check-out hour pair. Door-lock setup shows those values and links to Properties. Cleaning derives automatic availability from apartment hours and leaves legacy cleaning_property time columns untouched on instructions saves. Focused checks are being added for legacy precedence, preserved manual cleaning windows, and wizard ownership.

The flat-white host theme, dashboard/Stays composition, compact calendar controls, remaining browser adaptations, design/context updates, and CI verification are still pending. No local shell/browser tests have run; do not treat this checkpoint as implementation acceptance.
