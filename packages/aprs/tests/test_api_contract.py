# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import dataclasses
import importlib
import unittest
from typing import Any, cast, get_args, get_type_hints

import hamkit.aprs as a
from model_examples import SYMBOL, field_examples, payload_examples

HEADER = a.Header("N0CALL", "APRS")


class ModelContractTests(unittest.TestCase):
    def test_every_payload_has_construction_and_codec_example(self) -> None:
        examples = payload_examples()
        self.assertEqual({type(p) for p in examples}, set(get_args(a.Payload)))
        self.assertEqual({c.model for c in a.codec_support()}, set(get_args(a.Payload)))
        for payload in examples:
            with self.subTest(model=type(payload).__name__):
                packet = a.Packet(HEADER, payload)
                self.assertIs(packet.payload, payload)
                self.assertEqual(a.check_packet(packet), ())
                if a.codec_support_for(payload).encode == "unimplemented":
                    with self.assertRaises(a.CodecNotImplementedError):
                        a.serialize_packet(packet)
                else:
                    self.assertIsInstance(a.serialize_packet(packet), bytes)

    def test_every_public_dataclass_has_an_example(self) -> None:
        public = {
            getattr(a, name)
            for name in a.__all__
            if isinstance(getattr(a, name), type)
            and dataclasses.is_dataclass(getattr(a, name))
        }
        self.assertEqual(
            {type(v) for v in (*field_examples(), *payload_examples())}, public
        )

    def test_public_annotations_resolve(self) -> None:
        for name in a.__all__:
            value = getattr(a, name)
            if isinstance(value, type) and dataclasses.is_dataclass(value):
                with self.subTest(model=name):
                    self.assertIsInstance(get_type_hints(value), dict)

    def test_implementation_modules_are_private(self) -> None:
        for module in ("codec", "models", "data", "json", "fields", "errors"):
            with self.subTest(module=module), self.assertRaises(ImportError):
                importlib.import_module(f"hamkit.aprs.{module}")
        for old in (
            "Location",
            "Ambiguity",
            "ReplyAck",
            "Units",
            "Parameters",
            "Definition",
            "Address",
            "Text",
            "Path",
            "HeaderSemantics",
            "EncodedPacketFields",
            "DecodeOptions",
            "EncodeOptions",
            "get_capabilities",
            "encode_payload",
            "decode_payload",
        ):
            self.assertFalse(hasattr(a, old), old)

    def test_optional_fields_are_keyword_only(self) -> None:
        with self.assertRaises(TypeError):
            cast(Any, a.Position)(49, -72, SYMBOL, "comment")
        with self.assertRaises(TypeError):
            cast(Any, a.Message)("W1AW", "Hello", "003")
        with self.assertRaises(TypeError):
            cast(Any, a.Weather)(a.Measurement(1, "degrees"))

    def test_derived_values_are_properties(self) -> None:
        grid = a.Grid("AA00")
        self.assertEqual(grid.bounds, a.Extent((-90, -89), (-180, -178)))
        self.assertEqual(grid.center, a.Coordinates(-89.5, -179))
        csT = a.Compression(fix="current", nmea_source="RMC", origin_code=2)
        self.assertEqual(csT.type_value, 58)
        self.assertIsNone(a.Compression(ignored=True).type_value)
        bearing = a.Bearing(90, 9, 4, 7)
        self.assertTrue(bearing.manual)
        self.assertEqual(bearing.range_miles, 16)
        area = a.Area(0, 3, 10, 10)
        self.assertAlmostEqual(area.latitude_offset_deg, 100 / 1500)
        self.assertEqual(area.transmitted_anchor, "circle_center")
        phg = a.PHG(25, 80, 3)
        self.assertAlmostEqual(phg.display_radius_miles, phg.range_miles / 2)
        self.assertTrue(a.Bulletin("A", "News").announcement)
        self.assertFalse(a.Bulletin("1", "News").announcement)
        position = a.Position(49.05, -72.02, SYMBOL, ambiguity=2)
        extent = position.ambiguity_extent
        assert extent is not None
        self.assertAlmostEqual(extent.latitude[0], 49 + 3 / 60)
        self.assertAlmostEqual(extent.latitude[1], 49 + 4 / 60)
        self.assertAlmostEqual(extent.longitude[0], -(72 + 2 / 60))
        self.assertIsNone(a.Position(49, -72, SYMBOL).ambiguity_extent)
        south_west = a.Position(-0.0, -0.0, SYMBOL, ambiguity=4).ambiguity_extent
        self.assertEqual(south_west, a.Extent((-1.0, -0.0), (-1.0, -0.0)))
        self.assertEqual(
            a.Position(0.0, 0.0, SYMBOL, ambiguity=4).ambiguity_extent,
            a.Extent((0.0, 1.0), (0.0, 1.0)),
        )
        self.assertEqual(position.coordinates, a.Coordinates(49.05, -72.02))
        self.assertEqual(a.Symbol("c", "-").overlay, "2")
        self.assertEqual(a.Symbol("\\", "-").table, "alternate")

    def test_evidence_is_kept_but_ignored_by_equality(self) -> None:
        self.assertEqual(a.Measurement(0, "mph", raw=b"000"), a.Measurement(0, "mph"))
        self.assertNotIn("raw", repr(a.Measurement(0, "mph", raw=b"000")))
        packet = a.Packet(HEADER, a.Status("Ready"), original_wire=b"old")
        self.assertEqual(packet, a.Packet(HEADER, a.Status("Ready")))

    def test_subclasses_are_rejected_consistently(self) -> None:
        subclass = type("MyStatus", (a.Status,), {})
        packet = a.Packet(HEADER, subclass("x"))
        for convert in (a.serialize_packet, a.check_packet, a.to_json):
            with self.subTest(convert=convert), self.assertRaisesRegex(
                a.APRSError, "subclasses of APRS models are not supported"
            ):
                convert(packet)

    def test_header_text(self) -> None:
        header = a.Header.parse("N0CALL>APRS,WIDE1-1*,WIDE2-1")
        self.assertEqual(
            header,
            a.Header("N0CALL", "APRS", (a.Hop("WIDE1-1", True), a.Hop("WIDE2-1"))),
        )
        self.assertEqual(str(header), "N0CALL>APRS,WIDE1-1*,WIDE2-1")
        with self.assertRaises(a.EnvelopeError):
            a.Header.parse("N0CALL")

    def test_timestamp_constructors(self) -> None:
        self.assertEqual(
            a.Timestamp.dhm(9, 23, 45), a.Timestamp("dhm_utc", 23, 45, day=9)
        )
        self.assertEqual(a.Timestamp.dhm(9, 23, 45, local=True).kind, "dhm_local")
        self.assertEqual(
            a.Timestamp.hms(1, 2, 3), a.Timestamp("hms_utc", 1, 2, second=3)
        )
        self.assertEqual(
            a.Timestamp.mdhm(10, 17, 12, 30),
            a.Timestamp("mdhm_utc", 12, 30, day=17, month=10),
        )

    def test_nested_defined_variants_are_constructible(self) -> None:
        for value in field_examples():
            if isinstance(value, get_args(a.TelemetryDefinitionValue)):
                definition = a.TelemetryDefinition("N0CALL", value)
                self.assertIs(definition.definition, value)
            if isinstance(value, get_args(a.NTSRecord)):
                self.assertIs(a.Radiogram("W1AW", value).record, value)
            if isinstance(value, get_args(a.NMEASentence)):
                self.assertIs(a.NMEA(value, a.NMEAMetadata("GP")).sentence, value)
            if isinstance(value, get_args(a.ResponseValue)):
                self.assertIs(a.Response("W1AW", value).response, value)

    def test_missing_is_not_unavailable_or_zero(self) -> None:
        absent = a.Weather()
        unavailable = a.Weather(wind_speed=a.Measurement(None, "mph"))
        zero = a.Weather(wind_speed=a.Measurement(0, "mph"))
        self.assertNotEqual(absent, unavailable)
        self.assertNotEqual(unavailable, zero)
        self.assertNotEqual(absent, zero)

    def test_mic_e_requires_context(self) -> None:
        with self.assertRaises(a.ContextRequiredError):
            a.parse_payload(b"`12345678")
        mic_e = a.MicE(
            49,
            -72,
            SYMBOL,
            message="off_duty",
            extensions=a.Extensions(motion=a.Motion()),
        )
        with self.assertRaises(a.ContextRequiredError):
            a.serialize_payload(mic_e)
        with self.assertRaises(a.CodecNotImplementedError):
            a.serialize_packet(a.Packet(HEADER, mic_e))
        with self.assertRaises(a.CodecNotImplementedError):
            a.parse_payload(
                b"`12345678",
                header=a.Header("N0CALL", "490S5P"),
                unsupported="raise",
            )
        parsed = a.parse_packet(b"N0CALL>490S5P:`12345678")
        assert isinstance(parsed, a.Packet)
        self.assertEqual(parsed.header.destination, "490S5P")
        self.assertIsInstance(parsed.payload, a.Opaque)

    def test_option_values_are_checked(self) -> None:
        for kwargs in (
            {"profile": "radio"},
            {"unsupported": "ignore"},
            {"malformed": "opaque"},
            {"max_third_party_depth": -1},
            {"max_third_party_depth": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                a.parse_packet(b"N0CALL>APRS:>Ready", **cast(Any, kwargs))
        with self.assertRaises(TypeError):
            a.parse_packet(cast(Any, "N0CALL>APRS:>Ready"))
