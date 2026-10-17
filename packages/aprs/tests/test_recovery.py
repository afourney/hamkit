# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT

"""Strict construction and recoverable wire input are separate trust boundaries."""
import copy
import dataclasses
import json
import unittest
from typing import Any, cast

from hamkit import aprs as a
from hamkit.aprs.fields import encode_timestamp


class RecoveryTests(unittest.TestCase):
    def test_multiple_bad_components_keep_reliable_data(self) -> None:
        raw = b">APRS,BAD**:!4903.50N/19000.00W>tail\xff"
        result = a.parse_packet(raw)
        assert isinstance(result, a.Malformed)
        self.assertEqual(result.original_wire, raw)
        self.assertFalse(hasattr(result, "payload"))
        paths = {d.path for d in result.diagnostics}
        self.assertIn("$.header.source", paths)
        self.assertIn("$.header.path[0].address", paths)
        self.assertIn("$.payload.longitude_deg", paths)
        recovered = cast(dict[str, Any], result.recovered)
        self.assertEqual(recovered["header"]["destination"], "APRS")
        self.assertAlmostEqual(recovered["payload"]["latitude_deg"], 49 + 3.5 / 60)
        self.assertNotIn("longitude_deg", recovered["payload"])
        self.assertEqual(recovered["payload"]["tail"], "tail\xff")
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
            b"N0CALL>APRS,WIDE1-1*:!4903.50N/07200.00W>tail\xff",
        )
        self.assertNotIn("longitude_deg", recovered["payload"])

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
        payload = a.decode_payload(b"!4903.50N/19000.00W-")
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
        self.assertNotIn('"type": "malformed"', json.dumps(recovered))

    def test_text_is_ascii_and_binary_is_lossless(self) -> None:
        parsed = a.parse_packet(b"N0CALL>APRS:>Ready")
        assert isinstance(parsed, a.Packet)
        assert isinstance(parsed.payload, a.Status)
        self.assertEqual(parsed.payload.text, "Ready")
        for bad in (b"\xff", b"\xc3\xa9", b"bad\x00text", b"bad\r\ntext"):
            raw = b"N0CALL>APRS:>" + bad
            result = a.parse_packet(raw)
            assert isinstance(result, a.Malformed)
            self.assertEqual(result.original_wire, raw)
            self.assertNotIn("text", cast(dict[str, Any], result.recovered["payload"]))
            self.assertTrue(any(d.path == "$.payload.text" for d in result.diagnostics))
            self.assertEqual(a.from_json(a.to_json(result)), result)
        for bad_text in ("é", "\udcff", "bad\ntext"):
            with self.assertRaises(a.ModelError):
                a.Status(bad_text)
            with self.assertRaises(a.JSONModelError):
                a.from_json(json.dumps({"type": "status", "text": bad_text}))
        binary = a.Packet(
            a.Header("N0CALL", "APRS"), a.UserDefined(b"Q", b"1", bytes(range(256)))
        )
        self.assertEqual(a.parse_packet(a.serialize_packet(binary)), binary)
        self.assertEqual(a.from_json(a.to_json(binary)), binary)

    def test_unknown_codec_is_not_a_malformed_diagnosis(self) -> None:
        for raw in (
            b"N0CALL>APRS:_not-yet-interpreted",
            b"N0CALL>APRS:T#incomplete",
            b"N0CALL>APRS:~\xff",
        ):
            result = a.parse_packet(raw)
            assert isinstance(result, a.Packet)
            assert isinstance(result.payload, a.Opaque)
            self.assertEqual(a.serialize_packet(result), raw)
            with self.assertRaises(a.CodecNotImplemented):
                a.parse_packet(raw, options=a.DecodeOptions(unsupported="raise"))
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
            a.encode_packet_fields,
            a.encode_payload,
            a.serialize_tnc2_line,
        ):
            with self.assertRaises(a.FieldError):
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
    def test_required_fields_and_domain_constraints(self) -> None:
        for build in (
            lambda: a.Position(91, 0),
            lambda: a.Position(0, -181),
            lambda: a.Position(float("nan"), 0),
            lambda: a.Position(True, 0),
            lambda: a.Position(cast(Any, None), 0),
            lambda: a.Header("", "APRS"),
            lambda: a.Hop("WIDE1-1*"),
            lambda: a.Message("", "Hello"),
            lambda: a.Message("W1AW", "x" * 68),
            lambda: a.Acknowledgment("W1AW", ""),
            lambda: a.Status("x" * 63),
            lambda: a.Timestamp("dhm_utc", 12, 30),
            lambda: a.Timestamp("hms_utc", 12, 30),
            lambda: a.Timestamp("mdhm_utc", 12, 30, day=31, month=4),
            lambda: a.Object(
                "", a.Location(49, -72), a.Timestamp("dhm_utc", 12, 30, day=1)
            ),
            lambda: a.Item("a", a.Location(49, -72)),
            lambda: a.Symbol("/", ""),
            lambda: a.Extent((50, 49), (-73, -72)),
            lambda: a.Weather(temperature=a.Measurement(10, "mph")),
            lambda: a.Weather(humidity=a.Measurement(101, "percent")),
            lambda: a.Packet(a.Header("N0CALL", "APRS"), a.Weather()),
            lambda: a.Telemetry(),
            lambda: a.Telemetry((1, 2, 3), (True,), sequence=1),
            lambda: a.GLL(None, "123000", "A"),
            lambda: a.Address(("é", "street", "city", "zip")),
            lambda: a.Grid("not a grid"),
            lambda: a.UserDefined(b"", b"1", b"data"),
            lambda: a.Reserved(256, b"data"),
            lambda: a.Opaque(b""),
            lambda: a.Packet(
                a.Header("N0CALL", "APRS"),
                cast(Any, None),
                original_wire=b"valid-looking evidence",
            ),
        ):
            with self.subTest(build=build), self.assertRaises(a.ModelError):
                build()
        with self.assertRaises(TypeError):
            a.Position(cast(Any, 49))  # type: ignore[call-arg]
        for value in (
            {"type": "position", "latitude_deg": 49},
            {"type": "position", "latitude_deg": 99, "longitude_deg": 0},
            {
                "type": "packet",
                "header": {"source": "N0CALL", "destination": "APRS"},
                "payload": {"type": "position"},
                "original_wire": "N0CALL>APRS:!4903.50N/07201.75W-",
            },
        ):
            with self.assertRaises(a.JSONModelError):
                a.from_json_dict(value)

    def test_evidence_never_overrides_edits_or_missing_fields(self) -> None:
        timestamp = a.Timestamp("dhm_utc", 12, 30, day=17, raw=b"010000z")
        self.assertEqual(encode_timestamp(timestamp), b"171230z")
        packet = a.Packet(
            a.Header("N0CALL", "APRS"),
            a.Status("Edited", timestamp),
            original_wire=b"wrong",
        )
        self.assertEqual(a.serialize_packet(packet), b"N0CALL>APRS:>171230zEdited")
        with self.assertRaises(a.ModelError):
            a.Timestamp("dhm_utc", 12, 30, raw=b"171230z")
        with self.assertRaises(a.ModelError):
            a.Position(49, -72, tail=b"old", comment="edited")
        with self.assertRaises(a.ModelError):
            a.Object("", a.Location(49, -72), timestamp, name_raw=b"VALIDNAME")
        raw = a.Packet(
            a.Header("N0CALL", "APRS"), a.Opaque(b"~new"), original_wire=b"old"
        )
        self.assertEqual(a.serialize_packet(raw), b"N0CALL>APRS:~new")
        position = a.Position(49, -72, tail=b"raw\x00\xff")
        self.assertTrue(a.encode_payload(position).endswith(b"raw\x00\xff"))
        # Defend the serialization boundary even against frozen-dataclass bypasses.
        object.__setattr__(packet.payload, "text", "é")
        with self.assertRaises(a.ModelError):
            a.serialize_packet(packet)
        with self.assertRaises(a.JSONModelError):
            a.to_json(packet)

    def test_genuine_absence_and_unavailable_readings(self) -> None:
        absent = a.Weather()
        unavailable = a.Weather(wind_speed=a.Measurement(None, "mph", b"..."))
        zero = a.Weather(wind_speed=a.Measurement(0, "mph"))
        self.assertNotEqual(absent, unavailable)
        self.assertNotEqual(unavailable, zero)
        self.assertEqual(a.Message("W1AW").message_id, None)
        self.assertEqual(a.Position(49, -72).timestamp, None)
        self.assertEqual(a.GLL(None, "123000", "V").coordinates, None)
        self.assertEqual(dataclasses.replace(unavailable, wind_speed=None), absent)
