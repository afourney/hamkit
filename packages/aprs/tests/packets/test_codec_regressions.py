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


def test_mic_e_longitude_100_to_109_degrees_uses_specified_bytes():
    # APRS101 p.48 encodes 100-109 degrees as 'l'-'u'; bytes 28-37 decode to the
    # same values but include FS-US control characters.
    cases = [r for r in rows() if r["id"] in {f"MIC-{n}" for n in range(116, 126)}]
    assert len(cases) == 10
    for row in cases:
        raw = row["packet"].encode("latin-1")
        wire = a.serialize_packet(without_evidence(packet(raw)))
        assert wire == raw, row["id"]
        assert 108 <= wire[wire.index(b":") + 2] <= 117


def test_known_bad_nmea_checksum_requires_explicit_repair():
    received = packet(b"N0CALL>APRS:$GPGLL,4916.45,N,12311.12,W,225444,A*00")
    n = received.payload
    assert isinstance(n, a.NMEA) and n.metadata.checksum_valid is False
    finding = "$.payload.metadata.checksum_valid"
    assert [d.path for d in received.diagnostics] == [finding]  # Reported once.
    assert [d.path for d in a.check_packet(received)] == [finding]
    for send in (a.serialize_packet, a.validate_packet, a.serialize_tnc2_line):
        with pytest.raises(a.ConformanceError) as caught:
            send(received)
        assert [d.path for d in caught.value.diagnostics] == [finding]
    # Explicit repair: clear the verdict, and a fresh checksum is computed.
    trusted = dataclasses.replace(n.metadata, checksum_valid=None)
    repaired = dataclasses.replace(
        received, payload=dataclasses.replace(n, metadata=trusted)
    )
    resent = packet(a.serialize_packet(repaired)).payload
    assert isinstance(resent, a.NMEA) and resent.metadata.checksum_valid is True
    # Or omit the checksum entirely.
    unsigned = dataclasses.replace(
        received,
        payload=dataclasses.replace(n, metadata=a.NMEAMetadata(n.metadata.talker)),
    )
    assert b"*" not in a.serialize_packet(unsigned)


@pytest.mark.parametrize(
    "text",
    [
        "Directs= are fine, see you at 7",
        "Directs=",
        "N0CALL HEARD: 1 2 3",
        "N0CALL HEARD: 1 2 3 4 5 6 7 8 9",
    ],
)
def test_text_resembling_a_response_stays_a_message(text):
    raw = b"N0CALL>APRS::W1AW     :" + text.encode()
    value = packet(raw).payload
    assert value == a.Message("W1AW", text)
    assert a.serialize_packet(packet(raw)) == raw


def test_complete_response_grammar_is_still_structured():
    value = packet(b"N0CALL>APRS::W1AW     :Directs= W1AW W2ABC").payload
    assert value == a.Response("W1AW", a.DirectStations(("W1AW", "W2ABC")))


def test_structured_weather_is_exempt_from_the_position_comment_budget():
    weather = (
        b"N0CALL>APRS:@092345z4903.50N/07201.75W_220/004g005t077r000p000P000h50b09900"
    )
    # 44 bytes of structured weather data: an ordinary report is sendable.
    assert a.check_packet(packet(weather + b"L123wRSW")) == ()
    # Wind occupies the 7-byte data-extension slot; the comment keeps 36 bytes.
    assert a.check_packet(packet(weather + b" " + b"x" * 35)) == ()
    assert [d.path for d in a.check_packet(packet(weather + b" " + b"x" * 36))] == [
        "$.payload.comment"
    ]
    # With wind in compressed csT, all weather data is exempt.
    compressed = b"N0CALL>APRS:=/5L!!<*e7_7P[g005t077r000p000P000h50b09900L123"
    assert a.check_packet(packet(compressed + b" " + b"x" * 42)) == ()
    assert [d.path for d in a.check_packet(packet(compressed + b" " + b"x" * 43))] == [
        "$.payload.comment"
    ]
    # Envelope limits still count every weather byte.
    tight = dataclasses.replace(a.RF, max_information_bytes=60)
    findings = a.check_packet(packet(weather + b"L123wRSW"), policy=tight)
    assert [d.path for d in findings] == ["$.payload"]


@pytest.mark.parametrize(
    "raw",
    [
        b"N0CALL>APRS:_10090556c220s004g005t077r000p000P000h50b09900wRSW",
        b"N0CALL>APRS:!4903.50N/07201.75W_220/004g005t077r000p000P000h50b09900wRSW",
    ],
)
def test_weather_codes_must_end_the_report(raw):
    # APRS101 pp.63-66 end every weather report with the S/uuuu codes and define
    # no comment after them, so a comment would hide the codes on read-back.
    received = packet(raw)
    assert a.check_packet(received) == ()
    payload = dataclasses.replace(received.payload, comment="home")
    both = dataclasses.replace(received, payload=payload)
    findings = a.check_packet(both)
    assert [(d.path, d.message) for d in findings] == [
        (
            "$.payload.comment",
            (
                "weather software/unit codes must end the report; "
                "a comment cannot follow them"
            ),
        )
    ]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(both)
    # Without codes, the comment is sent and read back unchanged.
    if isinstance(payload, a.Weather):
        uncoded = dataclasses.replace(payload, software_code=None, device_code=None)
    else:
        assert payload.extensions.weather is not None
        weather = dataclasses.replace(
            payload.extensions.weather, software_code=None, device_code=None
        )
        uncoded = dataclasses.replace(
            payload,
            extensions=dataclasses.replace(payload.extensions, weather=weather),
        )
    # Without codes, a comment shaped like codes would be read back as codes.
    lookalike = dataclasses.replace(both, payload=uncoded)
    assert [(d.path, d.message) for d in a.check_packet(lookalike)] == [
        (
            "$.payload.comment",
            "comment would be read back as weather software/unit codes",
        )
    ]
    # Any other comment is sent and read back unchanged.
    for comment in ("home station", "73!"):
        plain = dataclasses.replace(
            lookalike, payload=dataclasses.replace(uncoded, comment=comment)
        )
        resent = packet(a.serialize_packet(plain))
        assert resent.payload.comment == comment


MIC_E = b"N0CALL>S32UVT:`(_f\x1e\x1eOj/"


@pytest.mark.parametrize(
    ("status", "device", "comment", "telemetry"),
    [
        (b'`"4T}Hi_%', "`_%", "Hi", None),  # Yaesu FTM-400DR with altitude
        (b"'Hello|3", "'|3", "Hello", None),  # Byonics TinyTrack3
        (b"'1020 x", "'", "1020 x", None),  # incomplete hex: a type byte
        (b"`plain", "`", "plain", None),  # undeclared suffix stays in the comment
        (b']"3x}=', "]=", "", None),  # Kenwood TM-D710
        (b">Ready^", ">^", "Ready", None),  # Kenwood TH-D74
        (b"`1020", None, "", "mic_e_hex"),  # APRS101 two-channel telemetry
        (b"'102030FFff text", None, " text", "mic_e_hex"),
        (b"'102030FFff|3", "'|3", "102030FFff", None),  # a declared suffix wins
    ],
)
def test_mic_e_type_codes(status, device, comment, telemetry):
    # APRS 1.2 (aprs.org/aprs12/mic-e-types.txt) redefines ` and ' as type bytes;
    # no type byte or suffix can make the packet Malformed.
    decoded = packet(MIC_E + status)
    assert decoded.payload.device_code == device
    assert decoded.payload.comment == comment
    t = decoded.payload.extensions.telemetry
    assert (t and t.encoding) == telemetry
    resent = packet(a.serialize_packet(decoded))
    assert (resent.payload.device_code, resent.payload.comment) == (device, comment)


def test_mic_e_type_codes_are_checked_before_sending():
    def mic_e(**fields):
        motion = a.Extensions(motion=a.Motion(90, 10))
        fields.setdefault("extensions", motion)
        payload = a.MicE(33.4277, -112.12, a.Symbol("/", ">"), message="off_duty")
        return a.Packet(
            a.Header("N0CALL", "S32UVT"), dataclasses.replace(payload, **fields)
        )

    def findings(**fields):
        return [(d.path, d.message) for d in a.check_packet(mic_e(**fields))]

    assert findings(device_code="`_%", comment="Hi") == []
    readback = (
        "$.payload.comment",
        "would be read back as a different Mic-E type code",
    )
    assert findings(device_code="`", comment="Hi_%") == [readback]
    assert findings(comment="]hello") == [readback]
    assert findings(comment="'1020") == [readback]
    assert findings(device_code=">", comment="ok=") == [readback]
    assert findings(device_code="]x") == [
        ("$.payload.device_code", "not a declared Mic-E type code")
    ]
    telemetry = a.Telemetry((1, 2, 3, 4, 5), encoding="mic_e_hex")
    shared = a.Extensions(motion=a.Motion(90, 10), telemetry=telemetry)
    assert findings(device_code="'", extensions=shared) == [
        (
            "$.payload.device_code",
            "Mic-E telemetry and a type code share the first byte",
        )
    ]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(mic_e(device_code="`", comment="Hi_%"))


def test_embedded_position_search_is_opt_in():
    # APRS101 p.18 (X1J) allowed a "!" position in the first 40 bytes of other
    # text; the APRS 1.1 addendum deprecates the search.
    raw = b"N0CALL>BEACON:X!4903.50N/07201.75W-"
    assert packet(raw).payload == a.Beacon("X!4903.50N/07201.75W-")
    legacy = a.parse_packet(raw, legacy_positions=True)
    assert isinstance(legacy.payload, a.LegacyPosition)
    assert legacy.payload.prefix == b"X"
    framed = a.parse_tnc2_line(raw + b"\r\n", legacy_positions=True)
    assert framed.payload == legacy.payload
    payload = a.parse_payload(raw.partition(b":")[2], legacy_positions=True)
    assert payload == legacy.payload
    beyond = b"N0CALL>BEACON:" + b"X" * 40 + b"!4903.50N/07201.75W-"
    assert isinstance(a.parse_packet(beyond, legacy_positions=True).payload, a.Beacon)
    with pytest.raises(TypeError):
        a.parse_packet(raw, legacy_positions="yes")
