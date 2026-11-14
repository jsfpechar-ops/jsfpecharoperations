# 1447: Go guest guide editor, part 8: add a card photo (POST .../photos)

Status: blocked — the upload needs a WebP decoder that is not in `go.mod` (AGENTS.md rule 4: no new dependency without an owner decision line in [decisions](../context/decisions.md)); until the owner decides, `POST /apartments/{id}/guide/{item}/photos` stays on Python. Do not run.
Depends on: 1441, owner decision | Base commit: 68c0e0985 | Branch: none
Executor: none (blocked) | Fits one session: not written

## 1. Objective

Port `guide_photo_add` (`App/app/routes/guest_guide.py` 402-421) and `guide_photos.add` (`App/app/guide_photos.py` 68-95) so the whole guide editor can move to Go.

## 2. Context

What Python does: it reads the multipart field `photo` (up to 10 MiB + 1), accepts the content types `image/jpeg`, `image/jpg`, `image/png`, `image/webp` and at least 64 bytes, allows at most 6 photos per card, then decodes the picture with Pillow (`passport_photos.reencode_image`: formats JPEG, MPO, PNG, WEBP, at most 40,000,000 pixels, first frame, EXIF orientation applied, every piece of metadata dropped, JPEG quality 90), shrinks it to 1600 px on the longest side (JPEG quality 82), writes it atomically under a random name in `$UBYHOST_DATA_DIR/guide_photos` and inserts the `guide_photo` row.

Why it cannot be ported inside the thread rules (checked in `go/go.mod`, `go/go.sum` and the standard library):

1. **WebP.** Go's standard library decodes JPEG, PNG and GIF only. A WebP decoder is `golang.org/x/image/webp`, which is not in `go.mod`. Refusing WebP would change behaviour (a host who uploads a WebP photo today gets it stored), so it is not done silently.
2. **Resizing and orientation.** The standard library has no image scaler (`golang.org/x/image/draw`) and no EXIF reader; both would be hand-written (a box filter and a small EXIF orientation parser). That is possible but unreviewed code on the path of an upload that holds guest-facing photos.
3. **Writable data volume.** The Go container mounts `/data` read-only (`deploy/lightsail/docker-compose.yml`, `ubyhost-data:/data:ro`); an upload needs a writable `guide_photos` folder. That is a deploy change the owner makes, not this thread.

Options for the owner (write the chosen one as a line in decisions, then ask for the brief):

- **A.** Approve `golang.org/x/image` (webp, draw) and a writable `guide_photos` volume for the Go service. Then the brief is a normal one: new `guide_photos_add.go`, Go decode, EXIF orientation, shrink, atomic write, golden images from the Python, tests with no network.
- **B.** Keep the upload on Python for good until Python is retired (plan section 7, X1-X3), which needs no work. Caddy then must not route `/apartments/*/guide/*/photos` (the exact path, no trailing `/*`) to Go, which is already the advice in brief 1446.
- **C.** Port JPEG and PNG only and answer WebP with `flash.error.guide_photo_type`. Smaller, but a behaviour change the owner must accept.

## 3. Files

None until the owner decides.

## 4. Steps

None: the brief is blocked. When the owner has chosen option A or C, the orchestrator replaces this section with numbered steps and sidecars like briefs 1440 to 1446 (copy, `sha256sum -c`, build, vet, tests on PostgreSQL).

## 5. Do not touch

Everything. Do not edit `go.mod`, `go.sum`, `deploy/lightsail/docker-compose.yml` or any Python file for this brief.

## 6. Commands

None.

## 7. Acceptance

- [ ] The owner has written the decision (A, B or C) as a line in decisions.md.

## 8. Stop and ask

Do not run this brief.

## 9. Report

None: no executor runs this brief.

## Owner steps

1. Choose A, B or C above and tell the orchestrator in the chat.
