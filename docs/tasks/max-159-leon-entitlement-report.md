# MAX-159: Leon Lite and Max subscription access

Owner's latest decision supersedes the earlier Max-only implementation: paid Standard includes Leon Lite permanently at the existing base allowance. Max uses the same model and capabilities with five times the Leon and Havel allowance. No absolute allowance counts are advertised; no unlimited AI claim is made.

Paused accounts have no AI allowance. Overdue and canceling keep their current paid allowance until the existing billing lifecycle changes status. Billing disabled, hosts without a billing account, and pending/active trials keep their existing base access. The existing shared stay conversation, guest history, opt-in, terms, feature/test-list/budget controls and host handoff remain in place. UbyPort filing is unchanged.

White label is withdrawn from new purchases: public pricing/rates, the order checkbox and upgrade option are removed. Core changes and order placement reject attempts to enable it on an account without the saved entitlement. Reordering preserves an existing entitlement even when the removed checkbox is omitted; invoices, stored configuration, migration and existing removal option remain.

Regression coverage: billing entitlement states, Standard activation, paused handoff/direct-call guards, shared-stay Lite/Max capacity and handoff, forged white-label order/change requests, existing contracts across reorder/change, Czech/English rendered marketing and one TTLock inclusion per Max card.

No local tests, context lint, browser or screenshot inspection ran: managed workspace cannot start because managed network requirements require sandbox enforcement. GitHub CI and 390 px pricing/subscription/Leon setup screenshot review remain required before release. No merge or deploy.
