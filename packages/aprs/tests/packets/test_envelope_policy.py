# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Public policy behavior across decoding, validation and both wire formats."""

import json
from dataclasses import FrozenInstanceError, asdict, replace
from typing import Any, cast

import pytest

from hamkit import aprs as a


def parse(raw: bytes, policy: a.EnvelopePolicy) -> a.Packet:
    packet = a.parse_packet(raw, policy=policy)
    assert isinstance(packet, a.Packet)
    assert packet.original_wire == raw
    return packet


def assert_conformance(
    raw: bytes, policy: a.EnvelopePolicy, paths: set[str]
) -> a.Packet:
    packet = parse(raw, policy)
    assert {d.path for d in packet.diagnostics} == paths
    assert all(d.code == "nonconforming" for d in packet.diagnostics)
    findings = a.check_packet(packet, policy=policy)
    assert {d.path for d in findings} == paths
    for operation in (a.serialize_packet, a.serialize_tnc2_line, a.validate_packet):
        if paths:
            with pytest.raises(a.ConformanceError) as caught:
                operation(packet, policy=policy)
            assert caught.value.diagnostics == findings
        else:
            result = operation(packet, policy=policy)
            if operation is a.serialize_packet:
                assert result == raw
            elif operation is a.serialize_tnc2_line:
                assert result == raw + b"\r\n"
            else:
                assert result is None
    for terminator in (b"\n", b"\r\n"):
        framed = a.parse_tnc2_line(raw + terminator, policy=policy)
        assert isinstance(framed, a.Packet)
        assert framed.original_wire == raw
        assert framed.diagnostics == packet.diagnostics
    return packet


@pytest.mark.parametrize(
    "address,rf_ok,internet_ok",
    [
        ("N0CALL", True, True),
        ("n0call", False, True),
        ("N0CALL-0", True, False),  # APRS-IS drops SSID -0.
        ("N0CALL-15", True, True),
        ("N0CALL-16", False, True),
        ("N0CALL-JS", False, True),
        ("N0CALL-123", False, False),
        ("ABCDEFGHI", False, True),
        ("ABCDEFGHIJ", False, False),
        ("ABCDEFG-A", False, True),
        ("ABCDEFG-AB", False, False),
        ("N0!CALL", False, False),
        ("N0_CALL", False, False),
        ("N0CALL-", False, False),
        ("N0CALL-A-B", False, False),
        ("A", True, False),
        ("AB", True, False),
        ("AB-12", True, False),
    ],
)
def test_source_formats(address: str, rf_ok: bool, internet_ok: bool) -> None:
    raw = address.encode() + b">APRS:>Ready"
    for policy, valid in ((a.RF, rf_ok), (a.APRS_IS, internet_ok)):
        assert_conformance(raw, policy, set() if valid else {"$.header.source"})


def test_internet_rejects_ssid_zero_everywhere() -> None:
    # aprs-is.net: "SSID -0 is dropped as conflicts with not present SSID".
    for raw, path in (
        (b"N0CALL>APRS-0:>Ready", "$.header.destination"),
        (b"N0CALL>APRS,WIDE1-0:>Ready", "$.header.path[0].address"),
    ):
        assert_conformance(raw, a.APRS_IS, {path})
        assert_conformance(raw, a.RF, set())


@pytest.mark.parametrize("address", ["A", "AB", "A-1", "qAR", "AE5PL-JS"])
def test_internet_destination_and_path_allow_short_addresses(address: str) -> None:
    assert_conformance(f"N0CALL>{address},{address}*:>Ready".encode(), a.APRS_IS, set())


def test_path_entries_preserve_q_and_repeated_marker() -> None:
    raw = b"N0CALL>APRS,WIDE1-1,W1AW*,qAR,AE5PL-JS:>Ready"
    internet = assert_conformance(raw, a.APRS_IS, set())
    rf = assert_conformance(
        raw, a.RF, {"$.header.path[2].address", "$.header.path[3].address"}
    )
    assert internet.header == rf.header
    assert internet.payload == rf.payload
    assert internet.header.path == (
        a.Hop("WIDE1-1"),
        a.Hop("W1AW", True),
        a.Hop("qAR"),
        a.Hop("AE5PL-JS"),
    )


def test_custom_patterns_are_independent_and_use_fullmatch() -> None:
    policy = a.EnvelopePolicy("src_[0-9]+", "dst_[A-Z]+", "via_[a-z]+")
    assert_conformance(b"src_12>dst_AB,via_home*:>Ready", policy, set())
    assert_conformance(
        b"xsrc_12>dst_ABx,via_home1*:>Ready",
        policy,
        {"$.header.source", "$.header.destination", "$.header.path[0].address"},
    )


def test_path_entry_limit_is_optional_and_counts_entries_not_hops() -> None:
    eight = b"N0CALL>APRS" + b",WIDE2-2" * 8 + b":>Ready"
    nine = b"N0CALL>APRS" + b",WIDE2-2" * 9 + b":>Ready"
    assert_conformance(eight, a.RF, set())
    assert_conformance(nine, a.RF, {"$.header.path"})
    assert_conformance(nine, replace(a.RF, max_path_entries=None), set())
    # More than eight entries are also valid under the default internet policy.
    assert_conformance(nine, a.APRS_IS, set())
    no_path = replace(a.APRS_IS, max_path_entries=0)
    assert_conformance(b"N0CALL>APRS:>Ready", no_path, set())
    assert_conformance(b"N0CALL>APRS,WIDE2-2:>Ready", no_path, {"$.header.path"})


@pytest.mark.parametrize("length", [255, 256, 257])
def test_rf_information_boundary(length: int) -> None:
    raw = b"N0CALL>APRS:~" + b"x" * (length - 1)
    paths = {"$.payload"} if length > 256 else set()
    assert_conformance(raw, a.RF, paths)
    assert_conformance(raw, a.APRS_IS, set())
    assert_conformance(raw, replace(a.RF, max_information_bytes=None), set())


@pytest.mark.parametrize("length", [511, 512, 513])
def test_internet_line_boundary_includes_header_and_crlf(length: int) -> None:
    prefix = b"N0CALL>APRS,TCPIP*,qAC,AE5PL-JS:~"
    raw = prefix + b"x" * (length - len(prefix) - 2)
    assert_conformance(raw, a.APRS_IS, {"$"} if length > 512 else set())
    assert_conformance(raw, replace(a.APRS_IS, max_tnc2_line_bytes=None), set())


def test_sizes_count_encoded_bytes_and_recompute_after_edits() -> None:
    raw = "N0CALL>APRS:>é".encode()
    policy = replace(a.RF, max_information_bytes=2, max_tnc2_line_bytes=len(raw) + 1)
    packet = assert_conformance(raw, policy, {"$.payload", "$"})
    # Stored diagnostics and original_wire do not control serialization.
    changed = replace(packet, payload=a.Status("e"))
    assert changed.diagnostics
    assert a.check_packet(changed, policy=policy) == ()
    assert a.serialize_packet(changed, policy=policy) == b"N0CALL>APRS:>e"
    cleared = replace(packet, diagnostics=())
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(cleared, policy=policy)


def test_parse_measures_received_bytes_check_measures_encoded_bytes() -> None:
    raw = b"N0CALL>APRS:>\xe9"
    policy = replace(a.RF, max_information_bytes=2)
    packet = parse(raw, policy)
    assert [d.path for d in packet.diagnostics] == ["$.payload.text"]
    # Latin-1 fallback becomes two UTF-8 bytes plus the status identifier.
    assert {d.path for d in a.check_packet(packet, policy=policy)} == {"$.payload"}


def test_zero_size_limits_are_limits_not_unlimited() -> None:
    policy = replace(a.RF, max_information_bytes=0, max_tnc2_line_bytes=0)
    assert_conformance(b"N0CALL>APRS:>Ready", policy, {"$.payload", "$"})


def test_envelope_limits_do_not_replace_payload_rules() -> None:
    unlimited = a.EnvelopePolicy(".*", ".*", ".*")
    assert_conformance(b"N0CALL>APRS:>" + b"x" * 63, unlimited, {"$.payload.text"})
    assert isinstance(
        a.parse_packet(b"N0 CALL>APRS:>Ready", policy=unlimited), a.Malformed
    )


@pytest.mark.parametrize("policy", [a.RF, a.APRS_IS])
def test_third_party_envelope_policy_applies_only_to_outer_packet(
    policy: a.EnvelopePolicy,
) -> None:
    # Inner identifiers are text, not outer AX.25 or APRS-IS addresses.
    inner = b"n0call-JS>APRS,TCPIP,W1AW*:>Ready"
    raw = b"W1AW>APRS,WIDE1-1:}" + inner
    packet = assert_conformance(raw, policy, set())
    assert isinstance(packet.payload, a.ThirdParty)
    assert packet.payload.packet.diagnostics == ()
    nested = b"W1AW>APRS:}" + raw
    assert_conformance(nested, policy, set())
    # A custom outer pattern must not silently become an inner pattern either.
    custom = replace(policy, source_pattern="W1AW", max_path_entries=1)
    assert_conformance(raw, custom, set())
    assert_conformance(
        raw, replace(custom, max_information_bytes=len(inner)), {"$.payload"}
    )


def test_third_party_payload_diagnostics_keep_nested_paths() -> None:
    raw = b"W1AW>APRS:}n0call-JS>APRS,TCPIP,W1AW*:>bad|text"
    packet = assert_conformance(raw, a.RF, {"$.payload.packet.payload.text"})
    assert isinstance(packet.payload, a.ThirdParty)
    assert {d.path for d in packet.payload.packet.diagnostics} == {"$.payload.text"}


def test_aprs_is_is_the_default_everywhere() -> None:
    raw = b"N0!CALL>APRS:~" + b"x" * 510
    packet = a.parse_packet(raw)
    assert isinstance(packet, a.Packet)
    assert {d.path for d in packet.diagnostics} == {"$.header.source", "$"}
    assert a.parse_tnc2_line(raw + b"\r\n").diagnostics == packet.diagnostics
    assert a.check_packet(packet) == a.check_packet(packet, policy=a.APRS_IS)
    for operation in (a.serialize_packet, a.serialize_tnc2_line, a.validate_packet):
        with pytest.raises(a.ConformanceError):
            operation(packet)


@pytest.mark.parametrize(
    "field", ["source_pattern", "destination_pattern", "path_address_pattern"]
)
def test_invalid_patterns_fail_when_policy_is_constructed(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        replace(a.RF, **cast(Any, {field: "["}))
    with pytest.raises(TypeError, match=field):
        replace(a.RF, **cast(Any, {field: b".*"}))


@pytest.mark.parametrize(
    "field", ["max_path_entries", "max_information_bytes", "max_tnc2_line_bytes"]
)
def test_invalid_limits_fail_when_policy_is_constructed(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        replace(a.RF, **cast(Any, {field: -1}))
    for value in (True, 1.5, "8"):
        with pytest.raises(TypeError, match=field):
            replace(a.RF, **cast(Any, {field: value}))


def test_policies_are_immutable_data() -> None:
    with pytest.raises(FrozenInstanceError):
        cast(Any, a.RF).max_path_entries = 9
    assert a.EnvelopePolicy(**json.loads(json.dumps(asdict(a.APRS_IS)))) == a.APRS_IS
    assert replace(a.RF, max_path_entries=None).max_path_entries is None
    assert a.RF.max_path_entries == 8


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
