#!/usr/bin/env python3
"""Split CI test files into shards by measured duration (stdlib only).

pick:    ci_shard.py pick --weights W.json --shards N --index I [--files-from FILE]
         Reads test file paths (one per line) from FILE or stdin and prints
         shard I (1-based) one per line, sorted. Greedy: heaviest file first
         into the currently lightest shard. Missing or unreadable weights:
         round-robin, with a note on stderr.
weights: ci_shard.py weights --out W.json X1.xml [X2.xml ...]
         Sums pytest JUnit testcase time per test file into W.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def shards(files, weights, n):
    """Return n sorted lists that partition the unique input files."""
    unique = sorted(set(files))
    if weights:
        fallback = float(statistics.median(weights.values()))
    else:
        fallback = 1.0
    w = {f: float(weights.get(f, fallback)) for f in unique}
    out = [[] for _ in range(n)]
    loads = [0.0] * n
    for f in sorted(unique, key=lambda f: (-w[f], f)):
        i = min(range(n), key=lambda k: (loads[k], k))
        out[i].append(f)
        loads[i] += w[f]
    return [sorted(s) for s in out]


def round_robin(files, n):
    unique = sorted(set(files))
    return [unique[k::n] for k in range(n)]


def load_weights(path):
    """Return {file: seconds}, or None if the file is missing or not a JSON object."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        str(k): float(v)
        for k, v in data.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def file_of(classname):
    """Map a JUnit classname (tests.test_x or tests.test_x.TestClass) to tests/test_x.py."""
    parts = []
    for seg in classname.split("."):
        if seg.startswith("Test"):
            break
        parts.append(seg)
    return "/".join(parts) + ".py"


def weights_from_xml(paths):
    totals = {}
    for p in paths:
        try:
            root = ET.parse(p).getroot()
        except (OSError, ET.ParseError) as exc:
            print(f"ci_shard: skip {p}: {exc}", file=sys.stderr)
            continue
        for tc in root.iter("testcase"):
            classname = tc.get("classname") or ""
            if not classname:
                continue
            f = file_of(classname)
            totals[f] = totals.get(f, 0.0) + float(tc.get("time") or 0)
    return {k: round(v, 1) for k, v in sorted(totals.items())}


def cmd_pick(args):
    if args.files_from:
        text = Path(args.files_from).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    files = [line.strip() for line in text.splitlines() if line.strip()]
    weights = load_weights(args.weights)
    if weights is None:
        print("ci_shard: no weights, using round-robin", file=sys.stderr)
        picked = round_robin(files, args.shards)[args.index - 1]
    else:
        picked = shards(files, weights, args.shards)[args.index - 1]
    for f in picked:
        print(f)
    return 0


def cmd_weights(args):
    data = weights_from_xml(args.xml)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ci_shard: wrote {len(data)} files to {out}", file=sys.stderr)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    pick = sub.add_parser("pick")
    pick.add_argument("--weights", required=True)
    pick.add_argument("--shards", type=int, required=True)
    pick.add_argument("--index", type=int, required=True)
    pick.add_argument("--files-from")
    pick.set_defaults(func=cmd_pick)

    wts = sub.add_parser("weights")
    wts.add_argument("--out", required=True)
    wts.add_argument("xml", nargs="+")
    wts.set_defaults(func=cmd_weights)

    args = parser.parse_args(argv)
    if args.command == "pick" and not 1 <= args.index <= args.shards:
        parser.error("--index must be between 1 and --shards")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
