# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Automatic destinations from semantic fields, with independent APRS101 anchors."""
from dataclasses import replace
from typing import get_args

import pytest
from packets.test_corpus import parse_row, rows
from packets.test_roundtrip_corpus import EXCEPTIONS, same_semantics, without_evidence

from hamkit import aprs as a


def payload(latitude=47.75, longitude=-122.15, **kwargs):
    return a.MicE(
        latitude,
        longitude,
        a.Symbol("/", ">"),
        message=kwargs.pop("message", "en_route"),
        extensions=a.Extensions(motion=a.Motion(90, 10)),
        **kwargs,
    )


def encode(p, policy=None):
    policy = a.APRS_IS() if policy is None else policy
    return a.serialize_packet(a.Packet(a.Header("N0CALL"), p), policy=policy)


@pytest.mark.parametrize(
    "latitude,longitude,message,address",
    [
        (47.75, -122.15, "en_route", "TW4UPP"),
        # APRS101 p44 worked example: 33d25.64 N, west, offset 0, bits 100.
        (33 + 25.64 / 60, -72.129, "returning", "S32U6T"),
        # APRS101 p46 first-three-byte example F2D = Custom-2 (bits 101).
        (52 + 30.12 / 60, 72.129, "custom_2", "F2DP12"),
        (0, 0, "emergency", "000PP0"),
        (-47.75, 122.15, "en_route", "TW45P0"),
    ],
)
def test_published_encoding_table_anchors(latitude, longitude, message, address):
    model = payload(latitude, longitude, message=message)
    wire = encode(model)
    assert wire.split(b":")[0] == f"N0CALL>{address}".encode()
    decoded = a.parse_packet(wire)
    assert isinstance(decoded, a.Packet)
    assert decoded.payload.latitude_deg == pytest.approx(latitude)
    assert decoded.payload.longitude_deg == pytest.approx(longitude)
    assert decoded.payload.message == message


@pytest.mark.parametrize(
    "message", [m for m in get_args(a.MicEMessage) if m != "unknown"]
)
@pytest.mark.parametrize("ambiguity", range(5))
@pytest.mark.parametrize("sign", [-1, 1])
def test_every_message_ambiguity_and_hemisphere(message, ambiguity, sign):
    original = payload(
        sign * 47.752, sign * 122.157, message=message, ambiguity=ambiguity
    )
    decoded = a.parse_packet(encode(original))
    assert isinstance(decoded, a.Packet)
    assert decoded.payload.message == message
    assert decoded.payload.ambiguity == ambiguity
    assert decoded.payload.ambiguity_extent == original.ambiguity_extent
    assert (decoded.payload.latitude_deg < 0) == (sign < 0)
    assert (decoded.payload.longitude_deg < 0) == (sign < 0)
    assert encode(decoded.payload) == encode(original)


@pytest.mark.parametrize(
    "longitude",
    [
        -179.9998,
        -110,
        -109.9999,
        -100,
        -99.99999,
        -10,
        -9.99999,
        -0.0,
        0.0,
        9.99999,
        10,
        99.99999,
        100,
        109.9999,
        110,
        179.9998,
    ],
)
@pytest.mark.parametrize("latitude", [-89.99999, -0.0, 0.0, 89.99999])
def test_rounding_at_latitude_and_longitude_encoding_boundaries(latitude, longitude):
    decoded = a.parse_packet(encode(payload(latitude, longitude)))
    assert isinstance(decoded, a.Packet)
    assert decoded.payload.latitude_deg == pytest.approx(latitude, abs=1 / 12000)
    assert decoded.payload.longitude_deg == pytest.approx(longitude, abs=1 / 12000)
    assert encode(decoded.payload) == encode(payload(latitude, longitude))


@pytest.mark.parametrize("longitude", [-180, 180, 179.999999])
def test_unrepresentable_longitude_is_a_clear_send_finding(longitude):
    p = a.Packet(a.Header("N0CALL"), payload(longitude=longitude))
    assert any(d.path == "$.header.destination" for d in a.check_packet(p))
    for send in (a.validate_packet, a.serialize_packet):
        with pytest.raises(a.ConformanceError, match="wire range"):
            send(p)


def test_omitted_json_destination_and_editable_auto_template():
    original = a.Packet(a.Header("N0CALL", path=(a.Hop("WIDE1-1"),)), payload())
    data = a.to_json_dict(original)
    assert "destination" not in data["header"]
    assert a.from_json_dict(data) == original
    full = a.to_json_dict(original, include_defaults=True)
    assert full["header"]["destination"] is None
    assert a.from_json_dict(full) == original
    edited = replace(
        original,
        payload=replace(original.payload, latitude_deg=-47.75, message="custom_2"),
    )
    assert original.header.destination is edited.header.destination is None
    assert a.serialize_packet(original) != a.serialize_packet(edited)
    assert a.parse_packet(a.serialize_packet(edited)).payload.message == "custom_2"
    assert (
        a.serialize_payload(original.payload)
        == a.serialize_packet(original).partition(b":")[2]
    )
    with pytest.raises(a.ContextRequiredError):
        a.parse_payload(a.serialize_payload(original.payload))
    with pytest.raises(a.FieldError, match="explicit destination"):
        a.parse_payload(
            a.serialize_payload(original.payload),
            header=a.Header("N0CALL"),
            malformed="raise",
        )
    with pytest.raises(a.EnvelopeError):
        str(original.header)


@pytest.mark.parametrize(
    "change",
    [
        {"latitude_deg": -47.75},
        {"longitude_deg": 122.15},
        {"longitude_deg": -72.15},
        {"message": "off_duty"},
        {"ambiguity": 1},
    ],
)
def test_explicit_destination_conflicts_and_parsed_edit_reset(change):
    wire = encode(payload())
    parsed = a.parse_packet(wire)
    assert isinstance(parsed, a.Packet)
    assert a.serialize_packet(parsed) == wire
    conflict = replace(parsed, payload=replace(parsed.payload, **change))
    assert any(d.path == "$.header.destination" for d in a.check_packet(conflict))
    with pytest.raises(a.ConformanceError, match="destination"):
        a.serialize_packet(conflict)
    reset = replace(conflict, header=replace(conflict.header, destination=None))
    assert a.serialize_packet(reset) != wire
    # Neither saved evidence nor clearing diagnostics substitutes old wire.
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(replace(conflict, diagnostics=()))


def test_explicit_ssid_is_preserved_and_unknown_message_is_not_invented():
    explicit = a.Packet(a.Header("N0CALL", "TW4UPP-3"), payload())
    assert a.serialize_packet(explicit).startswith(b"N0CALL>TW4UPP-3:")
    unknown = a.Packet(a.Header("N0CALL"), payload(message="unknown"))
    with pytest.raises(a.ConformanceError, match="unknown Mic-E message"):
        a.serialize_packet(unknown)


@pytest.mark.parametrize(
    "model",
    [
        a.Status("Ready"),
        a.Position(47, -122, a.Symbol("/", ">")),
        a.ThirdParty(a.Packet(a.Header("N0CALL"), payload())),
    ],
)
def test_missing_destination_remains_invalid_for_other_packets(model):
    with pytest.raises(a.ModelError, match="destination is required"):
        a.Packet(a.Header("N0CALL"), model)
    with pytest.raises(a.JSONModelError, match="destination is required"):
        a.from_json_dict(
            {
                "type": "packet",
                "header": {"source": "N0CALL"},
                "payload": a.to_json_dict(model),
            }
        )


def test_generated_header_is_policy_checked_including_lengths_and_nested_headers():
    auto = a.Packet(a.Header("N0CALL"), payload())
    policy = a.RF(destination_pattern="APRS")
    assert {d.path for d in a.check_packet(auto, policy=policy)} == {
        "$.header.destination"
    }
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(auto, policy=policy)
    wire = a.serialize_packet(auto)
    short = a.APRS_IS(max_tnc2_line_bytes=len(wire) + 1)
    assert any(d.path == "$" for d in a.check_packet(auto, policy=short))
    outer = a.Packet(a.Header("N0CALL", "APRS"), a.ThirdParty(auto))
    encoded = a.serialize_packet(outer, policy=policy)
    assert encoded == b"N0CALL>APRS:}" + wire
    assert isinstance(a.parse_packet(encoded, policy=policy), a.Packet)
    inner_conflict = replace(auto, header=a.Header("N0CALL", "APRS"))
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(
            replace(outer, payload=a.ThirdParty(inner_conflict)), policy=policy
        )


VECTORS = [
    r
    for r in rows()
    if r["expected"].get("payload", {}).get("type") == "mic_e"
    and r["id"] not in EXCEPTIONS
    and r["expected"].get("payload", {}).get("message") != "unknown"
]


@pytest.mark.parametrize("row", VECTORS, ids=lambda r: r["id"])
def test_auto_destination_from_independent_corpus_payload(row):
    policy = a.from_json_dict(row["policy"], expected_type=a.EnvelopePolicy)
    policy = replace(
        policy,
        source_pattern=".*",
        destination_pattern=".*",
        path_address_pattern=".*",
        max_path_entries=None,
        max_information_bytes=None,
        max_tnc2_line_bytes=None,
    )
    original = parse_row(row, row["packet"].encode("latin1"))
    assert isinstance(original, a.Packet) and isinstance(original.payload, a.MicE)
    assert original.payload.message != "unknown"
    auto = replace(original, header=replace(original.header, destination=None))
    result = a.parse_packet(a.serialize_packet(auto, policy=policy), policy=policy)
    assert isinstance(result, a.Packet)
    same_semantics(without_evidence(original.payload), without_evidence(result.payload))
