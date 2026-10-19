# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""JSON contracts, independent of the APRS wire codec."""

import dataclasses
import math
import unittest
from typing import Any, cast, get_args

import hamkit.aprs as a
from hamkit.aprs._json import _BY_MODEL, _SCHEMAS
from model_examples import SYMBOL, field_examples, payload_examples

HEADER = a.Header("N0CALL", "APRS")


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
                    # Dataclass equality intentionally ignores received evidence:
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
                    a.Header(
                        "N0CALL",
                        "APRS",
                        (a.Hop("WIDE1-1", True), a.Hop("qAR"), a.Hop("GATE")),
                    ),
                    payload,
                    original_wire=b"archival\x00\xff\r\n",
                    diagnostics=(
                        a.Diagnostic("nonconforming", "example", "$.payload"),
                    ),
                )
            )

    def test_every_structured_field_and_empty_default_model(self) -> None:
        examples = tuple(
            v for v in field_examples() if not isinstance(v, (a.CodecSupport, a.Extent))
        )
        covered = {type(v) for v in (*examples, *payload_examples())}
        self.assertEqual(covered, set(get_args(a.JSONModel)))
        for value in examples:
            self.round_trip(cast(a.JSONModel, value))
        for model in get_args(a.JSONModel):
            if model is not a.Compression and all(
                f.default is not dataclasses.MISSING
                or f.default_factory is not dataclasses.MISSING
                for f in dataclasses.fields(model)
            ):
                self.round_trip(model())

    def test_stable_tags_and_context(self) -> None:
        self.assertEqual(
            a.to_json_dict(a.Status("Ready")), {"type": "status", "text": "Ready"}
        )
        self.assertEqual(
            a.to_json_dict(a.Position(49, -72, SYMBOL)),
            {
                "type": "position",
                "latitude_deg": 49,
                "longitude_deg": -72,
                "symbol": {"table_id": "/", "code": "-"},
            },
        )
        self.assertEqual(
            a.to_json_dict(a.Packet(HEADER, a.Status(""))),
            {
                "type": "packet",
                "header": {"source": "N0CALL", "destination": "APRS"},
                "payload": {"type": "status", "text": ""},
            },
        )
        weather = a.Weather(temperature=a.Measurement(68, "fahrenheit"))
        self.assertEqual(
            a.to_json_dict(weather),
            {"type": "weather", "temperature": {"value": 68, "unit": "fahrenheit"}},
        )
        for value in payload_examples():
            self.assertIsInstance(a.to_json_dict(value)["type"], str)
        self.assertEqual(len({s.tag for s in _SCHEMAS}), len(_SCHEMAS))

    def test_tags_are_needed_only_where_a_field_allows_several_models(self) -> None:
        legacy = a.LegacyPosition(b"X1J ", a.Position(49, -72, SYMBOL))
        encoded = a.to_json_dict(legacy)
        self.assertNotIn("type", cast(dict[str, Any], encoded["position"]))
        tagged = {
            **encoded,
            "position": {
                **cast(dict[str, Any], encoded["position"]),
                "type": "position",
            },
        }
        self.assertEqual(a.from_json_dict(tagged), legacy)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(
                {
                    **encoded,
                    "position": {
                        **cast(dict[str, Any], encoded["position"]),
                        "type": "item",
                    },
                }
            )
        status = a.from_json_dict({"text": "Ready"}, expected_type=a.Status)
        self.assertEqual(status, a.Status("Ready"))

    def test_nested_union_variants(self) -> None:
        for value in field_examples():
            if isinstance(value, get_args(a.NMEASentence)):
                self.round_trip(a.NMEA(value, a.NMEAMetadata("GP")))
            if isinstance(value, get_args(a.TelemetryDefinitionValue)):
                self.round_trip(a.TelemetryDefinition("N0CALL", value))
            if isinstance(value, get_args(a.NTSRecord)):
                self.round_trip(a.Radiogram("W1AW", value))
            if isinstance(value, get_args(a.ResponseValue)):
                self.round_trip(a.Response("W1AW", value))

    def test_bytes_are_latin1_and_text_is_unicode(self) -> None:
        original = a.UserDefined(b"Q", b"1", bytes(range(256)))
        text = a.to_json(original)
        self.assertTrue(text.isascii())
        self.assertIn(r"\u00ff", text)
        self.assertIn(r"\u0000", text)
        self.round_trip(original)
        self.assertEqual(
            a.from_json('{"type":"status","text":"caf\\u00e9 \\u2615"}'),
            a.Status("café ☕"),
        )
        self.round_trip(a.Message("W1AW", "日本語", message_id="1"))
        with self.assertRaises(a.JSONModelError):
            a.from_json('{"type":"status","text":"\\udcff"}')

    def test_null_absent_and_zero(self) -> None:
        absent = a.from_json_dict({"type": "weather"})
        unavailable = a.from_json_dict(
            {"type": "weather", "wind_speed": {"value": None, "unit": "mph"}}
        )
        zero = a.from_json_dict(
            {"type": "weather", "wind_speed": {"value": 0, "unit": "mph"}}
        )
        self.assertEqual(absent, a.Weather())
        self.assertNotEqual(absent, unavailable)
        self.assertNotEqual(unavailable, zero)
        self.assertEqual(
            a.from_json_dict({"type": "status", "text": "Ready", "timestamp": None}),
            a.from_json_dict({"type": "status", "text": "Ready"}),
        )
        self.assertEqual(
            a.to_json_dict(a.Measurement(None, "mph")),
            {"type": "measurement", "value": None, "unit": "mph"},
        )

    def test_typed_sparse_conversion(self) -> None:
        weather: a.Weather = a.from_json('{"type":"weather"}', expected_type=a.Weather)
        self.assertEqual(weather, a.Weather())
        model = a.from_json_dict(
            {
                "type": "object",
                "name": "A",
                "latitude_deg": 49,
                "longitude_deg": -72,
                "symbol": {"table_id": "/", "code": "-"},
                "timestamp": {"kind": "dhm_utc", "hour": 0, "minute": 0, "day": 1},
            }
        )
        self.assertEqual(
            model, a.Object("A", 49, -72, SYMBOL, timestamp=a.Timestamp.dhm(1, 0, 0))
        )

    def test_integers_survive_json_exactly(self) -> None:
        value = a.Calibration(9007199254740993, 0, 0)
        restored = a.from_json(a.to_json(value))
        self.assertEqual(restored, value)
        self.assertIs(type(cast(a.Calibration, restored).a), int)
        self.assertIs(type(a.from_json('{"type":"range","miles":1.5}').miles), float)  # type: ignore[union-attr]

    def test_depth_limits_apply_before_recursion(self) -> None:
        packet = a.Packet(HEADER, a.Status("x"))
        for _ in range(1000):
            packet = a.Packet(HEADER, a.ThirdParty(packet))
        with self.assertRaisesRegex(a.JSONModelError, "nesting limit"):
            a.to_json(packet, max_depth=4)
        malformed = a.Malformed(
            b"bad",
            (a.Diagnostic("malformed", "bad"),),
            {"a": {"b": {"c": {"d": {"e": 1}}}}},
        )
        document = a.to_json_dict(malformed)
        for convert in (
            lambda: a.from_json_dict(document, max_depth=3),
            lambda: a.to_json_dict(malformed, max_depth=3),
        ):
            with self.assertRaisesRegex(a.JSONModelError, r"\$\.recovered\.a\.b\.c"):
                convert()
        self.assertEqual(a.from_json_dict(document, max_depth=6), malformed)

    def test_key_order_does_not_choose_type(self) -> None:
        value = a.to_json_dict(a.Message("W1AW", "Hello"))
        self.assertEqual(
            a.from_json_dict(dict(reversed(list(value.items())))),
            a.from_json_dict(value),
        )

    def test_nested_packets_and_unknown_payload_evidence(self) -> None:
        value = a.Packet(
            HEADER,
            a.Opaque(b"\xff\x00", diagnostic=a.Diagnostic("unsupported", "test")),
        )
        for _ in range(8):
            value = a.Packet(HEADER, a.ThirdParty(value))
        self.round_trip(value)  # JSON depth is independent of the wire depth.
        with self.assertRaises(a.JSONModelError):
            a.to_json(value, max_depth=3)
        with self.assertRaises(a.JSONModelError):
            a.from_json(a.to_json(value), max_depth=3)

    def test_shared_weather_and_telemetry(self) -> None:
        weather = a.Weather(
            wind_direction=a.Measurement(None, "degrees"),
            wind_speed=a.Measurement(None, "mph"),
            gust=a.Measurement(None, "mph"),
            temperature=a.Measurement(None, "fahrenheit", raw=b"..."),
            timestamp=a.Timestamp.mdhm(10, 17, 12, 30),
            comment="weather",
            raw=b"sensor bytes",
        )
        telemetry = a.Telemetry(
            (1, 2, 3, 4, 5), (True,) * 8, sequence="MIC", raw=b"channels", comment="t"
        )
        for model, tag in ((weather, "weather"), (telemetry, "telemetry")):
            self.round_trip(model)
            self.round_trip(a.Packet(HEADER, model))
            self.assertEqual(a.to_json_dict(model)["type"], tag)
        extensions = a.Extensions(
            weather=dataclasses.replace(weather, timestamp=None),
            telemetry=a.Telemetry((1, 2), sequence=1, encoding="base91_comment"),
        )
        self.round_trip(extensions)
        nested = a.to_json_dict(extensions)
        for field in ("weather", "telemetry"):
            self.assertNotIn("type", cast(dict[str, a.JSONValue], nested[field]))
        self.round_trip(a.Position(49, -72, a.Symbol("/", "_"), extensions=extensions))

    def test_json_does_not_require_encodable_header(self) -> None:
        mic_e = a.MicE(
            49,
            -72,
            SYMBOL,
            message="emergency",
            extensions=a.Extensions(motion=a.Motion()),
        )
        self.round_trip(mic_e)
        with self.assertRaises(a.FieldError):
            a.serialize_packet(a.Packet(HEADER, mic_e))


class JSONNegativeTests(unittest.TestCase):
    def test_standalone_objects_require_tag_or_explicit_context(self) -> None:
        for value in ({}, {"raw": "data"}):
            with self.subTest(value=value), self.assertRaises(a.JSONModelError):
                a.from_json_dict(value)

    def test_conflicts_unknown_keys_and_missing_required_fields(self) -> None:
        values: tuple[dict[str, object], ...] = (
            {"status_text": "Ready", "message_text": "Hello", "addressee": "W1AW"},
            {"type": "status", "text": "Ready", "typo": True},
            {"type": "message"},
            {"type": "weather", "temperature": {"value": 1}},
            {
                "type": "weather",
                "temperature": {"type": "symbol", "value": 1, "unit": "celsius"},
            },
            {"type": "position", "latitude_deg": 1},
            {"type": "Status", "text": "Ready"},
            {"type": "position", "latitude_deg": 1, "longitude_deg": 2, "tail": ""},
            {
                "header": {"source": "N0CALL", "destination": "APRS"},
                "payload": {"type": "status", "text": "Ready"},
                "information": ">Ready",
            },
            {"unit": "mph"},
        )
        for value in values:
            with self.subTest(value=value), self.assertRaises(a.JSONModelError):
                a.from_json_dict(value)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict({"message_text": "Hello"}, expected_type=a.Status)

    def test_invalid_scalars_enums_nulls_and_arrays(self) -> None:
        cases = (
            ({"addressee": "☃", "text": ""}, a.Message),
            ({"text": [65]}, a.Status),
            ({"addressee": None}, a.Message),
            ({"latitude_deg": True, "longitude_deg": 0}, a.Coordinates),
            ({"latitude_deg": "49", "longitude_deg": 0}, a.Coordinates),
            ({"dti": 1.0, "data": ""}, a.Reserved),
            (
                {
                    "latitude_deg": 1,
                    "longitude_deg": 2,
                    "symbol": {"table_id": "/", "code": "-"},
                    "messaging": 0,
                },
                a.Position,
            ),
            ({"kind": "UTC", "hour": 0, "minute": 0}, a.Timestamp),
            ({"value": 1, "unit": "furlongs"}, a.Measurement),
            ({"lines": ["one", "two"]}, a.NTSAddress),
            ({"analog": [True]}, a.Telemetry),
            ({"digital": [1]}, a.Telemetry),
            ({"line": True, "text": "one"}, a.NTSText),
            ({"table_id": "/", "code": "-"}, a.Status),
        )
        for value, expected in cases:
            with self.subTest(value=value), self.assertRaises(a.JSONModelError):
                a.from_json_dict(
                    {"type": _BY_MODEL[expected].tag, **value}, expected_type=expected
                )

    def test_duplicate_nonfinite_and_malformed_json(self) -> None:
        for text in (
            '{"status_text":"A","status_text":"B"}',
            '{"weather":{"wind_speed":null,"wind_speed":null}}',
            '{"value":NaN,"unit":"mph"}',
            '{"value":Infinity,"unit":"mph"}',
            '{"type":"measurement","value":1e999,"unit":"mph"}',
            "[]",
            "null",
            '"Ready"',
            "{",
            '{"status_text":"A",}',
        ):
            with self.subTest(text=text), self.assertRaises(a.JSONModelError):
                a.from_json(text)
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(a.ModelError):
                a.Measurement(value, "mph")

    def test_invalid_python_models_are_not_coerced(self) -> None:
        for build in (
            lambda: a.Status(cast(Any, b"Hello")),
            lambda: a.Position(True, 0, SYMBOL),
            lambda: a.Message("W1AW", "", message_id=cast(Any, 1)),
            lambda: a.Telemetry(digital=cast(Any, (1,))),
            lambda: a.Hop("D1", repeated=cast(Any, 1)),
            lambda: a.Header("N0CALL", "APRS", cast(Any, [a.Hop("WIDE1-1")])),
        ):
            with self.assertRaises(a.ModelError):
                build()

    def test_payload_union_does_not_accept_arbitrary_field_models(self) -> None:
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(
                {
                    "header": {"source": "N0CALL", "destination": "APRS"},
                    "payload": {"value": 1, "unit": "mph"},
                }
            )
        with self.assertRaises(a.JSONModelError):
            a.to_json(cast(a.JSONModel, a.codec_support_for(a.MicE)))

    def test_nested_union_tags_and_incompatible_tags(self) -> None:
        variants = (
            (a.TelemetryDefinition("N0CALL", a.TelemetryUnits(("V",))), "definition"),
            (a.NMEA(a.VTG(), a.NMEAMetadata("GP")), "sentence"),
            (a.Radiogram("W1AW", a.NTSText(1, "Hello")), "record"),
            (a.Response("W1AW", a.DirectStations(("N0CALL",))), "response"),
            (a.Packet(HEADER, a.Status("")), "payload"),
        )
        for model, key in variants:
            encoded = a.to_json_dict(model)
            nested = cast(dict[str, a.JSONValue], encoded[key])
            self.assertIn("type", nested)
            for bad in (None, 1, "Status", "unknown", "measurement"):
                altered = dict(nested)
                if bad is None:
                    del altered["type"]
                else:
                    altered["type"] = bad
                with self.subTest(model=type(model), tag=bad), self.assertRaises(
                    a.JSONModelError
                ):
                    a.from_json_dict({**encoded, key: altered})
        with self.assertRaisesRegex(a.JSONModelError, "incompatible"):
            a.from_json_dict({"type": "symbol"}, expected_type=a.Weather)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict({"type": "weather", "weather": {}})
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(
                {
                    "type": "packet",
                    "header": {"type": "symbol"},
                    "payload": {"type": "status", "text": ""},
                }
            )

    def test_cycles_and_excessive_depth_fail_cleanly(self) -> None:
        packet = a.Packet(HEADER, a.Status(""))
        object.__setattr__(packet, "payload", a.ThirdParty(packet))
        with self.assertRaises(a.JSONModelError):
            a.to_json(packet)
        with self.assertRaises(a.JSONModelError):
            a.from_json("[" * 2000 + "0" + "]" * 2000)
        with self.assertRaises(ValueError):
            a.from_json("{}", max_depth=0)
