# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT

"""Received input: lenient where usable, Malformed only where undecodable."""

import copy
import json
import unittest
from typing import Any, cast

from hamkit import aprs as a
from hamkit.aprs._fields import encode_timestamp

SYMBOL = a.Symbol("/", "-")


class MalformedTests(unittest.TestCase):
    # How received input decodes, including what Malformed recovers, is in the
    # case vectors (BAD-150, TIM-022, NET-033, MSG-086 and others); these test
    # the API around Malformed results.

    def test_recovered_data_round_trips_and_is_repaired_through_json(self) -> None:
        raw = b">APRS,BAD**:!4903.50N/19000.00W>tail\xff"
        result = a.parse_packet(raw)
        assert isinstance(result, a.Malformed)
        self.assertIsNone(result.header)
        recovered = cast(dict[str, Any], result.recovered)
        self.assertEqual(json.loads(a.to_json(result))["recovered"], recovered)
        self.assertEqual(a.from_json(a.to_json(result)), result)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(recovered)  # Recovered data is not a model.
        fixed = copy.deepcopy(recovered)
        fixed["header"]["source"] = "N0CALL"
        fixed["header"]["path"][0]["address"] = "WIDE1-1"
        fixed["payload"]["longitude_deg"] = -72.0
        packet = a.from_json_dict(fixed, expected_type=a.Packet)
        self.assertEqual(
            a.serialize_packet(packet),
            "N0CALL>APRS,WIDE1-1*:!4903.50N/07200.00W>tailÿ".encode(),
        )

    def test_partial_recovered_data_is_not_a_model(self) -> None:
        result = a.parse_packet(b"N0CALL>APRS:@001230z4903.50N")
        assert isinstance(result, a.Malformed)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(result.recovered)

    def test_payload_parsing_reports_payload_relative_paths(self) -> None:
        payload = a.parse_payload(b"!4903.50N/19000.00W-")
        assert isinstance(payload, a.Malformed)
        self.assertEqual(payload.recovered["type"], "position")
        self.assertTrue(any(d.path == "$.longitude_deg" for d in payload.diagnostics))

    def test_unknown_codec_raises_only_when_asked(self) -> None:
        with self.assertRaises(a.CodecNotImplementedError):
            a.parse_packet(b"N0CALL>APRS:~\xff", unsupported="raise")

    def test_malformed_is_not_serializable_or_a_packet_payload(self) -> None:
        result = a.parse_packet(b"broken")
        assert isinstance(result, a.Malformed)
        for encode in (
            a.serialize_packet,
            a.serialize_payload,
            a.serialize_tnc2_line,
            a.check_packet,
        ):
            with self.assertRaises(TypeError):
                encode(cast(Any, result))
        with self.assertRaises(a.ModelError):
            a.Packet(a.Header("N0CALL", "APRS"), cast(Any, result))
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(
                {
                    "type": "packet",
                    "header": {"source": "N0CALL", "destination": "APRS"},
                    "payload": a.to_json_dict(result),
                }
            )


class StrictConstructionTests(unittest.TestCase):
    def test_unrepresentable_values_raise(self) -> None:
        for build in (
            lambda: a.Position(91, 0, SYMBOL),
            lambda: a.Position(0, -181, SYMBOL),
            lambda: a.Position(float("nan"), 0, SYMBOL),
            lambda: a.Position(True, 0, SYMBOL),
            lambda: a.Position(cast(Any, None), 0, SYMBOL),
            lambda: a.Position(0, 0, SYMBOL, ambiguity=5),
            lambda: a.Header("", "APRS"),
            lambda: a.Hop("WIDE1-1*"),
            lambda: a.Message("", "Hello"),
            lambda: a.Message("W1AW", "a{b"),
            lambda: a.Message("W1AW", "ack003"),
            lambda: a.Message("W1AW", "ack01}02"),
            lambda: a.Message("W1AW", "rej1}"),
            lambda: a.Message("W1AW", "hi", reply_ack="01"),
            lambda: a.Acknowledgment("W1AW", ""),
            lambda: a.Status("092345zambiguous"),
            lambda: a.Status("x", timestamp=a.Timestamp.hms(1, 2, 3)),
            lambda: a.Timestamp("dhm_utc", 12, 30),
            lambda: a.Timestamp("hms_utc", 12, 30),
            lambda: a.Timestamp.mdhm(4, 31, 12, 30),
            lambda: a.Object("", 49, -72, SYMBOL, timestamp=a.Timestamp.dhm(1, 12, 30)),
            lambda: a.Item("a!b", 49, -72, SYMBOL),
            lambda: a.Symbol("/", ""),
            lambda: a.Extent((50, 49), (-73, -72)),
            lambda: a.Weather(temperature=a.Measurement(10, "mph")),
            lambda: a.Telemetry((1,) * 6),
            lambda: a.GLL(None, a.UTCTime(12, 30, 0), "active"),
            lambda: a.NTSAddress(("é", "street", "city", "zip")),
            lambda: a.Grid("not a grid"),
            lambda: a.UserDefined(b"", b"1", b"data"),
            lambda: a.Reserved(256, b"data"),
            lambda: a.Opaque(b""),
            lambda: a.Status("\udcff"),
            lambda: a.Packet(a.Header("N0CALL", "APRS"), cast(Any, None)),
        ):
            with self.subTest(build=build), self.assertRaises(a.ModelError):
                build()
        with self.assertRaises(TypeError):
            a.Position(cast(Any, 49))  # type: ignore[call-arg]
        for value in (
            {"type": "position", "latitude_deg": 49},
            {"type": "position", "latitude_deg": 99, "longitude_deg": 0},
        ):
            with self.assertRaises(a.JSONModelError):
                a.from_json_dict(value)

    def test_free_text_is_unicode_but_tokens_are_ascii(self) -> None:
        self.assertEqual(a.Status("Café ☕").text, "Café ☕")
        self.assertEqual(a.Message("W1AW", "日本語").text, "日本語")
        with self.assertRaises(a.ModelError):
            a.Message("W1ÄW", "Hello")
        with self.assertRaises(a.ModelError):
            a.Object("Café", 49, -72, SYMBOL, timestamp=a.Timestamp.dhm(1, 0, 0))

    def test_evidence_never_overrides_edits(self) -> None:
        timestamp = a.Timestamp("dhm_utc", 12, 30, day=17, raw=b"010000z")
        self.assertEqual(encode_timestamp(timestamp), b"171230z")
        # Sending edited fields over stale evidence is an STA/OTH case vector.
        packet = a.Packet(
            a.Header("N0CALL", "APRS"),
            a.Status("Edited", timestamp=timestamp),
            original_wire=b"wrong",
        )
        # Defend the serialization boundary even against frozen-dataclass bypasses.
        object.__setattr__(packet.payload, "text", "\udcff")
        with self.assertRaises(a.ModelError):
            a.serialize_packet(packet)
        with self.assertRaises(a.JSONModelError):
            a.to_json(packet)
