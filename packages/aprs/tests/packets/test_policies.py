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
                with self.assertRaises(a.CodecNotImplementedError):
                    a.parse_payload(information, unsupported="raise")
                value = a.parse_payload(information)
                assert isinstance(value, a.Opaque)
                self.assertEqual(value.information, information)
                self.assertEqual(
                    value.diagnostic.code if value.diagnostic else None, "unsupported"
                )

    def test_malformed_recovery_is_separate(self) -> None:
        raw = b"N0CALL>APRS:!9000.01N/07201.75W-"
        result = a.parse_packet(raw)
        assert isinstance(result, a.Malformed)
        self.assertEqual(result.original_wire, raw)
        self.assertEqual(result.recovered["type"], "packet")
        with self.assertRaises(a.FieldError):
            a.parse_packet(raw, malformed="raise")
        self.assertIsInstance(a.parse_packet(b"bad envelope"), a.Malformed)
        self.assertIsInstance(a.parse_payload(b":W1AW     :hi{\xff"), a.Malformed)

    def test_every_byte_in_user_data_survives(self) -> None:
        payload = a.UserDefined(b"Q", b"1", bytes(range(256)))
        packet = a.Packet(a.Header("N0CALL", "APRS"), payload)
        wire = a.serialize_packet(packet)
        self.assertEqual(a.parse_packet(wire), packet)
        self.assertEqual(a.parse_packet(wire).original_wire, wire)
        with self.assertRaises(a.EnvelopeError):
            a.serialize_tnc2_line(packet)
        with self.assertRaises(a.ConformanceError):
            a.serialize_packet(
                a.Packet(
                    a.Header("N0CALL", "APRS"), a.UserDefined(b"Q", b"1", b"x" * 300)
                ),
                profile="rf",
            )

    def test_line_framing_is_explicit(self) -> None:
        packet = a.Packet(a.Header("N0CALL", "APRS"), a.Status("Ready"))
        self.assertEqual(a.parse_tnc2_line(a.serialize_tnc2_line(packet)), packet)
        self.assertEqual(a.parse_tnc2_line(b"N0CALL>APRS:>Ready\n"), packet)
        # Unframed parsing keeps CR/LF: it becomes nonconforming status text.
        framed = a.parse_packet(b"N0CALL>APRS:>Ready\r\n")
        assert isinstance(framed, a.Packet)
        self.assertEqual({d.path for d in framed.diagnostics}, {"$.payload.text"})
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
        wire = a.serialize_packet(nested, max_third_party_depth=2)
        self.assertEqual(a.parse_packet(wire, max_third_party_depth=2), nested)
        with self.assertRaises(a.ResourceLimitError):
            a.serialize_packet(nested, max_third_party_depth=1)
        deep = outer
        for _ in range(1000):
            deep = a.Packet(outer.header, a.ThirdParty(deep))
        for send in (a.serialize_packet, a.check_packet, a.validate_packet):
            with self.subTest(send=send), self.assertRaises(a.ResourceLimitError):
                send(deep)
        with self.assertRaises(a.ResourceLimitError):
            a.parse_packet(wire, max_third_party_depth=1)
        with self.assertRaises(a.ResourceLimitError):
            a.parse_payload(b"}W1AW>APRS:>Ready", max_third_party_depth=0)
        parsed = a.parse_packet(b"N0CALL>APRS:}W1AW>490S5P:`12345678")
        assert isinstance(parsed, a.Packet)
        assert isinstance(parsed.payload, a.ThirdParty)
        self.assertEqual(parsed.payload.packet.header.destination, "490S5P")
        self.assertIsInstance(parsed.payload.packet.payload, a.Opaque)

    def test_third_party_findings_carry_their_path(self) -> None:
        parsed = a.parse_packet(b"N0CALL>APRS:}W1AW>APRS:>Caf\xe9|")
        assert isinstance(parsed, a.Packet)
        self.assertEqual(
            [(d.message, d.path) for d in parsed.diagnostics],
            [
                (
                    "text is not valid UTF-8; decoded as Latin-1",
                    "$.payload.packet.payload.text",
                ),
                (
                    "contains a reserved character (| ~)",
                    "$.payload.packet.payload.text",
                ),
            ],
        )

    def test_bad_inner_envelope_is_top_level_malformed(self) -> None:
        result = a.parse_payload(b"}broken")
        assert isinstance(result, a.Malformed)
        self.assertEqual(result.recovered["type"], "third_party")
        self.assertTrue(
            any(d.path.startswith("$.packet.header") for d in result.diagnostics)
        )

    def test_status_non_utc_timestamp_looking_text(self) -> None:
        for text in ("092345/Ready", "123045hReady"):
            self.assertEqual(a.parse_payload(b">" + text.encode()), a.Status(text))
            self.assertEqual(a.serialize_payload(a.Status(text)), b">" + text.encode())

    def test_new_fields_never_imply_working_codecs(self) -> None:
        from hamkit.aprs._fields import decode_timestamp, encode_timestamp

        with self.assertRaises(a.CodecNotImplementedError):
            encode_timestamp(a.Timestamp.mdhm(10, 17, 12, 30))
        with self.assertRaises(a.CodecNotImplementedError):
            decode_timestamp(b"10171230")
        with self.assertRaises(a.CodecNotImplementedError):
            a.serialize_payload(
                a.Position(
                    49,
                    -72,
                    a.Symbol("/", "-"),
                    extensions=a.Extensions(dao=a.DAO("W")),
                )
            )
