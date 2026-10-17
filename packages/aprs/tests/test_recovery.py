# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT

"""Received input: lenient where usable, Malformed only where undecodable."""

import copy
import dataclasses
import json
import unittest
from typing import Any, cast

from hamkit import aprs as a
from hamkit.aprs._fields import encode_timestamp

SYMBOL = a.Symbol("/", "-")


def codes(packet: a.Packet) -> set[tuple[str, str]]:
    return {(d.code, d.path) for d in packet.diagnostics}


class LenientDecodingTests(unittest.TestCase):
    def test_utf8_text_follows_aprs_1_2(self) -> None:
        raw = "N0CALL>APRS::W1AW     :héllo 👋{01".encode()
        packet = a.parse_packet(raw)
        assert isinstance(packet, a.Packet)
        self.assertEqual(packet.payload, a.Message("W1AW", "héllo 👋", message_id="01"))
        self.assertEqual(packet.diagnostics, ())
        self.assertEqual(a.serialize_packet(packet), raw)
        status = a.parse_packet("N0CALL>APRS:>Grüße".encode())
        assert isinstance(status, a.Packet)
        self.assertEqual(status.payload, a.Status("Grüße"))

    def test_invalid_utf8_falls_back_to_latin1(self) -> None:
        packet = a.parse_packet(b"N0CALL>APRS:!4903.50N/07201.75W-Caf\xe9")
        assert isinstance(packet, a.Packet)
        assert isinstance(packet.payload, a.Position)
        self.assertEqual(packet.payload.comment, "Café")
        self.assertEqual(codes(packet), {("nonconforming", "$.payload.comment")})
        self.assertEqual(
            packet.original_wire, b"N0CALL>APRS:!4903.50N/07201.75W-Caf\xe9"
        )
        # Sending transcodes the text to UTF-8; original_wire is never replayed.
        self.assertTrue(a.serialize_packet(packet).endswith("Café".encode()))

    def test_out_of_spec_but_usable_packets_still_decode(self) -> None:
        for raw, path in (
            (b"N0CALL>APRS:>" + b"x" * 80, "$.payload.text"),
            (b"N0CALL>APRS::W1AW     :" + b"x" * 100, "$.payload.text"),
            (b"N0CALL>APRS:>bad|text", "$.payload.text"),
            (b"N0CALL>APRS:>bell\x07", "$.payload.text"),
            (b"N0CALL>APRS:!4903.50N/07201.75W>" + b"c" * 50, "$.payload.comment"),
        ):
            with self.subTest(raw=raw):
                packet = a.parse_packet(raw)
                assert isinstance(packet, a.Packet)
                self.assertIn(("nonconforming", path), codes(packet))
                with self.assertRaises(a.ConformanceError):
                    a.serialize_packet(packet)

    def test_rf_policy_reports_instead_of_rejecting(self) -> None:
        raw = b"n0call>APRS,A,B,C,D,E,F,G,H,I:>" + b"x" * 10
        packet = a.parse_packet(raw, policy=a.RF())
        assert isinstance(packet, a.Packet)
        self.assertEqual(
            codes(packet),
            {("nonconforming", "$.header.source"), ("nonconforming", "$.header.path")},
        )
        internet = a.parse_packet(raw)
        assert isinstance(internet, a.Packet)
        self.assertEqual(internet.diagnostics, ())

    def test_extensions_leave_the_comment(self) -> None:
        raw = b"N0CALL>APRS:!4903.50N/07201.75W>088/036/A=001234 hi"
        packet = a.parse_packet(raw)
        assert isinstance(packet, a.Packet)
        assert isinstance(packet.payload, a.Position)
        self.assertEqual(packet.payload.comment, " hi")
        self.assertEqual(packet.payload.extensions.motion, a.Motion(88, 36))
        altitude = packet.payload.extensions.altitude
        assert altitude is not None
        self.assertEqual(altitude.measurement, a.Measurement(1234, "feet"))
        self.assertEqual(a.serialize_packet(packet), raw)

    def test_invalid_extension_text_stays_comment_with_a_finding(self) -> None:
        raw = b"N0CALL>APRS:!4903.50N/07201.75W>999/999Hello"
        packet = a.parse_packet(raw, unsupported="raise")
        assert isinstance(packet, a.Packet)
        assert isinstance(packet.payload, a.Position)
        self.assertEqual(packet.payload.comment, "999/999Hello")
        self.assertEqual(codes(packet), {("nonconforming", "$.payload.comment")})
        with self.assertRaises(a.ConformanceError):
            a.serialize_packet(packet)

    def test_recognized_extensions_decode(self) -> None:
        for information in (
            b"!4903.50N/07201.75W>hi !W12!",
            b"!4903.50N/07201.75W>|!!!!|",
            b"!4903.50N/07201.75W_090/005g010t068",
            b"!4903.50N\\07201.75WlT01/C02",
        ):
            with self.subTest(information=information):
                packet = a.parse_packet(b"N0CALL>APRS:" + information)
                assert isinstance(packet, a.Packet)
                self.assertIsInstance(packet.payload, a.Position)
                self.assertEqual(a.parse_packet(a.serialize_packet(packet)), packet)

    def test_invalid_df_bearing_is_inspectable_but_not_sendable(self) -> None:
        raw = b"N0CALL>APRS:!4903.50N/07201.75W\\088/036/999/729"
        packet = a.parse_packet(raw, unsupported="raise")
        assert isinstance(packet, a.Packet)
        assert isinstance(packet.payload, a.Position)
        self.assertEqual(packet.original_wire, raw)
        self.assertEqual(packet.payload.comment, "/999/729")
        self.assertEqual(packet.payload.extensions.motion, a.Motion(88, 36))
        self.assertIsNone(packet.payload.extensions.bearing)
        self.assertEqual(codes(packet), {("nonconforming", "$.payload.comment")})
        for policy in (a.APRS_IS(), a.RF()):
            self.assertTrue(a.check_packet(packet, policy=policy))
            with self.assertRaises(a.ConformanceError):
                a.serialize_packet(packet, policy=policy)


class MalformedTests(unittest.TestCase):
    def test_multiple_bad_components_keep_reliable_data(self) -> None:
        raw = b">APRS,BAD**:!4903.50N/19000.00W>tail\xff"
        result = a.parse_packet(raw)
        assert isinstance(result, a.Malformed)
        self.assertEqual(result.original_wire, raw)
        self.assertIsNone(result.header)
        paths = {d.path for d in result.diagnostics}
        self.assertIn("$.header.source", paths)
        self.assertIn("$.header.path[0].address", paths)
        self.assertIn("$.payload.longitude_deg", paths)
        recovered = cast(dict[str, Any], result.recovered)
        self.assertEqual(recovered["header"]["destination"], "APRS")
        self.assertAlmostEqual(recovered["payload"]["latitude_deg"], 49 + 3.5 / 60)
        self.assertNotIn("longitude_deg", recovered["payload"])
        self.assertEqual(recovered["payload"]["comment"], "tail\xff")
        self.assertEqual(json.loads(a.to_json(result))["recovered"], recovered)
        self.assertEqual(a.from_json(a.to_json(result)), result)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(recovered)
        fixed = copy.deepcopy(recovered)
        fixed["header"]["source"] = "N0CALL"
        fixed["header"]["path"][0]["address"] = "WIDE1-1"
        fixed["payload"]["longitude_deg"] = -72.0
        packet = a.from_json_dict(fixed, expected_type=a.Packet)
        self.assertEqual(
            a.serialize_packet(packet),
            "N0CALL>APRS,WIDE1-1*:!4903.50N/07200.00W>tailÿ".encode(),
        )

    def test_header_is_typed_when_intact(self) -> None:
        result = a.parse_packet(b"N0CALL>APRS,WIDE1-1:!4903.50N/19000.00W-")
        assert isinstance(result, a.Malformed)
        self.assertEqual(result.header, a.Header("N0CALL", "APRS", (a.Hop("WIDE1-1"),)))

    def test_partial_timestamp_and_missing_coordinate_are_not_invented(self) -> None:
        result = a.parse_packet(b"N0CALL>APRS:@001230z4903.50N")
        assert isinstance(result, a.Malformed)
        data = cast(dict[str, Any], result.recovered["payload"])
        self.assertEqual(
            data["timestamp"], {"kind": "dhm_utc", "hour": 12, "minute": 30}
        )
        self.assertNotIn("longitude_deg", data)
        paths = {d.path for d in result.diagnostics}
        self.assertIn("$.payload.timestamp.day", paths)
        self.assertIn("$.payload.longitude_deg", paths)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(result.recovered)

    def test_standalone_boundary_and_nested_packet_boundary(self) -> None:
        payload = a.parse_payload(b"!4903.50N/19000.00W-")
        assert isinstance(payload, a.Malformed)
        self.assertEqual(payload.recovered["type"], "position")
        self.assertTrue(any(d.path == "$.longitude_deg" for d in payload.diagnostics))
        outer = a.parse_packet(b"OUTER>APRS:}INNER>APRS:!4903.50N/19000.00W-")
        assert isinstance(outer, a.Malformed)
        recovered = cast(dict[str, Any], outer.recovered)
        self.assertEqual(recovered["payload"]["type"], "third_party")
        self.assertEqual(recovered["payload"]["packet"]["header"]["source"], "INNER")
        self.assertTrue(
            any(
                d.path == "$.payload.packet.payload.longitude_deg"
                for d in outer.diagnostics
            )
        )

    def test_invalid_message_id_is_kept_for_repair(self) -> None:
        result = a.parse_packet(b"W1AW>APRS::N0CALL   :hello{\xff")
        assert isinstance(result, a.Malformed)
        self.assertEqual({d.path for d in result.diagnostics}, {"$.payload.message_id"})
        fixed = copy.deepcopy(cast(dict[str, Any], result.recovered))
        self.assertEqual(fixed["payload"]["message_id"], "\xff")
        fixed["payload"]["message_id"] = "01"
        packet = a.from_json_dict(fixed, expected_type=a.Packet)
        self.assertEqual(packet.payload, a.Message("N0CALL", "hello", message_id="01"))

    def test_binary_is_lossless(self) -> None:
        binary = a.Packet(
            a.Header("N0CALL", "APRS"), a.UserDefined(b"Q", b"1", bytes(range(256)))
        )
        self.assertEqual(a.parse_packet(a.serialize_packet(binary)), binary)
        self.assertEqual(a.from_json(a.to_json(binary)), binary)

    def test_unknown_codec_is_not_a_malformed_diagnosis(self) -> None:
        for raw in (b"N0CALL>APRS:~\xff",):
            result = a.parse_packet(raw)
            assert isinstance(result, a.Packet)
            assert isinstance(result.payload, a.Opaque)
            self.assertEqual(a.serialize_packet(result), raw)
            with self.assertRaises(a.CodecNotImplementedError):
                a.parse_packet(raw, unsupported="raise")
        for raw in (b"N0CALL>APRS:_not-a-timestamp", b"N0CALL>APRS:T#incomplete"):
            self.assertIsInstance(a.parse_packet(raw), a.Malformed)
        result = a.parse_packet(b">490S5P:`12345678")
        assert isinstance(result, a.Malformed)
        self.assertEqual(
            cast(dict[str, Any], result.recovered["payload"])["type"], "opaque"
        )
        self.assertTrue(all(d.path.startswith("$.header") for d in result.diagnostics))

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
            lambda: a.GLL(None, a.UTCTime(12, 30, 0), "A"),
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
        packet = a.Packet(
            a.Header("N0CALL", "APRS"),
            a.Status("Edited", timestamp=timestamp),
            original_wire=b"wrong",
        )
        self.assertEqual(a.serialize_packet(packet), b"N0CALL>APRS:>171230zEdited")
        raw = a.Packet(
            a.Header("N0CALL", "APRS"), a.Opaque(b"~new"), original_wire=b"old"
        )
        self.assertEqual(a.serialize_packet(raw), b"N0CALL>APRS:~new")
        # Defend the serialization boundary even against frozen-dataclass bypasses.
        object.__setattr__(packet.payload, "text", "\udcff")
        with self.assertRaises(a.ModelError):
            a.serialize_packet(packet)
        with self.assertRaises(a.JSONModelError):
            a.to_json(packet)

    def test_genuine_absence_and_unavailable_readings(self) -> None:
        absent = a.Weather()
        unavailable = a.Weather(wind_speed=a.Measurement(None, "mph", raw=b"..."))
        self.assertNotEqual(absent, unavailable)
        self.assertEqual(a.Message("W1AW", "").message_id, None)
        self.assertEqual(a.Position(49, -72, SYMBOL).timestamp, None)
        self.assertEqual(a.GLL(None, a.UTCTime(12, 30, 0), "V").coordinates, None)
        self.assertEqual(dataclasses.replace(unavailable, wind_speed=None), absent)
