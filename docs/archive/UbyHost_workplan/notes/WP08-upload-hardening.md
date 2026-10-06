# WP08: Passport upload hardening

Commit `e48ec43` on local branch `wp08`, based on `wpbase` (492e2b1). WP09 is stacked on top of this commit.

## Summary
- Every uploaded passport image (JPEG, PNG, WebP) is now fully decoded with Pillow and saved again as a fresh JPEG (quality 90, same resolution) before it is encrypted. EXIF orientation is applied to the pixels, then all metadata is dropped: no EXIF, no GPS, no ICC profile, no comments, no trailing bytes. Transparent PNGs get a white background.
- Images Pillow cannot fully decode (truncated, corrupt, right magic bytes but garbage body) are refused with the existing "does not look like a valid image" message.
- Decompression bombs: the image header is checked against a per-upload bound of 40 MP before any pixel is decoded. The process-wide `Image.MAX_IMAGE_PIXELS` in `main.py` now uses the same constant.
- PDFs are unchanged: magic bytes and 15 MB limit, stored as-is.
- Re-encoded images are stored as `<guest_id>.jpg.enc`. Legacy `.png`/`.webp` files are still readable.
- The download route `/guests/{id}/passport-photo` now sends `Content-Disposition: attachment; filename="passport-<id>.<ext>"` and `X-Content-Type-Options: nosniff` (plus the existing `no-store` and sandbox CSP).
- The host guest page keeps the inline `<img>` preview for images. `Content-Disposition` does not affect an `<img>`, and the stored image is now always a re-encoded JPEG. The PDF `<iframe>` preview is replaced by a download button with an EN/CS hint.
- The guest form route runs the decode and re-encode in a thread (`run_in_threadpool`) so a large photo does not block the event loop. The re-encoded bytes are passed to `save_photo(..., prepared=True)` so they are not encoded twice.

## Files changed
- `App/app/passport_photos.py`: `reencode_image`, `prepare_upload`, `download_filename`, `MAX_IMAGE_PIXELS`, and `save_photo(prepared=...)`.
- `App/app/routes/guest.py`: guest upload uses `prepare_upload` in a thread. Adds a CS message for the pixel limit.
- `App/app/routes/admin.py`: the download route adds the attachment and nosniff headers.
- `App/app/templates/guest_form_admin.html`: PDF iframe replaced by a download link.
- `App/app/host_i18n.py`: `guest.admin.passport_pdf_download` and `guest.admin.passport_pdf_hint` added (EN, CS). `guest.admin.passport_pdf_title` removed (no longer used).
- `App/app/static/app.css`: iframe styles removed, link style added.
- `App/app/main.py`: global `Image.MAX_IMAGE_PIXELS` now equals `passport_photos.MAX_IMAGE_PIXELS`.
- `App/app/demo.py`: the demo passport PNG is now generated with Pillow. The hand-written bytes had a broken data stream and would now be refused.
- `App/tests/test_passport_photos.py`: new tests (below).
- `App/tests/test_accounts.py`, `App/tests/test_encrypt_blobs.py`: fixtures updated. They used a fake JPEG, or expected `.png.enc`.

## Tests added
In `tests/test_passport_photos.py`:
- `test_reencode_strips_exif_and_gps`: GPS IFD, Make and Software tags are gone. No `Exif` segment and no ICC profile remain.
- `test_reencode_applies_exif_orientation`: orientation 6 turns 40x20 into 20x40.
- `test_reencode_keeps_resolution`
- `test_trailing_payload_after_image_is_dropped`
- `test_truncated_image_is_rejected`
- `test_image_with_right_magic_but_garbage_body_is_rejected`
- `test_pixel_bomb_is_rejected_before_decoding`: a 10000x5000 PNG of a few KB.
- `test_pixel_bomb_message_has_czech_translation`
- `test_transparent_png_is_stored_as_jpeg`: stored as `.jpg.enc`, white background.
- `test_webp_upload_is_stored_as_jpeg`
- `test_pdf_is_still_accepted_unchanged`
- `test_image_download_is_an_attachment_with_nosniff`: checks the headers, that EXIF is gone in the served bytes, and that the inline `<img>` is still on the host page.
- `test_pdf_download_is_an_attachment_and_never_framed`: checks the headers, that the page has no `<iframe>`, and that the download link is present.

## Test commands and results (exact counts)
Run from `/tmp/wp/wp08/App` with `/tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider ...`:
- `tests/test_passport_photos.py`: 22 passed.
- Related set (passport, access_audit, retention, retention_job, encrypt_blobs, guest_navigation, guest_a11y, guest_pin, ticket_wallet_v3, accounts, p3_review_repro, demo_seed, host_guest_form, guest_why_passport): 180 passed, 1 failed. The failure is `test_p3_review_repro.py::test_cf_connecting_ip_spoof_no_longer_bypasses_per_ip_limits`. It fails the same way on the unchanged base in this combination (rate-limit state left by earlier files) and passes on its own (11 passed).
- Broad suite in three chunks:
  - `test_[a-f]*`: 600 passed, 2 skipped.
  - `test_[g-o]*`: 774 passed, 5 skipped, 1 failed. The failure is `test_host_geometry.py`: Chromium cannot start in this sandbox (missing `libXdamage.so.1`). This is the environment, not the code.
  - `test_[p-z]*`: 802 passed, 1 failed. The failure is `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`. It also fails on the unchanged base in the same chunk and passes on its own, so it depends on test order.
- Ruff (`--select E9,F63,F7,F82,F401,F841`): all checks passed.
- I did not run the full suite in one process, and I did not run the guest browser e2e (no Chromium libraries here).

## Deviations from the spec and why
- Pixel bound: I used 40 MP, checked per upload from the header, and also set it as the global Pillow bound. The old global of 12 MP would raise a hard Pillow error from 24 MP up, and that rejects normal 24 MP phone photos. Signatures and QR codes keep their own stricter checks in `validation.py`. Pillow only warns between 40 and 80 MP, so the explicit header check is what rejects those.
- The re-encoded JPEG can be larger than 5 MB (for example from a large PNG). The 5 MB limit applies to the upload, not to the stored file.
- Animated PNG or WebP: only the first frame is kept.
- I found that the old PDF `<iframe>` preview could never have worked: the global `X-Frame-Options: DENY` header applies to the attachment route too. Replacing it with a download link loses no working feature.

## What Cursor must verify or adapt when applying on the real main
- Any new test fixture that uploads a fake image (magic bytes followed by zeros) will now fail. Use a real image generated with Pillow.
- Check that nothing sets `ImageFile.LOAD_TRUNCATED_IMAGES = True`. Nothing does at `wpbase`.
- If WP04 (guest data access) changed the photo route or `access.guest`, re-apply the header block in `guest_passport_photo` by hand.
- Run the guest browser e2e with `UBYHOST_REQUIRE_BROWSER=1`. The guest upload path changed on the server side only, but README rule 9 asks for it.

## Manual steps for the owner
None. Photos already stored are not re-encoded. They are deleted within 30 days by the existing sweep.
