# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Policy changes interpretation, diagnostics and fresh composition together."""
from dataclasses import replace
from typing import Any, get_args

import pytest

from hamkit import aprs as a

BASELINE = a.APRS_IS(extensions=set())


def packet(raw: bytes, policy: a.EnvelopePolicy) -> a.Packet:
    result = a.parse_packet(raw, policy=policy)
    assert isinstance(result, a.Packet)
    return result


@pytest.mark.parametrize("factory", [a.RF, a.APRS_IS])
def test_factory_defaults_and_explicit_empty(factory):
    default = factory()
    assert set(default.extensions) == set(a.SUPPORTED_EXTENSIONS) - {
        "mice_hex_as_device",
        "water_height_tenths",
    }
    assert factory(extensions=set()).extensions == ()
    explicit = factory(extensions={"mice_device_ids"}, max_information_bytes=0)
    assert explicit.extensions == ("mice_device_ids",)
    assert explicit.max_information_bytes == 0
    assert a.from_json(a.to_json(default)) == default


def test_direct_policy_construction_and_fully_resolved_json():
    policy = a.EnvelopePolicy(
        source_pattern="src_[0-9]+",
        destination_pattern="dst_[A-Z]+",
        path_address_pattern="via_[a-z]+",
        max_path_entries=1,
        max_information_bytes=12,
        max_tnc2_line_bytes=None,
        extensions={"utf8_text"},
        byte_fallback="reject",
        legacy_positions=False,
    )
    wire = "src_12>dst_AB,via_home*:>Café".encode()
    received = packet(wire, policy)
    assert not received.diagnostics
    assert a.serialize_packet(received, policy=policy) == wire
    data = a.to_json_dict(policy)
    assert data["extensions"] == ["utf8_text"]
    assert data["max_tnc2_line_bytes"] is None
    assert len(data) == 10  # tag plus every resolved policy field
    assert a.from_json_dict(data, expected_type=a.EnvelopePolicy) == policy
    data.pop("type")
    assert a.from_json_dict(data, expected_type=a.EnvelopePolicy) == policy
    data.pop("max_path_entries")
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(data, expected_type=a.EnvelopePolicy)
    assert a.EnvelopePolicy(".*", ".*", ".*").extensions == ()


@pytest.mark.parametrize(
    "extensions", [("unknown",), ("high_speed",), ("dao", "dao"), "dao"]
)
def test_unknown_duplicate_or_invalid_extensions(extensions: Any):
    with pytest.raises((TypeError, ValueError)):
        a.RF(extensions=extensions)


def test_json_conflicting_tag_and_unknown_extension():
    data = a.to_json_dict(BASELINE)
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(data, expected_type=a.Packet)
    data["extensions"] = ["unknown"]
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(data)


@pytest.mark.parametrize(
    "tail,extension,field",
    [
        (b"before!W12!after", "dao", "dao"),
        (b"before|!!!!|after", "base91_telemetry", "telemetry"),
    ],
)
def test_comment_extension_disabled_preserves_text(tail, extension, field):
    wire = b"N0CALL>APRS:!4903.50N/07201.75W>" + tail
    baseline = packet(wire, BASELINE)
    assert isinstance(baseline.payload, a.Position)
    assert baseline.payload.comment == tail.decode()
    assert getattr(baseline.payload.extensions, field) is None
    assert a.serialize_packet(baseline, policy=BASELINE) == wire
    enabled = replace(BASELINE, extensions=(extension,))
    extended = packet(wire, enabled)
    assert isinstance(extended.payload, a.Position)
    assert extended.payload.comment == "beforeafter"
    assert getattr(extended.payload.extensions, field) is not None
    assert a.parse_payload(wire.partition(b":")[2], policy=enabled) == extended.payload
    assert (
        a.parse_payload(
            a.serialize_payload(extended.payload, policy=enabled), policy=enabled
        )
        == extended.payload
    )
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(extended, policy=BASELINE)
    assert a.check_packet(extended, policy=BASELINE)


def test_phg_rate_retains_legacy_comment_without_switch():
    wire = b"N0CALL>APRS:!4903.50N/07201.75W>PHG51302/ text "
    baseline = packet(wire, BASELINE)
    assert isinstance(baseline.payload, a.Position)
    assert baseline.payload.extensions.phg.rate_per_hour is None
    assert baseline.payload.comment == "2/ text "
    assert a.serialize_packet(baseline, policy=BASELINE) == wire
    extended = packet(wire, a.APRS_IS())
    assert extended.payload.extensions.phg.rate_per_hour == 2
    assert extended.payload.comment == "text"


def test_utf8_is_free_text_only_and_limits_are_bytes():
    raw = "N0CALL>APRS:>é".encode()
    baseline = packet(raw, BASELINE)
    assert baseline.payload.text == "é"
    assert baseline.diagnostics
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(baseline, policy=BASELINE)
    enabled = a.APRS_IS(extensions={"utf8_text"})
    assert not packet(raw, enabled).diagnostics
    assert a.serialize_packet(baseline, policy=enabled) == raw
    assert packet(raw, replace(enabled, max_information_bytes=2)).diagnostics
    assert not packet(raw, replace(enabled, max_information_bytes=3)).diagnostics
    assert isinstance(
        a.parse_packet("NéCALL>APRS:>ok".encode(), policy=enabled), a.Malformed
    )
    assert packet(b"N0CALL>APRS:>\xe9", enabled).diagnostics
    assert isinstance(
        a.parse_packet(
            b"N0CALL>APRS:>\xe9", policy=replace(enabled, byte_fallback="reject")
        ),
        a.Malformed,
    )
    # ASCII is identical under both interpretations.
    assert packet(b"N0CALL>APRS:>OK", enabled) == packet(b"N0CALL>APRS:>OK", BASELINE)


def test_expanded_telemetry_is_only_a_range_expansion():
    for value in (255, 256, 999):
        wire = f"N0CALL>APRS:T#001,{value:03},001,002,003,004,00000000".encode()
        old = packet(wire, BASELINE)
        new = packet(wire, a.APRS_IS())
        assert old.payload == new.payload
        assert bool(old.diagnostics) == (value > 255)
        assert not new.diagnostics
        assert a.serialize_packet(new) == wire
    overflow = packet(b"N0CALL>APRS:T#001,1000,001,002,003,004,00000000", a.APRS_IS())
    assert overflow.diagnostics


def test_mice_reused_selector_is_explicit_even_for_complete_hex():
    # APRS101 example location plus a complete two-channel hexadecimal field.
    wire = b"N0CALL>SXUQPS:`vXh\x1c\x1c\x1c>/`0102"
    old = packet(wire, BASELINE)
    assert isinstance(old.payload, a.MicE)
    assert old.payload.extensions.telemetry.encoding == "mic_e_hex"
    # Device identifiers alone keep complete hex as APRS 1.1 telemetry.
    ids = packet(wire, a.APRS_IS(extensions={"mice_device_ids"}))
    assert ids.payload == old.payload
    modern_policy = a.APRS_IS(extensions={"mice_hex_as_device"})
    modern = packet(wire, modern_policy)
    assert modern.payload.device_code == "`"
    assert modern.payload.comment == "0102"
    assert modern.payload.extensions.telemetry is None
    assert a.serialize_packet(old, policy=BASELINE) == wire
    assert a.serialize_packet(modern, policy=modern_policy) == wire
    for value, policy in ((old, modern_policy), (modern, BASELINE)):
        with pytest.raises(a.ConformanceError):
            a.serialize_packet(value, policy=policy)
    truncated = wire[:-3]
    assert isinstance(a.parse_packet(truncated, policy=BASELINE), a.Malformed)
    assert isinstance(a.parse_packet(truncated, policy=modern_policy), a.Packet)


@pytest.mark.parametrize("factory", [a.RF, a.APRS_IS])
@pytest.mark.parametrize(
    "extensions,expected",
    [(None, 1234), (set(), 1234), ({"water_height_tenths"}, 123.4)],
)
def test_water_height_interpretation(factory, extensions, expected):
    policy = factory() if extensions is None else factory(extensions=extensions)
    wire = b"N0CALL>APRS:_01020304c180s005g010t070F1234"
    decoded = packet(wire, policy)
    assert decoded.payload.water_height.measurement == a.Measurement(expected, "feet")
    assert not decoded.diagnostics
    assert not a.check_packet(decoded, policy=policy)
    a.validate_packet(decoded, policy=policy)
    restored = a.from_json(a.to_json(policy), expected_type=a.EnvelopePolicy)
    assert restored == policy
    assert packet(wire, restored) == decoded
    # Encoding reconstructs a semantic height, never replays ambiguous bytes.
    canonical = a.serialize_packet(decoded, policy=policy)
    assert canonical.endswith(f"F{expected:.1f}".encode())
    assert canonical != wire
    for reader in (a.APRS_IS(), a.APRS_IS(extensions={"water_height_tenths"})):
        assert packet(canonical, reader).payload == decoded.payload


def test_water_height_and_additive_weather_are_independent():
    wire = b"N0CALL>APRS:_01020304c180s005g010t070F1234X123V128"
    default = packet(wire, a.APRS_IS())
    assert default.payload.water_height.measurement.value == 1234
    assert default.payload.radiation.value == 12000
    assert default.payload.battery_voltage.value == 12.8
    modern = a.APRS_IS(extensions={*a.APRS_IS().extensions, "water_height_tenths"})
    assert packet(wire, modern).payload.water_height.measurement.value == 123.4
    unavailable = packet(wire.replace(b"F1234", b"F...."), modern)
    assert unavailable.payload.water_height.measurement.value is None
    assert a.serialize_packet(unavailable, policy=modern).endswith(b"F....X123V128")
    findings = a.check_packet(unavailable)
    assert [(d.path, d.message) for d in findings] == [
        ("$.payload.water_height", "unavailable height requires water_height_tenths")
    ]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(unavailable)
    # Unrecognized unavailable notation stays inspectable as legacy comment.
    legacy = packet(wire.replace(b"F1234", b"F...."), BASELINE)
    assert legacy.payload.water_height is None
    assert legacy.payload.comment == "F....X123V128"


CATALOG = [
    ("utf8_text", "additive", True),
    ("dao", "comment", True),
    ("base91_telemetry", "comment", True),
    ("mice_device_ids", "comment", True),
    ("mice_hex_as_device", "reinterpretive", False),
    ("expanded_telemetry", "additive", True),
    ("phg_rate", "comment", True),
    ("weather_extensions", "additive", True),
    ("water_height_tenths", "reinterpretive", False),
]


def test_catalog_classification_is_exhaustive_and_immutable():
    assert (
        set(a.EXTENSION_KINDS)
        == set(a.SUPPORTED_EXTENSIONS)
        == set(get_args(a.Extension))
    )
    assert set(a.EXTENSION_KINDS) == {identifier for identifier, _, _ in CATALOG}
    with pytest.raises(TypeError):
        a.EXTENSION_KINDS["mice_device_ids"] = "additive"  # type: ignore[index]


@pytest.mark.parametrize("identifier,kind,enabled", CATALOG)
def test_catalog_default_rule(identifier, kind, enabled):
    assert a.EXTENSION_KINDS[identifier] == kind
    for factory in (a.RF, a.APRS_IS):
        assert (identifier in factory().extensions) is enabled
        assert identifier in factory(extensions={identifier}).extensions
        assert not factory(extensions=set()).extensions
        assert all(
            a.EXTENSION_KINDS[x] in {"additive", "comment"}
            for x in factory().extensions
        )


def test_nested_header_exempt_but_payload_policy_propagates():
    wire = "W1AW>APRS:}lowercase>APRS,qAR,T2SERVER:>é".encode()
    old = packet(wire, a.RF(extensions=set()))
    assert {d.path for d in old.diagnostics} == {"$.payload.packet.payload.text"}
    enabled = a.RF(extensions={"utf8_text"})
    new = packet(wire, enabled)
    assert not new.diagnostics
    assert a.serialize_packet(new, policy=enabled) == wire
    # Never let captured bytes or saved diagnostics bypass fresh policy checks.
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(replace(new, diagnostics=()), policy=a.RF(extensions=set()))


@pytest.mark.parametrize("tail,value", [(b"F1234", 123.4), (b"F....", None)])
def test_located_water_height_uses_policy_through_comment_budget(tail, value):
    policy = a.RF(extensions={"water_height_tenths"})
    wire = b"N0CALL>APRS:!4903.50N/07201.75W_180/005g010t070" + tail
    received = packet(wire, policy)
    assert received.payload.extensions.weather.water_height.measurement.value == value
    assert not received.diagnostics
    canonical = a.serialize_packet(received, policy=policy)
    assert packet(canonical, policy).payload == received.payload
