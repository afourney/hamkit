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
        a.GLL(a.Coordinates(49, -72), a.UTCTime(12, 0, 0), "A"),
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
    policy = a.APRS_IS(
        extensions=set(a.APRS_IS().extensions)
        | ({"mice_device_ids"} if device is not None else set())
    )
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
        ("$.payload.device_code", "not a declared Mic-E type code")
    ]
    telemetry = a.Telemetry((1, 2, 3, 4, 5), encoding="mic_e_hex")
    shared = a.Extensions(motion=a.Motion(90, 10), telemetry=telemetry)
    assert findings(device_code="'", extensions=shared) == [
        (
            "$.payload.extensions.telemetry.encoding",
            "hexadecimal telemetry conflicts with mice_device_ids",
        )
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
