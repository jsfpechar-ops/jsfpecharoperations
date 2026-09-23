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
in `trusted_proxy_networks()` (`TRUSTED_PROXY_CIDRS`, or the RFC1918/loopback
defaults when `CLOUDFLARE_PROXY` is on) **and** `_normalise_visitor_ip` accepts
the header as an IP. With `TRUSTED_PROXY_CIDRS` unset and `CLOUDFLARE_PROXY` off
— the state the audit was describing — no header is trusted at all, so every
request behind a reverse proxy collapses onto the proxy's own address. That is a
deployment configuration to document and set, not something the application can
infer; changing it in code would mean trusting a client-supplied header by
default, which is a worse defect than the one it would fix.

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

### `FAIL https://ubyhost.com/login → HTTP 403 (expected 200)` in the public smoke

The post-deploy public smoke (`scripts/smoke-remote.sh`) reports a failure for
`/login` returning 403 where it expects 200. It is **not** a Phase 3 regression:
the identical failure appears in the Phase 1 (`35740871070`) and Phase 2
(`35743759624`) production deploys, before Phase 3 existed. The check is a
warning, not a gate — the script prints `WARNING: public smoke failed` and the
deploy still succeeds — so it has been silently tolerated for at least three
deploys.

The likely cause is Cloudflare bot protection challenging the CI runner, since
the same URL is fine from a browser and the internal `/healthz` check passes. It
needs its own investigation: either the smoke should assert something a bot
challenge cannot break, or the runner needs to be allow-listed. Until then the
warning should not be treated as evidence of an application defect.
