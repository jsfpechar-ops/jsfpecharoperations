"""Unit tests for scripts/ci_shard.py (CI shard balancing). No browser, no database."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci_shard.py"
_spec = importlib.util.spec_from_file_location("ci_shard", _SCRIPT)
ci_shard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci_shard)


def _files(n: int) -> list[str]:
    return [f"tests/test_{i:02d}.py" for i in range(n)]


def test_greedy_split_is_disjoint_complete_and_balanced():
    files = _files(12)
    weights = {f: float(w) for f, w in zip(files, [100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 5, 1])}
    result = ci_shard.shards(files, weights, 4)
    flat = [f for shard in result for f in shard]
    assert len(flat) == len(set(flat)) == len(files)
    assert sorted(flat) == sorted(files)
    loads = [sum(weights[f] for f in shard) for shard in result]
    assert max(loads) - min(loads) <= max(weights.values())


def test_unknown_files_get_the_median_weight():
    weights = {"tests/a.py": 10.0, "tests/b.py": 20.0, "tests/c.py": 30.0}
    files = ["tests/a.py", "tests/b.py", "tests/c.py", "tests/d.py"]
    # median of known weights is 20, so d (20) ties with b and sorts after it
    assert ci_shard.shards(files, weights, 2) == [
        ["tests/a.py", "tests/c.py"],
        ["tests/b.py", "tests/d.py"],
    ]


def test_no_weights_at_all_uses_weight_one_for_every_file():
    files = _files(8)
    assert ci_shard.shards(files, {}, 4) == ci_shard.round_robin(files, 4)


def test_split_is_deterministic_and_order_independent():
    files = _files(20)
    weights = {f: float((i * 37) % 11 + 1) for i, f in enumerate(files)}
    first = ci_shard.shards(files, weights, 4)
    assert first == ci_shard.shards(list(reversed(files)), weights, 4)
    assert first == ci_shard.shards(files, weights, 4)


def test_missing_weights_file_falls_back_to_round_robin(tmp_path, capsys):
    files = _files(10)
    listing = tmp_path / "files.txt"
    listing.write_text("\n".join(reversed(files)) + "\n", encoding="utf-8")
    rc = ci_shard.main([
        "pick", "--weights", str(tmp_path / "missing.json"), "--shards", "4",
        "--index", "2", "--files-from", str(listing),
    ])
    captured = capsys.readouterr()
    assert rc == 0
    assert "no weights, using round-robin" in captured.err
    # shard 2 of 4 takes positions 2, 6, 10 of the sorted list (0-based 1, 5, 9)
    assert captured.out.splitlines() == [files[1], files[5], files[9]]


def test_weights_that_are_not_a_json_object_fall_back(tmp_path):
    bad = tmp_path / "weights.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")
    assert ci_shard.load_weights(bad) is None


def test_weights_mode_sums_testcases_per_file(tmp_path):
    xml = tmp_path / "pg-full-1.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.test_x" name="test_one" time="1.5"/>'
        '<testcase classname="tests.test_x" name="test_two" time="2.0"/>'
        '<testcase classname="tests.test_y.TestFoo" name="test_three" time="3.0"/>'
        '<testcase classname="" name="tests.test_z" time="0.0"><skipped/></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    out = tmp_path / "weights" / "out.json"
    assert ci_shard.main(["weights", "--out", str(out), str(xml), str(tmp_path / "absent.xml")]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"tests/test_x.py": 3.5, "tests/test_y.py": 3.0}


@pytest.mark.parametrize(
    ("classname", "expected"),
    [("tests.test_x", "tests/test_x.py"), ("tests.sub.test_q.TestA", "tests/sub/test_q.py")],
)
def test_classname_maps_to_file(classname, expected):
    assert ci_shard.file_of(classname) == expected
