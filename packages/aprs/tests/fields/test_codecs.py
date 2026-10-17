# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import math
import unittest

from hamkit.aprs import CodecNotImplementedError, FieldError, Timestamp
from hamkit.aprs._fields import (
    decode_coordinate,
    decode_timestamp,
    encode_coordinate,
    encode_timestamp,
)


class CoordinateTests(unittest.TestCase):
    def test_decode(self) -> None:
        self.assertAlmostEqual(
            decode_coordinate(b"4903.50N", "latitude"), 49 + 3.5 / 60
        )
        self.assertAlmostEqual(
            decode_coordinate(b"07201.75W", "longitude"), -(72 + 1.75 / 60)
        )
        self.assertEqual(decode_coordinate(b"18000.00E", "longitude"), 180)

    def test_encode_quantization_and_carry(self) -> None:
        self.assertEqual(encode_coordinate(49 + 3.5 / 60, "latitude"), b"4903.50N")
        self.assertEqual(encode_coordinate(89.999999, "latitude"), b"9000.00N")
        self.assertEqual(encode_coordinate(-0.0, "longitude"), b"00000.00W")
        for value in (-179.99999, -72.123456, 0.0, 123.456789, 180.0):
            decoded = decode_coordinate(
                encode_coordinate(value, "longitude"), "longitude"
            )
            self.assertLessEqual(abs(value - decoded), 1 / 12000 + 1e-12)

    def test_invalid(self) -> None:
        for raw in (b"9060.00N", b"9000.01N", b"4903x50N", b"4903.50E", b"4903.5N"):
            with self.subTest(raw=raw), self.assertRaises(FieldError):
                decode_coordinate(raw, "latitude")
        for value in (math.nan, math.inf, -91, 91):
            with self.subTest(value=value), self.assertRaises(FieldError):
                encode_coordinate(value, "latitude")
        with self.assertRaises(CodecNotImplementedError):
            decode_coordinate(b"4903.5 N", "latitude")


class TimestampTests(unittest.TestCase):
    def test_round_trips(self) -> None:
        for raw, expected in (
            (b"010000z", Timestamp("dhm_utc", 0, 0, day=1)),
            (b"312359/", Timestamp("dhm_local", 23, 59, day=31)),
            (b"235959h", Timestamp("hms_utc", 23, 59, second=59)),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(decode_timestamp(raw), expected)
                self.assertEqual(encode_timestamp(expected), raw)

    def test_invalid(self) -> None:
        for raw in (
            b"000000z",
            b"322359z",
            b"012400z",
            b"016000z",
            b"235960h",
            b"123456x",
            b"123z",
        ):
            with self.subTest(raw=raw), self.assertRaises(FieldError):
                decode_timestamp(raw)
        with self.assertRaises(FieldError):
            encode_timestamp(Timestamp("hms_utc", 0, 0, day=1, second=0))
