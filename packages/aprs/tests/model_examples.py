# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Executable construction examples for every public payload and field category."""

import hamkit.aprs as a

SYMBOL = a.Symbol("/", "-")


def field_examples() -> tuple[object, ...]:
    coordinates = a.Coordinates(49, -72)
    grid = a.Grid("IO91SX")
    measurement = a.Measurement(None, "mph", raw=b"...")
    return (
        a.APRS_IS(),
        measurement,
        a.Timestamp.mdhm(10, 17, 12, 30),
        coordinates,
        a.Extent((49, 50), (-73, -72)),
        a.Symbol("a", ">"),
        grid,
        a.Motion(360, 12, course_code=360, speed_code=12, raw=b"360/012"),
        a.Altitude(a.Measurement(123, "meters"), "mic_e"),
        a.Range(12),
        a.PHG(25, 80, 3),
        a.Signal(5, 80, 3),
        a.Bearing(120, 3, 4, 7),
        a.Compression(fix="old", nmea_source="other", origin_code=0),
        a.DAO("W", encoding="decimal"),
        a.Area(0, 3, 100 / 1500, 100 / 1500),
        a.Signpost("55"),
        a.WaterHeight(a.Measurement(20.1, "feet")),
        a.Weather(
            wind_speed=measurement,
            humidity=a.Measurement(100, "percent", raw=b"00"),
        ),
        a.Storm(
            "HC",
            predicted=False,
            sustained_wind_knots=80,
            peak_gust_knots=100,
            central_pressure_hpa=990,
            hurricane_radius_nm=20,
            tropical_storm_radius_nm=50,
        ),
        a.Telemetry((1, 3), encoding="mic_e_hex"),
        a.Extensions(weather=a.Weather(temperature=a.Measurement(32, "fahrenheit"))),
        a.Beam(90, 100),
        a.TelemetryParameters(("Temp", None, "Volts")),
        a.TelemetryUnits(("deg.C", None, "V")),
        a.Calibration(0, 1, 0),
        a.TelemetryEquations((a.Calibration(0, 1, 0), None)),
        a.TelemetryBits((True,) * 8, project_title="Project"),
        a.NTSHeader(
            number="12",
            precedence="R",
            originator="N0CALL",
            check="5",
            place="REDMOND WA",
            date="OCT 15",
            handling="HXA",
            time="1800",
        ),
        a.NTSAddress(("ADAM", "123 MAIN ST", "REDMOND WA", "98052")),
        a.NTSPhone("5550100"),
        a.NTSText(1, "Hello"),
        a.NTSSignature("N0CALL"),
        a.NTSRouting(
            received_from="W1AW",
            received_at="151800Z",
            sent_to="N0CALL",
            sent_at="151805Z",
        ),
        a.Footprint(coordinates, 20),
        a.Capability("MSG_CNT", "43"),
        a.UTCTime(12, 30, 0.25),
        a.NMEADate(17, 10, 26),
        a.NMEAMetadata("GP", checksum_supplied="00", checksum_valid=False),
        a.GGA(
            a.UTCTime(12, 30, 0),
            coordinates,
            0,
            altitude_msl=a.Measurement(12, "meters"),
            geoid_separation=a.Measurement(3, "meters"),
        ),
        a.GLL(coordinates, a.UTCTime(12, 30, 0), "V"),
        a.RMC(
            a.UTCTime(12, 30, 0),
            a.NMEADate(17, 10, 26),
            "A",
            coordinates,
            speed_knots=12,
            course_deg=90,
        ),
        a.VTG(
            course_true_deg=90,
            course_magnetic_deg=89,
            speed_knots=10,
            speed_kmh_reported=18.52,
        ),
        a.WPL(coordinates, "HOME"),
        a.Hop("WIDE1-1"),
        a.Header("N0CALL", "APRS"),
        a.DirectStations(("W1AW",)),
        a.HeardStation("W1AW", (1, None, 3, 0, 0, 0, 0, 0)),
        a.Trace(a.Header("N0CALL", "APRS")),
        a.Diagnostic("unsupported", "codec pending"),
        a.Malformed(
            b"N0CALL>APRS:!4903.50N",
            (
                a.Diagnostic(
                    "malformed", "missing longitude", "$.payload.longitude_deg"
                ),
            ),
            {
                "type": "packet",
                "header": {"source": "N0CALL", "destination": "APRS"},
                "payload": {"type": "position", "latitude_deg": 49.05833333333333},
            },
        ),
        a.Packet(
            a.Header("N0CALL", "APRS"),
            a.Status("Caf\xe9"),
            diagnostics=(
                a.Diagnostic(
                    "nonconforming",
                    "text is not valid UTF-8; decoded as Latin-1",
                    "$.payload.text",
                ),
            ),
        ),
        a.CodecSupport(a.MicE, "unimplemented", "unimplemented", "header dependent"),
    )


def payload_examples() -> tuple[a.Payload, ...]:
    position = a.Position(49, -72, SYMBOL)
    timestamp = a.Timestamp.dhm(17, 12, 30)
    return (
        position,
        a.MicE(
            49,
            -72,
            a.Symbol("/", ">"),
            message="en_route",
            extensions=a.Extensions(motion=a.Motion(90, 10)),
        ),
        a.Object("AID #2", 49, -72, SYMBOL, timestamp=timestamp, alive=False),
        a.Item("abc", 49, -72, SYMBOL, alive=False),
        a.Weather(
            wind_direction=a.Measurement(None, "degrees"),
            wind_speed=a.Measurement(None, "mph"),
            gust=a.Measurement(None, "mph"),
            temperature=a.Measurement(None, "fahrenheit"),
            timestamp=a.Timestamp.mdhm(10, 17, 12, 30),
        ),
        a.Telemetry((1, 2, 3, 4, 5), (True,) * 8, sequence=1),
        a.TelemetryDefinition("N0CALL", a.TelemetryParameters(("Temp",))),
        a.Status("Ready"),
        a.Message("W1AW", "Hello", message_id="003"),
        a.Acknowledgment("W1AW", "003"),
        a.AutoAnswer("W1AW", "Away", previous_ack="02"),
        a.Bulletin("1", "Notice", group="WX"),
        a.NWSBulletin("NWS-WARN", "Storm", reference_id="S9JbA"),
        a.Radiogram("W1AW", a.NTSText(1, "Hello"), message_id="001"),
        a.Query("APRS", footprint=a.Footprint(a.Coordinates(49, -72), 20)),
        a.Response("W1AW", a.DirectStations(("N0CALL",))),
        a.Capabilities((a.Capability("IGATE"),)),
        a.NMEA(
            a.GLL(a.Coordinates(49, -72), a.UTCTime(12, 30, 0), "A"),
            a.NMEAMetadata("GP"),
        ),
        a.ThirdParty(a.Packet(a.Header("W1AW", "APRS"), a.Status("Ready"))),
        a.UserDefined(b"Q", b"1", bytes(range(256))),
        a.RawWeather("ultw", b"$ULTW0000"),
        a.Agrelo(123, 4),
        a.Maidenhead(a.Grid("IO91SX")),
        a.LegacyPosition(b"X1J ", position),
        a.Beacon("UIDIGI ready"),
        a.Invalid(b"invalid fix"),
        a.Reserved(ord("&"), b"data"),
        a.ExternalExtension("polygon_line", b"raw"),
        a.Opaque(b"~\xff\r\n"),
    )
