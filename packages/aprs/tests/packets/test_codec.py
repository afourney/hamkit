# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import unittest
from dataclasses import replace

from hamkit.aprs import (
    Acknowledgment,
    EnvelopeError,
    FieldError,
    Header,
    Message,
    Opaque,
    Packet,
    PathHop,
    Position,
    Status,
    Symbol,
    Timestamp,
    UnsupportedFormat,
    decode_payload,
    encode_payload,
    parse_packet,
    serialize_packet,
    validate_packet,
)


class PacketTests(unittest.TestCase):
    def test_build_position(self) -> None:
        packet = Packet(
            Header("N0CALL", "APRS", (PathHop("WIDE1-1"),)),
            Position(49 + 3.5 / 60, -(72 + 1.75 / 60), tail=b"Test"),
        )
        wire = b"N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-Test"
        self.assertEqual(serialize_packet(packet), wire)
        self.assertEqual(parse_packet(wire), packet)
        validate_packet(packet, profile="rf")

    def test_null_position_convention(self) -> None:
        value = decode_payload(b"!0000.00N\\00000.00W.")
        self.assertIsInstance(value, Position)
        assert isinstance(value, Position)
        self.assertTrue(value.is_null_position)
        self.assertFalse(Position(0, 0).is_null_position)

    def test_four_position_dtis(self) -> None:
        for messaging in (False, True):
            for timestamp in (None, Timestamp("dhm_utc", 23, 45, day=9)):
                value = Position(
                    -49.0,
                    72.0,
                    Symbol("A", ">"),
                    messaging,
                    timestamp,
                    b"123/045/A=001000\xff",
                )
                self.assertEqual(decode_payload(encode_payload(value)), value)

    def test_original_wire_is_archival(self) -> None:
        raw = b"n0call-0>APRS,qAR,igate:>radio: ready > listening"
        packet = parse_packet(raw)
        self.assertEqual(packet.original_wire, raw)
        self.assertEqual(serialize_packet(packet), raw)
        changed = replace(packet, payload=Status(b"Changed"))
        self.assertEqual(changed.original_wire, raw)
        self.assertTrue(serialize_packet(changed).endswith(b":>Changed"))
        with self.assertRaises(EnvelopeError):
            serialize_packet(packet, profile="rf")

    def test_path_markers(self) -> None:
        packet = parse_packet(b"N0CALL>APRS,D1,D2*,WIDE2-1:>Ready")
        self.assertEqual(
            packet.header.path, (PathHop("D1"), PathHop("D2", True), PathHop("WIDE2-1"))
        )

    def test_message_and_ack_round_trips(self) -> None:
        for payload in (
            Message("W1AW"),
            Message("W1AW", b" leading: trailing ", "003"),
            Acknowledgment("W1AW", "003"),
            Acknowledgment("W1AW", "Ab9Z0", True),
            Message("W1AW", b"acknowledge this please"),
        ):
            with self.subTest(payload=payload):
                self.assertEqual(decode_payload(encode_payload(payload)), payload)
        self.assertEqual(
            encode_payload(Message("W1AW", b"Hello", "003")), b":W1AW     :Hello{003"
        )

    def test_status_round_trip(self) -> None:
        for value in (
            Status(),
            Status(b"  padded  "),
            Status(b"Ready", Timestamp("dhm_utc", 23, 45, day=9)),
            Status(b"1234567 not a timestamp"),
        ):
            self.assertEqual(decode_payload(encode_payload(value)), value)

    def test_unsupported_preserved(self) -> None:
        for information in (
            b"`\x1c\x7f\xff",
            b";object",
            b"T#001,1,2,3,4,5,00000000",
            b"!4903.5 N/07201.7 W-",
            b"!/5L!!<*e7>7P[",
            b":W1AW     :Reply{01}02",
            b":BLN0     :Notice",
            b":NWS-WARN :Warning{123",
            b"}N0CALL>APRS:>inner",
        ):
            with self.subTest(information=information):
                packet = parse_packet(b"N0CALL>APRS:" + information)
                self.assertIsInstance(packet.payload, Opaque)
                self.assertEqual(serialize_packet(packet), packet.original_wire)

    def test_latin1_input(self) -> None:
        self.assertEqual(
            parse_packet("N0CALL>APRS:~\xff").original_wire, b"N0CALL>APRS:~\xff"
        )
        with self.assertRaises(EnvelopeError):
            parse_packet("N0CALL>APRS:>\u2603")

    def test_bad_envelopes(self) -> None:
        for wire in (
            b"",
            b"N0CALL>APRS",
            b"N0CALL:>x",
            b">APRS:>x",
            b"N0CALL>APRS,:>x",
            b"N0CALL>APRS,D1**:>x",
            b"N0CALL>APRS:",
            b"N0CALL>APRS:>x\n",
            b"N0CALL>APRS:>x\r\n",
            b"N0CALL>APRS>BAD:>x",
            b"N0CALL >APRS:>x",
        ):
            with self.subTest(wire=wire), self.assertRaises(EnvelopeError):
                parse_packet(wire)

    def test_bad_fields(self) -> None:
        for information in (
            b"!9000.01N/07201.75W-",
            b"!4903x50N/07201.75W-",
            b"!4903.50N/18000.01E-",
            b"!4903.50N",
            b":W1AW:Hello",
            b":W1AW     :Hello{",
            b":W1AW     :Hello{123456",
            b":W1AW     :" + b"x" * 68,
            b">" + b"x" * 63,
            b">092345/Ready",
            b"@000000z4903.50N/07201.75W-",
        ):
            with self.subTest(information=information), self.assertRaises(FieldError):
                decode_payload(information)

    def test_invalid_construction(self) -> None:
        for value in (
            Message("W1AW", b"ack003"),
            Message("W1AW", b"bad{body"),
            Message("W1AW", b"\xff"),
            Status(b"092345zambiguous"),
            Position(0, 0, Symbol("x", "-")),
        ):
            with self.subTest(value=value), self.assertRaises(FieldError):
                encode_payload(value)
        with self.assertRaises(UnsupportedFormat):
            encode_payload(Message("BLN0", b"Notice"))

    def test_rf_limits(self) -> None:
        for source in ("N0CALL-16", "TOOLONG", "n0call"):
            with self.subTest(source=source), self.assertRaises(EnvelopeError):
                serialize_packet(Packet(Header(source, "APRS"), Status()), profile="rf")
        for count in (8, 9):
            packet = Packet(
                Header("N0CALL", "APRS", tuple(PathHop("D1") for _ in range(count))),
                Status(),
            )
            if count == 8:
                validate_packet(packet, profile="rf")
            else:
                with self.assertRaises(EnvelopeError):
                    validate_packet(packet, profile="rf")
        with self.assertRaises(EnvelopeError):
            serialize_packet(
                Packet(Header("N0CALL", "APRS"), Opaque(b"~" * 257)), profile="rf"
            )
