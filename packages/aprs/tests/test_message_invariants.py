# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Message-family constructor rules apply before the wire codecs exist."""

import unittest
from typing import Any

from hamkit import aprs as a


class MessageInvariantTests(unittest.TestCase):
    def assert_invalid(
        self, model: type[Any], fields: dict[str, Any], tag: str
    ) -> None:
        with self.assertRaises(a.ModelError):
            model(**fields)
        # Primitive inputs deliberately exercise the same rules through JSON.
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict({"type": tag, **fields})

    def test_serializer_revalidates_even_bypassed_frozen_model(self) -> None:
        status = a.Status("Ready")
        packet = a.Packet(a.Header("N0CALL", "APRS"), status)
        object.__setattr__(status, "timestamp", a.Timestamp.hms(1, 2, 3))
        with self.assertRaises(a.ModelError):
            a.serialize_packet(packet)

    def test_status_grid_dependencies(self) -> None:
        grid, symbol = a.Grid("IO91"), a.Symbol("/", "-")
        with self.assertRaises(a.ModelError):
            a.Status("", grid=grid)
        with self.assertRaises(a.ModelError):
            a.Status("", symbol=symbol)
        with self.assertRaises(a.ModelError):
            a.Status("", grid=grid, symbol=symbol, timestamp=a.Timestamp.dhm(1, 1, 2))
        valid = a.Status(" House", grid=grid, symbol=symbol)
        self.assertEqual(a.from_json(a.to_json(valid)), valid)
        packet = a.Packet(a.Header("N0CALL", "APRS"), valid)
        self.assertEqual(a.parse_packet(a.serialize_packet(packet)), packet)

    def test_reply_ack_is_one_suffix(self) -> None:
        for fields in (
            {"addressee": "W1AW", "text": "Hi", "reply_ack": "02"},
            {"addressee": "W1AW", "text": "Hi", "message_id": "01", "reply_ack": "0-"},
        ):
            self.assert_invalid(a.Message, fields, "message")
        valid = a.Message("W1AW", "Hi", message_id="01", reply_ack="")
        self.assertEqual(a.from_json(a.to_json(valid)), valid)
        self.assertEqual(a.serialize_payload(valid), b":W1AW     :Hi{01}")
        ack = a.Acknowledgment("W1AW", "01", reply_ack="02")
        self.assertEqual(a.serialize_payload(ack), b":W1AW     :ack01}02")
        self.assertEqual(a.parse_payload(a.serialize_payload(ack)), ack)

    def test_bulletin_identifier_and_group(self) -> None:
        for fields in (
            {"identifier": "AB", "text": ""},
            {"identifier": "a", "text": ""},
            {"identifier": "A", "text": "", "group": "TEST"},
            {"identifier": "1", "text": "", "group": "TOOLONG"},
        ):
            self.assert_invalid(a.Bulletin, fields, "bulletin")
        self.assertEqual(a.Bulletin("1", "").text, "")
        self.assertTrue(a.Bulletin("A", "{").announcement)

    def test_autoanswer_and_nws(self) -> None:
        self.assert_invalid(
            a.AutoAnswer, {"addressee": "W1AW", "text": "a{b"}, "auto_answer"
        )
        self.assertEqual(a.AutoAnswer("W1AW", "", previous_ack="12").text, "")
        self.assert_invalid(
            a.NWSBulletin, {"addressee": "W1AW", "text": ""}, "nws_bulletin"
        )
        self.assert_invalid(
            a.NWSBulletin,
            {"addressee": "NWS-WARN", "text": "", "reference_id": "!"},
            "nws_bulletin",
        )

    def test_query_tokens(self) -> None:
        for fields in ({"name": "aprs"}, {"name": "APRS", "heard_station": "W1 AW"}):
            self.assert_invalid(a.Query, fields, "query")
        query = a.Query("CUSTOM", arguments=b"\xff")
        self.assertEqual(a.from_json(a.to_json(query)), query)
        packet = a.Packet(a.Header("N0CALL", "APRS"), query)
        self.assertEqual(a.parse_packet(a.serialize_packet(packet)), packet)
        with self.assertRaises(a.ModelError):
            a.Footprint(a.Coordinates(0, 0), -1)

    def test_capabilities_and_heard_statistics(self) -> None:
        for fields in ({"name": "a,b"}, {"name": "X", "value": "x,y"}, {"name": ""}):
            self.assert_invalid(a.Capability, fields, "capability")
        self.assertEqual(a.Capability("CUSTOM", "").value, "")
        with self.assertRaises(a.ModelError):
            a.HeardStation("W1AW", (1, -1))
        heard = a.HeardStation("W1AW", (0, None, 1, 2, 3, 4, 5, 6))
        self.assertEqual(a.from_json(a.to_json(heard)), heard)
        self.assertEqual(a.DirectStations(()).stations, ())

    def test_nts_optional_preamble_and_separator(self) -> None:
        header = a.NTSHeader(
            number="12",
            precedence="R",
            originator="N0CALL",
            check="5",
            place="REDMOND WA",
            date="OCT 15",
        )
        self.assertIsNone(header.handling)
        self.assertIsNone(header.time)
        self.assertEqual(a.from_json(a.to_json(header)), header)
        self.assert_invalid(a.NTSPhone, {"number": "12\\34"}, "nts_phone")
        routing = a.NTSRouting(received_from="", received_at="", sent_to="", sent_at="")
        self.assertEqual(a.from_json(a.to_json(routing)), routing)


if __name__ == "__main__":
    unittest.main()
