# MAX-159: Leon subscription access

Billed Standard subscriptions retain Havel at the existing base allowance. Leon setup, activation and model answers require Max. Max keeps the existing fivefold allowance for both assistants. Overdue and canceling accounts keep their current paid plan until the existing billing lifecycle changes it; paused accounts have no AI allowance.

Compatibility exceptions preserve existing functionality: billing disabled, hosts without a billing account, and pending/active free trials retain Leon at the existing base allowance. A trial is not promoted to Max, and this change creates no charge.

The separate `Entitlements.leon` flag is checked by Leon's host feature gate and its core allowance. Previously enabled guest chats remain readable and use the existing host handoff when access ends. Guest messages are passed to the host without calling the model; history, opt-in and accepted terms remain stored. New Standard accounts cannot enable Leon. UbyPort reporting is unchanged.

Focused regression coverage is in `test_billing_leon.py` and the updated `test_billing_enforcement.py`: subscription states, free exceptions, Havel preservation, host activation/setup, both guest doors across downgrade, retained history and direct core-call bypass attempts. Execution is delegated to GitHub CI because the managed local environment cannot meet this session's network enforcement requirements. No local tests, merge or deploy were performed.
