# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Composition and malformed-input regressions beyond fixture projections."""
from __future__ import annotations

import dataclasses
import random

import pytest
from packets.test_corpus import rows
from packets.test_roundtrip_corpus import same_semantics, without_evidence
from receiver import Receiver

from hamkit import aprs as a


def packet(raw):
    value = a.parse_packet(raw)
    assert isinstance(value, a.Packet)
    return value


def test_editing_nmea_recomputes_checksum_and_ignores_lexical_evidence():
    original = packet(b"N0CALL>APRS:$GPGLL,4916.45,N,12311.12,W,225444,A*31")
    n = original.payload
    assert isinstance(n, a.NMEA) and isinstance(n.sentence, a.GLL)
    changed = dataclasses.replace(
        original,
        payload=dataclasses.replace(
            n,
            sentence=dataclasses.replace(n.sentence, coordinates=a.Coordinates(51, -1)),
        ),
    )
    wire = a.serialize_packet(changed)
    assert b"5100,N,00100,W" in wire and wire != original.original_wire
    decoded = packet(wire).payload
    assert isinstance(decoded, a.NMEA)
    assert decoded.sentence.coordinates == a.Coordinates(51, -1)
    assert decoded.metadata.checksum_valid is True


def test_dao_is_not_applied_twice_when_composing():
    original = packet(b"N0CALL>APRS:!4903.50N/07201.75W>!W12!")
    clean = without_evidence(original)
    for _ in range(5):
        clean = packet(a.serialize_packet(clean))
        same_semantics(original, clean)
    p = original.payload
    changed = dataclasses.replace(
        original, payload=dataclasses.replace(p, latitude_deg=p.latitude_deg + 1)
    )
    assert b"5003.50N" in a.serialize_packet(changed)


def test_mic_e_uses_edited_semantics_and_checks_destination():
    original = packet(b"N0CALL>490S5P:`123456>/")
    p = original.payload
    assert isinstance(p, a.MicE)
    modified = dataclasses.replace(
        original,
        payload=dataclasses.replace(
            p, extensions=dataclasses.replace(p.extensions, motion=a.Motion(270, 42))
        ),
    )
    decoded = packet(a.serialize_packet(modified))
    assert decoded.payload.extensions.motion == a.Motion(270, 42)
    invalid = dataclasses.replace(modified, header=a.Header("N0CALL", "APRS"))
    with pytest.raises(a.FieldError, match="destination"):
        a.serialize_packet(invalid)


@pytest.mark.parametrize(
    "response",
    [
        a.DirectStations(("W1AW", "W2ABC")),
        a.HeardStation("W1AW", (1, None, 3, 0, 0, 0, 0, 0)),
        a.Trace(a.Header("N0CALL", "APRS", (a.Hop("WIDE1-1", True),))),
    ],
)
def test_structured_query_response_roundtrip(response):
    p = a.Response("W1AW", response)
    assert a.parse_payload(a.serialize_payload(p)) == p


def test_station_weather_association_survives_interleaved_station():
    receiver = Receiver()
    receiver.receive(packet(b"N0CALL>APRS:!4903.50N/07201.75W_"))
    receiver.receive(packet(b"W1AW>APRS:!5100.00N/00100.00W_"))
    state = receiver.receive(packet(b"N0CALL>APRS:_10151800c220s004g005t077"))
    assert state["weather_latitude_deg"] == pytest.approx(49.058333333333)
    assert state["weather_longitude_deg"] == pytest.approx(-72.029166666667)


def test_truncation_and_mutation_do_not_escape_recovery():
    rng = random.Random(4)
    for raw in sorted({r["packet"].encode("latin1") for r in rows()}):
        candidates = [raw[:i] for i in range(len(raw))]
        for _ in range(8):
            if raw:
                i = rng.randrange(len(raw))
                candidates.append(raw[:i] + bytes([rng.randrange(256)]) + raw[i + 1 :])
        for candidate in candidates:
            try:
                result = a.parse_packet(candidate)
            except (a.ContextRequiredError, a.ResourceLimitError):
                continue
            assert isinstance(result, (a.Packet, a.Malformed)), repr(candidate)
            assert result.original_wire == candidate


def test_weather_metric_units_are_converted_before_compression():
    weather = a.Weather(
        wind_direction=a.Measurement(180, "degrees"),
        wind_speed=a.Measurement(10, "m/s"),
        gust=a.Measurement(12, "m/s"),
        temperature=a.Measurement(20, "celsius"),
    )
    p = a.Position(
        49,
        -72,
        a.Symbol("/", "_"),
        compression=a.Compression(fix="current", nmea_source="RMC", origin_code=0),
        extensions=a.Extensions(weather=weather),
    )
    decoded = a.parse_payload(a.serialize_payload(p))
    assert isinstance(decoded, a.Position) and decoded.extensions.weather is not None
    w = decoded.extensions.weather
    assert w.wind_speed.unit == "knots"
    assert w.wind_speed.value == pytest.approx(10 * 3600 / 1852, rel=0.05)
    assert w.temperature == a.Measurement(68, "fahrenheit")


def test_unrepresentable_annotations_and_field_overflow_are_not_dropped():
    storm = a.Storm(
        "HC",
        predicted=False,
        sustained_wind_knots=1000,
        peak_gust_knots=100,
        central_pressure_hpa=990,
        hurricane_radius_nm=20,
        tropical_storm_radius_nm=50,
    )
    p = a.Position(
        49,
        -72,
        a.Symbol("\\", "@"),
        extensions=a.Extensions(motion=a.Motion(90, 10), storm=storm),
    )
    with pytest.raises(a.ConformanceError, match="sustained_wind"):
        a.serialize_payload(p)
    with pytest.raises(a.FieldError, match="structured fields"):
        a.serialize_payload(a.Status("IO91/- House"))
    with pytest.raises(a.FieldError, match="query response"):
        a.serialize_payload(a.Message("W1AW", "Directs= N0CALL"))
    report = a.NMEA(
        a.GLL(a.Coordinates(49, -72), "120000", "A"),
        a.NMEAMetadata("GP"),
        symbol=a.Symbol("/", "-"),
    )
    with pytest.raises(a.FieldError, match="symbol"):
        a.serialize_packet(a.Packet(a.Header("N0CALL", "APRS"), report))


def test_invalid_signpost_token_and_oversized_sequence_are_malformed():
    for wire in (
        b"N0CALL>APRS:!4903.50N\\07201.75Wm{\xff}",
        b"N0CALL>APRS:T#" + b"1" * 5000 + b",1,2,3,4,5,00000000",
    ):
        assert isinstance(a.parse_packet(wire), a.Malformed)
