# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import dataclasses
import unittest
from typing import get_args, get_type_hints

import hamkit.aprs as a
from model_examples import field_examples, payload_examples


class ModelContractTests(unittest.TestCase):
    def test_every_payload_has_construction_and_capability_example(self) -> None:
        examples = payload_examples()
        self.assertEqual({type(p) for p in examples}, set(get_args(a.Payload)))
        self.assertEqual(
            {c.model for c in a.get_capabilities()}, set(get_args(a.Payload))
        )
        header = a.Header("N0CALL", "APRS")
        for payload in examples:
            with self.subTest(model=type(payload).__name__):
                self.assertIs(a.Packet(header, payload).payload, payload)
                capability = a.capability_for(payload)
                if capability.encode == "unimplemented":
                    with self.assertRaises(a.CodecNotImplemented):
                        a.encode_packet_fields(a.Packet(header, payload))
                    with self.assertRaises(a.CodecNotImplemented):
                        a.serialize_packet(a.Packet(header, payload))
                else:
                    self.assertIsInstance(
                        a.serialize_packet(a.Packet(header, payload)), bytes
                    )

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

    def test_optional_components_are_not_silently_dropped(self) -> None:
        values: tuple[a.Payload, ...] = (
            a.Position(
                49,
                -72,
                encoding="compressed",
                compression=a.Compression(0, "old", "other", 0),
            ),
            a.Position(49, -72, ambiguity=a.Ambiguity(1)),
            a.Position(49, -72, extensions=a.Extensions(motion=a.Motion(90, 10))),
            a.Status(grid=a.Grid("IO91SX")),
            a.Message("W1AW", b"Reply", reply_ack=a.ReplyAck("01", "02")),
            a.Acknowledgment("W1AW", "01", reply_ack=a.ReplyAck("01", "02")),
        )
        for value in values:
            with self.subTest(model=value), self.assertRaises(a.CodecNotImplemented):
                a.encode_payload(value)

    def test_nested_defined_variants_are_constructible(self) -> None:
        for value in field_examples():
            if isinstance(value, get_args(a.DefinitionValue)):
                self.assertIs(a.Definition("N0CALL", value).definition, value)
            if isinstance(value, get_args(a.NTSRecord)):
                self.assertIs(a.Radiogram("W1AW", value).record, value)
            if isinstance(value, get_args(a.NMEASentence)):
                self.assertIs(a.NMEA(value).sentence, value)
            if isinstance(value, get_args(a.ResponseValue)):
                self.assertIs(a.Response("W1AW", value).response, value)

    def test_missing_is_not_unavailable_or_zero(self) -> None:
        absent = a.Weather()
        unavailable = a.Weather(wind_speed=a.Measurement(None, "mph", b"..."))
        zero = a.Weather(wind_speed=a.Measurement(0, "mph", b"000"))
        self.assertNotEqual(absent, unavailable)
        self.assertNotEqual(unavailable, zero)
        self.assertNotEqual(absent, zero)

    def test_mic_e_requires_context(self) -> None:
        with self.assertRaises(a.ContextRequired):
            a.decode_payload(b"`12345678")
        with self.assertRaises(a.ContextRequired):
            a.encode_payload(a.MicE(a.Location(49, -72), (False,) * 3))
        with self.assertRaises(a.CodecNotImplemented):
            a.decode_payload(
                b"`12345678",
                header=a.Header("N0CALL", "490S5P"),
                options=a.DecodeOptions(unsupported="raise"),
            )
        parsed = a.parse_packet(b"N0CALL>490S5P:`12345678")
        self.assertEqual(parsed.header.destination, "490S5P")
        self.assertIsInstance(parsed.payload, a.Opaque)

    def test_joint_encoding_result(self) -> None:
        packet = a.Packet(a.Header("N0CALL", "APRS"), a.Status(b"Ready"))
        result = a.encode_packet_fields(packet)
        self.assertEqual(result, a.EncodedPacketFields(packet.header, b">Ready"))
        self.assertEqual(
            a.encode_payload(packet.payload, header=packet.header), result.information
        )

    def test_policy_profiles_are_explicit(self) -> None:
        specifications: tuple[a.SpecificationProfile, ...] = (
            "historical-1.0",
            "compatibility-fap",
        )
        for specification in specifications:
            with self.subTest(specification=specification), self.assertRaises(
                a.CodecNotImplemented
            ):
                a.parse_packet(
                    b"N0CALL>APRS:>Ready",
                    options=a.DecodeOptions(specification=specification),
                )
