"""requirements.txt and requirements.lock must pin the same versions.

CI and the Docker image install requirements.lock, so a requirements.txt bump
(for example from Dependabot) without a lock regeneration ships the old version.
Regenerate with the command in the lock header (docs/tasks/1207).
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;\\]+)")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = PIN.match(line)
        if m:
            pins[_norm(m.group(1))] = m.group(2)
    return pins


def test_every_requirements_pin_matches_the_lock():
    wanted = _pins(APP / "requirements.txt")
    locked = _pins(APP / "requirements.lock")
    assert wanted, "no pins found in requirements.txt"
    drift = {
        name: (version, locked.get(name))
        for name, version in wanted.items()
        if locked.get(name) != version
    }
    assert not drift, (
        "requirements.lock differs from requirements.txt (name: txt, lock): "
        f"{drift}. Regenerate the lock with the command in its header."
    )
