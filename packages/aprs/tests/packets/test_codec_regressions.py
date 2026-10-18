# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Composition and malformed-input regressions beyond fixture projections."""
from __future__ import annotations

import dataclasses
import random

import pytest
from packets.test_corpus import rows
from packets.test_roundtrip_corpus import same_semantics, without_evidence

from hamkit import aprs as a


def packet(raw, policy=None):
    policy = a.APRS_IS() if policy is None else policy
    value = a.parse_packet(raw, policy=policy)
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
    assert b"5100.00,N,00100.00,W" in wire and wire != original.original_wire
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
        compression=a.Compression(
            fix="current", nmea_source="RMC", origin="compressed"
        ),
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
        "hurricane",
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
        a.GLL(a.Coordinates(49, -72), a.UTCTime(12, 0, 0), "active"),
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
        payload=dataclasses.replace(
            n, metadata=a.NMEAMetadata(n.metadata.talker, checksum=False)
        ),
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
    tight = dataclasses.replace(a.RF(), max_information_bytes=60)
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
    ("status", "extra", "device", "comment", "telemetry"),
    [
        (b'`"4T}Hi_%', (), "`_%", "Hi", None),  # Yaesu FTM-400DR with altitude
        (b"'Hello|3", (), "'|3", "Hello", None),  # Byonics TinyTrack3
        (b"'1020 x", (), "'", "1020 x", None),  # incomplete hex: a type byte
        (b"`plain", (), "`", "plain", None),  # undeclared suffix stays in comment
        (b']"3x}=', (), "]=", "", None),  # Kenwood TM-D710
        (b">Ready^", (), ">^", "Ready", None),  # Kenwood TH-D74
        (b"`1020", (), None, "", "mic_e_hex"),  # APRS101 two-channel telemetry
        (b"'102030FFff text", (), None, " text", "mic_e_hex"),
        # Complete hex keeps its APRS 1.1 meaning unless explicitly reinterpreted.
        (b"'102030FFff|3", (), None, "|3", "mic_e_hex"),
        (b"'102030FFff|3", ("mice_hex_as_device",), "'|3", "102030FFff", None),
        (b"`1020", ("mice_hex_as_device",), "`", "1020", None),
    ],
)
def test_mic_e_type_codes(status, extra, device, comment, telemetry):
    # APRS 1.2 (aprs.org/aprs12/mic-e-types.txt) type codes are on by default
    # where they do not change an APRS 1.1 field; no marker makes it Malformed.
    policy = a.APRS_IS(extensions={*a.APRS_IS().extensions, *extra})
    decoded = packet(MIC_E + status, policy=policy)
    assert decoded.payload.device_code == device
    assert decoded.payload.comment == comment
    t = decoded.payload.extensions.telemetry
    assert (t and t.encoding) == telemetry
    resent = packet(a.serialize_packet(decoded, policy=policy), policy=policy)
    assert (resent.payload.device_code, resent.payload.comment) == (device, comment)


def test_mic_e_type_codes_are_checked_before_sending():
    policy = a.APRS_IS(extensions={"mice_device_ids"})

    def mic_e(**fields):
        motion = a.Extensions(motion=a.Motion(90, 10))
        fields.setdefault("extensions", motion)
        payload = packet(MIC_E).payload
        return a.Packet(
            a.Header("N0CALL", "S32UVT"), dataclasses.replace(payload, **fields)
        )

    def findings(**fields):
        return [
            (d.path, d.message) for d in a.check_packet(mic_e(**fields), policy=policy)
        ]

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
        ("$.payload.device_code", "unsupported Mic-E type code")
    ]
    # Complete hex after a type byte is still telemetry without the opt-in.
    assert findings(device_code="'", comment="102030FFff") == [
        (
            "$.payload.extensions.telemetry",
            "would be lost or introduced by Mic-E status encoding",
        ),
        readback,
    ]
    # A type code takes the first status byte, so telemetry moves to base91,
    # which needs its extension and a sequence number.
    telemetry = a.Telemetry((1, 2, 3, 4, 5), encoding="mic_e_hex")
    shared = a.Extensions(motion=a.Motion(90, 10), telemetry=telemetry)
    assert findings(device_code="'", extensions=shared) == [
        (
            "$.payload.extensions.telemetry.encoding",
            "requires base91_telemetry extension",
        ),
        (
            "$.payload.extensions.telemetry.sequence",
            "base91 telemetry requires a sequence in 0..8280",
        ),
    ]
    # Under mice_hex_as_device, hex would be read as a type code, so the
    # library sends the same channels in the APRS101 binary form instead.
    hex_as_device = a.APRS_IS(extensions={"mice_hex_as_device"})
    sent = a.serialize_packet(mic_e(extensions=shared), policy=hex_as_device)
    assert b"/\x1d\x01\x02\x03\x04\x05" in sent
    off = [
        (d.path, d.message)
        for d in a.check_packet(
            mic_e(device_code="`_%"), policy=a.APRS_IS(extensions=())
        )
    ]
    assert off == [
        ("$.payload.device_code", "Mic-E device code requires mice_device_ids")
    ]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(mic_e(device_code="`", comment="Hi_%"), policy=policy)


@pytest.mark.parametrize("device", [">", "]", ">^", "]="])
@pytest.mark.parametrize("altitude", [b"", b'"4T}'])
def test_mic_e_grid_stays_in_comment_and_roundtrips(device, altitude):
    policy = a.APRS_IS(extensions={"mice_device_ids"})
    comment = b"IO91SX/G Ready"
    raw = MIC_E + device[:1].encode() + altitude + comment + device[1:].encode()
    decoded = without_evidence(packet(raw, policy=policy))
    assert decoded.payload.device_code == device
    assert decoded.payload.comment == comment.decode()
    assert decoded.payload.latitude_deg == pytest.approx(33.427333333333)
    assert decoded.payload.longitude_deg == pytest.approx(-112.129)
    assert a.check_packet(decoded, policy=policy) == ()
    assert a.serialize_packet(decoded, policy=policy) == raw
    assert (
        without_evidence(
            packet(a.serialize_packet(decoded, policy=policy), policy=policy)
        )
        == decoded
    )


def test_mic_e_grid_vector_preserves_all_captured_text():
    row = next(row for row in rows() if row["id"] == "MIC-265")
    source = row["source_expected"]
    original = packet(row["packet"].encode("latin1"))
    assert original.payload.device_code == source["mic_e"]["type_marker"]
    assert original.payload.comment == (
        source["grid_locator"]
        + source["grid_symbol"]["table_id_raw"]
        + source["grid_symbol"]["code"]
        + source["comment"]
    )
    assert row["expected"]["payload"]["device_code"] == original.payload.device_code
    assert row["expected"]["payload"]["comment"] == original.payload.comment
    assert a.serialize_packet(without_evidence(original)) == row["packet"].encode(
        "latin1"
    )


def test_mic_e_device_code_cannot_contain_a_grid():
    original = packet(MIC_E + b">IO91SX/G Ready")
    invalid = dataclasses.replace(
        original,
        payload=dataclasses.replace(
            original.payload, device_code=">IO91SX/G", comment=" Ready"
        ),
    )
    assert [d.path for d in a.check_packet(invalid)] == ["$.payload.device_code"]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(invalid)


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


WX = b"N0CALL>APRS:_12032359c000s000g000t033"


@pytest.mark.parametrize(
    ("tail", "field", "value", "unit"),
    [
        (b"X123", "radiation", 12000, "nSv/h"),  # 12 x 10^3 nanosieverts/hour
        (b"X100", "radiation", 10, "nSv/h"),
        (b"X...", "radiation", None, "nSv/h"),
        (b"V128", "battery_voltage", 12.8, "volts"),
        (b"V...", "battery_voltage", None, "volts"),
        (b"F0123", "water_height", 12.3, "feet"),  # APRS 1.2: tenths of a foot
        (b"F-042", "water_height", -4.2, "feet"),
        (b"F....", "water_height", None, "feet"),
        (b"F20.1", "water_height", 20.1, "feet"),  # APRS 1.1: decimal feet
        (b"f-1.2", "water_height", -1.2, "meters"),
    ],
)
def test_aprs_1_2_weather_fields(tail, field, value, unit):
    # aprs.org/aprs12/weather-new.txt; X and V are no longer read as codes.
    policy = a.APRS_IS(extensions={*a.APRS_IS().extensions, "water_height_tenths"})
    decoded = packet(WX + tail, policy=policy)
    reading = getattr(decoded.payload, field)
    if field == "water_height":
        reading = reading.measurement
    assert (reading.value, reading.unit) == (value, unit)
    assert decoded.payload.software_code is None
    assert decoded.diagnostics == ()
    assert packet(
        a.serialize_packet(without_evidence(decoded), policy=policy), policy=policy
    ) == without_evidence(decoded)


def test_weather_codes_still_follow_new_fields():
    decoded = packet(WX + b"X123V128XRSW")
    w = decoded.payload
    assert (w.radiation.value, w.battery_voltage.value) == (12000, 12.8)
    assert (w.software_code, w.device_code) == ("X", "RSW")


@pytest.mark.parametrize(
    "prefix", [WX, b"N0CALL>APRS:!4903.50N/07201.75W_220/004g005t077"]
)
@pytest.mark.parametrize("tag", [b"F", b"f"])
@pytest.mark.parametrize(
    "number",
    [
        b"0.0",
        b"999.0",
        b"1000.0",
        b"10000.0",
        b"-100.0",
        b"-1000.0",
        b"0.0000001",
        b"1234.56789",
        b"1000000.0",
    ],
)
def test_water_height_encoding_preserves_decimal_measurements(prefix, tag, number):
    original = without_evidence(packet(prefix + tag + number))
    assert a.check_packet(original) == ()
    wire = a.serialize_packet(original)
    assert wire == prefix + tag + number
    decoded = without_evidence(packet(wire))
    assert decoded == original
    assert a.serialize_packet(decoded) == wire


def test_new_weather_fields_are_checked_before_sending():
    w = packet(WX).payload
    odd = dataclasses.replace(w, radiation=a.Measurement(123, "nSv/h"))
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(a.Packet(a.Header("N0CALL", "APRS"), odd))
    hidden = dataclasses.replace(w, comment="X123 hot")
    assert [
        d.message for d in a.check_packet(a.Packet(a.Header("N0CALL", "APRS"), hidden))
    ] == ["comment would be read back as weather fields"]


@pytest.mark.parametrize(
    ("information", "analog", "digital"),
    [
        (b"T#001,42", (42.0,), ()),
        (b"T#1,1,,3,,5", (1.0, None, 3.0, None, 5.0), ()),
        (b"T#005,001,002,003,004,00000000", (1.0, 2.0, 3.0, 4.0), (False,) * 8),
    ],
)
def test_short_telemetry_is_a_nonconforming_packet(information, analog, digital):
    decoded = packet(b"N0CALL>APRS:" + information)
    assert (decoded.payload.analog, decoded.payload.digital) == (analog, digital)
    assert any(d.code == "nonconforming" for d in decoded.diagnostics)
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(decoded)


@pytest.mark.parametrize("value", [b"f", b"-", b"-1.", b"inf", b"nan", b"1e5"])
def test_telemetry_channels_are_plain_decimals(value):
    raw = b"N0CALL>APRS:T#001,1," + value + b",3,4,5,00000000"
    assert isinstance(a.parse_packet(raw), a.Malformed)


def test_invalid_object_timestamp_keeps_recovered_fields():
    result = a.parse_packet(b"N0CALL>APRS:;TestObj  *000000z4903.50N/07201.75W-Test")
    assert isinstance(result, a.Malformed)
    recovered = result.recovered["payload"]
    assert recovered["type"] == "object"
    assert (recovered["name"], recovered["alive"], recovered["comment"]) == (
        "TestObj",
        True,
        "Test",
    )
    assert recovered["latitude_deg"] == pytest.approx(49.058333333)


@pytest.mark.parametrize("digit", "0123456789")
def test_compressed_numeric_overlay_is_refused_before_sending(digit):
    p = a.Packet(
        a.Header("N0CALL", "APRS"),
        a.Position(
            49, -72, a.Symbol(digit, ">"), compression=a.Compression(ignored=True)
        ),
    )
    assert [d.path for d in a.check_packet(p)] == ["$.payload.symbol.table_id"]
    for send, value in (
        (a.serialize_packet, p),
        (a.validate_packet, p),
        (a.serialize_payload, p.payload),
    ):
        with pytest.raises(a.ConformanceError, match="compressed numeric overlays"):
            send(value)
    # Explicit compressed overlays retain their wire spelling and round-trip.
    compressed = dataclasses.replace(
        p.payload, symbol=a.Symbol(chr(ord("a") + int(digit)), ">")
    )
    assert a.parse_payload(a.serialize_payload(compressed)) == compressed
    uncompressed = dataclasses.replace(p.payload, compression=None)
    assert a.parse_payload(a.serialize_payload(uncompressed)) == uncompressed


@pytest.mark.parametrize("encoding", ["mic_e_hex", "mic_e_binary"])
@pytest.mark.parametrize(
    "channels",
    [(999, 2, 3, 4, 5), (-1, 2, 3, 4, 5), (1.5, 2, 3, 4, 5), (1, None, 3, 4, 5)],
)
def test_invalid_mic_e_channels_produce_findings(encoding, channels):
    original = packet(MIC_E)
    payload = dataclasses.replace(
        original.payload,
        extensions=dataclasses.replace(
            original.payload.extensions,
            telemetry=a.Telemetry(channels, encoding=encoding),
        ),
    )
    p = dataclasses.replace(original, payload=payload)
    index = 1 if channels[1] is None else 0
    findings = a.check_packet(p)
    assert [d.path for d in findings] == [
        f"$.payload.extensions.telemetry.analog[{index}]"
    ]
    for send in (a.serialize_packet, a.validate_packet, a.serialize_tnc2_line):
        with pytest.raises(a.ConformanceError) as caught:
            send(p)
        assert caught.value.diagnostics == findings
    assert a.from_json(a.to_json(p)) == p


@pytest.mark.parametrize(
    "tail,paths",
    [
        (b"c090s010", ["gust", "temperature"]),
        (b"c090s010g020t077s001", ["snow_24h"]),
    ],
)
def test_standalone_weather_has_packet_report_checks(tail, paths):
    p = packet(b"N0CALL>APRS:_10171200" + tail)
    assert [d.path for d in a.check_packet(p)] == [
        "$.payload." + name for name in paths
    ]
    with pytest.raises(a.ConformanceError) as caught:
        a.serialize_payload(p.payload)
    assert [d.path for d in caught.value.diagnostics] == ["$." + name for name in paths]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(p)
    complete = a.parse_payload(b"_10171200c...s...g...t...")
    assert a.parse_payload(a.serialize_payload(complete)) == complete


@pytest.mark.parametrize("destination", ["APRS", "T32UVT", "S32U5T", "S32UV4"])
@pytest.mark.parametrize("nested", [False, True])
def test_mic_e_header_conflicts_are_checked_without_envelope_limits(
    destination, nested
):
    p = dataclasses.replace(packet(MIC_E), header=a.Header("N0CALL", destination))
    if nested:
        p = a.Packet(a.Header("N0GATE", "APRS"), a.ThirdParty(p))
    prefix = "$.payload.packet" if nested else "$"
    for policy in (a.APRS_IS(), a.EnvelopePolicy(".*", ".*", ".*")):
        findings = a.check_packet(p, policy=policy)
        assert [d.path for d in findings] == [prefix + ".header.destination"]
        for send in (a.serialize_packet, a.validate_packet):
            with pytest.raises(a.ConformanceError) as caught:
                send(p, policy=policy)
            assert caught.value.diagnostics == findings


def test_nmea_symbol_requires_matching_header_context():
    p = packet(b"N0CALL-11>APRS:$GPGLL,4916.45,N,12311.12,W,225444,A")
    assert p.payload.symbol == a.Symbol("/", "O")
    assert a.check_packet(p) == ()
    assert packet(a.serialize_packet(p)).payload == p.payload
    with pytest.raises(a.ContextRequiredError, match="NMEA symbol"):
        a.serialize_payload(p.payload)
    changed = dataclasses.replace(p, header=a.Header("N0CALL-9", "APRS"))
    for policy in (a.APRS_IS(), a.EnvelopePolicy(".*", ".*", ".*")):
        findings = a.check_packet(changed, policy=policy)
        assert [d.path for d in findings] == ["$.payload.symbol"]
        with pytest.raises(a.ConformanceError) as caught:
            a.serialize_packet(changed, policy=policy)
        assert caught.value.diagnostics == findings
    # Decoding with the new header is still permissive and derives its symbol.
    assert packet(
        a.serialize_packet(p).replace(b"N0CALL-11", b"N0CALL-9")
    ).payload.symbol == a.Symbol("/", ">")


def _mic_e_packet(**extensions):
    payload = a.MicE(
        33.4277,
        -112.12,
        a.Symbol("/", ">"),
        message="off_duty",
        extensions=a.Extensions(motion=a.Motion(90, 10), **extensions),
    )
    return a.Packet(a.Header("N0CALL", None), payload)


@pytest.mark.parametrize(
    ("altitude", "wire"),
    [
        # The unit decides: whole meters fit the compact field, feet use /A=.
        (a.Altitude(a.Measurement(152, "meters")), b'"5T}'),
        (a.Altitude(a.Measurement(500, "feet")), b"/A=000500"),
        # A form the container cannot carry is replaced, not refused.
        (a.Altitude(a.Measurement(500, "feet"), encoding="compressed"), b"/A=000500"),
    ],
)
def test_mic_e_altitude_form_is_chosen_by_the_library(altitude, wire):
    packet_ = _mic_e_packet(altitude=altitude)
    assert a.check_packet(packet_) == ()
    sent = a.serialize_packet(packet_)
    assert sent.endswith(wire)
    assert packet(sent).payload.extensions.altitude == altitude


@pytest.mark.parametrize(
    ("telemetry", "extra", "wire"),
    [
        (a.Telemetry((1, 2, 3, 4, 5)), (), b"'0102030405"),  # APRS101 hex
        (a.Telemetry((16, 32)), (), b"`1020"),
        # Hex would be read as a type code, so the binary form is used.
        (
            a.Telemetry((1, 2, 3, 4, 5)),
            ("mice_hex_as_device",),
            b"\x1d\x01\x02\x03\x04\x05",
        ),
        # A sequence or wider values need base91 comment telemetry.
        (a.Telemetry((1, 2, 3), sequence=7), (), b'|!(!"!#!$|'),
    ],
)
def test_mic_e_telemetry_form_is_chosen_by_the_library(telemetry, extra, wire):
    policy = a.APRS_IS(extensions={*a.APRS_IS().extensions, *extra})
    packet_ = _mic_e_packet(telemetry=telemetry)
    assert a.check_packet(packet_, policy=policy) == ()
    sent = a.serialize_packet(packet_, policy=policy)
    assert wire in sent
    decoded = packet(sent, policy=policy).payload.extensions.telemetry
    assert [v for v in decoded.analog if v is not None] == list(telemetry.analog)


def test_position_altitude_form_follows_the_container():
    received = a.Altitude(a.Measurement(100, "meters"), encoding="mic_e")
    plain = a.Position(
        49, -72, a.Symbol("/", "-"), extensions=a.Extensions(altitude=received)
    )
    assert a.serialize_packet(a.Packet(a.Header("N0CALL", "APRS"), plain)).endswith(
        b"/A=000328"
    )
    # A GGA-sourced compressed position carries its altitude in csT.
    gga = a.Compression(fix="current", nmea_source="GGA", origin="software")
    compressed = dataclasses.replace(
        plain,
        compression=gga,
        extensions=a.Extensions(altitude=a.Altitude(a.Measurement(10004, "feet"))),
    )
    sent = a.serialize_packet(a.Packet(a.Header("N0CALL", "APRS"), compressed))
    assert b"/A=" not in sent
    height = packet(sent).payload.extensions.altitude.measurement
    assert height.value == pytest.approx(10004, rel=0.003)


def _weather_report(**changes):
    report = packet(b"N0CALL>APRS:_12032359c000s000g000t033").payload
    return dataclasses.replace(report, **changes)


def _mic_e(**extensions):
    return a.MicE(
        33.4277,
        -112.12,
        a.Symbol("/", ">"),
        message="off_duty",
        extensions=a.Extensions(**extensions),
    )


APRS = a.Header("N0CALL", "APRS")
NO_DESTINATION = a.Header("N0CALL", None)
SEND_REFUSALS = [
    (APRS, a.Status("x", beam=a.Beam(123, 9000)), "$.payload.beam.erp_w"),
    (
        NO_DESTINATION,
        _mic_e(motion=a.Motion(90, 900)),
        "$.payload.extensions.motion.speed_knots",
    ),
    (
        NO_DESTINATION,
        _mic_e(
            motion=a.Motion(90, 10),
            altitude=a.Altitude(a.Measurement(10, "meters"), reference="ellipsoid"),
        ),
        "$.payload.extensions.altitude.reference",
    ),
    (
        APRS,
        a.Position(
            49,
            -72,
            a.Symbol("/", "-"),
            extensions=a.Extensions(
                altitude=a.Altitude(a.Measurement(10, "meters"), reference="MSL")
            ),
        ),
        "$.payload.extensions.altitude.reference",
    ),
    (
        APRS,
        _weather_report(temperature=a.Measurement(1000, "fahrenheit")),
        "$.payload.temperature.value",
    ),
    (
        APRS,
        _weather_report(pressure=a.Measurement(200000, "hPa")),
        "$.payload.pressure.value",
    ),
    (
        APRS,
        _weather_report(
            water_height=a.WaterHeight(
                a.Measurement(1, "feet"), reference_datum="NAVD88"
            )
        ),
        "$.payload.water_height.reference_datum",
    ),
    (APRS, a.Message("W1AW", "Directs= W1AW"), "$.payload.text"),
]


@pytest.mark.parametrize(("header", "payload", "path"), SEND_REFUSALS)
def test_check_packet_predicts_every_send_refusal(header, payload, path):
    composed = a.Packet(header, payload)
    findings = a.check_packet(composed)
    assert [d.path for d in findings] == [path]
    with pytest.raises(a.ConformanceError) as caught:
        a.serialize_packet(composed)
    assert caught.value.diagnostics == findings


@pytest.mark.parametrize(
    ("extensions", "tail"),
    [
        (a.Extensions(motion=a.Motion(88, 10)), None),  # csT carries motion
        (a.Extensions(range=a.Range(20)), None),  # csT carries range
        (a.Extensions(), b"   "),  # nothing for csT: c=space
        (
            a.Extensions(altitude=a.Altitude(a.Measurement(500, "feet"))),
            b"   /A=000500",
        ),
    ],
)
def test_compression_needs_no_wire_fields(extensions, tail):
    position = a.Position(
        49, -72, a.Symbol("/", ">"), compression=a.Compression(), extensions=extensions
    )
    composed = a.Packet(APRS, position)
    assert a.check_packet(composed) == ()
    sent = a.serialize_packet(composed)
    body = sent.partition(b":")[2]
    assert body[:2] == b"!/"
    if tail is not None:
        assert body.endswith(tail)
    else:
        assert body[-3:-1] != b"  "
    # The type byte is wire metadata: equality ignores it.
    assert packet(sent).payload.compression == a.Compression()


def test_gga_compression_keeps_altitude_in_cst():
    gga = a.Compression(nmea_source="GGA")
    height = a.Altitude(a.Measurement(10004, "feet"))
    position = a.Position(
        49,
        -72,
        a.Symbol("/", ">"),
        compression=gga,
        extensions=a.Extensions(altitude=height),
    )
    sent = a.serialize_packet(a.Packet(APRS, position))
    assert b"/A=" not in sent
    received = packet(sent).payload
    assert received.compression.nmea_source == "GGA"
    assert received.extensions.altitude.measurement.value == pytest.approx(
        10004, rel=0.003
    )


@pytest.mark.parametrize(
    ("destination", "symbol"),
    # aprs.org/symbols/symbolsX.txt GPSxyz table, one row from each subgroup.
    [
        ("GPSBB", ("/", "!")),
        ("GPSOB", ("\\", "!")),
        ("GPSP0", ("/", "0")),
        ("GPSA9", ("\\", "9")),
        ("GPSMV", ("/", ">")),
        ("GPSNV3", ("3", ">")),
        ("GPSPC", ("/", "C")),
        ("GPSAC", ("\\", "C")),
        ("GPSHS", ("/", "[")),
        ("GPSDX", ("\\", "`")),
        ("GPSLC", ("/", "c")),
        ("GPSSC", ("\\", "c")),
        ("GPSJ1", ("/", "{")),
        ("GPSQ4", ("\\", "~")),
        ("GPSC30", ("/", ">")),
        ("GPSE12", ("\\", ",")),
    ],
)
def test_nmea_destination_symbols_follow_the_published_table(destination, symbol):
    raw = f"N0CALL>{destination}:$GPGLL,4916.45,N,12311.12,W,225444,A".encode()
    assert packet(raw).payload.symbol == a.Symbol(*symbol)


@pytest.mark.parametrize(
    "symbol", [a.Symbol("/", "C"), a.Symbol("\\", "["), a.Symbol("3", ">")]
)
def test_nmea_destination_is_generated_from_the_symbol(symbol):
    received = packet(b"N0CALL>APRS:$GPGLL,4916.45,N,12311.12,W,225444,A").payload
    nmea = dataclasses.replace(received, symbol=symbol)
    composed = a.Packet(NO_DESTINATION, nmea)
    assert a.check_packet(composed) == ()
    sent = a.serialize_packet(composed)
    assert sent.split(b":")[0].split(b">")[1].startswith(b"GPS")
    assert packet(sent).payload.symbol == symbol
    stale = a.Packet(APRS, nmea)
    assert [d.path for d in a.check_packet(stale)] == ["$.payload.symbol"]
    with pytest.raises(a.ModelError):
        a.Packet(NO_DESTINATION, received)  # Without a symbol, nothing to derive.


def test_coded_fields_take_names():
    offset = 12**2 / 1500  # an exact square-root code
    area = a.Area("filled_box", "gray", offset, offset, intensity="low")
    position = a.Position(1, 2, a.Symbol("\\", "l"), extensions=a.Extensions(area=area))
    sent = a.serialize_packet(a.Packet(APRS, position))
    assert b"l9" in sent and b"15" in sent  # filled box (9), low-intensity gray (15)
    assert packet(sent).payload.extensions.area == area
    storm = a.Storm(
        "tropical_storm",
        predicted=False,
        sustained_wind_knots=60,
        peak_gust_knots=80,
        central_pressure_hpa=990,
        hurricane_radius_nm=0,
        tropical_storm_radius_nm=30,
    )
    stormy = a.Position(
        1,
        2,
        a.Symbol("\\", "@"),
        extensions=a.Extensions(motion=a.Motion(90, 10), storm=storm),
    )
    sent = a.serialize_packet(a.Packet(APRS, stormy))
    assert b"/TS/" in sent
    assert packet(sent).payload.extensions.storm.kind == "tropical_storm"
    csT = a.Compression(fix="current", nmea_source="other", origin="kpc3")
    assert csT.type_value == 32 + 0 + 4  # current fix, other source, KPC3 origin
    rmc = packet(
        b"N0CALL>APRS:$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W"
    ).payload.sentence
    assert (rmc.fix_status, rmc.magnetic_variation_deg) == ("active", -3.1)
    gga = packet(
        b"N0CALL>APRS:$GPGGA,123519,4807.038,N,01131.000,E,2,08,0.9,545.4,M,46.9,M,,"
    ).payload.sentence
    assert gga.fix_quality == "dgps"


def test_timestamp_from_datetime():
    import datetime as dt

    moment = dt.datetime(
        2026, 10, 17, 23, 45, 30, tzinfo=dt.timezone(dt.timedelta(hours=-4))
    )
    assert a.Timestamp.from_datetime(moment) == a.Timestamp.dhm(18, 3, 45)
    assert a.Timestamp.from_datetime(moment, "hms_utc") == a.Timestamp.hms(3, 45, 30)
    assert a.Timestamp.from_datetime(moment, "mdhm_utc") == a.Timestamp.mdhm(
        10, 18, 3, 45
    )
    local = a.Timestamp.from_datetime(moment, "dhm_local")
    assert local == a.Timestamp.dhm(17, 23, 45, local=True)
    with pytest.raises(ValueError):
        a.Timestamp.from_datetime(dt.datetime(2026, 1, 1))  # offset unknown


def test_edited_mic_e_destination_error_says_how_to_fix_it():
    received = packet(b"N0CALL>S32UVT:`(_f\x1e\x1eOj/")
    moved = dataclasses.replace(
        received, payload=dataclasses.replace(received.payload, latitude_deg=40.0)
    )
    (finding,) = a.check_packet(moved)
    assert "leave header.destination out" in finding.message
    regenerated = dataclasses.replace(
        moved, header=dataclasses.replace(moved.header, destination=None)
    )
    assert a.check_packet(regenerated) == ()


@pytest.mark.parametrize(
    ("bearing", "nrq"),
    [
        # 60% hits -> N=5; 20 mi -> R=4 (16 mi); 10 deg -> Q=5 ("under 16 deg").
        (a.Bearing(270, 20, 10, hit_ratio=0.6), b"545"),
        (a.Bearing(270, 4, None, hit_ratio=1), b"820"),  # useless bearing: Q=0
        (a.Bearing(270, 16, 1, manual=True), b"949"),
        (a.Bearing(270), b"000"),  # nothing reported: NRQ is meaningless
    ],
)
def test_df_bearing_takes_plain_values(bearing, nrq):
    # APRS101 p30 (WB2OSZ APRS 1.2 reference): N, R and the Q accuracy table.
    position = a.Position(
        49,
        -72,
        a.Symbol("/", "\\"),
        extensions=a.Extensions(motion=a.Motion(90, 10), bearing=bearing),
    )
    sent = a.serialize_packet(a.Packet(APRS, position))
    assert sent.endswith(b"/270/" + nrq)
    received = packet(sent).payload.extensions.bearing
    assert (received.hits_code, received.range_code, received.quality_code) == tuple(
        int(c) for c in nrq.decode()
    )
    assert received.usable == (nrq[2:] != b"0" and nrq != b"000")
    with pytest.raises(a.ModelError):
        a.Bearing(270, 16, 1, hit_ratio=0.5, manual=True)


@pytest.mark.parametrize(
    "motion,course",
    [
        (a.Motion(None, 0), None),
        (a.Motion(0, 10), 360),
        (a.Motion(0.4, 10), 360),
        (a.Motion(360, 5), 360),
        (a.Motion(90, 10), 90),
    ],
)
def test_course_zero_means_unknown_for_mic_e_and_positions(motion, course):
    symbol = a.Symbol("/", ">")
    for payload in (
        a.MicE(49, -72, symbol, message="en_route"),
        a.Position(49, -72, symbol),
    ):
        value = a.Packet(
            a.Header("N0CALL", None if isinstance(payload, a.MicE) else "APRS"),
            dataclasses.replace(payload, extensions=a.Extensions(motion=motion)),
        )
        if isinstance(payload, a.Position) and course is None:
            continue  # 000/000 is the uncompressed "unavailable" pair.
        assert not a.check_packet(value)
        received = a.parse_packet(a.serialize_packet(value)).payload
        assert received.extensions.motion.course_deg == course
    # Received course code 0 is unknown, not north.
    mic_e = a.parse_packet(b"N0CALL>S32UVT:`(_f\x1c\x1c\x1cj/").payload
    assert mic_e.extensions.motion.course_deg is None
    assert mic_e.extensions.motion.course_code == 0


def test_mic_e_without_a_speed_is_a_finding():
    value = a.Packet(
        a.Header("N0CALL", None),
        a.MicE(
            49,
            -72,
            a.Symbol("/", ">"),
            message="en_route",
            extensions=a.Extensions(motion=a.Motion(90, None)),
        ),
    )
    findings = a.check_packet(value)
    assert [f.path for f in findings] == ["$.payload.extensions.motion.speed_knots"]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(value)
    no_motion = dataclasses.replace(
        value, payload=dataclasses.replace(value.payload, extensions=a.Extensions())
    )
    assert "Motion(None, 0)" in a.check_packet(no_motion)[0].message


@pytest.mark.parametrize("direction", [0, 0.4, 360])
def test_measured_north_wind_is_not_read_back_as_unavailable(direction):
    m = a.Measurement
    weather = a.Weather(
        wind_direction=m(direction, "degrees"),
        wind_speed=m(0, "mph"),
        gust=m(0, "mph"),
        temperature=m(50, "fahrenheit"),
    )
    value = a.Packet(
        a.Header("N0CALL", "APRS"),
        a.Position(
            49, -72, a.Symbol("/", "_"), extensions=a.Extensions(weather=weather)
        ),
    )
    wire = a.serialize_packet(value)
    assert b"_360/000g000t050" in wire
    received = a.parse_packet(wire)
    assert not received.diagnostics
    assert received.payload.extensions.weather.wind_direction.value == 360
    assert received.payload.extensions.weather.wind_speed.value == 0
    assert a.serialize_packet(received) == wire


@pytest.mark.parametrize("table,code", [("/", "_"), ("\\", "_"), ("/", "W")])
@pytest.mark.parametrize("compressed", [False, True])
def test_weather_symbol_course_speed_is_a_finding(table, code, compressed):
    # A weather symbol reads course/speed as wind, so a report without the
    # other required weather fields would come back incomplete.
    value = a.Packet(
        a.Header("N0CALL", "APRS"),
        a.Position(
            49,
            -72,
            a.Symbol(table, code),
            compression=a.Compression() if compressed else None,
            extensions=a.Extensions(motion=a.Motion(90, 10)),
        ),
    )
    findings = a.check_packet(value)
    assert [(f.path, f.message) for f in findings] == [
        ("$.payload.extensions.motion", "would be read back as weather")
    ]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(value)
    # The same motion under an ordinary symbol is fine.
    ordinary = dataclasses.replace(
        value, payload=dataclasses.replace(value.payload, symbol=a.Symbol("/", ">"))
    )
    assert not a.check_packet(ordinary)


def test_nmea_checksum_is_a_plain_choice():
    sentence = a.GLL(a.Coordinates(49, -72), a.UTCTime(12, 30, 0), "active")
    signed = a.Packet(
        a.Header("N0CALL", "APRS"), a.NMEA(sentence, a.NMEAMetadata("GP"))
    )
    wire = a.serialize_packet(signed)
    assert wire.endswith(b"*30")
    received = a.parse_packet(wire)
    meta = received.payload.metadata
    assert (meta.checksum, meta.checksum_valid, meta.checksum_supplied) == (
        True,
        True,
        "30",
    )
    # Received checksum facts are metadata: the parsed model equals the composed one.
    assert received.payload.metadata == signed.payload.metadata
    assert a.serialize_packet(received) == wire
    unsigned = dataclasses.replace(
        signed.payload, metadata=a.NMEAMetadata("GP", checksum=False)
    )
    assert b"*" not in a.serialize_payload(unsigned)
    assert a.parse_payload(a.serialize_payload(unsigned)).metadata.checksum is False
    with pytest.raises(a.ModelError):
        dataclasses.replace(unsigned, comment="hello")


@pytest.mark.parametrize(
    "codes,comment",
    [({"software_code": "b", "device_code": "1234"}, ""), ({}, "r00 rain")],
)
def test_weather_tail_that_reads_as_a_broken_field_is_a_finding(codes, comment):
    m = a.Measurement
    weather = a.Weather(
        wind_direction=m(90, "degrees"),
        wind_speed=m(5, "mph"),
        gust=m(5, "mph"),
        temperature=m(50, "fahrenheit"),
        timestamp=a.Timestamp.mdhm(10, 9, 5, 56),
        comment=comment,
        **codes,
    )
    value = a.Packet(a.Header("N0CALL", "APRS"), weather)
    path = "$.payload.software_code" if codes else "$.payload.comment"
    assert [f.path for f in a.check_packet(value)] == [path]
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(value)
    # A plain-text comment after a field letter is not a broken field.
    home = dataclasses.replace(weather, software_code=None, device_code=None)
    home = dataclasses.replace(home, comment="home station")
    received = a.parse_packet(
        a.serialize_packet(dataclasses.replace(value, payload=home))
    )
    assert not received.diagnostics and received.payload.comment == "home station"


@pytest.mark.parametrize(
    "latitude,longitude,fields",
    [
        (49, -72, b"4900.00,N,07200.00,W"),
        (51, -1, b"5100.00,N,00100.00,W"),
        (49 + 3.5 / 60, -(72 + 1.75 / 60), b"4903.50,N,07201.75,W"),
        (48.1173, 11.516666666, b"4807.038,N,01131.00,E"),
    ],
)
def test_nmea_coordinates_keep_a_decimal_point(latitude, longitude, fields):
    sentence = a.GLL(a.Coordinates(latitude, longitude), a.UTCTime(1, 2, 3), "active")
    wire = a.serialize_payload(a.NMEA(sentence, a.NMEAMetadata("GP")))
    assert fields in wire
    decoded = a.parse_payload(wire).sentence.coordinates
    assert decoded.latitude_deg == pytest.approx(latitude, abs=1e-9)
    assert decoded.longitude_deg == pytest.approx(longitude, abs=1e-9)


@pytest.mark.parametrize(
    "precedence,test,wire",
    [
        ("routine", False, "R"),
        ("welfare", False, "W"),
        ("priority", True, "TEST P"),
        ("emergency", False, "EMERGENCY"),
    ],
)
def test_nts_precedence_takes_names(precedence, test, wire):
    header = a.NTSHeader(
        number="12",
        precedence=precedence,
        test=test,
        originator="N0CALL",
        check="5",
        place="REDMOND WA",
        date="OCT 15",
    )
    value = a.Packet(
        a.Header("N0CALL", "APRS"), a.Radiogram("W1AW", header, message_id="001")
    )
    encoded = a.serialize_packet(value)
    assert f"N#\\12\\{wire}\\\\N0CALL".encode() in encoded
    assert a.parse_packet(encoded).payload == value.payload
    with pytest.raises(a.ModelError):
        dataclasses.replace(header, precedence="R")
    bad = encoded.replace(f"\\{wire}\\".encode(), b"\\X\\")
    assert isinstance(a.parse_packet(bad), a.Malformed)


def test_void_nmea_fix_is_not_a_diagnostic():
    received = a.parse_packet(b"N0CALL>APRS:$GPRMC,041518,V,,,,,,,230309,,*33")
    assert isinstance(received, a.Packet) and not received.diagnostics
    assert received.payload.position_usable is False
    assert a.serialize_packet(received) == received.original_wire


def test_altitude_encoding_is_keyword_only():
    with pytest.raises(TypeError):
        a.Altitude(a.Measurement(1, "feet"), "mic_e")  # type: ignore[misc]
    assert a.Altitude(a.Measurement(1, "feet"), encoding="mic_e").encoding == "mic_e"


@pytest.mark.parametrize(
    "wire,device",
    [
        (b'N0CALL>T2SP0W:`c_Vm6hk/`"4F}_%', "`_%"),  # Yaesu FTM-400DR
        (b"N0CALL>T2SP0W:`c_Vm6hk/'Hello|4", "'|4"),  # Byonics TinyTrack4
    ],
)
def test_strict_mic_e_keeps_position_when_status_is_not_hex(wire, device):
    strict = a.parse_packet(wire, policy=a.APRS_IS(extensions=()))
    assert isinstance(strict, a.Packet) and isinstance(strict.payload, a.MicE)
    assert strict.payload.extensions.motion is not None
    assert strict.payload.device_code is None
    assert strict.payload.comment == wire.split(b"k/", 1)[1].decode()
    assert [(d.code, d.path) for d in strict.diagnostics] == [
        ("nonconforming", "$.payload.comment")
    ]
    assert a.check_packet(strict, policy=a.APRS_IS(extensions=()))
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(strict, policy=a.APRS_IS(extensions=()))
    # The default policy reads the same text as an APRS 1.2 type code.
    default = a.parse_packet(wire)
    assert not default.diagnostics and default.payload.device_code == device
    assert (strict.payload.latitude_deg, strict.payload.longitude_deg) == (
        default.payload.latitude_deg,
        default.payload.longitude_deg,
    )
