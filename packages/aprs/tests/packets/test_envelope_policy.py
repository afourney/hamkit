# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Policy defaults, construction and argument checks (wire rules are case vectors)."""

import json
from dataclasses import FrozenInstanceError, asdict, replace
from typing import Any, cast

import pytest

from hamkit import aprs as a


def test_aprs_is_is_the_default_everywhere() -> None:
    # HDR case vectors cover each limit and address rule under explicit policies.
    raw = b"N0!CALL>APRS:~" + b"x" * 510
    packet = a.parse_packet(raw)
    assert isinstance(packet, a.Packet)
    assert {d.path for d in packet.diagnostics} == {"$.header.source", "$"}
    assert a.parse_tnc2_line(raw + b"\r\n").diagnostics == packet.diagnostics
    assert a.check_packet(packet) == a.check_packet(packet, policy=a.APRS_IS())
    for operation in (a.serialize_packet, a.serialize_tnc2_line, a.validate_packet):
        with pytest.raises(a.ConformanceError):
            operation(packet)


@pytest.mark.parametrize(
    "field", ["source_pattern", "destination_pattern", "path_address_pattern"]
)
def test_invalid_patterns_fail_when_policy_is_constructed(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        replace(a.RF(), **cast(Any, {field: "["}))
    with pytest.raises(TypeError, match=field):
        replace(a.RF(), **cast(Any, {field: b".*"}))


@pytest.mark.parametrize(
    "field", ["max_path_entries", "max_information_bytes", "max_tnc2_line_bytes"]
)
def test_invalid_limits_fail_when_policy_is_constructed(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        replace(a.RF(), **cast(Any, {field: -1}))
    for value in (True, 1.5, "8"):
        with pytest.raises(TypeError, match=field):
            replace(a.RF(), **cast(Any, {field: value}))


def test_policies_are_immutable_data() -> None:
    with pytest.raises(FrozenInstanceError):
        cast(Any, a.RF()).max_path_entries = 9
    assert (
        a.from_json_dict(
            json.loads(json.dumps(asdict(a.APRS_IS()))), expected_type=a.EnvelopePolicy
        )
        == a.APRS_IS()
    )
    assert replace(a.RF(), max_path_entries=None).max_path_entries is None
    assert a.RF().max_path_entries == 8


@pytest.mark.parametrize("bad", [None, "rf", "monitor", "aprs_is", {}, 42])
def test_entry_points_require_policy_objects(bad: Any) -> None:
    packet = a.Packet(a.Header("N0CALL", "APRS"), a.Status("Ready"))
    for operation, argument in (
        (a.parse_packet, b"N0CALL>APRS:>Ready"),
        (a.parse_tnc2_line, b"N0CALL>APRS:>Ready\r\n"),
        (a.serialize_packet, packet),
        (a.serialize_tnc2_line, packet),
        (a.check_packet, packet),
        (a.validate_packet, packet),
    ):
        with pytest.raises(TypeError, match="policy must be an EnvelopePolicy"):
            operation(cast(Any, argument), policy=bad)
