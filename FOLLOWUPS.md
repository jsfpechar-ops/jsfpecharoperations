# Follow-ups

Out-of-scope observations found while executing the remediation plan. Nothing
here was acted on: each entry needs a decision before it becomes work.

## From Phase 1 (missed filing paths)

### W1.5 — the completion gate waits for the quiet window, not for a save

`reporting.refresh_registration_completed_at` now treats a stay as final once
every form on file is complete and none has been touched for
`HEADCOUNT_QUIET_HOURS` (12 h). That function is only reached from a save path
(guest form save, host guest save, declared-count change), so a stay whose party
stopped growing and where nobody saves again stays unfiled until the next save.
The host is told: `headcount_mismatch` fires once the stay has started, so the
suppression is visible rather than silent. A periodic sweep in the `deadlines`
job would close the last gap, but it would also start unattended automatic
submissions, which is a product decision rather than a bug fix.

### W1.5 — a raise after completion re-opens the gate

`_set_declared_guests` calls `maybe_submit_after_completion`, which re-evaluates
completion. Raising the declared headcount therefore clears an already-reached
`registration_completed_at` and puts the stay back behind the quiet window. The
wait is bounded at 12 h and the host is alerted, but "the link holder cannot
hold the filing open" is only true after the quiet window, not immediately.

### W1.5 — the guest is not told the stay will be filed with fewer people

The plan's preferred option 1 would have refused the increase and told the guest
so. Under option 2 the guest link accepts the increase and says nothing; only
the host is alerted. Guest-facing copy explaining that the stay is filed with
the forms received would need a new EN/CS key in `host_i18n.py`.

### W1.5 — the plan's preferred remedy was not the one implemented

The plan prefers capping the declared headcount at what the guests filled
(option 1). That would have removed the "Add another person" affordance and
broken `test_completed_party_can_add_another_person` and
`test_an_unexpected_extra_guest_can_still_register`. Option 2 was chosen
deliberately and the reasoning belongs in the PR description.

### D3 — the inclusive reading still needs counsel, not just a decision

D3 was answered by the owner: the arrival day counts as the first working day
when it is one, so a Monday check-in now files by Wednesday. That is a product
call implementing the stricter reading of §100(c); the plan itself notes it
"needs counsel or a citation", and no citation has been recorded. If counsel
reads the window as starting the day after arrival, `deadlines.add_working_days`
reverts to `remaining = count` and the eight tests that pin the arithmetic will
need the same one-day shift. Worth one line of citation in `deadlines.py`
either way.

### W1.7 — an empty feed is now reported as incomplete

The retention guard raises `feed_incomplete` whenever the feed yields fewer
stays than the completeness threshold, which includes a feed that parsed
cleanly and returned nothing. All stays are still retained, so nothing is
cancelled, but a legitimately empty calendar will warn once per sync cycle.
Treating a fully empty parse as "nothing to compare against" instead is a
judgement call.

### Where the remediation plan lives

The plan was supplied as an attachment while Phase 1 ran and was not on disk;
it has since been committed to `main` as `CURSOR_REMEDIATION_PLAN.md` (root,
`f984560`). Two path notes: the plan's own header calls itself a companion to
`UBYHOST_CODE_AUDIT.md`, which lives under `docs/`, so the two documents do not
sit together; and the plan's `[Fnn]` references point at the audit in `docs/`.

## From Phase 6 (CI, tests and remaining unknowns)

### W6.3 — production ownership counts require owner-authorized access

The current code still uses SQLite-compatible `owner_user_id IS ?` predicates
in `App/app/access.py`. No production query was run. The owner must authorize
an audited, read-only production path before the two requested NULL counts for
`apartment.owner_user_id` and `legal_entity.owner_user_id` can be collected;
until then, no `IS ?` → `= ?` change or NOT NULL migration is justified. This is
not treated as an active W5.2.6 blocker on the Phase 5-complete branch.

### W6.3 — retry-path verification

The current call graph confirms that the unattended scheduler/deadline path
uses the `collect_sendable` automation gate and the
`SUBMISSION_MAX_AUTO_ATTEMPTS` bound. Host-initiated sends and explicit resends
pass `ignore_automation=True`; the existing retry-cap tests cover both paths.
No additional retry bug or cleared-`registration_completed_at` strand was
identified, so no submission-policy change was made.

### W6.3 — historical audit dates

The two audit reports remain dated historical snapshots from 15 September 2026;
the owner must decide whether to re-date them or append a separately scoped
post-1.1.0 verification note. Phase 6 corrected the two stale technical-audit
rows for environment/demo submission guards and updated the stale test-count
references without rewriting the reports' review dates.

## From Phase 2 (guest passport data at rest)

### W2.1 — the orphan-submission delete waits for the retention clock

The plan says to delete `submission` rows that have no surviving `guest` rows
after the guest purge. It is implemented that way *and* gated on the six-year
`retention_cutoff`, because a submission row with no guests is not always a
submission that never happened: a host who deletes a guest entered by mistake
would otherwise lose the Doručenka for a filing that really was sent, and the
receipt is the evidence the host has to be able to produce. Pinned by
`test_deleting_a_guest_by_hand_does_not_take_a_recent_receipt_with_it`. If the
intent was the literal reading, the gate comes out and that test is inverted.

### W2.1 — "terminal state" was read as every settled state

`reporting.purge_submission_payloads` blanks a payload once the submission is
no longer in flight (`ok`, `partial`, `error`, `transport_error`). The plan says
"terminal" without defining it. `running` is the only state excluded, so an
attempt that failed and will never be retried keeps its XML until the 90 days
elapse. The narrower reading — only `ok` — would retain envelopes for failures
the host may still need to diagnose.

### W2.2 — the plaintext columns are already dead, and are not dropped

The plan's step 3 says to write through both columns and step 5 says to stop
writing the plaintext one "only in a later release". Those two cannot both hold
with the plan's own required test that the stored value must not be the
plaintext, so plaintext writing stopped immediately and the plaintext column
survives only as a read fallback for rows the backfill has not reached. Two
things follow that a later release should pick up:

1. **The backfill is a manual deploy step.** `App/scripts/migrate_encrypt_doc_fields.py`
   is documented in `docs/OPERATIONS.md` but is not wired into
   `deploy/lightsail/scripts/deploy.sh`. Nothing runs it automatically, so
   production stays on the fallback until someone runs it. Wiring it in (or
   gating the deploy on it) is the durable fix; it was left out here because
   changing the deploy script is outside this work item.
2. **The plaintext columns are never dropped.** Once production is confirmed
   backfilled, `doc_number` and `visa_number` can stop being read and can be
   dropped, which removes the fallback path and the `_hydrate` shim with it.

### W2.2 — names and birth dates are still cleartext

The plan scopes this work item to `doc_number` and `visa_number` and defers the
rest. Guest `surname`, `given_names`, `birth_date` and `birth_place` are still
stored as plaintext and are the same class of personal data; they were deferred
because they appear in search, sort and PDF paths, so encrypting them changes
more than a column. Worth doing as its own change if the owner wants it.

### W2.4 — a link queued before this release still sends

`mail.delivery_body` passes a body with no marker through untouched, which is
what lets a rolling deploy finish the rows the previous release queued with a
cleartext link. That also means a cleartext link in a payload written before
this release keeps working until it is sent or purged. Once no such row can
exist — 14 days of retention, so one release cycle — the pass-through can
become a hard error.

### W2.4 — the platform-admin console view still reveals the secret

`recent_console_messages(None)` returns every workspace's console rows and puts
the secret back in each, because that is what it did before this change and who
may see what is not part of this work item. A platform admin therefore still
sees a working claim link for any host's guest. Narrowing that branch is a
product decision about platform-admin access, not a fix to the retention
finding.

## Requested by the owner during Phase 2 (not in the plan)

### An accidental headcount bump silently cancels the automatic filing

Reported against a real stay: the owner clicked "add another person" on a guest
link whose forms were already filled in, and the stay went from `4 / 4` to
`4 / 5` and stopped filing itself. Nothing told them why.

The chain is short and every link is deliberate on its own:

- `guest.add_another_person` raises `reservation.declared_guests` by one
  (`_set_declared_guests`), so the declared party is now 5 while four forms
  exist.
- `_set_declared_guests` calls `reporting.maybe_submit_after_completion`, which
  runs `refresh_registration_completed_at`.
- There, `declared_filled` requires
  `progress["filled"] >= progress["expected"] and not progress["incomplete"]`.
  With 4 filled against 5 expected it is False, so the function takes its
  `elif not complete and existing:` branch and **clears
  `registration_completed_at`**.
- `registration_completed_at` is the only gate on the automatic send
  (`due_for_automatic_send` returns False without it), so a stay that was about
  to file itself never does. `reservation_progress` also reports `incomplete`,
  which moves the row into the host's "needs action" queue as "Incomplete".

Two related defects sit beside it:

1. **A surplus blank form blocks a complete stay.** `declared_filled` also
   requires `not progress["incomplete"]`, which counts *every* incomplete guest
   including one past the declared headcount. So adding a blank 5th guest to a
   4-guest stay clears completion even though all four declared forms are
   complete. Fixing this one is not free: a host who adds a real extra guest
   without raising the headcount would then have that guest filed late or not
   at all, which is the under-reporting this whole remediation exists to stop.
   It needs an explicit answer, not a quiet change.
2. **There is no inverse of "add another person".** The guest link can raise the
   party but nothing on it lowers it back.

**What already works, and is the fix for the reported stay today:** the host is
not stuck. The stay detail page has a collapsible quick-edit panel with a
**Guests** field (`expected_guests_override`, `reservation_detail.html:79`) that
posts to `/reservations/{id}/quick-edit`; setting it to the real number re-runs
`maybe_submit_after_completion` on save and the filing proceeds. An override
also sets `can_raise_party` false on the guest link, so it cannot be bumped
again on that stay. A blank guest row that did get created can be removed from
the guest's row menu (**Archive**) or the guest page (**Remove guest**,
`/guests/{id}/delete`, which `guest_delete` hides once the row is `sent`).

**Open question for the owner.** When the declared headcount is met but an extra
incomplete form exists — should the stay file the declared guests and ignore the
stray form, or keep holding the filing until the stray form is dealt with? The
first is what the owner's report implies; the second is the safe reading for
under-reporting. Whichever is chosen, the silent cancellation deserves an alert
either way, because the host currently gets no signal that their click undid a
pending filing.

**Nothing in the filing gate was changed unattended.** The owner was asked which
way to go and was not available, so the gate was left exactly as it is. Filing a
party while an incomplete form is on file risks under-reporting to the Foreign
Police, which is the failure class this whole remediation exists to stop, and
that is not a call to make alone — nor is it Phase 2's to make, so it does not
belong on this branch either.

The safe half is separable and is the recommended first step. Telling the host
costs no change to who gets filed: `refresh_registration_completed_at` already
computes the transition (`elif not complete and existing:`), so an alert raised
there when a completion that had been set is cleared needs no gate change at
all. That alert should land before, or together with, whichever gate behaviour
is chosen.

## From Phase 3 (guest access control)

### W3.5 — the reach-back bound does not close ID enumeration inside the window

The stay-specific link `/l/{token}/{id}` is now bounded by the new apartment
field `permalink_reachback_days` (default 365). A stay whose `date_to` is older
than that bound answers with the same `unavailable.html` and the same status as
an id that was never part of the apartment, so the out-of-window case no longer
discloses whether an id belongs to the apartment.

The residual risk is deliberate and is the reason the forward side was left
unbounded. The reach-back bound only hides ids for stays that have already
drifted past the window; a stranger holding a valid apartment token can still
learn whether a *recent* low id belongs to that apartment, because an in-window
stay is genuinely reachable and must stay reachable — that is the documented
affordance (a forgotten, incomplete form can still be finished). Bounding the
forward side too would kill that affordance rather than protect anything, so it
was not done.

`/l/{token}/{id}/claim` (`claim_landing`, `guest.py`) performs its own
reservation SELECT and carries **no** reach-back bound at all. It was left alone
because the token in the URL is itself the access secret, `claim_confirm` fails
without a matching stored secret, and `confirm()` never bumps
`guest_access_reopened_at`, so its `guest_access_open` bypass is inert. If the
claim landing page is ever given an unauthenticated success path, it needs the
same bound as `_reservation_for_guest`.

### The host-side language cookie still uses an https-prefix-only Secure test

W3.6 moved the guest cookie flag onto `auth.secure_cookies()`, which treats
`UBYHOST_DEPLOYMENT=production` as sufficient for `Secure` even when
`PUBLIC_BASE_URL` is still `http://` (that combination is only *warned* about by
`env_guard`, never blocked, so it is reachable in practice).

`host_i18n.set_lang_cookie` (`App/app/host_i18n.py:2767`) still computes the
narrower `PUBLIC_BASE_URL.lower().startswith("https://")`. It sets
`ubyhost_lang` — the *same* cookie name that `routes/guest.py` defines as
`LANG_COOKIE` and that W3.6 hardened. The host side was out of W3.6's stated
scope (guest cookies), so it was left as-is, but it is the same class of gap and
should be pointed at `auth.secure_cookies()` — the host routes already import
`auth`. `security.py:110` computes the same expression inline for `ubyhost_csrf`;
it is already behaviourally identical, so that one is cosmetic only.

### `normalise_permalink_pin` is not the gate a guest meets

W3.7 tightened `auth.normalise_permalink_pin` to six digits only, but that
function has exactly one caller — the admin apartment save at
`App/app/routes/admin.py:735`. The guest PIN gate does not use it:
`routes/guest.py:verify_pin` calls `auth.pin_matches(token, entered,
apartment["permalink_pin"])`, a fingerprint comparison against the **stored**
value. Tightening the normaliser alone therefore does *not* retire F26 — a
four-digit PIN already in the database keeps opening the form. The work item's
text reads as if the normaliser is the control; it is not. The change that
actually closes the weakness is the startup rotation in
`main.rotate_weak_permalinks()`, which rewrites any stored PIN whose length is
not six. Worth remembering when reading the plan: the normaliser guards new
input, the rotation guards stored input, and neither substitutes for the other.

### No automatic PIN rotation after `guest_pin_abuse`

W3.7 raised the lockout from per-IP to per-link, and deliberately did **not**
auto-rotate the PIN when the `guest_pin_abuse` alert fires. Rotating at that
point would invalidate a PIN the host may already have sent to a legitimate
guest, and the guest would have no way to recover without a new message; the
alert already tells the host to rotate, and the `regenerate-pin` action exists
for them to do it. To keep that remedy real, the lockout key is the pair
`(token, pin_fingerprint(token, stored_pin))` rather than the token alone: a
fresh PIN is a fresh budget, so the host's action immediately unblocks the
guest. A token-only key would have locked the link for 24 hours with no
operator fix. If a future change makes rotation automatic, it must revisit this
trade-off rather than assume the two are independent.

### The Turnstile fail-open bound is per source address

W3.8 fails open for five attempts per (source address, action) inside a
15-minute window while the verifier is unreachable, so a real Cloudflare outage
does not stop guest registration. The bound is deliberately per-address rather
than global — a global counter would shut the whole site out after five guests,
which is the failure the item exists to prevent — but it does mean an attacker
who can both keep Turnstile unreachable *and* rotate source addresses gets an
unbounded bypass for the duration. That is a strictly better position than the
old behaviour (every guest blocked outright, no alert), and the outage is
reported either way, so it was accepted. If the bound ever needs to be global,
it should be a global *alert* threshold with a per-address allowance, not a
global rejection.

Note also that `verify` is shared: `routes/admin_accounts.py:33` (host login)
fails open on the same terms, which is intended — a host who cannot log in
during an outage cannot resolve the alert telling them about it.

### F32's proxy half is a deployment setting, not an app defect

W3.9 fixed the two app-level halves of [F32]: `rate_limit.blocked()` no longer
returns `False` for a falsy key (it fails closed), and `client_key()` maps a
missing peer address to the shared `UNIDENTIFIED_CLIENT` bucket instead of an
empty string, so a limit built on it still counts. The audit row's third point —
"the proxy bucket is shared" — was not a code change. `client_ip.py` only ever
*overwrites* `scope["client"]` with `CF-Connecting-IP` when the immediate peer is
in `trusted_proxy_networks()` (`TRUSTED_PROXY_CIDRS` — the explicit list, and
nothing else) **and** `_normalise_visitor_ip` accepts the header as an IP. With
`TRUSTED_PROXY_CIDRS` unset — the state the audit was describing, and still the
state with `CLOUDFLARE_PROXY=1`, which no longer implies any network — no header
is trusted at all, so every request behind a reverse proxy collapses onto the
proxy's own address. That is a deployment configuration to document and set, not
something the application can infer; changing it in code would mean trusting a
client-supplied header by default, which is a worse defect than the one it would
fix. The review of Phases 1-6 then closed the remaining hole: `CLOUDFLARE_PROXY`
used to imply the whole private space (loopback, `10/8`, `172.16/12`,
`192.168/16`), so any host that could reach the origin from a private address —
a co-tenant container, a machine on the office LAN — could name its own visitor
address and walk past every per-address limit. The implied default is gone; the
operator names the proxy network in `UBYHOST_TRUSTED_PROXY_CIDRS`.

### `GUEST_POST_MAX_ATTEMPTS = 30` is deliberately loose

The new limit on `/save`, `/party` and `/another` allows 30 writes per (source
address, link) per 15-minute window. It is set well above what a careful guest
does — a guest fixing validation errors saves repeatedly, and each attempt is
cheap — because the control it complements (the PIN gate and the claim cookie)
is what decides *who* may post; this one only bounds *how often*. The tests pin
the behaviour, not the number: they assert that the budget is spent and that a
different address or a different scope is unaffected, so raising the constant
would not fail the suite. A determined attacker can still spend 30 writes per
link per address; if that ever proves too many, tighten the constant rather than
adding a second limit on top of it.

## Found while landing Phase 3 (deploy path)

Unlike the sections above, the first entry here was acted on: the owner
authorised the fix as a follow-up PR after Phase 3 merged. It is recorded here
because it was found while verifying the Phase 3 deploy, not because it was in
the plan.

### The deploy never reloaded Caddy, so Caddyfile changes sat inert

Phase 3's W3.3 added `request_body { max_size 20MB }` to all three Caddyfiles.
The production deploy that followed (`35766856980`) succeeded, but the running
Caddy was still on the old config — its log showed `Container ubyhost-caddy-1
Running` rather than a recreate, and `Up 20 hours`.

Three facts combine to cause this:

- `deploy/lightsail/scripts/deploy.sh` copies the chosen Caddyfile to
  `caddy/Caddyfile.active` before starting the stack.
- The same script then runs only `docker compose up -d --remove-orphans`. The
  caddy service definition is unchanged by a config-only edit (the file is
  bind-mounted, so its *content* is not part of the service spec), so Compose
  sees no diff and never recreates the container.
- The compose service sets no `command:` override, so Caddy runs the image
  default `caddy run --config /etc/caddy/Caddyfile` with no `--watch`. Caddy
  documents `--watch` as development-only, so relying on it is not an option
  even if it were enabled.

The fix is an unconditional `caddy reload` after `up -d`, using the admin API
(`localhost:2019` inside the container, enabled by default). `caddy reload` is a
graceful, zero-downtime config swap; `docker compose restart caddy` would drop
live connections and is unnecessary.

**A change-detection design would have been the wrong fix**, and this is worth
recording because it is the intuitive first idea. Because the script copies the
new Caddyfile into place *before* the reload would run, on exactly the deploy
that needs a reload the deployed file already matches the mounted one — so
comparing them would report "no change" and skip the reload, leaving the cap
inert forever. The reload must be unconditional, and it must fail the deploy
when it fails: Caddy validates a new config before applying it and keeps the
running config if validation fails, so aborting on a bad config is safe.

Generalisation: any config consumed through a bind mount and applied by a
process that neither watches the file nor gets recreated by `up -d` has this
gap. Auditing the other bind-mounted configs for the same pattern is its own
follow-up.

### Cloudflare challenges `/login`, `/admin*` and `/l/*`, which the public smoke cannot see past

The post-deploy public smoke (`scripts/smoke-remote.sh`) reports a failure for
`/login` returning 403 where it expects 200. It is **not** a Phase 3 regression:
the identical failure appears in the Phase 1 (`35740871070`) and Phase 2
(`35743759624`) production deploys, before Phase 3 existed. The check is a
warning, not a gate — `deploy.sh` prints `WARNING: public smoke failed` and the
deploy still succeeds — so it was silently tolerated for at least three deploys.

**An earlier version of this entry was wrong and this corrects it.** It
attributed the 403 to bot protection aimed at the CI runner, on the grounds that
"the same URL is fine from a browser". Probing production by path from an
ordinary client on an ordinary network shows a **Cloudflare managed challenge**
(`cf-mitigated: challenge`, `server: cloudflare`, interstitial title
`Just a moment...`, `cType: 'managed'`) on a specific set of path patterns — not
something specific to CI:

| Path | Response |
| --- | --- |
| `/`, `/healthz`, `/legal`, `/privacy` | 200 — the app answers |
| `/login` | 403 — Cloudflare challenge |
| `/admin`, `/admin/login` | 403 — Cloudflare challenge |
| `/l/*` | 403 — Cloudflare challenge |

`/l` without a trailing slash 404s while `/l/` is challenged, which is the shape
of an edge path rule rather than anything the app does: the app's own guest
routes are `/l/{token}` (`routes/guest.py`) and links are built as
`{PUBLIC_BASE_URL}/l/{permalink_token}` (`routes/admin.py`). So the challenge
covers **the link every guest is sent**, plus host login and the admin console.

For a browser this is friction, not an outage — a managed challenge self-solves in
about a second, so a guest with JavaScript enabled still reaches their form. What
it does block is every non-JS client: the deploy smoke, `curl`, uptime monitoring.
The residual risk is a guest on a hardened browser, with JavaScript disabled, or
on a restrictive network, being stopped at the interstitial with no app-level
error and nothing in the app's logs. It has been present in every deploy log at
least as far back as Phase 1, so when it was configured is not recorded here.

Two ways out, neither of which is a code decision:

1. **Scope the challenge off `/l/*`** in Cloudflare, keeping it on `/login` and
   `/admin*`. This is the only option that removes the guest-facing friction, and
   it is a production configuration change requiring the owner's authorisation.
2. **Accept it and make the smoke honest about it.** Done: `smoke-remote.sh` now
   recognises a Cloudflare challenge and reports `SKIP … (Cloudflare challenge;
   origin not reached)` and counts it, rather than emitting a `FAIL` that the
   deploy then ignores. Any other unexpected status — 500, 502, 404 — still
   fails, so the smoke still asserts what a challenge cannot produce. A challenge
   is never a pass and never a failure, because the origin was never reached.

Option 2 removes the false alarm; it does not by itself establish that a real
guest can reach `/l/*`. Only option 1, or a browser check, settles that.

### The Caddy reload can race the admin API on a brand-new host

The unconditional reload added above runs `docker compose exec -T caddy caddy
reload` immediately after `docker compose up -d`. `up -d` returns when a container
is *started*, not when it is *ready*, and the `caddy` service declares no
`healthcheck` in `deploy/lightsail/docker-compose.yml` — unlike `ubyhost`, which
is `service_healthy` and is what `caddy` itself waits on. On the ordinary deploy
path this is invisible: the container has been up for hours and only its mounted
config changed.

On a first-ever deploy (the `docs/LIGHTSAIL.md` bootstrap path) or after a
`docker compose down`, the container is genuinely fresh and Caddy may not have
bound its admin API on `localhost:2019` yet when the reload runs. The deploy then
aborts with `Caddy reload failed — the deployed Caddyfile is NOT active.` That is
the intended fail-closed behaviour and the Caddyfile is correctly mounted either
way, so a re-run succeeds — but on the one deploy where the operator is least sure
of the system, the message reads like a real failure.

Not fixed here, because both remedies are changes to the deploy path beyond the
reload fix that was authorised: a bounded retry around the reload (poll
`caddy version` before reloading), or a `healthcheck` on the caddy service plus
`docker compose up -d --wait`. A healthcheck alone is not sufficient, because
nothing `depends_on` caddy.

## From Phase 4 (evidence trail and UbyPort semantics)

### W4.2 — the 1xx series is not generalised beyond 112

The Foreign Police's written answer describes 112 as a *critical transmission
error in the 1xx series* and says the series means the batch was not received at
all. Only 112 is treated as correctable. The other 1xx codes are left to the
default, which is already `error` (correctable) for anything unrecognised, so the
observed behaviour happens to match the series rule without asserting it.

It is not asserted on purpose. We hold no code book listing the other 1xx values,
and the register's own Czech prose is the only description we ever see for a code
that is not in `KNOWN_CODES`. Hardcoding "1xx means not received" and
blind-retrying a code that actually means "received, but this record was
rejected" would resend a batch the service already accepted, and the module
docstring in `App/app/ubyport/errors.py` warns that abusive resubmission can have
web-service access revoked. If the owner ever obtains the full 1xx list,
`CORRECTABLE_CODES` in that module is the single place to extend.

### W4.2 — classification still depends on the register's Czech wording

`classify()` now short-circuits 112 and 150, but every other code is classified by
substring-matching the *described* text against `NON_CORRECTABLE_MARKERS`
(`duplic`, `pozd`, `late`) and falling back to `KNOWN_CODES`. A wording change on
the police side therefore silently reclassifies records: that is exactly what made
the old 112 entry ("Reported late …") non-correctable, and the same trap is still
armed for every other code. A comment records this at the point of use, and 112 no
longer depends on it at all. Closing it properly means pinning classification to
codes rather than prose, which needs a code book we do not have.

### W4.3 — identity verification is advisory and never gates a send

Deleting `verified_by_user_id` from the send path settles the immediate defect, but
it leaves a wider question. Nothing checks `guest.identity_verified_at` before
filing: `reporting.send_controls` lists `awaiting_verification` among the sendable
statuses and `reporting.guest_issues` never consults the column, so an unverified
record can be submitted and the only consequences are the "Verify passport before
reporting" label and the `unverified` count in `reporting.registration_progress`.
Under `automation_mode` of `immediate` or `scheduled` it is even labelled
"Complete — sending automatically".

That is deliberate per `record_host_identity_confirmation`'s docstring ("Optional
before sending"), and it is why the parameter was deleted rather than wired up —
stamping a human attestation from an unattended sweep would be a fabrication. But
if the intent is that a foreign guest may not be filed before a human has checked
the travel document, the gate does not exist yet.

### W4.4 — there is still no normalised submission-to-guest link

`guest.submission_id` and `submission.guest_ids` are now explicitly documented as
two views of one fact, with tests covering both directions, but they remain two
denormalised columns that can disagree. A `submission_guest` join table keyed on
`(submission_id, guest_id)` would make the relationship the single authority and
remove the "which column wins" question entirely. It is not a small change: it
needs a backfill, and the append-only migration mechanism in `App/app/db.py`
cannot transform data, so it would need an explicit one-shot migration script.

### W4.6 — recurring events are detected and warned about, not expanded

Per the owner's decision, `RRULE`/`RDATE`/`EXDATE` are recognised and reported as
`feed_recurring_event` rather than expanded. A weekly cleaning block, for instance,
imports only its first occurrence and the host is told. Correct expansion needs a
recurrence engine (a new dependency, or a hand-written `RRULE` subset) plus a
decision about which occurrence is *the stay* — a repeating event is not obviously
one reservation. Until then the warning is the contract: a host who ignores it
under-imports a series.

### W4.7 — the pinned adapter builds its connection classes per request

`feed_fetch._pinned_adapter` generates four classes per call, because the pinned
address is class state. That is what makes the pin per-request rather than
process-global, so it is deliberate — but it means the adapter cannot be cached or
reused and every fetch allocates fresh class objects. At the current cadence (one
poll per apartment per interval, plus "Sync now") this is irrelevant. It is worth
revisiting only if feed fetching ever becomes hot.

### W4.2 — 112 is now retryable with no cap, backoff, or attempt counter

Making 112 correctable is the right call, but it introduced a state the code has
no brake on. A guest that comes back 112 stays `error`, `collect_sendable` only
skips `SENT` and `BLOCKED`, so the record is offered to the next sweep every
`UBYHOST_SUBMIT_SWEEP_MINUTES` (10) for as long as it keeps failing. The
`attempts` / `next_attempt_at` columns at `App/app/db.py:275` belong to the mail
queue, not to guests, so nothing counts submissions for a guest.

That matters because a *transient* 112 (interrupted connection) and a *data* 112
(invalid character in the generated `.UNZ`/`.XML`, empty mandatory field) arrive
as the same code. Retrying is exactly right for the first and futile for the
second, and the police's own remedy — check the guest's card, repeat the
submission — assumes a human is looking. Today the only signal that a record is
stuck is the `submission_rejected` critical banner, which is dedupe-keyed and so
updates in place rather than escalating, and `docs/OPERATIONS.md` can only
*advise* "if a record comes back 112 twice, stop retrying and check the data".
The application does not enforce it, and `docs/PRODUCTION_CHECKLIST.md` says the
same thing in prose.

A `guest.submit_attempts` column (append-only, `NOT NULL DEFAULT 0`) plus a
threshold — say the third consecutive 112 flipping the record to `BLOCKED` with
a distinct alert kind, so it leaves the automatic queue and becomes a human task
— would close it. It is out of scope here because it changes `submit_state`
transitions again and needs a decision from the owner on the threshold and on
whether the count resets on any non-112 outcome. Until then the exposure is
bounded but real: a structurally invalid record is re-sent every ten minutes
indefinitely, and each attempt is another submission against the host's
web-service access.

**Closed.** `guest.submit_attempts` now exists and the sweep stops offering a
record after `SUBMISSION_MAX_AUTO_ATTEMPTS = 3` consecutive refusals
(`App/app/reporting.py`). Three decisions were taken, and they differ from the
sketch above in two places on purpose:

- **The record is not flipped to `BLOCKED`.** `blocked` means "resending will
  not fix this", which is a claim about the *data* that a 112 does not support —
  the same code covers an interrupted connection. A stranded record stays
  `error`; only the automatic sweep declines to keep offering it.
- **The bound is on the unattended path alone.** Every host-initiated send
  passes `ignore_automation=True`, so the cap can never refuse a host action.
  The intended flow is: sweep hits the bound, a warning card names the stay, the
  host checks the data, the host sends by hand — which still works.
- **The count resets on any answer, not only on a non-112 one.** An accept and a
  duplicate (`150`) both restart it at 0, and so does the host saving the guest
  form, so correcting the data is the remedy rather than a second dead end.

The `submission_stuck` card is raised once per stay at the bound and resolves
itself when no guest on that stay is stranded any more. `docs/OPERATIONS.md`
now describes the enforced bound rather than advising one.

### The host notification e-mail is always English

`App/app/mail_notify.py` sends the submission-problem notice in
`host_i18n.DEFAULT_LANGUAGE` ("en") and passes no `lang` to
`build_submission_problem`. The web UI is fully bilingual and honours the
`ubyhost_lang` cookie, so a Czech host reads the app in Czech and then receives a
failure e-mail in English — the one message that most needs to be understood.

The reason is structural, not an oversight: **there is no stored language
preference anywhere.** `user_account` (`App/app/db.py:24-38`) has no language
column, and `reservation.lang` is the *guest's* language for the claim flow, not
the host's. The cookie is the only record of the host's choice, and the send
happens in a background sweep where there is no request and therefore no cookie.

Fixing it properly means an `owner_user_id`-keyed language column with a
migration, plus a decision on what a platform-admin or multi-owner account
defaults to. A cheaper interim would be to store the language on the
`legal_entity` row beside `contact_email`, which is the address the mail already
goes to — but that is still a schema change and an owner decision, so it is
recorded rather than guessed at.

Two related behaviours are deliberate and not defects: the mail is sent at most
once per property per Prague day (a same-day repeat updates the alert but does
not re-send, so the host keeps the first explanation rather than a stream of
them), and it goes only to the host. Guests are not mailed about a filing
failure; the guest-facing incomplete-registration reminder is a different
message on a different trigger.

### The `dates_changed` mail kind is registered but nothing ever sends it

**Resolved by UX-134 (audit E-16).** `dates_changed` has been removed from
`mail.KINDS` and `mail.HOST_KINDS`; the list now reflects what the app actually
sends. `docs/SES.md` no longer promises a plain-text-only kind. Re-adding it
needs a composer in `mail_notify.py`, EN/CS strings in `i18n.py`, and a test —
and it belongs in exactly one of `GUEST_KINDS` / `HOST_KINDS`.

The product gap the entry described is still open and unchanged: when the
calendar moves a stay's dates after the guest signed, the host gets an alert
(`dates_changed_resign`) and the guest gets nothing, even though the signed form
names dates that are no longer true. Whether the guest should be told is a
product decision — it is a change to a legal declaration, and telling the guest
may be worse than telling only the host. The audit's own recommendation is to
build it as a separate product item, because it adds a guest step.

### W4.2 — records already stored `blocked` by an earlier 112 are not swept

The corrected 112 classification is applied when a response is *received*, so it
only changes what happens to filings attempted after this phase deploys. A guest
who was already stored `blocked` by an earlier 112 — which, before W4.2, was
every guest in such a batch — is not picked up by anything afterwards. Nothing
resets the stored state: `submit_state` appears in `App/app/db.py` only in the
`SCHEMA` literal and an index, never in a migration, and the state machine has no
age-out. `reporting.pending_reportable` excludes `BLOCKED` outright
(`App/app/reporting.py:349`), so neither an automatic nor a scheduled send will
ever put that record back in the queue, and `reporting.py:689` skips `BLOCKED`
again on the send path unless the caller passes `allow_resend`.

The result is a record that is silently stranded: the UI shows no signal that
anything is wrong, because the guest never re-enters the queue to be noticed.

This is a gap in *bulk and automatic* recovery, not in recoverability. Two manual
paths work today, both confirmed on this branch:

1. **Saving the guest's form resets the state.** `App/app/routes/admin.py:1698`
   moves `submit_state` out of `(ERROR, BLOCKED, NOT_REQUIRED)` back to `PENDING`
   and clears `last_errors` (the "Rule 10.4(5)" comment at line 1699), and the
   trailing `reporting.submit_stay_if_complete(...)` at line 1705 then fires a
   send. This is the more natural path, and the right one when the 112 had a
   *data* cause — a bad nationality, date of birth or document number — because
   the operator has to correct the field anyway.
2. **The single-guest resend works on a 112-blocked record.**
   `POST /guests/{guest_id}/resend` (`App/app/routes/admin.py:1849`) refuses only
   when `reporting.blocked_as_duplicate(guest)` is true, and that reads
   `guest["last_errors"]` through `uby_errors.is_duplicate` for a duplicate
   marker (`App/app/reporting.py:629-635`) — which a 112 record does not carry, so
   the route proceeds with `allow_resend=True` and `reporting.py:695` lets it
   through. The control is in the guest form's danger zone,
   `App/app/templates/guest_form_admin.html:226-236`. This is the right path when
   the 112 had a *transient* cause — an interrupted connection — and no field
   needs changing.

**What this means for the deploy.** Deploying this phase does not fix the
records that are already blocked; it only stops new ones from joining them. After
deploy, an operator must walk the existing `blocked` list deliberately and take
each record through one of the two paths above. That list is the honest measure
of how many guests the pre-W4.2 behaviour left undeclared, and until it is
cleared those guests stay unreported to the Foreign Police with no automatic
signal that anything is outstanding.

A migration that reset every `blocked` row would not be safe as written, because
`BLOCKED` also holds genuine duplicates (`reporting.py:861` sets `BLOCKED` for
`not_correctable`, and a duplicate is correctly not resendable). Any automatic
sweep would have to distinguish the two, which is why this is recorded as a
deliberate manual step rather than fixed in code.

## From Phase 5 (W5.1 dead code)

### W5.1 — CSV migration of existing reservations / a paper house book

`stays_import.import_csv` and `housebook.import_csv` were deleted because no
route, form, or CLI reached either of them, and `housebook.import_csv`'s only
tests (`App/tests/test_housebook_import.py`) exercised it in isolation. The
feature they were written for is real and still unbuilt: a host arriving from a
paper house book, or from a spreadsheet of already-booked reservations, has no
way to get that history into UbyHost today. Rebuilding it needs a decision on
which of these is wanted before any code exists:

1. **Import historical reservations** so past stays appear in reports and the
   retention clock, accepting that their guests were filed on paper and carry no
   UbyPort receipt.
2. **Import a paper house book** as already-filed records, which is what the
   deleted code assumed — it wrote the literal marker `imported` into the row in
   place of a signature image, and refused to submit anything it imported.
3. **Neither**, on the grounds that a back-filled record is weaker evidence than
   a fresh filing and the operator should enter only what is still actionable.

Options 1 and 2 need upload UI, a parser, duplicate/collision handling against
existing stays, and an audit trail — none of which existed. `docs/TECHNICAL_
COMPLIANCE_AUDIT.md` used to reason about option 2 through a symbol
(`import_housebook_rows`) that appears nowhere in the repository; that row has
been corrected to describe only the PDF that the application actually generates.

### W5.1 — unreferenced tools and guide screenshots

`tools/walkthrough.py`, `tools/feature_smoke.py`, and `tools/pin_gate_check.py`
were removed, as were `static/guide/housebook-filters.png` and
`static/guide/help-link.png`. Nothing in the repository referenced any of them.
`tools/design_matrix.py` was kept: its `IndentationError` at the `print(target)`
line was a stray over-indent, and the script is the screenshot matrix referenced
by the design workflow. CI does not lint `tools/`, so these had been invisible to
every gate; making CI lint `tools/` is W6.1.

### W5.1 — the SES feedback queue setting is documented in an old patch file

`config.SES_FEEDBACK_QUEUE_URL` was deleted because nothing read it, and
`docs/ENVIRONMENT.md` plus `docs/SES.md` were updated to say so.
`docs/ubyhost-docs-update.patch` still contains the removed row. It is a
historical patch artifact rather than live documentation, so it was left alone.

## From Phase 5 (W5.2 duplication collapse)

### W5.2 — two naive-timestamp conventions still coexist

`reporting.py` now documents its module-level convention — a naive timestamp
stored by the application is UTC — and `_as_utc()` is the single converter the
send-decision code uses. `deadlines.local_now()` deliberately keeps the other
convention: a naive timestamp compared against it is Prague civil time, because
it is answering "what does the guest's phone say", not "when did we record
this". The split is intentional and now documented on both sides, but it is
still a trap for the next reader: the same column can mean two things depending
on which module reads it. The durable fix is to store every timestamp as an
explicit UTC ISO-8601 value with a `Z` and convert at the edge, which is a
migration and was out of scope here.

## From Phase 5 (W5.3 efficiency)

### W5.3 — `connect()` no longer repairs a database swapped under a running server

The schema check used to run on every `connect()`, which is why a database file
restored from an older backup, or replaced under a server that was already
running, healed itself on the next query. It now runs only in `init_db()`, at
startup, which is what took a 29-pragma cost off the query path. A database
replaced while the process is up is therefore no longer healed until restart.
Nothing in the deployment does that today — `deploy-production.yml` restarts the
service around a data change — so the trade was worth taking, but if a
hot-restore path is ever added it needs an explicit re-check rather than a
reliance on `connect()`.

### W5.3 — `init_db()` migrates the schema twice, and should not have to

`SCHEMA`'s `CREATE TABLE guest` is missing eight columns that only
`ADDED_COLUMNS` supplies (`archived_at`, `passport_photo_at`,
`identity_verified_at`, `identity_verified_by`, `doc_number_enc`,
`visa_number_enc`, `receipt_submission_id`, `submit_attempts`), and `SCHEMA`
creates indexes over `owner_user_id`, which an older database also lacks. So
`init_db()` now runs `_add_missing_columns()` both before `executescript(SCHEMA)`
(because the indexes would otherwise fail on a legacy database) and after it
(because a fresh database has no tables for the first pass to inspect). Two
passes, nine pragmas each, once at startup: cheap, but a symptom. The fix is for
`SCHEMA` to describe the current shape of every table and for `ADDED_COLUMNS` to
carry only what an upgrade genuinely needs — which the append-only migration rule
forbids doing in place, so it is a deliberate re-baseline rather than a patch.

## From Phase 5 (W5.4 language)

### W5.4 — the guest page default moved from English to Czech

`host_i18n.PUBLIC_DEFAULT_LANGUAGE` is `"cs"` and `i18n.DEFAULT_LANGUAGE` is
`"en"`, which read as a contradiction until the two roles were separated in the
docstrings: `cs` is the language a *signed-out visitor* gets, `en` is only what a
*missing key* falls back to. A guest following a host's link with no `?lang=` and
no language cookie now reads a Czech form where they used to read an English one.
That is the intended behaviour for a Czech host, but it is a visible change and
it silently inverted roughly two dozen tests that asserted English guest copy;
those now ask for English explicitly. If a host ever wants to onboard a
non-Czech guest, the language switcher is the only escape hatch and it is
cookie-scoped, not per-link.

### W5.4 — the alert-language split needs a migration to be complete

Alert rows are now language-neutral: `message` and `detail` hold English log and
fallback copy, and a new `alert.params` column holds the interpolation values as
JSON so `alerts.present()` can rebuild the card in whatever language the reader
is using. The catch is that `params` is added by `ADDED_COLUMNS` and every
pre-existing row has `NULL` there. A stored alert whose copy interpolates
therefore still renders English after the upgrade, because `_localised` refuses
to substitute into a card whose parameters it does not have. New alerts are
correct immediately. A one-off backfill cannot fix the old rows — the values
were never stored, only baked into the English sentence — so the practical
answer is to let the old alerts age out, or to resolve them by hand if any
matter.

### W5.4 — the `err=` flash messages are still English

The plan asked for the `msg=` flashes, and those are converted: 40 sites in
`routes/admin.py` and 3 in `routes/admin_accounts.py` now go through
`admin_helpers.flash(request, key, **params)`, which translates at the raise
because `back()` carries a plain string in a URL query parameter. The sibling
`err=` parameter is untouched: **87 sites in `admin.py` and 5 in
`admin_accounts.py` still flash hardcoded English error copy** to a Czech host.
The mechanism is identical, so the conversion is mechanical, but it is a large
enough diff to deserve its own review pass and was explicitly out of scope for
W5.4.

### W5.4 — two plan items were already satisfied and needed no change

The plan asks for the guest-visible English validation error at
`reporting.py:184-186` to be routed through the guest catalog, and for the "dead
English deadline prose at `reporting.py:997-1003`" to be deleted. The first was
already fixed by W5.2's single completeness predicate: the message now comes from
`reporting.guest_issues(..., translate=...)` with the guest translator passed by
the guest route. The second describes a block that no longer exists at any line —
`reporting.py` has been rewritten twice since the plan was written (the code-112
retry fix, then W5.2), and no dead English deadline prose remains. Both are
recorded here rather than re-done so the audit trail shows they were checked.

### W5.4 — the alert language had to be a presentation concern, not a key rename

The plan implies the alert copy can be moved key-by-key into `host_i18n` the way
the flash messages were. It cannot, for the alerts whose card is rebuilt from
live data (`_COMPUTED_ALERT_KINDS`) or whose wording depends on a state the
stored English sentence happens to describe: the reader's language is not known
when the alert is raised, and a card is read long after the event that raised it.
So `raise_alert` now takes `params=` and stores them, and `present()` dispatches
between a stored card and a computed one. Any future alert kind that interpolates
must pass `params=`; a test walks the AST of `app/**` to enforce that, because
the failure mode is silent — the card simply stays English.

### W5.5 — `require_login` short-circuits when the database has no accounts

Found while writing the split's test. `auth.require_login` deliberately returns
`None` — i.e. grants access — when `accounts_exist()` is false, bootstrap is
disabled and the deployment is not production (`auth.py:274-279`). In the test
environment `UBYHOST_BOOTSTRAP_ADMIN=0`, so an anonymous request renders a host
page instead of redirecting to `/login`. That is intended for a first run, but it
means any test asserting "an anonymous request is redirected" has to create an
account first or it silently tests nothing.

### W5.5 — `/onboarding` renders an undefined template variable with no workspace

Same investigation. `templating.render` sets the `onboarding` template global only
when a workspace user exists (`templating.py:142-143`), but
`routes/onboarding.py::onboarding_view` renders `onboarding.html`, which reads it.
With no accounts and bootstrap off, `require_login` lets the request through and
the template raises `jinja2.exceptions.UndefinedError: 'onboarding' is undefined`.
This is **pre-existing** — the route and the render path are unchanged by the
split (the moved function is byte-identical to its `HEAD` version) — and it is
only reachable in the no-accounts development configuration, where the page has
nothing to show anyway. Recorded rather than fixed: making it a 404 or a redirect
to `/setup` is a product decision, not a refactor.

### W5.5 — five routes the plan's wording could have moved were deliberately left

The plan names `submissions_list`, `submission_detail`, `housebook_view`,
`dismiss_alert` and `settings_view` in the exports work item's parenthetical. Read
in context those names document the *functions the export routes call* (and the
`ARCHIVED_TYPES` constant `settings_archived_view` needs), not move targets; the
plan's own "what remains in `admin.py`" list never mentions submissions or the
settings page, and the move would have split those pages across two modules.
`guide_view` is likewise left in place because the plan does not ask for it. All
six are recorded here so the choice is visible in review rather than implied.

## From the UX audit — UX-80 (E-14): host mail is English by decision

The audit flagged that host mail hard-coded `"lang": "en"` in one place and
defaulted to `host_i18n.DEFAULT_LANGUAGE` in another, so nobody could tell
whether English was a decision or an accident. **The product owner has decided:
host mail stays English.** It is not to follow the host's UI language and not to
use bilingual subjects. The reason is that there is no stored per-host language
preference to read; guessing from the request would send a different language
from the same host depending on which device happened to trigger the sweep.

The choice is now named once: `mail_notify.HOST_MAIL_LANGUAGE = "en"`, used by
`submission_problem()` and by the `reminder_host` payload that `claim.py`
enqueues. It is a constant, not a literal, so the one place to change when a
per-host preference eventually exists is obvious and greppable.

**The Czech host-mail keys stay in `host_i18n.STRINGS["cs"]`.** The audit's
"don't leave the CS keys dead" rule only applies to the CS-default scenario; with
English chosen they are the copy a future per-host preference would select, and
they keep the EN/CS parity test meaningful.

**`PLAN_GUEST_INVOICE_FEATURE.md` was corrected in the same change.** Its
`invoice_request_host` row specced the body in Czech ("Host X požádal o
fakturu"), which contradicted the English decision; the row now specs English
copy and cites E-14. Only the plan text changed — the invoice feature itself is
still unbuilt.

**Still open:** a stored per-host language preference would retire this interim
rule and let the CS keys above go live. That is a schema change (a column on
`user_account` or `legal_entity`) plus a Settings control, and it is not part of
the audit.

## From the GDPR plan

### LD-4 — the register's DPA-version bump and the support-mailbox row are deferred
The register correction shipped in `App/app/subprocessors_i18n.py`: the AWS S3
row and the Google Drive rows no longer claim the backups are encrypted, and
`subprocessors.effective` is now Version 1.1. Two parts of LD-4 remain open, and
neither is an engineering call:

- **`config.DPA_VERSION` was not bumped.** The register says it forms part of the
  DPA, and LD-4 gates the bump on counsel ("if counsel treats the register as
  part of the DPA"). It is also inert today: BE-1/FE-1, the mechanism that turns
  a bump into re-acceptance, does not exist yet. Bump it together with BE-1 once
  counsel confirms.
- **The support mailbox provider is still unidentified**, so it has no row in the
  register. LD-9 identifies it; add the row then, under the 30-day notice rule in
  `subprocessors.change_body`.

### LD-4 — other public copy also calls the backups encrypted, and one cadence is wrong
LD-4 names only `subprocessors_i18n.py`, but the same false claim sits in the
documents LD-3 already owns:

- `privacy_policy_i18n.py` §11 (`:172` EN, `:408` CS) says the Operator may keep
  "encrypted database and key backups" and "encrypted off-site copies" — false
  until OPS-1.
- `dpa_i18n.py` §15 (`:190` EN) says Guest Data may be "retained in encrypted
  backups"; the CS body (`:404`) does not say encrypted, so the pair also
  disagrees.
- The same privacy §11 sentence says off-site copies go "weekly to Google Drive
  and monthly to Amazon S3"; `backup-s3.sh` is documented as weekly, so that
  cadence needs checking when LD-3 aligns the copy.

Left untouched on purpose: outside LD-4's stated file scope, and LD-3 already
owns `privacy_policy_i18n.py` §11 and `dpa_i18n.py` §15. Until OPS-1/OPS-2 land,
the honest wording is the non-encrypted one.
