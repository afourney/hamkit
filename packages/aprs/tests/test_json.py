# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""JSON contracts are independent of partial APRS wire codec support."""

import dataclasses
import math
import unittest
from typing import Any, cast, get_args

import hamkit.aprs as a
from model_examples import field_examples, payload_examples


class JSONRoundTripTests(unittest.TestCase):
    def round_trip(self, value: a.JSONModel) -> None:
        for include_defaults in (False, True):
            with self.subTest(model=type(value).__name__, defaults=include_defaults):
                encoded = a.to_json_dict(value, include_defaults=include_defaults)
                for decoded in (
                    a.from_json_dict(encoded),
                    a.from_json(a.to_json(value, include_defaults=include_defaults)),
                ):
                    self.assertIs(type(decoded), type(value))
                    self.assertEqual(decoded, value)
                    # Dataclass equality intentionally ignores archival metadata:
                    # verify those fields survive too, not just semantic equality.
                    self.assertEqual(
                        dataclasses.asdict(decoded), dataclasses.asdict(value)
                    )
                    self.assertEqual(
                        a.to_json_dict(decoded, include_defaults=include_defaults),
                        encoded,
                    )

    def test_every_payload_and_full_packet(self) -> None:
        examples = payload_examples()
        self.assertEqual({type(p) for p in examples}, set(get_args(a.Payload)))
        for payload in examples:
            self.round_trip(payload)
            self.round_trip(
                a.Packet(
                    a.Header("N0CALL", "APRS", (a.PathHop("WIDE1-1", True),)),
                    payload,
                    original_wire=b"archival\x00\xff\r\n",
                    header_semantics=a.HeaderSemantics(q_construct="qAR"),
                )
            )

    def test_every_structured_field_and_empty_default_model(self) -> None:
        examples = tuple(
            v for v in field_examples() if not isinstance(v, a.CodecCapability)
        )
        covered = {type(v) for v in (*examples, *payload_examples())}
        self.assertEqual(covered, set(get_args(a.JSONModel)))
        for value in examples:
            self.round_trip(cast(a.JSONModel, value))
        for model in get_args(a.JSONModel):
            if all(
                f.default is not dataclasses.MISSING
                or f.default_factory is not dataclasses.MISSING
                for f in dataclasses.fields(model)
            ):
                self.round_trip(model())

    def test_stable_domain_shapes_without_tags(self) -> None:
        self.assertEqual(a.to_json_dict(a.Status(b"Ready")), {"status_text": "Ready"})
        self.assertEqual(
            a.to_json_dict(a.Message("W1AW", b"Hello", "003")),
            {"addressee": "W1AW", "message_text": "Hello", "message_id": "003"},
        )
        self.assertEqual(
            a.to_json_dict(a.Position(49, -72)),
            {"latitude_deg": 49, "longitude_deg": -72, "messaging": False},
        )
        self.assertEqual(
            a.to_json_dict(a.Coordinates(49, -72)),
            {"latitude_deg": 49, "longitude_deg": -72},
        )
        self.assertEqual(
            a.to_json_dict(a.TelemetryParameters(("Temp", None))),
            {"channel_names": ["Temp", None]},
        )
        self.assertEqual(
            a.to_json_dict(a.TelemetryUnits(("deg.C", None))),
            {"channel_units": ["deg.C", None]},
        )

        def no_tags(value: object) -> None:
            if isinstance(value, dict):
                self.assertFalse(
                    set(value) & {"type", "__type__", "model", "class", "$type"}
                )
                for child in value.values():
                    no_tags(child)
            elif isinstance(value, list):
                for child in value:
                    no_tags(child)

        for value in payload_examples():
            no_tags(a.to_json_dict(value, include_defaults=True))

    def test_nested_union_variants(self) -> None:
        for value in field_examples():
            if isinstance(value, get_args(a.NMEASentence)):
                self.round_trip(a.NMEAReport(value))
            if isinstance(value, get_args(a.TelemetryDefinitionData)):
                self.round_trip(a.TelemetryDefinition("N0CALL", value))
            if isinstance(value, get_args(a.NTSRecord)):
                self.round_trip(a.NTSMessage("W1AW", value))
            if isinstance(value, get_args(a.QueryResponseData)):
                self.round_trip(a.QueryResponse("W1AW", value))

    def test_bytes_are_reversible_latin1_strings(self) -> None:
        original = a.UserDefined(b"Q", b"1", bytes(range(256)))
        text = a.to_json(original)
        self.assertTrue(text.isascii())
        self.assertIn(r"\u00ff", text)
        self.assertIn(r"\u0000", text)
        self.round_trip(original)
        self.assertEqual(a.from_json('{"status_text":"\\u00e9"}'), a.Status(b"\xe9"))

    def test_null_absent_and_zero(self) -> None:
        absent = a.from_json_dict({"weather": {}})
        unavailable = a.from_json_dict(
            {"weather": {"wind_speed": {"value": None, "unit": "mph"}}}
        )
        zero = a.from_json_dict(
            {"weather": {"wind_speed": {"value": 0, "unit": "mph"}}}
        )
        self.assertIsInstance(absent, a.WeatherReport)
        self.assertEqual(absent, a.WeatherReport(a.Weather()))
        self.assertNotEqual(absent, unavailable)
        self.assertNotEqual(unavailable, zero)
        self.assertEqual(
            a.from_json_dict({"status_text": "Ready", "timestamp": None}),
            a.from_json_dict({"status_text": "Ready"}),
        )
        self.assertEqual(
            a.to_json_dict(a.Measurement(None, "mph")), {"value": None, "unit": "mph"}
        )

    def test_typed_sparse_conversion_and_context(self) -> None:
        weather: a.Weather = a.from_json("{}", expected_type=a.Weather)
        self.assertEqual(weather, a.Weather())
        position: a.Position = a.from_json_dict(
            {"latitude_deg": 49, "longitude_deg": -72}, expected_type=a.Position
        )
        self.assertEqual(position, a.Position(49, -72))
        # Within an object, its declared location type supplies the symbol default.
        model = a.from_json_dict(
            {
                "object_name": "A",
                "position": {"latitude_deg": 49, "longitude_deg": -72},
                "timestamp": {
                    "timestamp_format": "dhm_utc",
                    "hour": 0,
                    "minute": 0,
                    "day": 1,
                },
            }
        )
        self.assertIsInstance(model, a.ObjectReport)

    def test_key_order_does_not_choose_type(self) -> None:
        value = a.to_json_dict(a.Message("W1AW", b"Hello"))
        self.assertEqual(
            a.from_json_dict(dict(reversed(list(value.items())))),
            a.from_json_dict(value),
        )

    def test_nested_packets_and_unknown_payload_evidence(self) -> None:
        value = a.Packet(
            a.Header("N0CALL", "APRS"),
            a.Opaque(
                b"\xff\x00", "unsupported vendor", a.Diagnostic("unsupported", "test")
            ),
        )
        for _ in range(8):
            value = a.Packet(a.Header("N0CALL", "APRS"), a.ThirdParty(value))
        self.round_trip(value)  # JSON depth is independent of wire max_depth=4.
        with self.assertRaises(a.JSONModelError):
            a.to_json(value, max_depth=3)
        with self.assertRaises(a.JSONModelError):
            a.from_json(a.to_json(value), max_depth=3)

    def test_json_does_not_require_working_wire_codec(self) -> None:
        mic_e = a.MicE(a.Location(49, -72), (True, False, True))
        self.round_trip(mic_e)
        with self.assertRaises(a.CodecNotImplemented):
            a.serialize_packet(a.Packet(a.Header("N0CALL", "APRS"), mic_e))


class JSONNegativeTests(unittest.TestCase):
    def test_ambiguous_sparse_objects(self) -> None:
        for value in ({}, {"raw": "data"}):
            with self.subTest(value=value), self.assertRaises(a.AmbiguousJSONError):
                a.from_json_dict(value)

    def test_conflicts_unknown_keys_and_missing_required_fields(self) -> None:
        values: tuple[dict[str, object], ...] = (
            {"status_text": "Ready", "message_text": "Hello", "addressee": "W1AW"},
            {"channel_names": [], "channel_units": []},
            {"object_name": "A", "item_name": "B"},
            {"status_text": "Ready", "typo": True},
            {"type": "Status", "status_text": "Ready"},
            {
                "header": {"source": "N0CALL", "destination": "APRS"},
                "payload": {"status_text": "Ready"},
                "information": ">Ready",
            },
            {"unit": "mph"},
        )
        for value in values:
            with self.subTest(value=value), self.assertRaises(a.JSONModelError):
                a.from_json_dict(value)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict({"text": "Ready"}, expected_type=a.Status)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict({"message_text": "Hello"}, expected_type=a.Status)

    def test_invalid_scalars_enums_nulls_and_arrays(self) -> None:
        cases = (
            ({"status_text": "\u2603"}, a.Status),
            ({"status_text": [65]}, a.Status),
            ({"addressee": None}, a.Message),
            ({"latitude_deg": True, "longitude_deg": 0}, a.Coordinates),
            ({"latitude_deg": "49", "longitude_deg": 0}, a.Coordinates),
            ({"dti": 1.0, "data": ""}, a.Reserved),
            ({"latitude_deg": 1, "longitude_deg": 2, "messaging": 0}, a.Position),
            ({"timestamp_format": "UTC", "hour": 0, "minute": 0}, a.Timestamp),
            ({"value": 1, "unit": "furlongs"}, a.Measurement),
            ({"address_lines": ["one", "two"]}, a.NTSAddress),
            ({"analog": [True]}, a.TelemetryData),
            ({"digital": [1]}, a.TelemetryData),
            ({"line": True, "line_text": "one"}, a.NTSText),
            ({"table_id": "/", "code": "-"}, a.Status),
        )
        for value, expected in cases:
            with self.subTest(value=value), self.assertRaises(a.JSONModelError):
                a.from_json_dict(value, expected_type=expected)

    def test_duplicate_nonfinite_and_malformed_json(self) -> None:
        for text in (
            '{"status_text":"A","status_text":"B"}',
            '{"weather":{"wind_speed":null,"wind_speed":null}}',
            '{"value":NaN,"unit":"mph"}',
            '{"value":Infinity,"unit":"mph"}',
            '{"value":1e999,"unit":"mph"}',
            "[]",
            "null",
            '"Ready"',
            "{",
            '{"status_text":"A",}',
        ):
            with self.subTest(text=text), self.assertRaises(a.JSONModelError):
                a.from_json(text)
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(a.JSONModelError):
                a.to_json(a.Measurement(value, "mph"))

    def test_invalid_python_models_are_not_coerced(self) -> None:
        for value in (
            a.Status(cast(Any, "Hello")),
            a.Position(True, 0),
            a.Message("W1AW", message_id=cast(Any, 1)),
            a.TelemetryData(digital=cast(Any, (1,))),
            a.PathHop("D1", repeated=cast(Any, 1)),
        ):
            with self.subTest(value=value), self.assertRaises(a.JSONModelError):
                a.to_json(value)

    def test_payload_union_does_not_accept_arbitrary_field_models(self) -> None:
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(
                {
                    "header": {"source": "N0CALL", "destination": "APRS"},
                    "payload": {"value": 1, "unit": "mph"},
                }
            )
        with self.assertRaises(a.JSONModelError):
            a.to_json(cast(a.JSONModel, a.capability_for(a.MicE)))

    def test_cycles_and_excessive_depth_fail_cleanly(self) -> None:
        packet = a.Packet(a.Header("N0CALL", "APRS"), a.Status())
        object.__setattr__(packet, "payload", a.ThirdParty(packet))
        with self.assertRaises(a.JSONModelError):
            a.to_json(packet)
        with self.assertRaises(a.JSONModelError):
            a.from_json("[" * 2000 + "0" + "]" * 2000)
        with self.assertRaises(ValueError):
            a.from_json("{}", max_depth=0)
