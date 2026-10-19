# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Automatic Mic-E destinations: JSON and API behaviour (wire anchors are MIC case vectors)."""
from dataclasses import replace

import pytest

from case_tool import all_rows, policy_of
from hamkit import aprs as a
from semantics import same_semantics, without_evidence


def payload(latitude=47.75, longitude=-122.15, **kwargs):
    return a.MicE(
        latitude,
        longitude,
        a.Symbol("/", ">"),
        message=kwargs.pop("message", "en_route"),
        extensions=a.Extensions(motion=a.Motion(90, 10)),
        **kwargs,
    )


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
    # The generated destinations for both are MIC case vectors.
    assert original.header.destination is edited.header.destination is None
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


VECTORS = [
    r
    for r in all_rows()
    if r["tnc2"] is not None
    and r["encoding_error"] is None
    and r["decoded"].get("payload", {}).get("type") == "mic_e"
    and r["decoded"]["payload"]["message"] != "unknown"
]


@pytest.mark.parametrize("row", VECTORS, ids=lambda r: r["id"])
def test_auto_destination_from_independent_corpus_payload(row):
    policy = policy_of(row)
    original = a.parse_packet(row["tnc2"].encode("latin1"), policy=policy)
    assert isinstance(original, a.Packet) and isinstance(original.payload, a.MicE)
    assert original.payload.message != "unknown"
    auto = replace(original, header=replace(original.header, destination=None))
    result = a.parse_packet(a.serialize_packet(auto, policy=policy), policy=policy)
    assert isinstance(result, a.Packet)
    same_semantics(without_evidence(original.payload), without_evidence(result.payload))
