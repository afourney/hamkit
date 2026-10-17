# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import unittest

import hamkit.aprs as a


class PolicyTests(unittest.TestCase):
    def test_implemented_families_and_truncated_reports(self) -> None:
        for information, cls in (
            (b"!/5L!!<*e7>7P[", a.Position),
            (b"T#001,1,2,3,4,5,00000000", a.Telemetry),
            (b":BLN0     :Notice", a.Bulletin),
            (b":N0CALL   :PARM.Temp", a.TelemetryDefinition),
            (b"?APRS?", a.Query),
            (b"<IGATE", a.Capabilities),
            (b"$ULTW0000", a.RawWeather),
            (b"!!0000", a.RawWeather),
            (b"%123/4", a.Agrelo),
            (b"[IO91SX", a.Maidenhead),
        ):
            with self.subTest(information=information):
                self.assertIsInstance(
                    a.parse_payload(information, unsupported="raise"), cls
                )
        for information in (b";OBJECT   *", b")ITEM!", b"$GPGGA,"):
            self.assertIsInstance(a.parse_payload(information), a.Malformed)

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
                policy=a.RF,
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
        parsed = a.parse_packet(b"N0CALL>APRS:}W1AW>490S5P:`123456>/")
        assert isinstance(parsed, a.Packet)
        assert isinstance(parsed.payload, a.ThirdParty)
        self.assertEqual(parsed.payload.packet.header.destination, "490S5P")
        self.assertIsInstance(parsed.payload.packet.payload, a.MicE)

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

    def test_mdhm_and_dao_codecs(self) -> None:
        from hamkit.aprs._fields import decode_timestamp, encode_timestamp

        stamp = a.Timestamp.mdhm(10, 17, 12, 30)
        self.assertEqual(encode_timestamp(stamp), b"10171230")
        self.assertEqual(decode_timestamp(b"10171230"), stamp)
        p = a.Position(
            49, -72, a.Symbol("/", "-"), extensions=a.Extensions(dao=a.DAO("W"))
        )
        self.assertEqual(a.parse_payload(a.serialize_payload(p)), p)
