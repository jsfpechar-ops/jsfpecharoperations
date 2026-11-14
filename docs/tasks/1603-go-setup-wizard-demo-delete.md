# 1603: Go setup wizard, part 5: delete the demo stay on "Delete and continue" (try-it skip)

Status: blocked: the Go web service cannot delete the demo guests' passport photo files (its `/data` volume is read-only and no exported Go photo delete exists)
Tier: A
Depends on: 1602, and the owner's decision on a writable data volume for the Go web service (the same decision brief 1447 waits for) | Base commit: current branch (One big PR mode) | Branch: current branch
Executor: none until unblocked

> **One big PR mode.** When this brief is unblocked and rewritten as `todo`, the executor works on the current branch and commits `1603 step k` after each step that changes a file; it never creates a branch, never pushes, never opens a PR.

## 1. Objective

Serve the last branch of `POST /apartments/{apartment_id}/setup` on Go: `step=try_it`, `action=skip` while the property has a demo stay. Python (`App/app/routes/onboarding_wizard.py` 362-366) calls `demo.delete_demo_stay` (`App/app/demo.py` 126-144), audits `apartment=N step=try_it action=skip` and goes back to the finish page with the flash `flash.setup.demo_deleted`. After brief 1602, Go answers 501 there and writes nothing (`wizard_post.go`, `TestWizardSkipWithDemoStayIs501`). Without this brief the owner should not route the wizard paths to Go: "Delete and continue" is the main button of the try-it page once a demo guest has registered.

## 2. What is missing (why it is blocked)

`delete_demo_stay` does four things in order: for each guest of the demo stay `passport_photos.delete_photo(guest_id)` (it unlinks every file `$UBYHOST_DATA_DIR/passport_photos/<guest_id>.*`), then `DELETE FROM alert`, `DELETE FROM guest` and `DELETE FROM reservation WHERE ... AND source = 'demo'`. The three DELETEs are plain SQL and easy to port. The file part is not, inside the rules of this series:

1. **Read-only volume.** `deploy/lightsail/docker-compose.yml` mounts `ubyhost-data:/data:ro` in the Go service (line 266). The Go web process cannot remove a file there. A demo guest's photo is a real picture the host uploaded while testing (often of their own ID card), so leaving it behind is not acceptable as a silent best effort (brief 1442 took that route for guide photos only because those carry no personal data and an orphan sweep removes them within an hour). The owner decides whether the Go container gets a writable `/data` (brief 1447 waits for the same decision for guide photo uploads, its point 3).
2. **No exported Go photo delete.** `go/internal/photosweep/files.go` has `deletePhoto(dir, id)` and `photosDir(dataDir)` (the port of `passport_photos._paths_for` and `delete_photo`), but both are unexported and the package is the photo-sweep job. The web package must not copy file-deletion code that already exists; the clean step is to export one function (for example `photosweep.DeleteGuestPhoto(dataDir, guestID)`), which is a change in another area that this series may not make.

Nothing else is missing: the 1599 context, the 1602 route and its audit helper are in place.

## 3. When unblocked (plan for the brief writer)

- Owner: a writable `/data` for `ubyhost-go` (or a dedicated writable `passport_photos` mount), decided in `docs/context/decisions.md`.
- A small brief in the photo-sweep area exports the delete of `photosweep/files.go` with its tests.
- This brief then: in `wizard_post.go`, replace the 501 branch by a port of `delete_demo_stay` (check the stay is the property's and `source = 'demo'`, delete the photo files of its guests through the exported function, then the alerts, guests and the stay, in one transaction for the rows), the audit line and `hostweb.Back(... done, msg flash.setup.demo_deleted)`; remove `TestWizardSkipWithDemoStayIs501`; add a golden part (`onboarding_wizard_golden_demo.py`) with the skip on apartments 20 and 22 of the 1599 seed and a photo file for guest 501, comparing the final rows and that the file is gone.

## 4. Owner steps

1. Decide whether the Go web service may write to the data volume (the same question as brief 1447). Tell the orchestrator.
2. Until this brief is done, keep `/apartments/*/setup` and `/apartments/*/setup/*` out of `UBYHOST_GO_PATHS` (brief 1602, Owner steps).
