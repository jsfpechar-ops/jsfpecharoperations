# 0302 report

Status: review

Executor commit 118f11f did steps 1-3; Czech at 1024 px still overflowed by 10 px, so the orchestrator added `td:first-child { min-width: 8rem; }` (key 0302b). §6 tests: 29 passed.

Follow-up (CI guest-browser): 0298's phone card wrap also hit the guest link card, so Copy dropped under the label and Czech cards overflowed at 360 px. The wrap now skips `.host-property-card-static`, which keeps Copy beside its label and lets only Open drop a line (key 0302e). Wizard, controls, UX acceptance, wide geometry and inline-controls tests: 104 passed with `UBYHOST_REQUIRE_BROWSER=1`.
