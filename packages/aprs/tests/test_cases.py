# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Run every case vector in tests/cases; each row is checked every way it can be.

A row with ``tnc2`` tests decoding and encoding; a row without it starts from
``decoded`` and tests encoding. ``id``, ``comment`` and ``fap`` are not consulted
beyond the uniqueness of ``id``. See tests/cases/README.md.
"""

from __future__ import annotations

import collections
import json
from typing import Any

import pytest

from case_tool import FIELDS, case_files, encode, error_json, policy_of, read
from hamkit import aprs as a
from semantics import same_semantics, without_evidence

ROWS = [(path.name, row) for path in case_files() for row in read(path)]


def test_rows_have_exactly_the_fields_and_unique_ids():
    for name, row in ROWS:
        assert tuple(row) == FIELDS, (name, row.get("id"))
        assert isinstance(row["comment"], str) and row["comment"].strip(), row["id"]
        assert (row["reencoded"] is None) != (row["encoding_error"] is None), row["id"]
    counts = collections.Counter(row["id"] for _, row in ROWS)
    assert not [i for i, n in counts.items() if n > 1]


def exact(x: Any, y: Any) -> bool:
    """JSON equality that also tells -0.0 from 0.0 and 1 from 1.0."""
    return json.dumps(x, ensure_ascii=False) == json.dumps(y, ensure_ascii=False)


def outcome(value: Any, policy: a.EnvelopePolicy) -> tuple[str | None, Any]:
    return encode(value, policy)


def needs_context(payload: Any) -> bool:
    """Payloads that cannot be encoded without the header: an NMEA symbol is
    written into the destination. (A Mic-E destination is computed from the
    payload, so a Mic-E payload encodes alone.)"""
    return isinstance(payload, a.NMEA) and payload.symbol is not None


def payload_outcome(value: a.Packet, policy: a.EnvelopePolicy) -> Any:
    try:
        return a.serialize_payload(value.payload, policy=policy)
    except a.ContextRequiredError:
        assert needs_context(value.payload), "only an NMEA symbol needs context"
        return "context"
    except (a.APRSError, TypeError) as exc:
        return error_json(exc)


def mic_e_alone(value: a.Packet, policy: a.EnvelopePolicy) -> Any:
    """What serialize_payload must give for a Mic-E payload, from the packet."""
    import dataclasses

    auto = dataclasses.replace(
        value, header=dataclasses.replace(value.header, destination=None)
    )
    loose = dataclasses.replace(
        policy,
        source_pattern=".*",
        destination_pattern=".*",
        path_address_pattern=".*",
        max_path_entries=None,
        max_information_bytes=None,
        max_tnc2_line_bytes=None,
    )
    try:
        return a.serialize_packet(auto, policy=loose).partition(b":")[2]
    except a.ConformanceError as exc:
        found = [
            {**d, "path": "$"}
            if d["path"] == "$.header.destination"
            else {**d, "path": "$" + d["path"][len("$.payload") :]}
            for d in error_json(exc)["diagnostics"]
        ]
        return {"type": "ConformanceError", "diagnostics": found}
    except (a.APRSError, TypeError) as exc:
        return error_json(exc)


def payload_relative(error: dict[str, Any]) -> dict[str, Any] | None:
    """The refusal serialize_payload gives: payload findings, made relative.

    Header findings and envelope size limits ("information exceeds N bytes",
    reported at $.payload) belong to the packet, not the payload alone.
    """
    if error["type"] != "ConformanceError":
        return error
    found = [
        {**d, "path": "$" + d["path"][len("$.payload") :]}
        for d in error["diagnostics"]
        if (d["path"] == "$.payload" or d["path"].startswith("$.payload."))
        and not d["message"].startswith("information exceeds ")
    ]
    return {"type": "ConformanceError", "diagnostics": found} if found else None


def check_encoding(
    row: dict[str, Any], value: Any, policy: a.EnvelopePolicy, *, received: bool
) -> None:
    """Every sending path agrees with reencoded/encoding_error."""
    expected = (row["reencoded"], row["encoding_error"])
    assert outcome(value, policy) == expected
    error = row["encoding_error"]
    if not isinstance(value, a.Packet):
        return
    # check_packet predicts exactly the conformance findings, and nothing else.
    findings = [
        a.to_json_dict(d, include_defaults=True)
        for d in a.check_packet(value, policy=policy)
    ]
    conformance = (
        error["diagnostics"] if error and error["type"] == "ConformanceError" else []
    )
    assert findings == conformance
    try:
        a.validate_packet(value, policy=policy)
        validated = None
    except a.APRSError as exc:
        validated = error_json(exc)
    assert validated == error
    # Without received evidence the value is sent from its fields alone: it is
    # refused the same way, or reads back stably (with the same meaning, for a
    # received value; a composed one may be quantized, see reencoded).
    clean = without_evidence(value)
    sent, refused = outcome(clean, policy)
    assert refused == error
    if sent is not None:
        decoded = a.parse_packet(sent.encode("latin-1"), policy=policy)
        if received:
            same_semantics(clean, decoded)
        assert outcome(without_evidence(decoded), policy) == (sent, None)
    payload = payload_outcome(value, policy)
    if row["reencoded"] is None:
        # Line framing refuses exactly as serialize_packet does, and the payload
        # alone is refused for its own findings (header-only refusals aside).
        try:
            a.serialize_tnc2_line(value, policy=policy)
            line = None
        except (a.APRSError, TypeError) as exc:
            line = error_json(exc)
        assert line == error
        relative = payload_relative(error)
        if payload == "context":
            return  # The NMEA symbol is checked against the header (above).
        if not isinstance(value.payload, a.MicE):
            assert payload == (relative or payload), payload
            assert isinstance(payload, bytes) or relative is not None, payload
            return
        # A Mic-E payload alone encodes like the packet with its destination
        # generated (under a permissive envelope): destination-level problems
        # then appear at "$", and payload-local refusals must match.
        assert payload == mic_e_alone(value, policy), payload
        return
    wire = row["reencoded"].encode("latin-1")
    # The payload alone encodes to the same information field, unless it needs
    # header context (Mic-E, NMEA symbols). An unknown Mic-E message is refused
    # outright without its destination.
    if isinstance(payload, bytes):
        assert payload == wire.partition(b":")[2]
    elif payload != "context":
        p = value.payload
        assert isinstance(p, a.MicE) and p.message == "unknown", payload
    if b"\r" in wire or b"\n" in wire:
        with pytest.raises(a.EnvelopeError):
            a.serialize_tnc2_line(value, policy=policy)
    else:
        assert a.serialize_tnc2_line(value, policy=policy) == wire + b"\r\n"
    # What we send reads back cleanly and re-encodes to the same bytes.
    again = a.parse_packet(wire, policy=policy)
    assert isinstance(again, a.Packet), again
    assert again.diagnostics == ()
    assert a.serialize_packet(again, policy=policy) == wire
    assert a.from_json_dict(a.to_json_dict(again)) == again


@pytest.mark.parametrize("row", [r for _, r in ROWS], ids=[r["id"] for _, r in ROWS])
def test_case(row):
    policy = policy_of(row)
    canonical = a.to_json_dict(policy, include_defaults=True)
    assert exact(canonical, row["policy"]), "policy is not in canonical form"
    if row["tnc2"] is not None:
        wire = row["tnc2"].encode("latin-1")
        parsed = a.parse_packet(wire, policy=policy)
        assert exact(a.to_json_dict(parsed, include_defaults=True), row["decoded"])
        if b"\r" not in wire and b"\n" not in wire:
            for terminator in (b"\r\n", b"\n"):
                line = a.parse_tnc2_line(wire + terminator, policy=policy)
                assert exact(
                    a.to_json_dict(line, include_defaults=True), row["decoded"]
                )
        # decoded is lossless: it rebuilds the parsed value exactly.
        rebuilt = a.from_json_dict(row["decoded"])
        assert rebuilt == parsed
        assert exact(a.to_json_dict(rebuilt, include_defaults=True), row["decoded"])
        check_encoding(row, parsed, policy, received=True)
        check_encoding(row, rebuilt, policy, received=True)
        return
    try:
        value = a.from_json_dict(row["decoded"])
    except a.APRSError as exc:
        assert row["reencoded"] is None and error_json(exc) == row["encoding_error"]
        return
    # Encode-only input is written out in full (canonical form), like decoded.
    assert exact(a.to_json_dict(value, include_defaults=True), row["decoded"])
    check_encoding(row, value, policy, received=False)
