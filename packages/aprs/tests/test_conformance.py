# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""APRS rules a well-formed model can break: reported, and never sent."""

from __future__ import annotations

import unittest
from typing import Any

from hamkit import aprs as a

HEADER = a.Header("N0CALL", "APRS")
SYMBOL = a.Symbol("/", "-")


def findings(payload: Any, policy: a.EnvelopePolicy | None = None) -> set[str]:
    policy = a.APRS_IS() if policy is None else policy
    return {d.path for d in a.check_packet(a.Packet(HEADER, payload), policy=policy)}


def complete_weather(**changes: Any) -> a.Weather:
    values: dict[str, Any] = {
        "wind_direction": a.Measurement(None, "degrees"),
        "wind_speed": a.Measurement(None, "mph"),
        "gust": a.Measurement(None, "mph"),
        "temperature": a.Measurement(None, "fahrenheit"),
        "timestamp": a.Timestamp.mdhm(10, 17, 12, 0),
    }
    values.update(changes)
    return a.Weather(**values)


class SendingTests(unittest.TestCase):
    def test_serialization_refuses_nonconforming_packets(self) -> None:
        packet = a.Packet(HEADER, a.Message("W1AW", "x" * 68, message_id="1"))
        self.assertEqual(
            a.check_packet(packet),
            (a.Diagnostic("nonconforming", "exceeds 67 bytes", "$.payload.text"),),
        )
        for send in (a.serialize_packet, a.validate_packet, a.serialize_tnc2_line):
            with self.subTest(send=send), self.assertRaises(a.ConformanceError) as ctx:
                send(packet)
            self.assertEqual(ctx.exception.diagnostics, a.check_packet(packet))
        with self.assertRaises(a.ConformanceError):
            a.serialize_payload(packet.payload)

    def test_all_findings_are_reported_together(self) -> None:
        packet = a.Packet(
            a.Header("n0call", "APRS", tuple(a.Hop("WIDE") for _ in range(9))),
            a.Status("bad|status" + "x" * 60),
        )
        self.assertEqual(
            {d.path for d in a.check_packet(packet, policy=a.RF())},
            {"$.header.source", "$.header.path", "$.payload.text"},
        )
        self.assertEqual({d.path for d in a.check_packet(packet)}, {"$.payload.text"})

    def test_rf_policy_limits(self) -> None:
        for source in ("N0CALL-16", "TOOLONG", "n0call"):
            packet = a.Packet(a.Header(source, "APRS"), a.Status(""))
            self.assertIsInstance(a.serialize_packet(packet), bytes)
            with self.subTest(source=source), self.assertRaises(a.ConformanceError):
                a.serialize_packet(packet, policy=a.RF())
        hops = tuple(a.Hop("D1") for _ in range(8))
        a.validate_packet(
            a.Packet(a.Header("N0CALL", "APRS", hops), a.Status("")), policy=a.RF()
        )
        with self.assertRaises(a.ConformanceError):
            a.validate_packet(
                a.Packet(a.Header("N0CALL", "APRS", hops * 2), a.Status("")),
                policy=a.RF(),
            )
        large = a.Packet(HEADER, a.UserDefined(b"A", b"B", b"x" * 260))
        self.assertEqual(
            [d.path for d in a.check_packet(large, policy=a.RF())], ["$.payload"]
        )
        self.assertEqual(a.check_packet(large), ())
        with self.assertRaises(a.ConformanceError):
            a.serialize_packet(a.Packet(HEADER, a.Opaque(b"~" * 257)), policy=a.RF())

    def test_rf_header_rules_skip_third_party_inner_headers(self) -> None:
        inner = a.Packet(
            a.Header("w1aw", "APRS", (a.Hop("TCPIP", True),)), a.Status("")
        )
        packet = a.Packet(HEADER, a.ThirdParty(inner))
        self.assertEqual(a.check_packet(packet, policy=a.RF()), ())

    def test_control_characters_are_never_sent(self) -> None:
        for payload in (a.Status("bell\x07"), a.Message("W1AW", "line\nbreak")):
            self.assertEqual(len(findings(payload)), 1)
            with self.assertRaises(a.ConformanceError):
                a.serialize_payload(payload)


class MessageFamilyTests(unittest.TestCase):
    def test_status_size_reserved_and_grid_layout(self) -> None:
        self.assertEqual(findings(a.Status("x" * 62)), set())
        self.assertEqual(findings(a.Status("x" * 63)), {"$.payload.text"})
        self.assertEqual(findings(a.Status("é" * 32)), {"$.payload.text"})
        for char in "|~":
            self.assertEqual(findings(a.Status(char)), {"$.payload.text"})
        grid = a.Grid("IO91")
        self.assertEqual(
            findings(a.Status("No separator", grid=grid, symbol=SYMBOL)),
            {"$.payload.text"},
        )
        self.assertEqual(findings(a.Status(" House", grid=grid, symbol=SYMBOL)), set())

    def test_message_reply_ack_budget(self) -> None:
        self.assertEqual(
            findings(a.Message("W1AW", "Hi", message_id="01", reply_ack="02")), set()
        )
        self.assertEqual(
            findings(a.Message("W1AW", "Hi", message_id="123", reply_ack="45")),
            {"$.payload.reply_ack"},
        )

    def test_bulletin_and_autoanswer_text(self) -> None:
        self.assertEqual(findings(a.Bulletin("1", "~")), {"$.payload.text"})
        self.assertEqual(findings(a.AutoAnswer("W1AW", "x" * 65)), {"$.payload.text"})
        self.assertEqual(
            findings(a.AutoAnswer("W1AW", "", previous_ack="123")),
            {"$.payload.previous_ack"},
        )

    def test_query_context(self) -> None:
        for query, path in (
            (a.Query("APRSD"), "$.payload.addressee"),
            (a.Query("WX", addressee="W1AW"), "$.payload.addressee"),
            (a.Query("APRS", heard_station="W1AW"), "$.payload.heard_station"),
            (a.Query("APRS", arguments=b"opaque"), "$.payload.arguments"),
            (
                a.Query("APRS", footprint=a.Footprint(a.Coordinates(0, 0), 0.5)),
                "$.payload.footprint.radius_miles",
            ),
        ):
            with self.subTest(query=query):
                self.assertEqual(findings(query), {path})
        self.assertEqual(findings(a.Query("CUSTOM", arguments=b"\xff")), set())

    def test_capabilities_and_heard_statistics(self) -> None:
        self.assertEqual(findings(a.Capabilities(())), {"$.payload.tokens"})
        self.assertEqual(
            findings(a.Capabilities((a.Capability("MSG_CNT", "-1"),))),
            {"$.payload.tokens[0].value"},
        )
        self.assertEqual(
            findings(a.Response("W1AW", a.HeardStation("W1AW", (1, None)))),
            {"$.payload.response.counts"},
        )

    def test_nts_records(self) -> None:
        for record, path in (
            (a.NTSText(1, "x" * 65), "$.payload.record.record"),
            (a.NTSSignature(""), "$.payload.record.text"),
            (
                a.NTSHeader(
                    number="0",
                    precedence="R",
                    originator="N0CALL",
                    check="5",
                    place="X",
                    date="OCT 15",
                ),
                "$.payload.record.number",
            ),
        ):
            with self.subTest(record=record):
                self.assertEqual(findings(a.Radiogram("W1AW", record)), {path})
        self.assertEqual(findings(a.Radiogram("W1AW", a.NTSText(1, "x" * 64))), set())

    def test_telemetry_definitions(self) -> None:
        limits = (7, 6, 5, 5, 4, 5, 4, 3, 3, 3, 2, 2, 2)
        full = a.TelemetryParameters(tuple("x" * n for n in limits))
        self.assertEqual(findings(a.TelemetryDefinition("N0CALL", full)), set())
        for i, limit in enumerate(limits):
            values = ["x"] * (i + 1)
            values[i] = "x" * (limit + 1)
            labels = a.TelemetryUnits(tuple(values))
            self.assertEqual(
                findings(a.TelemetryDefinition("N0CALL", labels)),
                {f"$.payload.definition.channels[{i}]"},
            )
        bits = a.TelemetryBits((True,) * 8, project_title="x" * 24)
        self.assertEqual(
            findings(a.TelemetryDefinition("N0CALL", bits)),
            {"$.payload.definition.project_title"},
        )


class PlaceTests(unittest.TestCase):
    def test_comment_and_item_name_limits(self) -> None:
        self.assertEqual(findings(a.Position(1, 2, SYMBOL, comment="x" * 43)), set())
        self.assertEqual(
            findings(a.Position(1, 2, SYMBOL, comment="x" * 44)), {"$.payload.comment"}
        )
        # The budget covers extensions and comment together: 7 + 36 bytes.
        motion = a.Extensions(motion=a.Motion(90, 10))
        self.assertEqual(
            findings(a.Position(1, 2, SYMBOL, comment="x" * 36, extensions=motion)),
            set(),
        )
        self.assertEqual(
            findings(a.Position(1, 2, SYMBOL, comment="x" * 37, extensions=motion)),
            {"$.payload.comment"},
        )
        self.assertEqual(findings(a.Item("ab", 1, 2, SYMBOL)), {"$.payload.name"})

    def test_comment_must_read_back_unchanged(self) -> None:
        for comment in ("088/036 hi", "PHG5132", "x/A=001234", "999/999Hello"):
            with self.subTest(comment=comment):
                position = a.Position(1, 2, SYMBOL, comment=comment)
                self.assertEqual(findings(position), {"$.payload.comment"})
                with self.assertRaises(a.ConformanceError):
                    a.serialize_payload(position)
        self.assertEqual(
            findings(a.Position(1, 2, SYMBOL, comment="hi !W12!")),
            {"$.payload.comment"},
        )

    def test_extension_values_must_be_representable(self) -> None:
        for extensions, path in (
            # Beyond the code ranges, even after rounding.
            (a.Extensions(phg=a.PHG(200, 80, 3)), "phg.power_w"),
            (a.Extensions(phg=a.PHG(25, 5, 3)), "phg.height_haat_ft"),
            (a.Extensions(motion=a.Motion(90, 1000)), "motion.speed_knots"),
            (a.Extensions(motion=a.Motion(90)), "motion.speed_knots"),
            (
                a.Extensions(
                    altitude=a.Altitude(
                        a.Measurement(1000000, "meters"), "feet_extension"
                    )
                ),
                "altitude.measurement.value",
            ),
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    findings(a.Position(1, 2, SYMBOL, extensions=extensions)),
                    {f"$.payload.extensions.{path}"},
                )
        # Values between codes round to the nearest code, like coordinates.
        rounded = a.Position(
            1, 2, SYMBOL, extensions=a.Extensions(motion=a.Motion(88.4, 36.2))
        )
        self.assertEqual(findings(rounded), set())
        self.assertTrue(a.serialize_payload(rounded).endswith(b"-088/036"))
        # 30 W -> 25 W, 75 ft -> 80 ft (log scale), 3.4 dBi -> 3, 10 deg -> north.
        phg = a.PHG(30, 75, 3.4, directivity_deg=10)
        between = a.Position(1, 2, SYMBOL, extensions=a.Extensions(phg=phg))
        self.assertEqual(findings(between), set())
        self.assertTrue(a.serialize_payload(between).endswith(b"PHG5338"))

    def test_motion_encoding_preserves_known_values_and_zero_meaning(self) -> None:
        for motion, symbol in (
            (a.Motion(None, 0), SYMBOL),
            (a.Motion(None, 0.2), SYMBOL),
            (a.Motion(None, None, zero_pair="unavailable"), a.Symbol("/", "\\")),
            (a.Motion(None, 0, zero_pair="fixed"), SYMBOL),
            (a.Motion(90, 10, zero_pair="unavailable"), SYMBOL),
        ):
            with self.subTest(motion=motion, symbol=symbol):
                value = a.Position(1, 2, symbol, extensions=a.Extensions(motion=motion))
                self.assertTrue(findings(value))
                with self.assertRaises(a.ConformanceError):
                    a.serialize_payload(value)
        for motion, symbol in (
            (a.Motion(None, None), SYMBOL),
            (a.Motion(None, None, zero_pair="unavailable"), SYMBOL),
            (a.Motion(None, 0, zero_pair="fixed"), a.Symbol("/", "\\")),
            (a.Motion(360, 0), SYMBOL),
            (a.Motion(None, 1), SYMBOL),
        ):
            with self.subTest(motion=motion, symbol=symbol):
                value = a.Position(1, 2, symbol, extensions=a.Extensions(motion=motion))
                self.assertEqual(a.parse_payload(a.serialize_payload(value)), value)

    def test_phg_rate_roundtrip(self) -> None:
        for rate in (0, 5):
            value = a.Position(
                1,
                2,
                SYMBOL,
                extensions=a.Extensions(phg=a.PHG(25, 80, 3, rate_per_hour=rate)),
            )
            self.assertEqual(a.parse_payload(a.serialize_payload(value)), value)

    def test_fields_without_a_wire_field_are_findings(self) -> None:
        # These values exist in the model but APRS has nowhere to send them, so
        # check_packet reports them and sending refuses with the same finding.
        for extensions, symbol, path in (
            (
                a.Extensions(
                    altitude=a.Altitude(a.Measurement(100, "feet"), reference="MSL")
                ),
                SYMBOL,
                "$.payload.extensions.altitude.reference",
            ),
        ):
            with self.subTest(extensions=extensions):
                value = a.Position(1, 2, symbol, extensions=extensions)
                self.assertEqual(a.from_json(a.to_json(value)), value)
                self.assertEqual(findings(value), {path})
                with self.assertRaises(a.ConformanceError):
                    a.serialize_payload(value)
                with self.assertRaises(a.ConformanceError):
                    a.serialize_packet(a.Packet(HEADER, value), policy=a.RF())

    def test_extension_symbols_and_slots(self) -> None:
        storm = a.Storm(
            "hurricane",
            predicted=False,
            sustained_wind_knots=80,
            peak_gust_knots=100,
            central_pressure_hpa=990,
            hurricane_radius_nm=20,
            tropical_storm_radius_nm=50,
        )
        extensions = a.Extensions(motion=a.Motion(90, 10), storm=storm)
        self.assertEqual(
            findings(a.Position(1, 2, a.Symbol("/", "@"), extensions=extensions)),
            {"$.payload.symbol"},
        )
        self.assertEqual(
            findings(a.Position(1, 2, a.Symbol("\\", "@"), extensions=extensions)),
            set(),
        )
        self.assertEqual(
            findings(
                a.Position(
                    1,
                    2,
                    SYMBOL,
                    extensions=a.Extensions(
                        motion=a.Motion(90, 1), phg=a.PHG(25, 80, 3)
                    ),
                )
            ),
            {"$.payload.extensions.phg"},
        )
        df = a.Symbol("/", "\\")
        self.assertEqual(
            findings(
                a.Position(
                    1,
                    2,
                    df,
                    extensions=a.Extensions(
                        bearing=a.Bearing(90, 16, 4, hit_ratio=1 / 8)
                    ),
                )
            ),
            {"$.payload.extensions.bearing"},
        )
        self.assertEqual(
            findings(
                a.Item(
                    "Sign",
                    1,
                    2,
                    SYMBOL,
                    extensions=a.Extensions(signpost=a.Signpost("55")),
                )
            ),
            {"$.payload.symbol"},
        )

    def test_compressed_layout(self) -> None:
        ignored = a.Compression(ignored=True)
        self.assertEqual(findings(a.Position(1, 2, SYMBOL, compression=ignored)), set())
        self.assertEqual(
            findings(
                a.Position(
                    1,
                    2,
                    SYMBOL,
                    compression=ignored,
                    extensions=a.Extensions(motion=a.Motion(90, 1)),
                )
            ),
            {"$.payload.compression"},
        )
        gga = a.Compression(fix="old", nmea_source="GGA", origin="compressed")
        self.assertIn(
            "$.payload.compression", findings(a.Position(1, 2, SYMBOL, compression=gga))
        )

    def test_mic_e_motion_and_telemetry(self) -> None:
        self.assertEqual(
            findings(a.MicE(1, 2, SYMBOL, message="en_route")),
            {"$.header.destination", "$.payload.extensions.motion"},
        )
        telemetry = a.Telemetry((1, 2), sequence=1, encoding="base91_comment")
        self.assertEqual(
            findings(
                a.MicE(
                    1,
                    2,
                    SYMBOL,
                    message="en_route",
                    extensions=a.Extensions(motion=a.Motion(), telemetry=telemetry),
                )
            ),
            {"$.header.destination"},
        )


class WeatherAndTelemetryTests(unittest.TestCase):
    def test_positionless_weather_report(self) -> None:
        self.assertEqual(findings(complete_weather()), set())
        for field in (
            "timestamp",
            "wind_direction",
            "wind_speed",
            "gust",
            "temperature",
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    findings(complete_weather(**{field: None})), {f"$.payload.{field}"}
                )
        self.assertEqual(
            findings(complete_weather(snow_24h=a.Measurement(1, "inches"))),
            {"$.payload.snow_24h"},
        )

    def test_located_weather_uses_enclosing_time_and_symbol(self) -> None:
        weather = complete_weather(timestamp=None)
        position = a.Position(
            1, 2, a.Symbol("/", "_"), extensions=a.Extensions(weather=weather)
        )
        self.assertEqual(findings(position), set())
        self.assertEqual(
            findings(
                a.Position(
                    1,
                    2,
                    a.Symbol("/", "_"),
                    extensions=a.Extensions(weather=complete_weather()),
                )
            ),
            {"$.payload.extensions.weather.timestamp"},
        )
        self.assertEqual(
            findings(
                a.Position(1, 2, SYMBOL, extensions=a.Extensions(weather=weather))
            ),
            {"$.payload.symbol"},
        )

    def test_reading_ranges_and_station_codes(self) -> None:
        self.assertEqual(
            findings(complete_weather(humidity=a.Measurement(101, "percent"))),
            {"$.payload.humidity.value"},
        )
        self.assertEqual(
            findings(complete_weather(temperature=a.Measurement(-500, "fahrenheit"))),
            {"$.payload.temperature.value"},
        )
        self.assertEqual(
            findings(complete_weather(software_code="XX", device_code="X")),
            {"$.payload.software_code", "$.payload.device_code"},
        )

    def test_telemetry_layouts(self) -> None:
        classic = a.Telemetry((0, 1, 2, 3, 255), (False,) * 8, sequence="MIC")
        self.assertEqual(findings(classic), set())
        for telemetry, path in (
            (a.Telemetry((1, 2, 3)), "$.payload.analog"),
            (a.Telemetry((1,) * 5, (True,) * 8, sequence=1000), "$.payload.sequence"),
            (a.Telemetry((1,) * 5, (True,) * 8), "$.payload.sequence"),
            (a.Telemetry((1000,) * 5, (True,) * 8, sequence=1), "$.payload.analog[0]"),
            # A report is always sent as classic telemetry, whatever its form.
            (a.Telemetry((1, 2), encoding="mic_e_hex"), "$.payload.analog"),
        ):
            with self.subTest(telemetry=telemetry):
                self.assertIn(path, findings(telemetry))
        located = a.Telemetry((8280,), sequence=8280, encoding="base91_comment")
        self.assertEqual(
            findings(
                a.Position(1, 2, SYMBOL, extensions=a.Extensions(telemetry=located))
            ),
            set(),
        )
