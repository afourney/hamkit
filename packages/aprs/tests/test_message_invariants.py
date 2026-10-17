# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Message-family invariants apply before the corresponding wire codecs exist."""
import unittest
from typing import Any

from hamkit import aprs as a


class MessageInvariantTests(unittest.TestCase):
    def assert_invalid(
        self, model: type[Any], fields: dict[str, Any], tag: str
    ) -> None:
        with self.assertRaises(a.ModelError):
            model(**fields)
        # Primitive inputs deliberately exercise the same semantics through JSON.
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict({"type": tag, **fields})

    def test_status_reserved_characters_recover_without_faking_valid_packet(
        self,
    ) -> None:
        for char in "|~":
            self.assert_invalid(a.Status, {"text": char}, "status")
            raw = b"N0CALL>APRS:>" + char.encode("ascii")
            result = a.parse_packet(raw)
            self.assertIsInstance(result, a.Malformed)
            assert isinstance(result, a.Malformed)
            self.assertEqual(result.original_wire, raw)
            self.assertTrue(any("text" in d.path for d in result.diagnostics))
        for body in ("", "Ready"):
            packet = a.Packet(a.Header("N0CALL", "APRS"), a.Status(body))
            self.assertEqual(
                a.serialize_packet(packet), b"N0CALL>APRS:>" + body.encode()
            )

    def test_serializer_revalidates_even_bypassed_frozen_model(self) -> None:
        status = a.Status("Ready")
        packet = a.Packet(a.Header("N0CALL", "APRS"), status)
        object.__setattr__(status, "text", "~")
        with self.assertRaises(a.ModelError):
            a.serialize_packet(packet)

    def test_status_grid_dependencies_and_total_size(self) -> None:
        grid, symbol = a.Grid("IO91"), a.Symbol("/", "-")
        with self.assertRaises(a.ModelError):
            a.Status("", grid=grid)
        with self.assertRaises(a.ModelError):
            a.Status("", symbol=symbol)
        with self.assertRaises(a.ModelError):
            a.Status(
                "",
                grid=grid,
                symbol=symbol,
                timestamp=a.Timestamp("dhm_utc", 1, 2, day=1),
            )
        with self.assertRaises(a.ModelError):
            a.Status("No separator", grid=grid, symbol=symbol)
        with self.assertRaises(a.ModelError):
            a.Status(" " + "x" * 56, grid=grid, symbol=symbol)
        valid = a.Status(" House", grid=grid, symbol=symbol)
        self.assertEqual(a.from_json(a.to_json(valid)), valid)
        with self.assertRaises(a.CodecNotImplemented):
            a.serialize_packet(a.Packet(a.Header("N0CALL", "APRS"), valid))

    def test_reply_ack_has_one_consistent_identifier(self) -> None:
        self.assert_invalid(
            a.ReplyAck, {"message_number": "12345", "previous_ack": "12"}, "reply_ack"
        )
        for cls in (a.Message, a.Acknowledgment):
            with self.assertRaises(a.ModelError):
                if cls is a.Message:
                    cls("W1AW", "Hi", "01", a.ReplyAck("02", "03"))
                else:
                    cls("W1AW", "01", reply_ack=a.ReplyAck("02", "03"))
        valid = a.Message("W1AW", "Hi", "01", a.ReplyAck("01", "02"))
        self.assertEqual(a.from_json(a.to_json(valid)), valid)
        # Short components are not rejected merely because the source illustrates MM}AA.
        self.assertEqual(
            a.from_json(a.to_json(a.ReplyAck("1", "2"))), a.ReplyAck("1", "2")
        )

    def test_bulletin_and_autoanswer_constraints(self) -> None:
        for fields in (
            {"identifier": "AB", "text": ""},
            {"identifier": "1", "text": "~"},
            {"identifier": "A", "text": "", "announcement": True, "group": "TEST"},
        ):
            self.assert_invalid(a.Bulletin, fields, "bulletin")
        self.assertEqual(a.Bulletin("1", "").text, "")
        self.assertEqual(a.Bulletin("A", "{", announcement=True).text, "{")
        self.assert_invalid(
            a.AutoAnswer, {"addressee": "W1AW", "text": "x" * 65}, "auto_answer"
        )
        self.assertEqual(a.AutoAnswer("W1AW", "", previous_ack="12").text, "")

    def test_query_context_and_unknown_raw_extension(self) -> None:
        for fields in (
            {"name": "APRS", "message_id": "1"},
            {"name": "APRSD"},
            {"name": "WX", "addressee": "W1AW"},
            {"name": "APRS", "heard_station": "W1AW"},
        ):
            self.assert_invalid(a.Query, fields, "query")
        query = a.Query("CUSTOM", arguments=b"\xff")
        self.assertEqual(a.from_json(a.to_json(query)), query)
        with self.assertRaises(a.CodecNotImplemented):
            a.serialize_packet(a.Packet(a.Header("N0CALL", "APRS"), query))
        with self.assertRaises(a.ModelError):
            a.Query("APRS", arguments=b"opaque")
        for radius in (0.5, 10000):
            with self.assertRaises(a.ModelError):
                a.Footprint(a.Coordinates(0, 0), radius)
        self.assertEqual(a.Footprint(a.Coordinates(0, 0), 0).radius_miles, 0)

    def test_capabilities_and_heard_statistics(self) -> None:
        with self.assertRaises(a.ModelError):
            a.Capabilities(())
        with self.assertRaises(a.JSONModelError):
            a.from_json('{"type":"capabilities","tokens":[]}')
        for fields in (
            {"name": "a,b"},
            {"name": "X", "value": "x,y"},
            {"name": "MSG_CNT", "value": "-1"},
        ):
            self.assert_invalid(a.Capability, fields, "capability")
        self.assertEqual(a.Capability("CUSTOM", "").value, "")
        with self.assertRaises(a.ModelError):
            a.HeardStation("W1AW", (1, None))
        heard = a.HeardStation("W1AW", (0, None, 1, 2, 3, 4, 5, 6))
        self.assertEqual(a.from_json(a.to_json(heard)), heard)
        self.assertEqual(a.DirectStations(()).stations, ())

    def test_nts_optional_preamble_and_record_budgets(self) -> None:
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
        for model, fields, tag in (
            (a.Text, {"line": 1, "text": "x" * 65}, "text"),
            (a.Signature, {"text": ""}, "signature"),
            (a.Phone, {"number": "12\\34"}, "phone"),
        ):
            self.assert_invalid(model, fields, tag)
        routing = a.Routing("", "", "", "")
        self.assertEqual(a.from_json(a.to_json(routing)), routing)
        text = a.Text(1, "x" * 64)
        self.assertEqual(a.from_json(a.to_json(text)), text)
        with self.assertRaises(a.CodecNotImplemented):
            a.serialize_packet(
                a.Packet(a.Header("N0CALL", "APRS"), a.Radiogram("W1AW", text))
            )


if __name__ == "__main__":
    unittest.main()
