# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Compute and review the case vectors in tests/cases (see README there).

Expectations are never overwritten silently. ``propose`` prints the rows whose
stored expectations differ from what the library now produces; ``--write``
applies them, and the diff must then be reviewed and explained in ``comment``.

``sweep`` runs a capture of TNC2 lines (for example from APRS-IS) through the
parser, FAP and the runner's checks, reports runner failures, disagreements
with FAP and shapes of packet not yet in the cases, and with ``--add`` appends
up to ``--per`` rows for each new shape and software family.

``fap`` fills in missing fap snapshots using the fapsnapshot binary built from
tests/fap_snapshot (``go build -o fapsnapshot .`` there).

Usage (from packages/aprs):
    python tests/case_tool.py propose [--write] [FILE ...]
    python tests/case_tool.py fap FAPSNAPSHOT [FILE ...]
    python tests/case_tool.py sweep CAPTURE [--fap FAPSNAPSHOT] [--policy rf]
                                    [--add FILE] [--per N]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from hamkit import aprs as a

CASES = Path(__file__).parent / "cases"
FIELDS = (
    "id",
    "comment",
    "tnc2",
    "policy",
    "decoded",
    "reencoded",
    "encoding_error",
    "fap",
)


def error_json(exc: BaseException) -> dict[str, Any]:
    """An expected error as the library reports it."""
    if isinstance(exc, a.ConformanceError):
        return {
            "type": "ConformanceError",
            "diagnostics": [
                a.to_json_dict(d, include_defaults=True) for d in exc.diagnostics
            ],
        }
    return {"type": type(exc).__name__, "message": str(exc)}


def policy_of(row: dict[str, Any]) -> a.EnvelopePolicy:
    return a.from_json_dict(row["policy"], expected_type=a.EnvelopePolicy)


def encode(value: Any, policy: a.EnvelopePolicy) -> tuple[str | None, Any]:
    """(reencoded, encoding_error) for a parsed or composed value."""
    try:
        return a.serialize_packet(value, policy=policy).decode("latin-1"), None
    except (a.APRSError, TypeError) as exc:
        return None, error_json(exc)


def expected(row: dict[str, Any]) -> dict[str, Any]:
    """The row with decoded/reencoded/encoding_error as the library now behaves."""
    policy = policy_of(row)
    result = dict(row)
    if row["tnc2"] is not None:
        parsed = a.parse_packet(row["tnc2"].encode("latin-1"), policy=policy)
        result["decoded"] = a.to_json_dict(parsed, include_defaults=True)
        value: Any = parsed
    else:
        try:
            value = a.from_json_dict(row["decoded"])
        except a.APRSError as exc:
            result["reencoded"], result["encoding_error"] = None, error_json(exc)
            return result
    result["reencoded"], result["encoding_error"] = encode(value, policy)
    return result


def read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().split("\n") if line]


def case_files() -> list[Path]:
    return sorted(CASES.glob("*.jsonl"))


def all_rows() -> list[dict[str, Any]]:
    return [row for path in case_files() for row in read(path)]


def same(x: Any, y: Any) -> bool:
    """JSON equality that also tells -0.0 from 0.0 and 1 from 1.0."""
    return json.dumps(x, ensure_ascii=False) == json.dumps(y, ensure_ascii=False)


def shape(row: dict[str, Any]) -> tuple[Any, ...]:
    """What kind of packet a row is: its payload type, the problems we report
    (indices and quoted text removed) and whether FAP rejects it."""
    decoded = row["decoded"]
    kind = decoded["type"] if decoded["type"] == "malformed" else decoded["payload"]["type"]
    problems = sorted(
        {
            (
                d["code"],
                re.sub(r"\[\d+\]", "[]", d["path"]),
                re.sub(r"'[^']*'", "''", d["message"]),
            )
            for d in decoded["diagnostics"]
        }
    )
    fap = row["fap"] or {}
    return (kind, tuple(problems), "error" in fap)


def software(row: dict[str, Any]) -> str:
    """The software family: the first four characters of the destination."""
    return row["tnc2"].partition(">")[2].split(",")[0].split(":")[0][:4]


def fap_snapshots(
    binary: Path, rows: list[dict[str, Any]], *, ax25: bool
) -> dict[str, Any]:
    """go-aprs-fap's output for each row with tnc2, keyed by id."""
    options = {"accept_broken_mice": False, "ax25": ax25, "raw_timestamp": False}
    requests = "".join(
        json.dumps({"id": r["id"], "hex": r["tnc2"].encode("latin-1").hex()} | options)
        + "\n"
        for r in rows
    )
    out = subprocess.run(
        [str(binary)], input=requests, capture_output=True, text=True, check=True
    ).stdout
    return {
        o["id"]: {"implementation": "go-aprs-fap", "options": options} | o["fap"]
        for o in map(json.loads, out.splitlines())
    }


def fill_fap(binary: Path, paths: list[Path]) -> None:
    rf = a.RF().source_pattern
    for path in paths:
        rows = read(path)
        missing = [r for r in rows if r["tnc2"] is not None and r["fap"] is None]
        for ax25 in (False, True):
            group = [r for r in missing if (r["policy"]["source_pattern"] == rf) == ax25]
            snapshots = fap_snapshots(binary, group, ax25=ax25) if group else {}
            for r in group:
                r["fap"] = snapshots[r["id"]]
        if missing:
            write(path, rows)
        print(f"{path.name}: {len(missing)} fap snapshot(s) added")


def write(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = (
        json.dumps({k: row[k] for k in FIELDS}, ensure_ascii=False) for row in rows
    )
    path.write_text("\n".join(lines) + "\n")


def propose(paths: list[Path], apply: bool) -> int:
    changed = 0
    for path in paths:
        rows = read(path)
        new = [expected(row) for row in rows]
        for old, row in zip(rows, new):
            if not same(old, row):
                changed += 1
                print(f"{path.name} {row['id']}:")
                for key in ("decoded", "reencoded", "encoding_error"):
                    if old.get(key) != row[key]:
                        print(f"  {key}: {json.dumps(old.get(key))}")
                        print(f"  {' ' * len(key)}->{json.dumps(row[key])}")
        if apply and not same(new, rows):
            write(path, new)
    print(f"{changed} row(s) differ" + (" (written)" if apply and changed else ""))
    return changed


def sweep(
    capture: Path,
    *,
    policy: a.EnvelopePolicy,
    binary: Path | None,
    add: Path | None,
    per: int,
) -> int:
    from test_cases import test_case  # the runner's checks, row by row

    lines = [
        line.removesuffix(b"\r") for line in capture.read_bytes().split(b"\n") if line
    ]
    counts = collections.Counter(lines)
    first = {}
    for n, line in enumerate(lines, 1):
        first.setdefault(line, n)
    policy_json = a.to_json_dict(policy, include_defaults=True)
    rows = [
        expected(
            {
                "id": f"{capture.name}:{n}",
                "comment": "",
                "tnc2": line.decode("latin-1"),
                "policy": policy_json,
                "decoded": None,
                "reencoded": None,
                "encoding_error": None,
                "fap": None,
            }
        )
        for line, n in first.items()
    ]
    if binary is not None:
        snapshots = fap_snapshots(
            binary, rows, ax25=policy.source_pattern == a.RF().source_pattern
        )
        for r in rows:
            r["fap"] = snapshots[r["id"]]
    failures = []
    for r in rows:
        try:
            test_case(r)
        except AssertionError as exc:
            failures.append((r, str(exc).splitlines()[0] if str(exc) else ""))
    known_shapes = collections.Counter()
    known_keys = collections.Counter()
    for r in all_rows():
        if r["tnc2"] is not None and r["fap"] is not None:
            known_shapes[shape(r)] += 1
            known_keys[(shape(r), software(r))] += 1
    new_shapes = collections.defaultdict(list)
    for r in rows:
        if shape(r) not in known_shapes:
            new_shapes[shape(r)].append(r)
    print(f"{len(lines)} lines, {len(rows)} distinct")
    print(
        "decoded:",
        dict(collections.Counter(r["decoded"]["type"] for r in rows)),
        "sent:",
        sum(r["reencoded"] is not None for r in rows),
    )
    if binary is not None:
        table = collections.Counter(
            (r["decoded"]["type"], "fap rejects" if "error" in r["fap"] else "fap parses")
            for r in rows
        )
        print("ours / fap:", dict(table))
    print(f"runner failures: {len(failures)}")
    for r, message in failures[:20]:
        print(f"  {r['id']}: {r['tnc2'][:90]!r} {message[:120]}")
    print(f"new shapes: {len(new_shapes)}" + ("" if binary else " (without fap)"))
    for s, examples in sorted(new_shapes.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(examples):5d} {s}")
        print(f"        e.g. {examples[0]['id']}: {examples[0]['tnc2'][:100]!r}")
    if add is not None:
        if binary is None:
            raise SystemExit("--add needs --fap, so new rows carry FAP's output")
        existing = read(add) if add.exists() else []
        prefix = existing[0]["id"].split("-")[0] if existing else "TRF"
        number = max((int(r["id"].split("-")[1]) for r in existing), default=0)
        width = max((len(r["id"].split("-")[1]) for r in existing), default=5)
        added = []
        for r in rows:
            key = (shape(r), software(r))
            if known_keys[key] >= per:
                continue
            known_keys[key] += 1
            number += 1
            seen = counts[r["tnc2"].encode("latin-1")]
            r["id"] = f"{prefix}-{number:0{width}d}"
            r["comment"] = (
                f"Captured traffic: line {first[r['tnc2'].encode('latin-1')]} of "
                f"{capture.name}" + (f" (seen {seen} times)" if seen > 1 else "")
                + ". Added by sweep for a new shape or software family; the "
                "expectations are this library's output, to be reviewed against fap."
            )
            added.append(r)
        write(add, existing + added)
        print(f"added {len(added)} row(s) to {add}")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--write", action="store_true")
    p.add_argument("files", nargs="*", type=Path)
    f = sub.add_parser("fap")
    f.add_argument("binary", type=Path)
    f.add_argument("files", nargs="*", type=Path)
    w = sub.add_parser("sweep")
    w.add_argument("capture", type=Path)
    w.add_argument("--fap", type=Path, dest="binary")
    w.add_argument("--policy", choices=("aprs-is", "rf"), default="aprs-is")
    w.add_argument("--add", type=Path)
    w.add_argument("--per", type=int, default=2)
    args = parser.parse_args(argv)
    if args.command == "fap":
        fill_fap(args.binary, args.files or case_files())
        return 0
    if args.command == "sweep":
        policy = a.RF() if args.policy == "rf" else a.APRS_IS()
        return sweep(
            args.capture, policy=policy, binary=args.binary, add=args.add, per=args.per
        )
    files = args.files or case_files()
    return 1 if propose(files, args.write) and not args.write else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
