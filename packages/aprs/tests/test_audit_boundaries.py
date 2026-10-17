# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Authoritative construction, incomplete repair, and explicitly raw boundaries."""
import copy
import unittest
from typing import Any, cast

from hamkit import aprs as a


class AuditBoundaryTests(unittest.TestCase):
    def test_storm_and_telemetry_container_invariants(self) -> None:
        storm = a.Storm("HC", False, 80, 100, 990, 20, 50)
        extensions = a.Extensions(motion=a.Motion(90, 10), storm=storm)
        for symbol in (a.Symbol("/", "@"), a.Symbol("/", "-")):
            with self.assertRaises(a.ModelError):
                a.Position(1, 2, symbol, extensions=extensions)
            with self.assertRaises(a.JSONModelError):
                a.from_json_dict(
                    {
                        "type": "position",
                        "latitude_deg": 1,
                        "longitude_deg": 2,
                        "symbol": a.to_json_dict(symbol),
                        "extensions": a.to_json_dict(extensions),
                    }
                )
        with self.assertRaises(a.ModelError):
            a.Location(1, 2, a.Symbol("\\", "@"), extensions=a.Extensions(storm=storm))
        position = a.Position(1, 2, a.Symbol("\\", "@"), extensions=extensions)
        self.assertEqual(a.from_json(a.to_json(position)), position)
        with self.assertRaises(a.CodecNotImplemented):
            a.encode_payload(position)
        for telemetry in (
            a.Telemetry((1, 2), encoding="mic_e_hex"),
            a.Telemetry((1,), sequence=1, encoding="base91_comment"),
        ):
            with self.assertRaises(a.ModelError):
                a.Packet(a.Header("W1AW", "APRS"), telemetry)
            with self.assertRaises(a.JSONModelError):
                a.from_json_dict(
                    {
                        "type": "packet",
                        "header": {"source": "W1AW", "destination": "APRS"},
                        "payload": a.to_json_dict(telemetry),
                    }
                )
        classic = a.Telemetry((1,) * 5, (True,) * 8, sequence=1)
        with self.assertRaises(a.ModelError):
            a.Position(
                1, 2, a.Symbol("/", "-"), extensions=a.Extensions(telemetry=classic)
            )

    def test_plain_position_comment_bounds(self) -> None:
        for comment in ("x" * 44, "raw|comment", "~"):
            with self.assertRaises(a.ModelError):
                a.Position(1, 2, a.Symbol("/", "-"), comment=comment)
            with self.assertRaises(a.JSONModelError):
                a.from_json_dict(
                    {
                        "type": "position",
                        "latitude_deg": 1,
                        "longitude_deg": 2,
                        "symbol": {"table_id": "/", "code": "-"},
                        "comment": comment,
                    }
                )
        value = a.Position(1, 2, a.Symbol("/", "-"), comment="x" * 43)
        self.assertTrue(a.encode_payload(value).endswith(b"x" * 43))
        # Unsliced wire suffix is explicit raw content, not parsed plain text.
        self.assertTrue(
            a.encode_payload(
                a.Position(1, 2, a.Symbol("/", "-"), tail=b"|raw|")
            ).endswith(b"|raw|")
        )

    def test_recovered_missing_facts_require_explicit_repair(self) -> None:
        for raw, patch in (
            (
                b"W1AW>APRS:!4903.50N/07201.75W",
                {"symbol": {"table_id": "/", "code": "-"}},
            ),
            (b"W1AW>APRS:>bad\xff", {"text": "repaired"}),
            (b"W1AW>APRS::N0CALL   :bad\xff", {"text": "repaired"}),
            (b"W1AW>APRS::N0CALL   :hello{\xff", {"message_id": "01"}),
        ):
            with self.subTest(raw=raw):
                result = a.parse_packet(raw)
                assert isinstance(result, a.Malformed)
                self.assertEqual(result.original_wire, raw)
                with self.assertRaises(a.JSONModelError):
                    a.from_json_dict(result.recovered)
                fixed = copy.deepcopy(cast(dict[str, Any], result.recovered))
                fixed["payload"].update(patch)
                packet = a.from_json_dict(fixed, expected_type=a.Packet)
                self.assertIsInstance(
                    a.parse_packet(a.serialize_packet(packet)), a.Packet
                )
                self.assertEqual(a.from_json(a.to_json(result)), result)

    def test_required_facts_are_not_authoring_defaults(self) -> None:
        for model, args, data in (
            (a.Symbol, (), {"type": "symbol", "table_id": "/"}),
            (
                a.Position,
                (1, 2),
                {"type": "position", "latitude_deg": 1, "longitude_deg": 2},
            ),
            (
                a.Location,
                (1, 2),
                {"type": "location", "latitude_deg": 1, "longitude_deg": 2},
            ),
            (a.Status, (), {"type": "status"}),
            (a.Message, ("W1AW",), {"type": "message", "addressee": "W1AW"}),
        ):
            with self.subTest(model=model):
                with self.assertRaises(TypeError):
                    cast(Any, model)(*args)
                with self.assertRaises(a.JSONModelError):
                    a.from_json_dict(data)
        for payload in (a.Status(""), a.Message("W1AW", "")):
            self.assertEqual(a.decode_payload(a.encode_payload(payload)), payload)

    def test_reserved_identifier_is_not_an_assigned_family(self) -> None:
        for dti in (ord(">"), ord("!"), ord("T"), ord("~"), 0, 255):
            with self.subTest(dti=dti):
                with self.assertRaises(a.ModelError):
                    a.Reserved(dti, b"hello")
                with self.assertRaises(a.JSONModelError):
                    a.from_json_dict({"type": "reserved", "dti": dti, "data": "hello"})
        for dti in b'"&(+.-\\]^':
            payload = a.Reserved(dti, b"hello")
            self.assertEqual(a.encode_payload(payload), bytes([dti]) + b"hello")
            self.assertEqual(a.from_json(a.to_json(payload)), payload)
        self.assertEqual(a.encode_payload(a.Opaque(b"~raw")), b"~raw")
        payload = a.Reserved(ord("&"), b"hello")
        object.__setattr__(payload, "dti", ord(">"))
        with self.assertRaises(a.ModelError):
            a.encode_payload(payload)

    def test_raw_and_historical_contexts(self) -> None:
        pos = a.Position(1, 2, a.Symbol("/", "-"))
        for model, args, data in (
            (
                a.RawWeather,
                ("ultw", b">hi"),
                {"type": "raw_weather", "format": "ultw", "information": ">hi"},
            ),
            (
                a.LegacyPosition,
                (b"x" * 40, pos),
                {
                    "type": "legacy_position",
                    "prefix": "x" * 40,
                    "position": a.to_json_dict(pos),
                },
            ),
            (a.Beacon, ("",), {"type": "beacon", "text": ""}),
        ):
            with self.subTest(model=model):
                with self.assertRaises(a.ModelError):
                    cast(Any, model)(*args)
                with self.assertRaises(a.JSONModelError):
                    a.from_json_dict(data)
        for field in (
            {"messaging": True},
            {"timestamp": a.Timestamp("hms_utc", 0, 0, second=0)},
        ):
            with self.assertRaises(a.ModelError):
                a.LegacyPosition(b"X1J", a.Position(1, 2, a.Symbol("/", "-"), **field))
        for value in (
            a.LegacyPosition(b"X1J ", pos),
            a.RawWeather("ultw", b"$ULTW0000"),
        ):
            self.assertEqual(a.from_json(a.to_json(value)), value)
            with self.assertRaises(a.CodecNotImplemented):
                a.encode_payload(value)
        with self.assertRaises(a.ModelError):
            a.Opaque(b">hi", diagnostic=a.Diagnostic("malformed", "bad"))

    def test_header_interpretations_are_consistent(self) -> None:
        for fields in ({"destination_ssid_route": 999}, {"q_construct": "nonsense"}):
            with self.assertRaises(a.ModelError):
                a.HeaderSemantics(**fields)
            with self.assertRaises(a.JSONModelError):
                a.from_json_dict({"type": "header_semantics", **fields})
        semantics = a.HeaderSemantics(destination_ssid_route=1, q_construct="qAR")
        with self.assertRaises(a.ModelError):
            a.Packet(a.Header("W1AW", "APRS"), a.Status(""), header_semantics=semantics)
        header = a.Header("W1AW", "APRS-1", (a.Hop("qAR"), a.Hop("GATE")))
        packet = a.Packet(header, a.Status(""), header_semantics=semantics)
        self.assertEqual(a.from_json(a.to_json(packet)), packet)
        self.assertEqual(a.serialize_packet(packet), b"W1AW>APRS-1,qAR,GATE:>")
