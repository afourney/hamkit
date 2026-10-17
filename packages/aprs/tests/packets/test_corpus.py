# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Every JSONL row is independently collected, without expected-failure escapes."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from hamkit import aprs

DIRECTORY = Path(__file__).parents[1] / "vectors"

# Rows still checked through the private compatibility view; every other row
# compares parse_packet output directly. Each waits on a decision: 000000z
# timestamps, short or decimal telemetry, minimal GLL and trailing APRS 1.2
# weather fields (X/V tails also read as software/unit codes).
COMPATIBILITY_PENDING = {
    "FAP-362",
    "FAP-433",
    "FAP-434",
    "FAP-435",
    "FAP-436",
    "FAP-454",
    "FAP-455",
    "FAP-456",
    "FAP-482",
    "FAP-483",
    "FAP-484",
    "FAP-485",
    "FAP-486",
    "FAP-487",
    "FAP-488",
    "FAP-489",
    "FAP-490",
    "FAP-497",
}


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


# Receivers in these profiles search other text for an embedded "!" position.
LEGACY_POSITION_PROFILES = {"historical-1.0", "compatibility-fap"}


def parse_row(row: dict[str, Any], raw: bytes) -> aprs.Packet | aprs.Malformed:
    options = row.get("options") or {}
    strict = row["profile"] == "strict-envelope" or options.get("ax25")
    return aprs.parse_packet(
        raw,
        policy=aprs.RF if strict else aprs.APRS_IS,
        legacy_positions=row["profile"] in LEGACY_POSITION_PROFILES,
    )


def rows():
    return [
        json.loads(line)
        for file in sorted(DIRECTORY.glob("*.jsonl"))
        for line in file.read_text().splitlines()
    ]


def load() -> list[Any]:
    return [pytest.param(row, id=row["id"]) for row in rows()]


def public_phg_row(row: dict[str, Any]) -> bool:
    """PHG/PHGR expectations must be met by the public API without rewrites."""
    payload = row.get("expected", {}).get("payload", {})
    if payload.get("type") == "legacy_position":
        payload = payload["position"]
    return bool(payload.get("extensions", {}).get("phg"))


def check(row: dict[str, Any]) -> None:
    raw = row["packet"].encode("latin-1")
    packet: aprs.Packet | aprs.Malformed | None = None
    if row["id"] in COMPATIBILITY_PENDING:
        from hamkit.aprs._compatibility import view

        actual, rejected = view(raw, row["profile"], row.get("options"))
    else:
        packet = parse_row(row, raw)
        actual = aprs.to_json_dict(packet, include_defaults=True)
        rejected = isinstance(packet, aprs.Malformed) or any(
            d.code == "nonconforming" for d in packet.diagnostics
        )
    assert actual["original_wire"] == row["packet"], "original bytes changed"
    assert not row.get("gap") and not row.get("unresolved")
    errors = differences(actual, row["expected"])
    if row.get("rejection") and not rejected:
        errors.append("$: expected malformed/nonconforming input")
    if row.get("rejection"):
        from source_details import check_rejection

        errors.extend(check_rejection(row))
    if row.get("unmapped"):
        from source_details import check_core, check_fap, check_public_phg

        if row["profile"] != "compatibility-fap":
            errors.extend(check_core(row))
        elif public_phg_row(row):
            errors.extend(check_public_phg(row, packet))
        else:
            errors.extend(
                check_fap(row, packet if isinstance(packet, aprs.Packet) else None)
            )
    if row.get("sequence"):
        from receiver import Receiver

        receiver = Receiver()
        for step in rows():
            if step.get("sequence") == row["sequence"]:
                state = receiver.receive(
                    aprs.parse_packet(step["packet"].encode("latin1"))
                )
                if step["id"] == row["id"]:
                    errors.extend(differences(state, row["state_expected"]))
                    break
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("row", load())
def test_documented_vector(row: dict[str, Any]) -> None:
    check(row)
