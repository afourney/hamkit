# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import unittest
from dataclasses import replace

from hamkit.aprs import (
    RF,
    Acknowledgment,
    Altitude,
    CodecNotImplementedError,
    EnvelopeError,
    EnvelopePolicy,
    Extensions,
    FieldError,
    Header,
    Hop,
    Malformed,
    Measurement,
    Message,
    Motion,
    Opaque,
    Packet,
    Position,
    Status,
    Symbol,
    Timestamp,
    parse_packet,
    parse_payload,
    serialize_packet,
    serialize_payload,
    validate_packet,
)


class PacketTests(unittest.TestCase):
    def test_build_position(self) -> None:
        packet = Packet(
            Header("N0CALL", "APRS", (Hop("WIDE1-1"),)),
            Position(
                49 + 3.5 / 60, -(72 + 1.75 / 60), Symbol("/", "-"), comment="Test"
            ),
        )
        wire = b"N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-Test"
        self.assertEqual(serialize_packet(packet), wire)
        self.assertEqual(parse_packet(wire), packet)
        validate_packet(packet, policy=RF)

    def test_null_position_convention(self) -> None:
        value = parse_payload(b"!0000.00N\\00000.00W.")
        assert isinstance(value, Position)
        self.assertTrue(value.is_null_position)
        self.assertFalse(Position(0, 0, Symbol("/", "-")).is_null_position)

    def test_four_position_dtis(self) -> None:
        for messaging in (False, True):
            for timestamp in (None, Timestamp.dhm(9, 23, 45)):
                value = Position(
                    -49.0,
                    72.0,
                    Symbol("A", ">"),
                    comment=" ✓",
                    messaging=messaging,
                    timestamp=timestamp,
                    extensions=Extensions(
                        motion=Motion(123, 45),
                        altitude=Altitude(Measurement(1000, "feet"), "feet_extension"),
                    ),
                )
                self.assertEqual(parse_payload(serialize_payload(value)), value)

    def test_data_extensions_round_trip(self) -> None:
        for tail in (
            b">088/036 moving",
            b">360/000",
            b">.../...",
            b">000/000",
            b"#PHG5132Radio",
            b"#PHG5:32",
            b"#RNG0050Range",
            b"\\DFS2360",
            b"\\088/036/270/729",
            b"\\000/000/270/000",
            b"-/A=001234 tail",
            b"-/A=-00012",
            b">088/036/A=000100 both",
        ):
            with self.subTest(tail=tail):
                wire = b"N0CALL>APRS:!4903.50N/07201.75W" + tail
                packet = parse_packet(wire, unsupported="raise")
                assert isinstance(packet, Packet)
                self.assertEqual(packet.diagnostics, ())
                self.assertTrue(packet.payload.extensions)  # type: ignore[union-attr]
                self.assertEqual(serialize_packet(packet), wire)

    def test_original_wire_is_archival(self) -> None:
        # Unusual tokens (lowercase, SSID -0) show nothing is normalized; the
        # permissive policy keeps envelope rules out of this archival check.
        loose = EnvelopePolicy(".*", ".*", ".*")
        raw = b"n0call-0>APRS,qAR,igate:>radio: ready > listening"
        packet = parse_packet(raw)
        assert isinstance(packet, Packet)
        self.assertEqual(packet.original_wire, raw)
        self.assertEqual(serialize_packet(packet, policy=loose), raw)
        changed = replace(packet, payload=Status("Changed"))
        self.assertEqual(changed.original_wire, raw)
        self.assertTrue(serialize_packet(changed, policy=loose).endswith(b":>Changed"))

    def test_path_markers(self) -> None:
        packet = parse_packet(b"N0CALL>APRS,D1,D2*,WIDE2-1:>Ready")
        assert isinstance(packet, Packet)
        self.assertEqual(
            packet.header.path, (Hop("D1"), Hop("D2", True), Hop("WIDE2-1"))
        )

    def test_message_and_ack_round_trips(self) -> None:
        for payload in (
            Message("W1AW", ""),
            Message("W1AW", " leading: trailing ", message_id="003"),
            Message("W1AW", "Hello", message_id="1", reply_ack="02"),
            Message("W1AW", "Hello", message_id="1", reply_ack=""),
            Acknowledgment("W1AW", "003"),
            Acknowledgment("W1AW", "Ab9Z0", rejected=True),
            Acknowledgment("W1AW", "01", reply_ack="02"),
            Message("W1AW", "acknowledge this please"),
            Message("W1AW", "braces } are fine"),
            Message("W1AW", "ack01}02", message_id="3"),
        ):
            with self.subTest(payload=payload):
                self.assertEqual(parse_payload(serialize_payload(payload)), payload)
        self.assertEqual(
            serialize_payload(Message("W1AW", "Hello", message_id="003")),
            b":W1AW     :Hello{003",
        )

    def test_status_round_trip(self) -> None:
        for value in (
            Status(""),
            Status("  padded  "),
            Status("Ready", timestamp=Timestamp.dhm(9, 23, 45)),
            Status("1234567 not a timestamp"),
            Status("Grüße"),
        ):
            self.assertEqual(parse_payload(serialize_payload(value)), value)

    def test_unsupported_preserved(self) -> None:
        for information in (
            b"~unknown",
            b"&reserved",
            b"$GPXYZ,unknown",
        ):
            with self.subTest(information=information):
                packet = parse_packet(b"N0CALL>APRS:" + information)
                assert isinstance(packet, Packet)
                self.assertIsInstance(packet.payload, Opaque)
                self.assertEqual(serialize_packet(packet), packet.original_wire)

    def test_bad_envelopes(self) -> None:
        for wire in (
            b"",
            b"N0CALL>APRS",
            b"N0CALL:>x",
            b">APRS:>x",
            b"N0CALL>APRS,:>x",
            b"N0CALL>APRS,D1**:>x",
            b"N0CALL>APRS>>BAD:>x",
            b"N0CALL >APRS:>x",
        ):
            with self.subTest(wire=wire):
                self.assertIsInstance(parse_packet(wire), Malformed)
                with self.assertRaises(EnvelopeError):
                    parse_packet(wire, malformed="raise")

    def test_bad_fields(self) -> None:
        for information in (
            b"",
            b"!9000.01N/07201.75W-",
            b"!4903x50N/07201.75W-",
            b"!4903.50N/18000.01E-",
            b"!4903.50N",
            b":W1AW:Hello",
            b":W1AW     :Hello{",
            b":W1AW     :Hello{123456",
            b"@000000z4903.50N/07201.75W-",
            b">000000zReady",
        ):
            with self.subTest(information=information):
                self.assertIsInstance(parse_payload(information), Malformed)
                with self.assertRaises(FieldError):
                    parse_payload(information, malformed="raise")

    def test_invalid_construction(self) -> None:
        for build in (
            lambda: Message("W1AW", "ack003"),
            lambda: Message("W1AW", "bad{body"),
            lambda: Status("092345zambiguous"),
            lambda: Position(0, 0, Symbol("x", "-")),
        ):
            with self.assertRaises(FieldError):
                build()
        with self.assertRaises(CodecNotImplementedError):
            serialize_payload(Message("BLN0", "Notice"))
