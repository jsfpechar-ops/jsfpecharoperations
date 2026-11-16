Status: review
Chunk: C2 done
Done: steps 2.1 to 2.6 (commits "A4 C2 step 1" to "step 6"). Left: C3 (browser test, UX gate, screenshots, PR).
Tool calls used: 26
Deviations:
- Step 2.2: the brief's section has 4 jinja fences; the 4th is the existing anchor line (b), not an insert. Inserted the three blocks (a, c, d) after their anchors.
- Step 2.6: the brief's minimal save payload gave 400 (required fields missing). The last test now uses the full `_payload()` helper from tests/test_police_letter_flow.py (added to the import list). Assertion unchanged (303 or 422).
- Step 2.3: `from app import alerts` added inside the endtoend test function (brief allowed it).
- Branch is feat/ubyport-settings-check (not task/a4-ubyport-settings-consistency). Not pushed.
Commands and results (App/ unless noted):
- `python -c "import app.routes.admin"`: no output, rc 0
- `pytest tests/test_police_letter_flow.py`: 48 passed
- `pytest tests/test_endtoend.py -k fault_flash_names_the_fault`: 1 passed, 29 deselected
- `gofmt -l internal/ubyport/`: no output; `go vet ./internal/ubyport/`: no output
- `go test ./internal/ubyport/...`: ok; `-run TestTransportAlertParamsNameTheThreeFieldsOnlyOnAFault -v`: PASS
- `scripts/go_host_i18n.py` (regenerate) then `--check`: rc 0 (go/internal/hostweb/layout/i18n.json changed)
- `go test ./internal/hostweb/...`: ok
- Combined set `pytest tests/test_police_check.py tests/test_police_letter_flow.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_flash_literals.py tests/test_no_em_dashes.py tests/test_privacy_first.py -rs`: 96 passed, 0 skipped
- `python3 scripts/context_lint.py`: OK
Branch head: see `git log --oneline -1` on feat/ubyport-settings-check
Next: start C3 with this brief; first command `git log --oneline -5` must show "A4 C2 step 6".
