# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import unittest
from dataclasses import replace

from hamkit.aprs import (
    CodecNotImplementedError,
    EnvelopeError,
    EnvelopePolicy,
    FieldError,
    Message,
    Packet,
    Position,
    Status,
    Symbol,
    parse_packet,
    parse_payload,
    serialize_packet,
    serialize_payload,
)


class PacketTests(unittest.TestCase):
    def test_null_position_convention(self) -> None:
        value = parse_payload(b"!0000.00N\\00000.00W.")
        assert isinstance(value, Position)
        self.assertTrue(value.is_null_position)
        self.assertFalse(Position(0, 0, Symbol("/", "-")).is_null_position)

    def test_original_wire_is_archival(self) -> None:
        # The byte-for-byte round trip is a case vector (HDR); an edit keeps the
        # archived bytes but sends the edited fields.
        loose = EnvelopePolicy(".*", ".*", ".*")
        raw = b"n0call-0>APRS,qAR,igate:>radio: ready > listening"
        packet = parse_packet(raw)
        assert isinstance(packet, Packet)
        changed = replace(packet, payload=Status("Changed"))
        self.assertEqual(changed.original_wire, raw)
        self.assertTrue(serialize_packet(changed, policy=loose).endswith(b":>Changed"))

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
            # The Malformed results are case vectors; this is the raise option.
            with self.subTest(wire=wire), self.assertRaises(EnvelopeError):
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
            b">000000zReady",
        ):
            with self.subTest(information=information), self.assertRaises(FieldError):
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
