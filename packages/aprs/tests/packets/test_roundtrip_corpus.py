# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Every vector is encoded from semantic fields or has a reviewed refusal reason."""
from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path
from typing import Any

import pytest
from packets.test_corpus import load, rows

from hamkit import aprs as a

EXCEPTIONS = json.loads(
    (Path(__file__).parents[1] / "roundtrip_exceptions.json").read_text()
)


def without_evidence(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.replace(
            value,
            **{
                f.name: without_evidence(getattr(value, f.name))
                if f.compare
                else f.default
                for f in dataclasses.fields(value)
            },
        )
    if isinstance(value, tuple):
        return tuple(without_evidence(v) for v in value)
    return value


def same_semantics(x: Any, y: Any, path="$") -> None:
    assert (
        type(x) is type(y)
        or isinstance(x, (int, float))
        and isinstance(y, (int, float))
    ), path
    if dataclasses.is_dataclass(x):
        for f in dataclasses.fields(x):
            # Checksum characters describe the original lexemes, which the
            # encoder can normalize. Their validity is checked separately.
            if f.compare and not (
                isinstance(x, a.NMEAMetadata) and f.name == "checksum_supplied"
            ):
                same_semantics(
                    getattr(x, f.name), getattr(y, f.name), path + "." + f.name
                )
    elif isinstance(x, tuple):
        assert len(x) == len(y), path
        for i, (v, w) in enumerate(zip(x, y)):
            same_semantics(v, w, f"{path}[{i}]")
    elif isinstance(x, (float, int)) and not isinstance(x, bool):
        assert math.isclose(x, y, abs_tol=1e-8, rel_tol=1e-9), (path, x, y)
        if x == y == 0:
            assert math.copysign(1, x) == math.copysign(1, y), (
                path,
                "hemisphere changed",
            )
    else:
        assert x == y, (path, x, y)


@pytest.mark.parametrize("row", load())
def test_vector_roundtrip(row):
    packet = a.parse_packet(row["packet"].encode("latin1"))
    # JSON is lossless even for malformed or nonconforming received packets.
    assert a.to_json_dict(a.from_json(a.to_json(packet))) == a.to_json_dict(packet)
    exception = EXCEPTIONS.get(row["id"])
    if isinstance(packet, a.Malformed):
        assert exception is not None and exception["kind"] == "malformed"
        assert [d.message for d in packet.diagnostics] == exception["reasons"]
        return
    clean = without_evidence(packet)
    if exception:
        assert exception["kind"] == "conformance"
        with pytest.raises(a.ConformanceError) as caught:
            a.serialize_packet(clean)
        assert [d.message for d in caught.value.diagnostics] == exception["reasons"]
        return
    wire = a.serialize_packet(clean)
    decoded = a.parse_packet(wire)
    assert isinstance(decoded, a.Packet)
    if isinstance(clean.payload, a.NMEA):
        n = clean.payload
        if n.metadata.checksum_supplied is not None:
            assert isinstance(decoded.payload, a.NMEA)
            assert decoded.payload.metadata.checksum_valid is True
            if n.metadata.checksum_valid is False:
                # Three deliberately bad checksums are repaired, not replayed.
                s = n.sentence
                usable = (
                    s.fix_quality > 0
                    if isinstance(s, a.GGA)
                    else s.fix_status == "A"
                    if isinstance(s, (a.GLL, a.RMC))
                    else isinstance(s, a.WPL)
                )
                clean = dataclasses.replace(
                    clean,
                    payload=dataclasses.replace(
                        n,
                        metadata=dataclasses.replace(n.metadata, checksum_valid=True),
                        position_usable=usable,
                    ),
                )
    same_semantics(clean, decoded)
    # Canonical bytes stabilize after one pass, including checksum and rounding.
    assert a.serialize_packet(without_evidence(decoded)) == wire


def test_no_stale_exception_ids():
    assert EXCEPTIONS.keys() <= {r["id"] for r in rows()}
