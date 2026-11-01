"""The Go iCal parser reads these golden files (go/internal/ical/parse_test.go)."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "ical_golden", APP_DIR / "scripts" / "ical_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ical_golden_files_match_parse_events(tmp_path):
    generator = _load_generator()
    fixtures = generator.TESTDATA
    names = sorted(path.stem for path in fixtures.glob("*.ics"))
    assert len(names) >= 14
    generator.generate(fixtures, tmp_path)
    for name in names:
        committed = (fixtures / f"{name}.json").read_bytes()
        regenerated = (tmp_path / f"{name}.json").read_bytes()
        assert regenerated == committed, name
