# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Executable construction examples for every public payload and field category."""

import hamkit.aprs as a


def field_examples() -> tuple[object, ...]:
    coordinates = a.Coordinates(49, -72)
    bounds = a.Extent((49, 50), (-73, -72))
    grid = a.Grid("IO91SX", bounds, coordinates)
    measurement = a.Measurement(None, "mph", b"...")
    return (
        measurement,
        a.Timestamp("mdhm_utc", 12, 30, day=17, month=10),
        a.Location(49, -72),
        coordinates,
        bounds,
        a.Ambiguity(4, bounds),
        a.Symbol("a", ">"),
        grid,
        a.Motion(360, 12, 360, 12, b"360/012"),
        a.Altitude(a.Measurement(123, "meters"), "mic_e"),
        a.Range(12),
        a.PHG(25, 80, 3),
        a.Signal(5, 80, 3),
        a.Bearing(120, 3, 2, 7),
        a.Compression(0, "old", "other", 0),
        a.DAO("W", 1, 2, "decimal"),
        a.Area(0, 3, 10, 10),
        a.Signpost(b"55"),
        a.WaterHeight(a.Measurement(20.1, "feet")),
        a.Weather(
            wind_speed=measurement, humidity=a.Measurement(100, "percent", b"00")
        ),
        a.Storm("HC", False, 80, 100, 990, 20, 50),
        a.Telemetry((1, None, 3), (True, None), "MIC", "mic_e_hex"),
        a.Extensions(weather=a.Weather(temperature=a.Measurement(32, "fahrenheit"))),
        a.Beam(90, 100),
        a.ReplyAck("01", "02"),
        a.Parameters(("Temperature", None, "Voltage")),
        a.Units(("deg.C", None, "V")),
        a.Calibration(0, 1, 0),
        a.Equations((a.Calibration(0, 1, 0), None)),
        a.Bits((True,) * 8, b"Project"),
        a.NTSHeader("12", "R", "HXA", "N0CALL", "5", "REDMOND WA", "1800", "OCT 15"),
        a.Address(("ADAM", "123 MAIN ST", "REDMOND WA", "98052")),
        a.Phone("5550100"),
        a.Text(1, b"Hello"),
        a.Signature(b"N0CALL"),
        a.Routing("W1AW", "151800Z", "N0CALL", "151805Z"),
        a.Footprint(coordinates, 20),
        a.Capability("MSG_CNT", b"43"),
        a.NMEAMetadata(checksum_supplied="00", checksum_valid=False),
        a.GGA(b"123000", coordinates, 0, altitude_msl_m=12, geoid_separation_m=3),
        a.GLL(coordinates, b"123000", "V"),
        a.RMC(b"123000", b"171026", "A", coordinates, 12, 90),
        a.VTG(90, 89, 10, 18.52),
        a.WPL(coordinates, b"HOME"),
        a.DecodeOptions(),
        a.EncodeOptions(),
        a.Hop("WIDE1-1"),
        a.Header("N0CALL", "APRS"),
        a.HeaderSemantics(destination_grid=grid),
        a.DirectStations(("W1AW",)),
        a.HeardStation("W1AW", (1, None, 3)),
        a.Trace(a.Header("N0CALL", "APRS")),
        a.Diagnostic("unsupported", "codec pending"),
        a.Packet(a.Header("N0CALL", "APRS"), a.Status()),
        a.EncodedPacketFields(a.Header("N0CALL", "APRS"), b">Ready"),
        a.CodecCapability(a.MicE, "unimplemented", "unimplemented", "header dependent"),
    )


def payload_examples() -> tuple[a.Payload, ...]:
    position = a.Position(49, -72)
    timestamp = a.Timestamp("dhm_utc", 12, 30, day=17)
    return (
        position,
        a.MicE(position.location, (True, False, True)),
        a.Object("AID #2", position.location, timestamp, False, b"AID #2   "),
        a.Item("abc", position.location, False),
        a.Weather(timestamp=a.Timestamp("mdhm_utc", 12, 30, day=17, month=10)),
        a.Telemetry((1, 2, 3, 4, 5), (True,) * 8, 1),
        a.Definition("N0CALL", a.Parameters(("Temperature",))),
        a.Status(b"Ready"),
        a.Message("W1AW", b"Hello", "003"),
        a.Acknowledgment("W1AW", "003"),
        a.AutoAnswer("W1AW", b"Away", "02"),
        a.Bulletin("1", b"Notice", "WX"),
        a.NWSBulletin("NWS-WARN", b"Storm", "S9JbA"),
        a.Radiogram("W1AW", a.Text(1, b"Hello"), "001"),
        a.Query("APRS", footprint=a.Footprint(a.Coordinates(49, -72), 20)),
        a.Response("W1AW", a.DirectStations(("N0CALL",))),
        a.Capabilities((a.Capability("IGATE"),)),
        a.NMEA(a.GLL(a.Coordinates(49, -72), b"123000", "A")),
        a.ThirdParty(a.Packet(a.Header("W1AW", "APRS"), a.Status(b"Ready"))),
        a.UserDefined(b"Q", b"1", bytes(range(256))),
        a.RawWeather("ultw", b"$ULTW0000"),
        a.Agrelo(123, 4),
        a.Maidenhead(a.Grid("IO91SX")),
        a.LegacyPosition(b"X1J ", position),
        a.Beacon(b"UIDIGI ready"),
        a.Invalid(b"invalid fix"),
        a.Reserved(ord("~"), b"data"),
        a.ExternalExtension("polygon_line", b"raw"),
        a.Opaque(b"~\xff\r\n"),
    )
