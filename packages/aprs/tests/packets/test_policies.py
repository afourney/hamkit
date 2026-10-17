# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import unittest

import hamkit.aprs as a


class PolicyTests(unittest.TestCase):
    def test_unimplemented_families_have_explicit_failure(self) -> None:
        for information in (
            b"!/5L!!<*e7>7P[",
            b";OBJECT   *",
            b")ITEM!",
            b"_10171230",
            b"T#001,1,2,3,4,5,00000000",
            b":W1AW     :Reply{01}02",
            b":BLN0     :Notice",
            b":N0CALL   :PARM.Temp",
            b"?APRS?",
            b"<IGATE",
            b"$GPGGA,",
            b"$ULTW0000",
            b"!!0000",
            b"%123/4",
            b"[IO91SX",
        ):
            with self.subTest(information=information):
                with self.assertRaises(a.CodecNotImplemented):
                    a.decode_payload(
                        information, options=a.DecodeOptions(unsupported="raise")
                    )
                value = a.decode_payload(information)
                self.assertIsInstance(value, a.Opaque)
                assert isinstance(value, a.Opaque)
                self.assertEqual(value.information, information)
                self.assertEqual(
                    value.diagnostic.code if value.diagnostic else None, "unsupported"
                )

    def test_malformed_recovery_is_separate(self) -> None:
        raw = b"N0CALL>APRS:!9000.01N/07201.75W-"
        with self.assertRaises(a.FieldError):
            a.parse_packet(raw)
        packet = a.parse_packet(raw, options=a.DecodeOptions(malformed="opaque"))
        assert isinstance(packet.payload, a.Opaque)
        self.assertEqual(
            packet.payload.diagnostic.code if packet.payload.diagnostic else None,
            "malformed",
        )
        self.assertEqual(a.serialize_packet(packet), raw)
        with self.assertRaises(a.EnvelopeError):
            a.parse_packet(b"bad envelope", options=a.DecodeOptions(malformed="opaque"))
        with self.assertRaises(a.FieldError):
            a.decode_payload(b":W1AW     :\xff")
        self.assertIsInstance(
            a.decode_payload(
                b":W1AW     :\xff", options=a.DecodeOptions(malformed="opaque")
            ),
            a.Opaque,
        )

    def test_every_byte_in_user_data_survives(self) -> None:
        payload = a.UserDefined(b"Q", b"1", bytes(range(256)))
        packet = a.Packet(a.Header("N0CALL", "APRS"), payload)
        wire = a.serialize_packet(packet)
        self.assertEqual(a.parse_packet(wire), packet)
        self.assertEqual(a.parse_packet(wire).original_wire, wire)
        with self.assertRaises(a.EnvelopeError):
            a.serialize_tnc2_line(packet)
        with self.assertRaises(a.EnvelopeError):
            a.serialize_packet(packet, profile="rf")

    def test_line_framing_is_explicit(self) -> None:
        packet = a.Packet(a.Header("N0CALL", "APRS"), a.Status(b"Ready"))
        self.assertEqual(a.parse_tnc2_line(a.serialize_tnc2_line(packet)), packet)
        self.assertEqual(a.parse_tnc2_line(b"N0CALL>APRS:>Ready\n"), packet)
        self.assertEqual(
            a.parse_packet(b"N0CALL>APRS:>Ready\r\n").payload, a.Status(b"Ready\r\n")
        )
        for raw in (
            b"N0CALL>APRS:>Ready",
            b"N0CALL>APRS:>Ready\r",
            b"N0CALL>APRS:>One\nTwo\n",
        ):
            with self.subTest(raw=raw), self.assertRaises(a.EnvelopeError):
                a.parse_tnc2_line(raw)

    def test_third_party_boundary_and_inner_context(self) -> None:
        inner = a.Packet(
            a.Header("W1AW", "APRS"), a.UserDefined(b"Q", b"1", b"\x00\xff")
        )
        outer = a.Packet(a.Header("N0CALL", "APRS"), a.ThirdParty(inner))
        self.assertEqual(a.parse_packet(a.serialize_packet(outer)), outer)
        nested = a.Packet(outer.header, a.ThirdParty(outer))
        wire = a.serialize_packet(nested, options=a.EncodeOptions(max_depth=2))
        self.assertEqual(
            a.parse_packet(wire, options=a.DecodeOptions(max_depth=2)), nested
        )
        with self.assertRaises(a.ResourceLimitError):
            a.serialize_packet(nested, options=a.EncodeOptions(max_depth=1))
        with self.assertRaises(a.ResourceLimitError):
            a.parse_packet(
                wire, options=a.DecodeOptions(max_depth=1, malformed="opaque")
            )
        with self.assertRaises(a.ResourceLimitError):
            a.decode_payload(b"}W1AW>APRS:>Ready", options=a.DecodeOptions(max_depth=0))
        parsed = a.parse_packet(b"N0CALL>APRS:}W1AW>490S5P:`12345678")
        assert isinstance(parsed.payload, a.ThirdParty)
        self.assertEqual(parsed.payload.packet.header.destination, "490S5P")
        self.assertIsInstance(parsed.payload.packet.payload, a.Opaque)

    def test_bad_inner_envelope_is_payload_error(self) -> None:
        with self.assertRaises(a.FieldError):
            a.decode_payload(b"}broken")
        self.assertIsInstance(
            a.decode_payload(b"}broken", options=a.DecodeOptions(malformed="opaque")),
            a.Opaque,
        )

    def test_status_non_utc_timestamp_looking_text(self) -> None:
        for text in (b"092345/Ready", b"123045hReady"):
            self.assertEqual(a.decode_payload(b">" + text), a.Status(text))
            self.assertEqual(a.encode_payload(a.Status(text)), b">" + text)

    def test_new_fields_never_imply_working_codecs(self) -> None:
        from hamkit.aprs.fields import decode_timestamp, encode_timestamp

        with self.assertRaises(a.CodecNotImplemented):
            encode_timestamp(a.Timestamp("mdhm_utc", 12, 30, day=17, month=10))
        with self.assertRaises(a.CodecNotImplemented):
            decode_timestamp(b"10171230")
        with self.assertRaises(a.FieldError):
            a.encode_payload(a.Position(49, -72, tail=b"raw", comment=b"structured"))
        with self.assertRaises(ValueError):
            a.parse_packet(b"N0CALL>APRS:>Ready", options=a.DecodeOptions(max_depth=-1))
