# 2026 report — `/guests/{id}`: blocked, the contradiction is in both stacks

Status: blocked (the brief's §8: the cause is shared with Python, and the fix would change guest validation / UbyPort field semantics)

## What the gate saw, and what it actually is

The 2019 gate recorded: a field marked "(optional)" that reports "required", red
validation errors on a clean GET, five helper lines, a 12 × 12 input.

I traced the first two and they are **one defect, not two**, and it is not a Go regression:

- `go/internal/web/stays/templates/guest_form_admin.tmpl:121` labels `res_street`:
  `<span class="ui-opt">{{t "common.optional"}}</span>`
- `go/internal/validation/validation.go:300-302` raises it as an **error**, not a warning:
  `Issue{"res_street", "Street and number are required.", severityError}`
- Python does the same thing: `App/app/validation.py:518-532`
  `validate_residence(...)` → `if not street:` → the same required issue.

So the template promises optional and the validator demands it **in both stacks**. On a clean
GET of a guest with an empty residence street, that error is present, `guestBad` adds `bad`
and `guestErrFor` adds a red `ui-error` — which is exactly what the gate saw. Everything the
gate reported is downstream of this one disagreement.

The rendering logic itself is correct and already matches Python exactly:

```
go/internal/web/stays/guest_form_page.go:125  guestBad   → "bad" only when Severity == "error"
go/internal/web/stays/guest_form_page.go:134  guestErrFor → ui-error for errors, ui-help for warnings
App/app/templates/guest_form_admin.html:13    bad(field) → only issue.is_error
```

That last pair is why the DOM-text audit says `10851/10851` while the page still *looks*
wrong: severity changes a CSS class and a colour, and the audit compares normalised text.

## Why I stopped instead of picking a winner

Two candidate fixes, and both cross a line this brief (and the repo rules) put in front of me:

1. **Drop "(optional)" from `res_street`.** Then the label matches the validator. But the
   field is genuinely conditional for filing (the residence address matters when the guest
   resides outside the property's country), so the honest fix is a conditional label, not a
   deletion — and that is a copy decision on a filing form.
2. **Downgrade the validator to a warning.** That changes what blocks a guest from being
   filed, which is UbyPort field semantics — `docs/UBYPORT_CORE.md` forbids changing that
   without the owner, and §8 of the brief names it as a stop.

Either one also needs the owner's `UBYHOST_GO_PATHS` step if it lands Go-only, or a Python
change in the same brief, which the [go-first](docs/context/go-first.md) rule only allows
under exception 3 and only with this brief saying so.

The remaining two items are ordinary work and can be done in the same session once the
above is decided: collapsing the five helper lines into one explanation (rule 9), and
raising the 12 × 12 input to a 44 px hit area (design-system §1 rule 8).

## Files changed

None. Nothing was edited — a guess here would have silently loosened a filing rule or
removed a required marker from a police-submitted form.

## What the owner has to decide

1. Is the residence street **required** for filing, or **conditional**? (One line answer is
   enough; it decides whether the label or the validator moves.)
2. If conditional: should the label read "(if the guest lives abroad)" rather than
   "(optional)"?
3. Does the fix go Go-only with a `UBYHOST_GO_PATHS` switch, or Python too under exception 3?

## Note on the other four FAIL pages

This is the second brief of the five (after 2027) to stop on a shared-with-Python cause, which
is what the 2019 gate predicted: every FAIL page is character-identical to Python. If the
owner's answer to 3 is "Go-only, switch the path", then all of these become ordinary design
work; if it is "both stacks", they all become Python changes and belong in one brief.
