# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Independent anchors and edit/JSON round trips for semantic field construction."""
import math
from dataclasses import replace

import pytest

from hamkit import aprs as a

SYMBOL = a.Symbol("/", ">")


def packet(payload):
    return a.Packet(
        a.Header("N0CALL", None if isinstance(payload, a.MicE) else "APRS"), payload
    )


def send(payload):
    value = packet(payload)
    a.validate_packet(value)
    assert not a.check_packet(value)
    wire = a.serialize_packet(value)
    assert wire == a.serialize_packet(a.from_json(a.to_json(value)))
    parsed = a.parse_packet(wire)
    assert isinstance(parsed, a.Packet)
    return wire, parsed.payload


@pytest.mark.parametrize(
    "encoding,pair,lat_extra,lon_extra",
    [
        ("high", b"!W23!", 0.002, 0.003),
        ("highest", b"!wAb!", 32 / 9100, 65 / 9100),
    ],
)
@pytest.mark.parametrize("sign", [-1, 1])
def test_dao_spec_anchors_and_edit(encoding, pair, lat_extra, lon_extra, sign):
    p = a.Position(
        sign * (49 + (3.5 + lat_extra) / 60),
        -sign * (72 + (1.75 + lon_extra) / 60),
        SYMBOL,
        extensions=a.Extensions(dao=a.DAO(precision=encoding)),
    )
    wire, decoded = send(p)
    assert pair in wire
    assert decoded.latitude_deg == pytest.approx(p.latitude_deg, abs=1e-10)
    assert decoded.longitude_deg == pytest.approx(p.longitude_deg, abs=1e-10)
    assert decoded.extensions.dao.precision == encoding
    # Parsed extension evidence cannot override edited semantic coordinates.
    changed = replace(decoded, latitude_deg=50, longitude_deg=-73)
    rewritten, result = send(changed)
    assert (b"!W00!" if encoding == "high" else b"!w!!!") in rewritten
    assert (result.latitude_deg, result.longitude_deg) == (50, -73)


@pytest.mark.parametrize("kind", [a.Position, a.MicE])
@pytest.mark.parametrize("encoding", ["high", "highest"])
@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (0.0, -0.0),
        (-12.99999999, 99.99999999),
        (89.99999999, -179.99999),
        (47.75234, -122.15987),
    ],
)
def test_dao_rounding_carries_and_semantic_roundtrip(
    kind, encoding, latitude, longitude
):
    extra = {"motion": a.Motion(90, 10)} if kind is a.MicE else {}
    p = kind(
        latitude,
        longitude,
        SYMBOL,
        **({"message": "off_duty"} if kind is a.MicE else {}),
        extensions=a.Extensions(dao=a.DAO(precision=encoding), **extra),
    )
    _, decoded = send(p)
    tolerance = 1 / (120000 if encoding == "high" else 1092000)
    assert abs(decoded.latitude_deg - latitude) <= tolerance + 1e-12
    assert abs(decoded.longitude_deg - longitude) <= tolerance + 1e-12
    assert math.copysign(1, decoded.longitude_deg) == math.copysign(1, longitude)
    assert a.serialize_packet(packet(decoded)) == a.serialize_packet(packet(p))


def test_dao_datum_only_policy_and_privacy():
    p = a.Position(
        49, -72, SYMBOL, ambiguity=2, extensions=a.Extensions(dao=a.DAO("N"))
    )
    assert b"!N  !" in send(p)[0]
    refined = replace(p, extensions=a.Extensions(dao=a.DAO(precision="high")))
    for v in (
        refined,
        replace(refined, ambiguity=0, compression=a.Compression(ignored=True)),
    ):
        assert a.check_packet(packet(v))
        with pytest.raises(a.ConformanceError):
            a.serialize_packet(packet(v))
    enabled = replace(refined, ambiguity=0)
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(packet(enabled), policy=a.RF(extensions=()))
    wire = b"N0CALL>APRS:!4903.  N/07201.  W>!W23!"
    received = a.parse_packet(wire)
    assert isinstance(received, a.Packet) and received.diagnostics
    assert received.payload.latitude_deg == pytest.approx(49 + 3.5 / 60)
    assert received.payload.extensions.dao.raw == b"!W23!"
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(received)
    assert (
        a.parse_packet(
            b"N0CALL>APRS:!4903.50N/07201.75W>!W23!", policy=a.RF(extensions=())
        ).payload.comment
        == "!W23!"
    )


@pytest.mark.parametrize("encoding", ["feet_extension", "compressed", "mic_e", "nmea"])
def test_altitude_equivalent_units(encoding):
    def model(unit, value):
        reading = a.Measurement(value, unit)
        if encoding == "nmea":
            return a.NMEA(
                a.GGA(
                    a.UTCTime(12, 30, 0),
                    a.Coordinates(49, -72),
                    "gps",
                    altitude_msl=reading,
                    geoid_separation=a.Measurement(-10, "feet"),
                ),
                a.NMEAMetadata("GP"),
            )
        e = a.Extensions(altitude=a.Altitude(reading, encoding=encoding))
        if encoding == "mic_e":
            return a.MicE(
                49,
                -72,
                SYMBOL,
                message="off_duty",
                extensions=replace(e, motion=a.Motion(90, 10)),
            )
        return a.Position(
            49,
            -72,
            SYMBOL,
            extensions=e,
            compression=a.Compression(
                fix="current", nmea_source="GGA", origin="compressed"
            )
            if encoding == "compressed"
            else None,
        )

    feet, metric = model("feet", 200), model("meters", 60.96)
    first, decoded = send(feet)
    assert first == send(metric)[0]
    if encoding == "feet_extension":
        assert b"/A=000200" in first
    elif encoding == "mic_e":
        assert decoded.extensions.altitude.measurement == a.Measurement(61, "meters")
    elif encoding == "nmea":
        assert b",60.96,M,-3.048,M," in first
        assert decoded.sentence.altitude_msl == a.Measurement(60.96, "meters")
    else:
        assert decoded.extensions.altitude.measurement.value == pytest.approx(
            200, rel=0.0011
        )


@pytest.mark.parametrize(
    "encoding,value",
    [
        ("feet_extension", 1e7),
        ("feet_extension", -1e6),
        ("compressed", 0),
        ("compressed", 0.1),
        ("compressed", 1e10),
        ("mic_e", -10001),
        ("mic_e", 743571),
    ],
)
def test_altitude_range_checks_use_converted_units(encoding, value):
    unit = "meters" if encoding == "mic_e" else "feet"
    e = a.Extensions(altitude=a.Altitude(a.Measurement(value, unit), encoding=encoding))
    if encoding == "mic_e":
        p = a.MicE(
            49,
            -72,
            SYMBOL,
            message="off_duty",
            extensions=replace(e, motion=a.Motion(90, 10)),
        )
    else:
        p = a.Position(
            49,
            -72,
            SYMBOL,
            extensions=e,
            compression=a.Compression(
                fix="current", nmea_source="GGA", origin="compressed"
            )
            if encoding == "compressed"
            else None,
        )
    for measurement in (
        a.Measurement(value, unit),
        a.Measurement(
            value * 0.3048 if unit == "feet" else value / 0.3048,
            "meters" if unit == "feet" else "feet",
        ),
    ):
        v = replace(
            p,
            extensions=replace(
                p.extensions, altitude=replace(e.altitude, measurement=measurement)
            ),
        )
        assert a.check_packet(packet(v))
        with pytest.raises(a.ConformanceError):
            a.serialize_packet(packet(v))


@pytest.mark.parametrize("year", range(100))
def test_nmea_century_is_never_invented(year):
    p = a.NMEA(
        a.RMC(
            a.UTCTime(1, 2, 3.125),
            a.NMEADate(28, 2, year),
            "active",
            a.Coordinates(49, -72),
        ),
        a.NMEAMetadata("GP", checksum_supplied="00"),
    )
    wire, decoded = send(p)
    assert f",2802{year:02d},".encode() in wire
    assert b",010203.125," in wire
    assert decoded.sentence.date == p.sentence.date
    assert decoded.sentence.time_utc == p.sentence.time_utc
    assert decoded.metadata.checksum_valid is True
    edited = replace(
        decoded,
        sentence=replace(
            decoded.sentence,
            time_utc=a.UTCTime(23, 59, 60.25),
            date=a.NMEADate(31, 12, year),
        ),
    )
    result = send(edited)[1]
    assert result.sentence.date == edited.sentence.date
    assert result.sentence.time_utc.second == 60.25


def test_nmea_missing_and_partial_values_are_preserved():
    missing = a.NMEA(a.RMC(None, None, "void", None), a.NMEAMetadata("GP"))
    assert send(missing)[0] == b"N0CALL>APRS:$GPRMC,,V,,,,,,,,,*31"
    partial = a.parse_packet(b"N0CALL>APRS:$GPRMC,1234,V,,,,,,,2303,,")
    assert isinstance(partial, a.Packet)
    assert partial.payload.sentence.time_utc == a.UTCTime(12, 34)
    assert partial.payload.sentence.date == a.NMEADate(23, 3)
    assert partial.diagnostics
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(partial)
    assert a.from_json(a.to_json(partial)) == partial
    for date in (a.NMEADate(month=3), a.NMEADate(year_mod_100=99)):
        value = packet(replace(missing, sentence=replace(missing.sentence, date=date)))
        assert a.check_packet(value)
        with pytest.raises(a.ConformanceError):
            a.serialize_packet(value)


@pytest.mark.parametrize("second", [0, -0.0, 0.0000001, 3.25, 59.9999999])
def test_nmea_fractional_seconds_do_not_gain_exponents(second):
    wire, decoded = send(
        a.NMEA(
            a.GLL(a.Coordinates(0, 0), a.UTCTime(1, 2, second), "active"),
            a.NMEAMetadata("GP"),
        )
    )
    assert decoded.sentence.time_utc.second == second
    assert b"e-" not in wire


def test_conversion_overflow_is_a_finding_and_gga_uses_decimal_numbers():
    p = a.Position(
        49,
        -72,
        SYMBOL,
        extensions=a.Extensions(
            altitude=a.Altitude(
                a.Measurement(1e308, "meters"), encoding="feet_extension"
            )
        ),
    )
    assert a.check_packet(packet(p))
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(packet(p))
    for value in (1e-8, -1e-8, 1e20):
        nmea = a.NMEA(
            a.GGA(None, None, "invalid", altitude_msl=a.Measurement(value, "meters")),
            a.NMEAMetadata("GP"),
        )
        wire, decoded = send(nmea)
        assert b"e" not in wire and b"E" not in wire
        assert decoded.sentence.altitude_msl.value == value


@pytest.mark.parametrize(
    "model,values",
    [
        (a.UTCTime, {"hour": 24, "minute": 0}),
        (a.UTCTime, {"hour": 12, "minute": 0, "second": 60}),
        (a.UTCTime, {"hour": 23, "minute": 59, "second": 61}),
        (a.NMEADate, {"day": 29, "month": 2, "year_mod_100": 23}),
        (a.NMEADate, {"day": 31, "month": 4}),
        (a.NMEADate, {"year_mod_100": 2026}),
    ],
)
def test_component_constraints_match_python_and_json(model, values):
    with pytest.raises(a.ModelError):
        model(**values)
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(values, expected_type=model)
