# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Every JSONL row is independently collected; only reviewed gaps may xfail."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from hamkit import aprs

DIRECTORY = Path(__file__).parents[1] / "vectors"


class KnownGap(AssertionError):
    """A specifically enumerated missing capability, never a generic mismatch."""


def differences(actual: Any, expected: Any, path: str = "$") -> list[str]:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {actual!r}"]
        return [
            error
            for key, value in expected.items()
            for error in (
                [f"{path}.{key}: missing"]
                if key not in actual
                else differences(actual[key], value, f"{path}.{key}")
            )
        ]
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return [f"{path}: expected {expected!r}, got {actual!r}"]
        return [
            error
            for i, value in enumerate(expected)
            for error in differences(actual[i], value, f"{path}[{i}]")
        ]
    if isinstance(expected, float) and isinstance(actual, (float, int)):
        tolerance = 1e-8 if path.endswith(("latitude_deg", "longitude_deg")) else 1e-6
        if math.isclose(actual, expected, rel_tol=1e-9, abs_tol=tolerance):
            return []
    if type(actual) is not type(expected) and isinstance(actual, bool) != isinstance(
        expected, bool
    ):
        return [f"{path}: expected {expected!r}, got {actual!r}"]
    return (
        [] if actual == expected else [f"{path}: expected {expected!r}, got {actual!r}"]
    )


def load() -> list[Any]:
    params = []
    for file in sorted(DIRECTORY.glob("*.jsonl")):
        for line, text in enumerate(file.read_text().splitlines(), 1):
            row = json.loads(text)
            label = f"{file.name}:{line}:{row['id']}"
            marks = []
            if row.get("gap"):
                marks = [
                    pytest.mark.xfail(
                        strict=True, raises=KnownGap, reason=row["gap"]["reason"]
                    )
                ]
            params.append(pytest.param(row, id=label, marks=marks))
    assert params, "no vectors found"
    return params


def check(row: dict[str, Any]) -> None:
    raw = row["packet"].encode("latin-1")
    packet = aprs.parse_packet(
        raw,
        profile="rf"
        if row["profile"] == "strict-envelope" or row.get("options", {}).get("ax25")
        else "monitor",
    )
    actual = aprs.to_json_dict(packet, include_defaults=True)
    assert actual["original_wire"] == row["packet"], "original bytes changed"
    if row.get("unresolved"):
        raise KnownGap(row["unresolved"])
    expected = row["expected"]
    errors = differences(actual, expected)
    if row.get("rejection"):
        rejected = isinstance(packet, aprs.Malformed) or any(
            d.code == "nonconforming" for d in packet.diagnostics
        )
        if not rejected:
            errors.append("$: expected malformed/nonconforming input")
    if not errors:
        return
    gap = row.get("gap", {})
    if (
        gap.get("kind") == "opaque"
        and isinstance(packet, aprs.Packet)
        and isinstance(packet.payload, aprs.Opaque)
    ):
        if "header" in expected:
            assert not differences(
                actual["header"], expected["header"]
            ), "opaque header changed"
        assert (
            packet.payload.information == raw.partition(b":")[2]
        ), "opaque bytes changed"
        assert packet.payload.diagnostic is not None
        assert (
            gap["reason"]
            == "Unimplemented decoding: " + packet.payload.diagnostic.message
        ), "different unsupported capability"
        raise KnownGap(gap["reason"] + "\n" + "\n".join(errors))
    if gap.get("kind") == "fields":
        allowed = gap["allowed_actual"]
        paths = {error.split(": ", 1)[0] for error in errors}
        if paths <= allowed.keys():
            for path in paths:
                if path == "$":
                    assert allowed[path] == "rejection" and isinstance(
                        packet, aprs.Packet
                    )
                    continue
                current: Any = actual
                for key in path[2:].split("."):
                    if not isinstance(current, dict) or key not in current:
                        current = {"missing": True}
                        break
                    current = current[key]
                assert (
                    current == allowed[path]
                ), f"{path}: changed beyond the documented gap"
            raise KnownGap(gap["reason"] + "\n" + "\n".join(errors))
    raise AssertionError("\n".join(errors))


@pytest.mark.parametrize("row", load())
def test_documented_vector(row: dict[str, Any]) -> None:
    check(row)
