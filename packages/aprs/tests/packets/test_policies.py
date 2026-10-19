# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import unittest

import hamkit.aprs as a


class PolicyTests(unittest.TestCase):
    def test_line_framing_is_explicit(self) -> None:
        packet = a.Packet(a.Header("N0CALL", "APRS"), a.Status("Ready"))
        self.assertEqual(a.parse_tnc2_line(a.serialize_tnc2_line(packet)), packet)
        self.assertEqual(a.parse_tnc2_line(b"N0CALL>APRS:>Ready\n"), packet)
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
